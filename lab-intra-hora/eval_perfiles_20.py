# -*- coding: utf-8
"""Perfiles @min19 (bloque 00-19) -> cierre de hora. One-shot lab."""
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
T19 = 19


def gs(h):
    return sorted(
        [t for t in (h.tiros_nucleo or []) if t.color == "G" and t.lumen is not None],
        key=lambda t: (t.m0, t.s0),
    )


def snap(h, T):
    g = [t for t in gs(h) if t.m0 <= T]
    g19 = g
    grest = [t for t in gs(h) if t.m0 > T]
    lums = [t.lumen for t in g19]
    lums_all = [t.lumen for t in gs(h)]
    return {
        "tag": h.tag.lower(),
        "n19": len(g19),
        "first_m": g19[0].m0 if g19 else None,
        "sum19": sum(lums) if lums else 0,
        "mean19": sum(lums) / len(lums) if lums else None,
        "max19": max(lums) if lums else 0,
        "mins19": [t.m0 for t in g19],
        "n_total": len(gs(h)),
        "sum_total": sum(lums_all),
        "mean_total": sum(lums_all) / len(lums_all) if lums_all else 0,
        "max_total": max(lums_all) if lums_all else 0,
        "sum20_59": sum(t.lumen for t in grest),
        "n20_59": len(grest),
        "max40_59": max((t.lumen for t in gs(h) if t.m0 >= 40), default=0),
        "opaca": sum(lums_all) < SUM_OP,
        "generosa": sum(lums_all) >= SUM_GEN,
        "n500": sum(1 for t in gs(h) if t.lumen >= 500),
    }


def perfil(r):
    """Clasificación @19."""
    if r["n19"] == 0:
        return "A_vacio_0_19"
    if r["n19"] == 1 and r["first_m"] >= 15:
        return "B_1G_tarde"
    if r["n19"] == 1 and r["first_m"] <= 9:
        return "C_1G_early"
    if r["n19"] == 1:
        return "D_1G_medio"
    if r["first_m"] >= 15 and r["mean19"] is not None and r["mean19"] < 80:
        return "E_cluster_tarde_flaco"
    if r["first_m"] >= 15:
        return "F_cluster_tarde_mixto"
    if r["first_m"] <= 9 and r["n19"] >= 3 and r["mean19"] >= 70:
        return "G_early_denso"
    if r["first_m"] <= 9:
        return "H_early_ligero"
    return "I_resto"


def report(name, rows):
    if not rows:
        print(f"  {name}: n=0")
        return
    n = len(rows)
    print(
        f"  {name:<22s} n={n:4d} ({100*n/942:.1f}%)  "
        f"P(opaca)={100*sum(r['opaca'] for r in rows)/n:.0f}%  "
        f"P(gen)={100*sum(r['generosa'] for r in rows)/n:.0f}%  "
        f"P(G500)={100*sum(r['n500']>0 for r in rows)/n:.0f}%  "
        f"med sum={median(r['sum_total'] for r in rows):.0f}  "
        f"med +20-59={median(r['sum20_59'] for r in rows):.0f}  "
        f"med max40+={median(r['max40_59'] for r in rows):.0f}"
    )


def main():
    cinta, _, _ = cargar_ingesta("")
    rows = [snap(cinta.get(t), T19) for t in cinta.orden]
    rows = [r for r in rows if r["n_total"] > 0]
    print(f"PERFILES @min19 -> cierre hora · {len(rows)} h\n")

    by = defaultdict(list)
    for r in rows:
        by[perfil(r)].append(r)

    order = [
        "A_vacio_0_19",
        "B_1G_tarde",
        "C_1G_early",
        "D_1G_medio",
        "E_cluster_tarde_flaco",
        "F_cluster_tarde_mixto",
        "G_early_denso",
        "H_early_ligero",
        "I_resto",
    ]
    print("=== PERFILES @19 ===")
    for k in order:
        report(k, by.get(k, []))

    # Usuario: @20 con 3 G en 17,20,23 bajas -> at T19 would be 2 G (17, and maybe not 20 yet)
    # At T=23 snapshot for cluster pattern
    print("\n=== SNAPSHOT @min23 (3 G en 17-23, mean<80) ===")
    late23 = []
    for t in cinta.orden:
        h = cinta.get(t)
        g = [x for x in gs(h) if x.m0 <= 23]
        if len(g) < 3:
            continue
        if g[0].m0 < 15:
            continue
        lums = [x.lumen for x in g if 15 <= x.m0 <= 23]
        if len(lums) < 3:
            continue
        if sum(lums) / len(lums) >= 80:
            continue
        all_l = [x.lumen for x in gs(h)]
        late23.append({
            "tag": h.tag.lower(),
            "mins": [x.m0 for x in g if x.m0 <= 23],
            "opaca": sum(all_l) < SUM_OP,
            "generosa": sum(all_l) >= SUM_GEN,
            "sum_total": sum(all_l),
            "max_total": max(all_l),
            "n500": sum(1 for x in gs(h) if x.lumen >= 500),
        })
    n = len(late23)
    if n:
        print(f"  n={n} ({100*n/942:.1f}%)")
        print(f"  P(opaca)={100*sum(x['opaca'] for x in late23)/n:.0f}%")
        print(f"  P(gen)={100*sum(x['generosa'] for x in late23)/n:.0f}%")
        print(f"  P(G500)={100*sum(x['n500']>0 for x in late23)/n:.0f}%")
        print(f"  med sum={median(x['sum_total'] for x in late23):.0f} max={median(x['max_total'] for x in late23):.0f}")

    # Discriminación: vacío @19 vs early
    print("\n=== SEÑAL @19: nG=0 vs nG>=1 ===")
    v0 = [r for r in rows if r["n19"] == 0]
    v1 = [r for r in rows if r["n19"] >= 1]
    report("nG=0 @19", v0)
    report("nG>=1 @19", v1)

    print("\n=== SEÑAL @19: first_m>=15 vs first_m<=9 (con al menos 1 G) ===")
    late = [r for r in rows if r["n19"] >= 1 and r["first_m"] >= 15]
    early = [r for r in rows if r["n19"] >= 1 and r["first_m"] <= 9]
    report("1erG>=15 @19", late)
    report("1erG<=9 @19", early)

    print("\n=== EJEMPLOS E_cluster_tarde_flaco ===")
    for r in sorted(by.get("E_cluster_tarde_flaco", []), key=lambda x: -x["sum_total"])[:6]:
        print(
            f"  {r['tag']} @19: n={r['n19']} mins={r['mins19']} "
            f"mean19={r['mean19']:.0f} -> sum={r['sum_total']} max={r['max_total']} "
            f"{'opaca' if r['opaca'] else 'gen' if r['generosa'] else 'normal'}"
        )

    print("\n=== E_cluster flaco CON pico (max_total>=400) ===")
    flaco_hi = [r for r in by.get("E_cluster_tarde_flaco", []) if r["max_total"] >= 400]
    for r in sorted(flaco_hi, key=lambda x: -x["max_total"]):
        print(
            f"  {r['tag']} mins19={r['mins19']} mean19={r['mean19']:.0f} "
            f"-> sum={r['sum_total']} max={r['max_total']}"
        )


if __name__ == "__main__":
    main()
