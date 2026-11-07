# -*- coding: utf-8
"""Bloque 0-19 + 20-39 -> perfil bloque 40-59 / cierre."""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.lectores import cargar_ingesta  # noqa: E402

SUM_OP = 450
SUM_GEN = 850


def gs(h):
    return sorted(
        [t for t in (h.tiros_nucleo or []) if t.color == "G" and t.lumen is not None],
        key=lambda t: (t.m0, t.s0),
    )


def blk(h, lo, hi):
    g = [t for t in gs(h) if lo <= t.m0 <= hi]
    l = [t.lumen for t in g]
    return {
        "n": len(g),
        "sum": sum(l) if l else 0,
        "mean": sum(l) / len(l) if l else None,
        "max": max(l) if l else 0,
        "mins": [t.m0 for t in g],
    }


def perf19(h):
    b = blk(h, 0, 19)
    if b["n"] == 0:
        return "A_vacio"
    if b["n"] == 1 and b["mins"][0] >= 15:
        return "B_1G_tarde"
    if b["mins"][0] >= 15 and b["mean"] and b["mean"] < 80 and b["n"] >= 2:
        return "E_tarde_flaco"
    if b["mins"][0] <= 9 and b["n"] >= 3 and b["mean"] and b["mean"] >= 70:
        return "G_early_denso"
    if b["mins"][0] <= 9:
        return "H_early"
    return "I_resto"


def perf39(h):
    """Estado al cerrar bloque 20-39."""
    b = blk(h, 20, 39)
    a = blk(h, 0, 19)
    acum = a["sum"] + b["sum"]
    if b["n"] == 0:
        return "M0_sin_G_2039"
    if acum < 250:
        return "M1_acum_bajo"
    if acum >= 550 and b["mean"] and b["mean"] >= 75:
        return "M3_acum_fuerte"
    if b["max"] >= 400:
        return "M2_pico_2039"
    return "M4_medio"


def row(h):
    g = gs(h)
    l = [t.lumen for t in g]
    b3 = blk(h, 40, 59)
    b2 = blk(h, 20, 39)
    b1 = blk(h, 0, 19)
    return {
        "tag": h.tag.lower(),
        "p19": perf19(h),
        "p39": perf39(h),
        "sum_total": sum(l),
        "opaca": sum(l) < SUM_OP,
        "generosa": sum(l) >= SUM_GEN,
        "n500": sum(1 for t in g if t.lumen >= 500),
        "sum40_59": b3["sum"],
        "n40_59": b3["n"],
        "max40_59": b3["max"],
        "sum20_39": b2["sum"],
        "acum39": b1["sum"] + b2["sum"],
    }


def report(label, xs):
    if not xs:
        print(f"  {label}: n=0")
        return
    n = len(xs)
    print(
        f"  {label:<36s} n={n:4d}  "
        f"P(opaca)={100*sum(x['opaca'] for x in xs)/n:.0f}%  "
        f"P(gen)={100*sum(x['generosa'] for x in xs)/n:.0f}%  "
        f"P(G500)={100*sum(x['n500']>0 for x in xs)/n:.0f}%  "
        f"med sum40-59={median(x['sum40_59'] for x in xs):.0f}  "
        f"med max40+={median(x['max40_59'] for x in xs):.0f}  "
        f"med sum={median(x['sum_total'] for x in xs):.0f}"
    )


def main():
    cinta, _, _ = cargar_ingesta("")
    rows = [row(cinta.get(t)) for t in cinta.orden]
    rows = [r for r in rows if r["sum_total"] > 0]
    print(f"BLOQUE 0-19 + 20-39 -> 40-59 · {len(rows)} h\n")

    print("=== SOLO perfil @19 (lo ya visto) -> cierre ===")
    by19 = defaultdict(list)
    for r in rows:
        by19[r["p19"]].append(r)
    for k in sorted(by19):
        report(f"@19 {k}", by19[k])

    print("\n=== SOLO perfil @39 (bloque 20-39) -> cierre ===")
    by39 = defaultdict(list)
    for r in rows:
        by39[r["p39"]].append(r)
    for k in sorted(by39):
        report(f"@39 {k}", by39[k])

    print("\n=== COMBO @19 + @39 (ejemplos clave) ===")
    combos = defaultdict(list)
    for r in rows:
        combos[(r["p19"], r["p39"])].append(r)
    # most informative for user case
    keys = [
        ("B_1G_tarde", "M0_sin_G_2039"),
        ("B_1G_tarde", "M1_acum_bajo"),
        ("B_1G_tarde", "M4_medio"),
        ("B_1G_tarde", "M2_pico_2039"),
        ("B_1G_tarde", "M3_acum_fuerte"),
        ("E_tarde_flaco", "M1_acum_bajo"),
        ("E_tarde_flaco", "M4_medio"),
        ("G_early_denso", "M3_acum_fuerte"),
        ("G_early_denso", "M4_medio"),
        ("H_early", "M1_acum_bajo"),
        ("H_early", "M3_acum_fuerte"),
        ("A_vacio", "M0_sin_G_2039"),
    ]
    for k in keys:
        if combos.get(k):
            report(f"{k[0]} + {k[1]}", combos[k])

    print("\n=== ¿Mejora vs solo @19? B_1G_tarde ===")
    b = by19["B_1G_tarde"]
    report("solo B @19", b)
    for p39 in sorted(set(r["p39"] for r in b)):
        report(f"  + @39 {p39}", [r for r in b if r["p39"] == p39])

    print("\n=== VEREDICTO numerico: lift opaca B_tarde ===")
    base_op = sum(r["opaca"] for r in rows) / len(rows)
    b_op = sum(r["opaca"] for r in b) / len(b) if b else 0
    b_m1 = [r for r in b if r["p39"] == "M1_acum_bajo"]
    if b_m1:
        print(
            f"  baseline opaca {100*base_op:.0f}% · B@19 {100*b_op:.0f}% · "
            f"B@19+M1@39 {100*sum(r['opaca'] for r in b_m1)/len(b_m1):.0f}% (n={len(b_m1)})"
        )


if __name__ == "__main__":
    main()
