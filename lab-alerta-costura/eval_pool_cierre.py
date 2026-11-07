# -*- coding: utf-8
"""
Lab pool × cierre abierto — ¿la señal h+1 ayuda a leer bloque 00-19 / pools?
Target hora: hN+1 · señal desde hN @55-59 (olor) + confirmado 0-3.
"""
from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
GP = ROOT / "lab-global-pool"
RZ = ROOT / "lab-ruleta-zero"
sys.path.insert(0, str(RZ))
sys.path.insert(0, str(GP))
sys.path.insert(0, str(ROOT))

from core_alerta import build_pairs, split_holdout  # noqa: E402
from eval_h1_only import confirmado_h1, olor_hn, pred_nueva  # noqa: E402
from src.boleto_inter2 import precompute_beta_chips  # noqa: E402
from src.lectores import cargar_ingesta  # noqa: E402
from src.tablero import recorrer, score  # noqa: E402
from src.motor import dist_anillo  # noqa: E402

ALERT_MIN = 55
HOLDOUT = 72


def _gs(tiros):
    return [t for t in (tiros or []) if t.color == "G" and t.lumen is not None]


def olor_any_hn(h_n):
    for T in range(ALERT_MIN, 60):
        if olor_hn(h_n, T):
            return True
    return False


def pred_olor_only(cinta, r):
    return olor_any_hn(cinta.get(r.tag_n))


def pct(n, d):
    return 100 * n / d if d else 0.0


def banda(chips, mins):
    if not mins or not chips:
        return None
    g, pm1 = score(chips, mins)
    return (g + pm1) / len(mins)


def build_hour_rows(cinta):
    rec = recorrer(cinta)
    hist = {f["for"]: f for f in rec["historico"] if f.get("for")}
    beta_by = precompute_beta_chips(cinta)
    rows = {}
    for tag, f in hist.items():
        ofc = sorted(f.get("oficiales") or [])
        if len(ofc) < 3:
            continue
        inter2 = list(f.get("chips") or [])
        if not inter2:
            continue
        rows[tag.lower()] = {
            "tag": tag.lower(),
            "ofc": ofc,
            "inter2": inter2,
            "classic": list(f.get("chips_classic") or f.get("chips") or []),
        }
    return rows


def hour_stats(row):
    ofc = row["ofc"]
    p8 = row["inter2"]
    early = [m for m in ofc if m <= 19]
    mid = [m for m in ofc if 20 <= m <= 39]
    late = [m for m in ofc if m >= 40]
    first = ofc[0] if ofc else None
    return {
        "n_ofc": len(ofc),
        "early03": first is not None and first <= 3,
        "early19": len(early) > 0,
        "n_early": len(early),
        "first_m": first,
        "p8_chip_0019": any(0 <= c <= 19 for c in p8),
        "p8_banda_0019": banda(p8, early),
        "p8_banda_2040": banda(p8, mid),
        "p8_banda_4059": banda(p8, late),
        "p8_banda_full": banda(p8, ofc),
    }


def compare_group(name, items):
    n = len(items)
    if not n:
        print(f"  {name}: n=0")
        return None
    early03 = sum(1 for x in items if x["early03"])
    early19 = sum(1 for x in items if x["early19"])
    chip0019 = sum(1 for x in items if x["p8_chip_0019"])
    b19 = [x["p8_banda_0019"] for x in items if x["p8_banda_0019"] is not None]
    b40 = [x["p8_banda_4059"] for x in items if x["p8_banda_4059"] is not None]
    bf = [x["p8_banda_full"] for x in items if x["p8_banda_full"] is not None]
    med_first = sorted(x["first_m"] for x in items if x["first_m"] is not None)
    med_f = med_first[len(med_first) // 2] if med_first else None
    out = {
        "name": name,
        "n": n,
        "early03": early03,
        "early19": early19,
        "chip0019": chip0019,
        "b19": sum(b19) / len(b19) if b19 else None,
        "b40": sum(b40) / len(b40) if b40 else None,
        "bf": sum(bf) / len(bf) if bf else None,
        "med_first": med_f,
    }
    print(
        f"  {name:<28s} n={n:4d}  "
        f"early03={pct(early03, n):4.0f}%  early19={pct(early19, n):4.0f}%  "
        f"P8∈00-19={pct(chip0019, n):4.0f}%  "
        f"banda00-19={pct(out['b19'], 1) if out['b19'] else 0:4.0f}%  "
        f"banda40-59={pct(out['b40'], 1) if out['b40'] else 0:4.0f}%  "
        f"1erG med={med_f if med_f is not None else '—'}"
    )
    return out


def eval_pairs(pairs, cinta, hour_rows, pred_fn, label):
    on, off = [], []
    for r in pairs:
        tag1 = r.tag_n1
        if tag1 not in hour_rows:
            continue
        st = hour_stats(hour_rows[tag1])
        if pred_fn(cinta, r):
            on.append(st)
        else:
            off.append(st)
    print(f"\n=== {label} ===")
    g_on = compare_group("SEÑAL ON", on)
    g_off = compare_group("SEÑAL OFF", off)
    if g_on and g_off and g_on["b19"] and g_off["b19"]:
        print(f"  Δ banda 00-19 ON-OFF: {100*(g_on['b19']-g_off['b19']):+.0f} pp")
    if g_on and g_off:
        print(
            f"  Δ early03 ON-OFF: {pct(g_on['early03'], g_on['n']) - pct(g_off['early03'], g_off['n']):+.0f} pp"
        )
    return g_on, g_off


def lc01_early_hit(cinta, tag):
    """LC-01 incremental: acierto d≤1 en 0-19 tras cada prefijo de luces."""
    h = cinta.get(tag)
    gs = sorted(_gs(h.tiros_nucleo or []), key=lambda t: (t.m0, t.s0))
    luces = []
    hits = misses = 0
    for g in gs:
        if g.m0 > 19:
            break
        m = g.m0
        if luces:
            tips = _lc01_chips(luces)
            if tips:
                d = min(dist_anillo(m, t) for t in tips)
                if d <= 1:
                    hits += 1
                else:
                    misses += 1
        luces.append(m)
    return hits, misses


def _lc01_chips(luces):
    """Replica mínima chipsLc01 / tipSiguienteG ventana."""
    sorted_l = sorted(set(luces))
    tips = set()
    for i in range(len(sorted_l) + 1):
        prefix = sorted_l[:i]
        T = prefix[-1] if prefix else -1
        if T >= 59:
            continue
        gh = [prefix[k] - prefix[k - 1] for k in range(1, len(prefix))]
        gap = sorted(gh)[max(0, int(len(gh) * 0.3) - 1)] if gh else 5
        gap = max(1, gap)
        c = min(59, max(T + 1, T + gap))
        for x in (c, c + 1, c + 2):
            if T < x <= 59:
                tips.add(x)
    return sorted(tips)


def main():
    cinta, _, _ = cargar_ingesta("")
    pairs = build_pairs(cinta)
    train, hold = split_holdout(pairs)
    hour_rows = build_hour_rows(cinta)

    print("LAB POOL × CIERRE ABIERTO")
    print(f"pares h→h+1: {len(pairs)} · horas con pool P8: {len(hour_rows)}")
    print(f"holdout: {len(hold)} pares")
    print("Pool juez: inter2 (P8) · banda d≤1 · bloque 00-19")

    eval_pairs(pairs, cinta, hour_rows, pred_nueva, "TODA CINTA · señal NUEVA h+1-only")
    eval_pairs(train, cinta, hour_rows, pred_nueva, f"TRAIN · señal NUEVA")
    eval_pairs(hold, cinta, hour_rows, pred_nueva, f"HOLDOUT {len(hold)}")

    eval_pairs(pairs, cinta, hour_rows, pred_olor_only, "TODA CINTA · solo OLOR @55-59 (predictivo)")
    eval_pairs(hold, cinta, hour_rows, pred_olor_only, f"HOLDOUT · solo OLOR")

    # LC-01 incremental early block
    print("\n=== LC-01 incremental (0-19) · señal NUEVA ===")
    for label in ("ON", "OFF"):
        hits = misses = 0
        for r in pairs:
            p = pred_nueva(cinta, r)
            if (label == "ON") != p:
                continue
            if r.tag_n1 not in hour_rows:
                continue
            h, m = lc01_early_hit(cinta, r.tag_n1)
            hits += h
            misses += m
        tot = hits + misses
        print(f"  {label}: n tiros eval={tot}  hit d≤1={pct(hits, tot):.0f}%  ({hits}/{tot})")

    # Baseline sin señal
    all_h = list(hour_rows.values())
    print("\n=== BASELINE horas (sin cruce señal) ===")
    compare_group("todas las horas P8", [hour_stats(r) for r in all_h])

    # Veredicto
    print("\n=== VEREDICTO ===")
    on_hold, off_hold = [], []
    for r in hold:
        if r.tag_n1 not in hour_rows:
            continue
        st = hour_stats(hour_rows[r.tag_n1])
        (on_hold if pred_nueva(cinta, r) else off_hold).append(st)
    if on_hold and off_hold:
        pe = pct(sum(1 for x in on_hold if x["early19"]), len(on_hold))
        po = pct(sum(1 for x in off_hold if x["early19"]), len(off_hold))
        be = (
            sum(x["p8_banda_0019"] for x in on_hold if x["p8_banda_0019"] is not None)
            / max(1, sum(1 for x in on_hold if x["p8_banda_0019"] is not None))
        )
        bo = (
            sum(x["p8_banda_0019"] for x in off_hold if x["p8_banda_0019"] is not None)
            / max(1, sum(1 for x in off_hold if x["p8_banda_0019"] is not None))
        )
        print(f"  Holdout: early19 ON={pe:.0f}% OFF={po:.0f}% (Δ {pe-po:+.0f} pp)")
        print(f"  Holdout: P8 banda 00-19 ON={100*be:.0f}% OFF={100*bo:.0f}% (Δ {100*(be-bo):+.0f} pp)")
        if pe - po >= 10 and be > bo:
            print("  OLOR VIVE como contexto pools bloque temprano — no boleto.")
        elif pe - po >= 5:
            print("  OLOR útil para expectativa de actividad temprana; banda P8 mejora poco.")
        else:
            print("  FRIO para pools: señal no separa bien bloque 00-19 en holdout.")


if __name__ == "__main__":
    main()
