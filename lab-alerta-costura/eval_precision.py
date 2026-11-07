# -*- coding: utf-8
"""Barrido precision cierre abierto @55 — no toca front."""
from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
sys.path.insert(0, str(ROOT))

from core_alerta import build_pairs, split_holdout, cargar_ingesta  # noqa: E402

ALERT_MIN = 55
COLA_MIN = 50
CORTE_LARGO_S = 70


def _gs(tiros):
    return [t for t in (tiros or []) if t.color == "G" and t.lumen is not None]


def tiros_hasta(tiros, T):
    return sorted(
        [t for t in (tiros or []) if t.m0 <= T],
        key=lambda t: (t.m0, t.s0),
    )


def duracion_s(t):
    a = t.m0 * 60 + t.s0
    b = t.m1 * 60 + t.s1
    return (b - a + 3600) % 3600


def snap55(h):
    tiros = h.tiros_nucleo or []
    xs = tiros_hasta(tiros, ALERT_MIN)
    gs = _gs(xs)
    ultimo = xs[-1] if xs else None
    return {
        "ultimo_r": bool(ultimo and ultimo.color == "R"),
        "g_cola58": any(g.m0 >= 58 for g in gs),
        "g_50_54": any(COLA_MIN <= g.m0 <= ALERT_MIN for g in gs),
        "g_55_59": any(55 <= g.m0 <= 59 for g in gs),  # solo post-check
        "l_wrap": l_wrap_proxy(ultimo),
        "sin_early": not any(g.m0 <= 9 for g in gs),
        "nG": len(gs),
        "sumG": sum(g.lumen for g in gs),
    }


def l_wrap_proxy(ultimo):
    if not ultimo or ultimo.color != "R":
        return False
    if ultimo.m1 < ultimo.m0 or ultimo.m0 >= 58:
        return True
    if ultimo.m0 >= COLA_MIN and duracion_s(ultimo) >= CORTE_LARGO_S:
        fin = ultimo.m0 + duracion_s(ultimo) // 60
        return fin >= 58
    return False


# ── Reglas candidatas (True = cierre abierto @55) ──

RULES = [
    ("actual (R|G50|wrap, OFF opaca)", lambda s: not (
        s["sin_early"] and not s["g_50_54"] and not s["ultimo_r"] and not s["l_wrap"]
    ) and (s["ultimo_r"] or s["g_50_54"] or s["l_wrap"])),
    ("G50-54 solo", lambda s: s["g_50_54"]),
    ("L_wrap solo", lambda s: s["l_wrap"]),
    ("G50 OR wrap (sin R solo)", lambda s: s["g_50_54"] or s["l_wrap"]),
    ("R AND G50", lambda s: s["ultimo_r"] and s["g_50_54"]),
    ("R AND (G50 OR wrap)", lambda s: s["ultimo_r"] and (s["g_50_54"] or s["l_wrap"])),
    ("wrap OR (R AND G50)", lambda s: s["l_wrap"] or (s["ultimo_r"] and s["g_50_54"])),
    ("G50 OR (R AND NOT sin_early)", lambda s: s["g_50_54"] or (s["ultimo_r"] and not s["sin_early"])),
    ("(G50 OR wrap) AND NOT sin_early", lambda s: (s["g_50_54"] or s["l_wrap"]) and not s["sin_early"]),
    ("2+ senales (R,G50,wrap)", lambda s: sum([s["ultimo_r"], s["g_50_54"], s["l_wrap"]]) >= 2),
    ("G50 + R largo implícito", lambda s: s["g_50_54"] and s["ultimo_r"]),
    ("sumG>=400 @55 AND G50", lambda s: s["g_50_54"] and s["sumG"] >= 400),
    ("sumG>=500 @55 AND (G50 OR wrap)", lambda s: s["sumG"] >= 500 and (s["g_50_54"] or s["l_wrap"])),
    ("nG>=5 AND G50", lambda s: s["nG"] >= 5 and s["g_50_54"]),
    # ── Más estrictas (precision) ──
    ("G52-54", lambda s: s.get("g_52_54", False)),
    ("G54 solo", lambda s: s.get("g_54_54", False)),
    ("G53-54 OR wrap", lambda s: s.get("g_53_54", False) or s["l_wrap"]),
    ("G50-54 AND sumG>=600", lambda s: s["g_50_54"] and s["sumG"] >= 600),
    ("G50-54 AND meanG>=60", lambda s: s["g_50_54"] and s["nG"] >= 2 and s["sumG"] / s["nG"] >= 60),
    ("G50-54 AND NOT sin_early", lambda s: s["g_50_54"] and not s["sin_early"]),
    ("wrap AND G50", lambda s: s["l_wrap"] and s["g_50_54"]),
    ("wrap AND NOT sin_early", lambda s: s["l_wrap"] and not s["sin_early"]),
    ("R largo en cola (m0>=50)", lambda s: s.get("r_largo_cola", False)),
]


def enrich_snap(h):
    s = snap55(h)
    tiros = h.tiros_nucleo or []
    xs = tiros_hasta(tiros, ALERT_MIN)
    gs = _gs(xs)
    for lo, hi in [(52, 54), (54, 54), (53, 54)]:
        s[f"g_{lo}_{hi}"] = any(lo <= g.m0 <= hi for g in gs)
    ultimo = xs[-1] if xs else None
    s["r_largo_cola"] = (
        ultimo
        and ultimo.color == "R"
        and ultimo.m0 >= COLA_MIN
        and duracion_s(ultimo) >= CORTE_LARGO_S
    )
    if s["nG"]:
        s["meanG"] = s["sumG"] / s["nG"]
    else:
        s["meanG"] = 0
    return s


def eval_rule(rows, cinta, pred_fn, target="costura"):
    tp = fp = tn = fn = 0
    for r in rows:
        h = cinta.get(r.tag_n)
        s = enrich_snap(h)
        pred = bool(pred_fn(s))
        if target == "cola":
            y = r.cola_58
        elif target == "early":
            y = r.early_03
        else:
            y = r.costura
        if pred:
            if y:
                tp += 1
            else:
                fp += 1
        else:
            if y:
                fn += 1
            else:
                tn += 1
    n = len(rows)
    on = tp + fp
    prec = tp / on if on else 0
    rec = tp / (tp + fn) if (tp + fn) else 0
    cov = on / n if n else 0
    acc = (tp + tn) / n if n else 0
    off_prec = tn / (tn + fn) if (tn + fn) else 0
    return {
        "n": n, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "prec": prec, "rec": rec, "cov": cov, "acc": acc, "off_prec": off_prec,
    }


def fmt(m):
    return (
        f"prec={100*m['prec']:.0f}% rec={100*m['rec']:.0f}% "
        f"cov={100*m['cov']:.0f}% acc={100*m['acc']:.0f}% "
        f"OFF={100*m['off_prec']:.0f}%"
    )


def main():
    cinta, _, _ = cargar_ingesta("")
    rows = build_pairs(cinta)
    train, hold = split_holdout(rows)
    base = sum(1 for r in rows if r.costura) / len(rows)

    print("BARRIDO PRECISION — cierre abierto @min55")
    print(f"cinta: {len(rows)} pares · baseline costura {100*base:.0f}%")
    print(f"{'regla':<42s}  {'TRAIN':<38s}  {'HOLD':<38s}")
    print("-" * 120)

    ranked = []
    for name, fn in RULES:
        tr = eval_rule(train, cinta, fn)
        ho = eval_rule(hold, cinta, fn)
        print(f"{name:<42s}  {fmt(tr):<38s}  {fmt(ho)}")
        ranked.append((name, tr, ho))

    print("\n=== TOP por precision TRAIN (cov>=15%) ===")
    filt = [(n, tr, ho) for n, tr, ho in ranked if tr["cov"] >= 0.15]
    filt.sort(key=lambda x: (-x[1]["prec"], -x[1]["rec"]))
    for name, tr, ho in filt[:8]:
        print(f"  {name}")
        print(f"    train: {fmt(tr)}  ({tr['tp']+tr['fp']} ON · {tr['fp']} falsas)")
        print(f"    hold:  {fmt(ho)}  ({ho['tp']+ho['fp']} ON · {ho['fp']} falsas)")

    print("\n=== TOP precision HOLD (cov>=10%) ===")
    filt2 = [(n, tr, ho) for n, tr, ho in ranked if ho["cov"] >= 0.10]
    filt2.sort(key=lambda x: (-x[2]["prec"], -x[2]["rec"]))
    for name, tr, ho in filt2[:5]:
        print(f"  {name}: hold prec {100*ho['prec']:.0f}% rec {100*ho['rec']:.0f}% cov {100*ho['cov']:.0f}%")

    print("\n=== REGLAS ESTRICTAS (solo nuevas) ===")
    strict = RULES[14:]
    for name, fn in strict:
        tr = eval_rule(train, cinta, fn)
        ho = eval_rule(hold, cinta, fn)
        print(f"  {name:<32s} train {fmt(tr)}  |  hold {fmt(ho)}")

    print("\n=== MEJOR G50-54 vs target COLA 58+ (no early) ===")
    for name, fn in [("G50-54", RULES[1][1]), ("G52-54", strict[0][1]), ("G53-54 OR wrap", strict[2][1]), ("wrap AND G50", strict[7][1])]:
        tr = eval_rule(train, cinta, fn, target="cola")
        ho = eval_rule(hold, cinta, fn, target="cola")
        print(f"  {name}: train prec {100*tr['prec']:.0f}% rec {100*tr['rec']:.0f}% | hold prec {100*ho['prec']:.0f}% rec {100*ho['rec']:.0f}%")

    print("\n=== RECOMENDACION lab (precision > recall) ===")
    best = max(
        [(n, tr, ho) for n, tr, ho in ranked if tr["cov"] >= 0.15 and ho["cov"] >= 0.08],
        key=lambda x: (min(x[1]["prec"], x[2]["prec"]), x[1]["prec"] + x[2]["prec"]),
        default=None,
    )
    # mejor estricto excluyendo actual
    strict_ranked = []
    for name, fn in strict:
        tr = eval_rule(train, cinta, fn)
        ho = eval_rule(hold, cinta, fn)
        strict_ranked.append((name, tr, ho))
    best_strict = max(
        [(n, tr, ho) for n, tr, ho in strict_ranked if tr["cov"] >= 0.08 and ho["cov"] >= 0.05],
        key=lambda x: (min(x[1]["prec"], x[2]["prec"]), x[1]["prec"] + x[2]["prec"]),
        default=None,
    )
    if best:
        n, tr, ho = best
        print(f"  Balance general: {n}")
        print(f"  Train prec {100*tr['prec']:.0f}% · Hold prec {100*ho['prec']:.0f}%")
        print(f"  Train rec {100*tr['rec']:.0f}% · Hold rec {100*ho['rec']:.0f}%")
        print(f"  Cobertura ON: train {100*tr['cov']:.0f}% · hold {100*ho['cov']:.0f}%")
    if best_strict:
        n, tr, ho = best_strict
        print(f"\n  Mejor ESTRICTA (sube precision, baja cov):")
        print(f"  {n}")
        print(f"  Train prec {100*tr['prec']:.0f}% · Hold prec {100*ho['prec']:.0f}%")
        print(f"  Train rec {100*tr['rec']:.0f}% · Hold rec {100*ho['rec']:.0f}%")
        print(f"  Cobertura ON: train {100*tr['cov']:.0f}% · hold {100*ho['cov']:.0f}%")
        print(f"  Falsas alarmas train: {tr['fp']} · hold: {ho['fp']}")


if __name__ == "__main__":
    main()
