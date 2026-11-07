# -*- coding: utf-8 -*-
"""
Lab calendario-hod (anti-Jaccard) — hod×DOW y pares de horas.
  python run_lab.py
Fuente: depurar-all-4G-detail.txt (solo lectura).
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))

from core_cal import (  # noqa: E402
    DOW_ES,
    HoraCal,
    DATA_DEFAULT,
    load_horas,
    pearson,
    split_holdout,
)

OUT = LAB / "reports"
OUT.mkdir(exist_ok=True)
MIN_CELL = 8
HOD_FOCUS = 8
PAIRS = [(8, 9), (8, 18), (10, 8), (15, 19), (4, 13)]


def w(lines, s=""):
    lines.append(s)
    print(s.encode("ascii", "replace").decode("ascii"))


def cell_stats(rows: list[HoraCal]) -> dict:
    if not rows:
        return {}
    return {
        "n": len(rows),
        "med_mean": median(h.mean_g for h in rows),
        "med_sum": median(h.sum_g for h in rows),
        "p_gen": sum(1 for h in rows if h.mean_g >= 55) / len(rows),
    }


def hod_dow_matrix(horas: list[HoraCal]) -> dict[tuple[int, int], list[HoraCal]]:
    g: dict[tuple[int, int], list[HoraCal]] = defaultdict(list)
    for h in horas:
        g[(h.hod, h.dow)].append(h)
    return g


def spread_dow(hod: int, horas: list[HoraCal]) -> tuple[float, list[tuple[str, float, int]]]:
    by = defaultdict(list)
    for h in horas:
        if h.hod == hod:
            by[h.dow].append(h.mean_g)
    cells = []
    for d in range(7):
        xs = by.get(d, [])
        if xs:
            cells.append((DOW_ES[d], median(xs), len(xs)))
    if len(cells) < 2:
        return 0.0, cells
    meds = [c[1] for c in cells]
    return max(meds) - min(meds), cells


def pair_same_day(h1: int, h2: int, horas: list[HoraCal]):
    by_day: dict[str, dict[int, HoraCal]] = defaultdict(dict)
    for h in horas:
        if h.hod in (h1, h2):
            by_day[h.day][h.hod] = h
    xs, ys, meta = [], [], []
    for day, d in by_day.items():
        if h1 in d and h2 in d:
            xs.append(d[h1].mean_g)
            ys.append(d[h2].mean_g)
            meta.append((day, d[h1].dow))
    return xs, ys, meta


def pair_by_dow(h1: int, h2: int, horas: list[HoraCal]):
    xs, ys, meta = pair_same_day(h1, h2, horas)
    by_dow: dict[int, tuple[list[float], list[float]]] = defaultdict(lambda: ([], []))
    for x, y, (_, dow) in zip(xs, ys, meta):
        by_dow[dow][0].append(x)
        by_dow[dow][1].append(y)
    out = {}
    for d, (a, b) in by_dow.items():
        out[d] = {"n": len(a), "r": pearson(a, b), "med_a": median(a) if a else 0, "med_b": median(b) if b else 0}
    return out, pearson(xs, ys), len(xs)


def cross_next_day(ha: int, hb: int, horas: list[HoraCal]):
    idx = {h.tag: h for h in horas}
    xs, ys = [], []
    for h in horas:
        if h.hod != ha:
            continue
        nxt = f"h{hb}-{h.day}"
        # día siguiente en tag
        dt2 = h.dt.replace(hour=hb)
        from datetime import timedelta

        dt2 = dt2 + timedelta(days=1)
        tag2 = f"h{hb}-{dt2.strftime('%d%m%y')}"
        b = idx.get(tag2)
        if b:
            xs.append(h.mean_g)
            ys.append(b.mean_g)
    return pearson(xs, ys), len(xs)


def main():
    horas = load_horas()
    train, test = split_holdout(horas)
    lines: list[str] = []

    w(lines, "LAB CALENDARIO-HOD (anti-Jaccard)")
    w(lines, "=" * 60)
    w(lines, f"fuente: {DATA_DEFAULT}")
    w(lines, f"horas: {len(horas)}  train: {len(train)}  test: {len(test)}  holdout: 72h")
    w(lines, "eje: mean_G / sum_g · sin Jaccard · sin chips")
    w(lines, "")

    # P0
    w(lines, "-- P0 CATÁLOGO --")
    dias = len({h.day for h in horas})
    w(lines, f"  días únicos: {dias}")
    w(lines, f"  rango: {horas[0].tag} .. {horas[-1].tag}")
    w(lines, "")

    # H1 hod×DOW spread global
    w(lines, "-- H1 SPREAD DOW por hod (train) --")
    spreads = []
    for hod in range(24):
        sp, cells = spread_dow(hod, train)
        if sum(c[2] for c in cells) >= MIN_CELL * 2:
            spreads.append((sp, hod, cells))
    spreads.sort(reverse=True)
    for sp, hod, cells in spreads[:8]:
        w(lines, f"  h{hod:02d} spread mean_G={sp:.1f}")
        for name, med, n in cells:
            w(lines, f"    {name}: med={med:.1f} n={n}")
    w(lines, "")

    # H2 foco h8 (ejemplo humano)
    w(lines, f"-- H2 FOCO h{HOD_FOCUS:02d} × DOW (train / test) --")
    for label, part in [("train", train), ("test", test)]:
        sp, cells = spread_dow(HOD_FOCUS, part)
        w(lines, f"  {label}: spread={sp:.1f}")
        for name, med, n in cells:
            w(lines, f"    {name}: med={med:.1f} n={n}")
    w(lines, "")

    # H3 celdas hod×DOW vs mediana global hod
    w(lines, "-- H3 CELDAS hod×DOW vs mediana del hod (train) --")
    mat = hod_dow_matrix(train)
    hod_med = {hod: median(h.mean_g for h in train if h.hod == hod) for hod in range(24)}
    hot, cold = [], []
    for (hod, dow), rows in mat.items():
        if len(rows) < MIN_CELL:
            continue
        med = median(h.mean_g for h in rows)
        base = hod_med.get(hod, med)
        lift = med - base
        item = (abs(lift), hod, dow, med, base, len(rows), lift)
        if lift >= 8:
            hot.append(item)
        elif lift <= -8:
            cold.append(item)
    hot.sort(reverse=True)
    cold.sort()
    w(lines, "  CALIENTES (mean_G +8 vs med hod):")
    for _, hod, dow, med, base, n, lift in hot[:12]:
        w(lines, f"    h{hod:02d}-{DOW_ES[dow]}: {med:.1f} vs {base:.1f} (n={n}, {lift:+.1f})")
    w(lines, "  FRÍAS (-8):")
    for _, hod, dow, med, base, n, lift in cold[:12]:
        w(lines, f"    h{hod:02d}-{DOW_ES[dow]}: {med:.1f} vs {base:.1f} (n={n}, {lift:+.1f})")
    w(lines, "")

    # H4 pares mismo día
    w(lines, "-- H4 PARES mismo día (mean_G) train --")
    for h1, h2 in PAIRS:
        by_dow, r_all, n = pair_by_dow(h1, h2, train)
        w(lines, f"  h{h1:02d}↔h{h2:02d}: r={r_all if r_all is not None else '—'} n={n}")
        for d in range(7):
            info = by_dow.get(d)
            if not info or info["n"] < 4:
                continue
            w(
                lines,
                f"    {DOW_ES[d]}: r={info['r'] if info['r'] is not None else '—'} "
                f"n={info['n']} med={info['med_a']:.0f}/{info['med_b']:.0f}",
            )
    w(lines, "")

    # H5 tejido +1d (sin DOW primero)
    w(lines, "-- H5 CRUCES +1d (train) --")
    crosses = []
    for ha, hb in PAIRS:
        r, n = cross_next_day(ha, hb, train)
        if n >= 8 and r is not None:
            crosses.append((abs(r), ha, hb, r, n))
    crosses.sort(reverse=True)
    for _, ha, hb, r, n in crosses[:10]:
        w(lines, f"  h{ha:02d}→h{hb:02d}(+1d): r={r:+.2f} n={n}")
    w(lines, "")

    # H6 holdout: top spreads repiten?
    w(lines, "-- H6 HOLDOUT top spreads (train top3 hod) --")
    top_hods = [h for _, h, _ in spreads[:3]]
    for hod in top_hods:
        sp_tr, _ = spread_dow(hod, train)
        sp_te, cells_te = spread_dow(hod, test)
        w(lines, f"  h{hod:02d}: train spread={sp_tr:.1f}  test spread={sp_te:.1f}")
        if cells_te:
            for name, med, n in cells_te:
                if n:
                    w(lines, f"    test {name}: med={med:.1f} n={n}")
    w(lines, "")

    # Síntesis automática
    w(lines, "-- SÍNTESIS (P0) --")
    h8_sp, _ = spread_dow(HOD_FOCUS, train)
    w(lines, f"  h08 spread DOW train={h8_sp:.1f} (ejemplo humano: revisar celdas arriba)")
    w(lines, f"  hod max spread: h{spreads[0][1]:02d}={spreads[0][0]:.1f}" if spreads else "  sin spread")
    if crosses:
        w(lines, f"  mejor cruce +1d: h{crosses[0][1]:02d}→h{crosses[0][2]:02d} r={crosses[0][3]:+.2f}")
    w(lines, "  Jaccard: no entra. Cable: no. INFO / Brillo / Eco solamente.")
    w(lines, "")

    out = OUT / "LAB_CALENDARIO_HOD.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(lines, f"escrito: {out}")


if __name__ == "__main__":
    main()
