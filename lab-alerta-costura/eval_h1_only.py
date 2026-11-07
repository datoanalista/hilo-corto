# -*- coding: utf-8
"""Eval regla cableada h+1-only vs target early_03 (1er G hN+1 min 0-3)."""
from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
sys.path.insert(0, str(ROOT))

from core_alerta import build_pairs, split_holdout, cargar_ingesta  # noqa: E402

ALERT_MIN = 55
COLA_MIN = 50
COLA_MAX = 54
APERTURA_MAX = 3


def _gs(tiros):
    return [t for t in (tiros or []) if t.color == "G" and t.lumen is not None]


def tiros_hasta(tiros, T):
    return sorted(
        [t for t in (tiros or []) if t.m0 <= T],
        key=lambda t: (t.m0, t.s0),
    )


def olor_hn(h_n, T):
    """G 50-54 hasta T + hora abrio (G 0-9)."""
    xs = tiros_hasta(h_n.tiros_nucleo or [], T)
    gs = _gs(xs)
    g_cola = any(COLA_MIN <= g.m0 <= min(COLA_MAX, T) for g in gs)
    sin_early = not any(g.m0 <= 9 for g in gs)
    return g_cola and not sin_early


def g_cola_hn(h_n, T):
    xs = tiros_hasta(h_n.tiros_nucleo or [], T)
    return any(g.m0 >= 58 for g in _gs(xs))


def confirmado_h1(h_n1):
    gs = _gs(h_n1.tiros_nucleo or [])
    if not gs:
        return False
    first = min(gs, key=lambda t: (t.m0, t.s0))
    return first.m0 <= APERTURA_MAX


def pred_olor_snap55(r):
    s = r.snap
    return s.G_en_50_54 and not s.sin_early_0_9


def pred_nueva(cinta, r):
    """Dashboard h+1-only: olor @55-59 hN OR confirmado G 0-3 hN+1."""
    h_n = cinta.get(r.tag_n)
    h_n1 = cinta.get(r.tag_n1)
    for T in range(ALERT_MIN, 60):
        if olor_hn(h_n, T):
            return True
    return confirmado_h1(h_n1)


def pred_vieja(cinta, r):
    """Regla anterior: olor OR gCola 58+ @55-59 hN OR confirmado h+1."""
    h_n = cinta.get(r.tag_n)
    h_n1 = cinta.get(r.tag_n1)
    for T in range(ALERT_MIN, 60):
        if olor_hn(h_n, T) or g_cola_hn(h_n, T):
            return True
    return confirmado_h1(h_n1)


def pred_solo_gcola(cinta, r):
    h_n = cinta.get(r.tag_n)
    for T in range(ALERT_MIN, 60):
        if g_cola_hn(h_n, T):
            return True
    return False


def metrics(rows, pred_fn, target_fn):
    tp = fp = tn = fn = 0
    for r in rows:
        y = bool(target_fn(r))
        p = bool(pred_fn(r))
        if p:
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
    prec = tp / on if on else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    cov = on / n if n else 0.0
    acc = (tp + tn) / n if n else 0.0
    base = sum(1 for r in rows if target_fn(r)) / n if n else 0.0
    return {
        "n": n,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "prec": prec,
        "rec": rec,
        "cov": cov,
        "acc": acc,
        "base": base,
    }


def fmt(m):
    return (
        f"prec={100*m['prec']:.0f}% rec={100*m['rec']:.0f}% "
        f"cov={100*m['cov']:.0f}% acc={100*m['acc']:.0f}% "
        f"({m['tp']+m['fp']} ON · {m['fp']} falsas)"
    )


def main():
    cinta, _, _ = cargar_ingesta("")
    rows = build_pairs(cinta)
    train, hold = split_holdout(rows)
    tgt = lambda r: r.early_03

    rules = [
        ("olor @55 snap (G50-54 + apertura)", lambda r: pred_olor_snap55(r)),
        (
            "olor @55-59 hN (solo predictivo)",
            lambda r: any(
                olor_hn(cinta.get(r.tag_n), T) for T in range(ALERT_MIN, 60)
            ),
        ),
        ("solo gCola 58+ @55-59 hN", lambda r: pred_solo_gcola(cinta, r)),
        ("NUEVA h+1-only (olor + confirmado h+1)", lambda r: pred_nueva(cinta, r)),
        ("VIEJA (+ gCola 58+ hN)", lambda r: pred_vieja(cinta, r)),
    ]

    print("EVAL h+1-only — target: 1er G hN+1 en min 0-3 (early_03)")
    print(f"cinta: {len(rows)} pares · baseline early {100*sum(1 for r in rows if r.early_03)/len(rows):.0f}%")
    print(f"holdout: {len(hold)} pares\n")
    print(f"{'regla':<42s}  {'TRAIN':<44s}  HOLD")
    print("-" * 120)

    results = []
    for name, fn in rules:
        tr = metrics(train, fn, tgt)
        ho = metrics(hold, fn, tgt)
        print(f"{name:<42s}  {fmt(tr):<44s}  {fmt(ho)}")
        results.append((name, tr, ho))

    # Desglose nueva regla
    print("\n=== DESGLOSE NUEVA (toda cinta) ===")
    olor_only = sum(1 for r in rows if pred_olor_snap55(r))
    conf_only = sum(
        1
        for r in rows
        if confirmado_h1(cinta.get(r.tag_n1)) and not pred_olor_snap55(r)
    )
    ambos = sum(
        1
        for r in rows
        if confirmado_h1(cinta.get(r.tag_n1)) and pred_olor_snap55(r)
    )
    gcola_extra = sum(
        1
        for r in rows
        if pred_vieja(cinta, r) and not pred_nueva(cinta, r)
    )
    print(f"  olor @55 solo:           {olor_only}")
    print(f"  confirmado h+1 solo:    {conf_only}")
    print(f"  olor + confirmado:      {ambos}")
    print(f"  extra ON vieja (gCola): {gcola_extra}")

    print("\n=== gCola 58+ solo — falsas hacia early_03 ===")
    gc = [r for r in rows if pred_solo_gcola(cinta, r)]
    gc_tp = sum(1 for r in gc if r.early_03)
    gc_fp = len(gc) - gc_tp
    print(f"  dispara: {len(gc)} · acierta early: {gc_tp} · falsas: {gc_fp} · prec {100*gc_tp/len(gc) if gc else 0:.0f}%")

    print("\n=== RECOMENDACION ===")
    _, tr_n, ho_n = results[3]
    _, tr_v, ho_v = results[4]
    print(f"  NUEVA hold: {fmt(ho_n)}")
    print(f"  VIEJA hold: {fmt(ho_v)}")
    print(f"  Delta falsas hold: {ho_v['fp'] - ho_n['fp']} menos con h+1-only")
    print(f"  Delta prec hold: {100*(ho_n['prec']-ho_v['prec']):+.0f} pp")


if __name__ == "__main__":
    main()
