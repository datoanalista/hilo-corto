# -*- coding: utf-8 -*-
"""
Ronda 3 — INFO cartel · costura h14→h15 · h08 profundo · holdout fino.
  python run_lab_r3.py
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from statistics import mean, median

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))

from core_cal import (  # noqa: E402
    DOW_ES,
    HoraCal,
    TRAMO,
    index_day_hod,
    load_horas,
    pearson,
    split_holdout,
)
from run_lab import pair_by_dow, spread_dow  # noqa: E402
from run_lab_r2 import (  # noqa: E402
    cell_lift,
    costura_lift,
    cross_r,
    dow_tramo_cells,
    tramo_de_hod,
)

OUT = LAB / "reports"
OUT.mkdir(exist_ok=True)
MIN_CELL = 8
LIFT_PCT = 5.0
HOD_FOCUS = 8
INFO_CELLS = [(5, "noc"), (5, "tar"), (5, "man"), (2, "man"), (6, "noc")]
COSTURA_FOCUS = [(14, 15, 5, "tar"), (6, 7, 2, "man"), (10, 11, None, "tar")]
H08_PAIRS = [(8, 9), (8, 14), (8, 18), (20, 22)]
TEJIDO_R3 = [(10, 8), (4, 13), (15, 19), (22, 9)]


def w(lines, s=""):
    lines.append(s)
    print(s.encode("ascii", "replace").decode("ascii"))


def base_mean(part: list[HoraCal]) -> float:
    return mean(h.mean_g for h in part) if part else 0.0


def lift_mean(rows: list[HoraCal], base: float) -> float:
    if not rows or not base:
        return 0.0
    return 100.0 * (mean(h.mean_g for h in rows) - base) / base


def main():
    horas = load_horas()
    train, test = split_holdout(horas)
    test_a, test_b = (test[:36], test[36:]) if len(test) >= 36 else (test, [])
    b_train = base_mean(train)
    b_test = base_mean(test) if test else b_train
    lines: list[str] = []

    w(lines, "LAB CALENDARIO-HOD — RONDA 3")
    w(lines, "=" * 60)
    w(lines, f"train={len(train)} test={len(test)} (A={len(test_a)} B={len(test_b)})")
    w(lines, f"base mean_G train={b_train:.1f} test={b_test:.1f}")
    w(lines, "")

    # R3-H1 INFO DOW×tramo · candidatos R2 + holdout fino
    w(lines, "-- R3-H1 INFO · DOW×tramo candidatos (train / test / test-A / test-B) --")
    info_ok, info_flip, info_weak = [], [], []
    for d, tr in INFO_CELLS:
        tr_r = [h for h in train if h.dow == d and h.tramo == tr]
        if len(tr_r) < MIN_CELL:
            continue
        lift_tr = lift_mean(tr_r, b_train)
        te_r = [h for h in test if h.dow == d and h.tramo == tr]
        te_a = [h for h in test_a if h.dow == d and h.tramo == tr]
        te_b = [h for h in test_b if h.dow == d and h.tramo == tr]
        lift_te = lift_mean(te_r, b_test) if te_r else None
        lift_a = lift_mean(te_a, base_mean(test_a)) if te_a and test_a else None
        lift_b = lift_mean(te_b, base_mean(test_b)) if te_b and test_b else None
        same = lift_tr * lift_te > 0 if lift_te is not None else None
        item = (abs(lift_tr), d, tr, lift_tr, lift_te, lift_a, lift_b, len(tr_r), len(te_r))
        if same is True:
            info_ok.append(item)
        elif same is False:
            info_flip.append(item)
        else:
            info_weak.append(item)
        sa = f"{lift_a:+.0f}%" if lift_a is not None else "—"
        sb = f"{lift_b:+.0f}%" if lift_b is not None else "—"
        ste = f"{lift_te:+.0f}%" if lift_te is not None else "—"
        w(
            lines,
            f"  {DOW_ES[d]}/{tr}: train {lift_tr:+.0f}% (n={len(tr_r)}) "
            f"test {ste} (n={len(te_r)}) "
            f"A {sa} B {sb} "
            f"{'OK' if same else 'FLIP' if same is False else '—'}",
        )
    w(lines, f"  resumen INFO: OK={len(info_ok)} FLIP={len(info_flip)} sin_test={len(info_weak)}")
    w(lines, "")

    # R3-H2 Costura opaco → cartel Brillo
    w(lines, "-- R3-H2 COSTURA opaco→sig · foco R2 (train / test) --")

    def mk_filt(dow_i, tr_name):
        def filt(h, di=dow_i, tn=tr_name):
            if di is not None and h.dow != di:
                return False
            return h.tramo == tn

        return filt

    costura_vive = []
    for ha, hb, dow_i, tr_name in COSTURA_FOCUS:
        filt = mk_filt(dow_i, tr_name)
        c_tr = costura_lift(train, ha, hb, filt=filt)
        c_te = costura_lift(test, ha, hb, filt=filt) if test else {}
        if c_tr["n_op"] < 3:
            continue
        label = f"{DOW_ES[dow_i] if dow_i is not None else '*'}/{tr_name}"
        w(
            lines,
            f"  {label} h{ha:02d}→h{hb:02d}: op med={c_tr['med_op']:+.1f} "
            f"(n={c_tr['n_op']}) test_op={c_te.get('med_op') if c_te else '—'} "
            f"(n={c_te.get('n_op', 0) if c_te else 0})",
        )
        if c_tr["med_op"] and c_tr["med_op"] >= 8:
            costura_vive.append((label, ha, hb, c_tr["med_op"], c_tr["n_op"]))
    w(lines, "")

    # R3-H3 h08 profundo
    w(lines, f"-- R3-H3 h{HOD_FOCUS:02d} PROFUNDO --")
    for label, part in [("train", train), ("test", test), ("all", horas)]:
        sp, cells = spread_dow(HOD_FOCUS, part)
        w(lines, f"  spread {label}={sp:.1f}")
        for name, med, n in cells:
            w(lines, f"    {name}: med={med:.1f} n={n}")
    w(lines, "  h08↔h09 por DOW (mean_G mismo día):")
    for label, part in [("train", train), ("test", test)]:
        by_dow, r_all, n = pair_by_dow(HOD_FOCUS, 9, part)
        w(lines, f"    {label} global: r={r_all if r_all is not None else '—'} n={n}")
        for d in range(7):
            info = by_dow.get(d)
            if not info or info["n"] < 3:
                continue
            w(
                lines,
                f"      {DOW_ES[d]}: r={info['r'] if info['r'] is not None else '—'} "
                f"n={info['n']} med={info['med_a']:.0f}/{info['med_b']:.0f}",
            )
    w(lines, "  h08 celdas vs mediana hod (train):")
    hod8_med = median(h.mean_g for h in train if h.hod == HOD_FOCUS)
    for d in range(7):
        rows = [h for h in train if h.hod == HOD_FOCUS and h.dow == d]
        if len(rows) < MIN_CELL:
            continue
        med = median(h.mean_g for h in rows)
        w(
            lines,
            f"    {DOW_ES[d]}: {med:.1f} vs hod8={hod8_med:.1f} "
            f"({med - hod8_med:+.1f}) n={len(rows)}",
        )
    w(lines, "  h08 mean_G@40 por DOW (train):")
    for d in range(7):
        rows = [h for h in train if h.hod == HOD_FOCUS and h.dow == d and h.mean_g_40]
        if len(rows) < 4:
            continue
        w(
            lines,
            f"    {DOW_ES[d]}: @40={mean(h.mean_g_40 for h in rows):.1f} n={len(rows)}",
        )
    w(lines, "")

    # R3-H4 pares con h08
    w(lines, "-- R3-H4 PARES con h08 (train) --")
    pair_rank = []
    for h1, h2 in H08_PAIRS:
        by_dow, r_all, n = pair_by_dow(h1, h2, train)
        if n >= 6 and r_all is not None:
            pair_rank.append((abs(r_all), h1, h2, r_all, n))
        w(lines, f"  h{h1:02d}↔h{h2:02d}: r={r_all if r_all is not None else '—'} n={n}")
    pair_rank.sort(reverse=True)
    w(lines, "")

    # R3-H5 tejido +1d holdout fino
    w(lines, "-- R3-H5 TEJIDO +1d (train / test / test-A / test-B) --")
    tejido_ok = []
    for ha, hb in TEJIDO_R3:
        r_tr, n_tr = cross_r(train, ha, hb)
        r_te, n_te = cross_r(test, ha, hb) if test else (None, 0)
        r_a, n_a = cross_r(test_a, ha, hb) if test_a else (None, 0)
        r_b, n_b = cross_r(test_b, ha, hb) if test_b else (None, 0)
        ok = r_tr and r_te and r_tr * r_te > 0
        if ok:
            tejido_ok.append((ha, hb, r_tr, r_te))
        w(
            lines,
            f"  h{ha:02d}→h{hb:02d}: tr r={r_tr if r_tr is not None else '—'} n={n_tr} "
            f"te r={r_te if r_te is not None else '—'} n={n_te} "
            f"A={r_a if r_a is not None else '—'} B={r_b if r_b is not None else '—'} "
            f"{'OK' if ok else 'FLIP' if r_tr and r_te else '—'}",
        )
    w(lines, "")

    # R3-H6 borrador cartel INFO (Brillo/Eco — no cable)
    w(lines, "-- R3-H6 BORRADOR CARTEL INFO (Brillo modal · no cable) --")
    if info_ok:
        top = max(info_ok, key=lambda x: x[0])
        d, tr, lift_tr, lift_te = top[1], top[2], top[3], top[4]
        w(
            lines,
            f"  [Brillo calendario] {DOW_ES[d]} {tr}: mean_G suele ir "
            f"{lift_tr:+.0f}% vs base (train). Holdout {lift_te:+.0f}%. "
            f"Solo lectura — no boleto.",
        )
    for label, ha, hb, med, n in costura_vive[:2]:
        w(
            lines,
            f"  [Brillo costura] Si h{ha:02d} cierra opaca ({label}), "
            f"h{hb:02d} mismo día med +{med:.0f} lumen (n={n}). Descriptivo.",
        )
    if tejido_ok:
        ha, hb, r_tr, r_te = tejido_ok[0]
        w(
            lines,
            f"  [Eco tejido] h{ha:02d} muy fuerte → h{hb:02d} día+1 "
            f"r={r_tr:+.2f} train / {r_te:+.2f} test. Eco, no chip.",
        )
    w(
        lines,
        "  [h08 acumular] Spread DOW alto; lun↔h09 r frágil (n pequeño). "
        "No cartel hasta más semanas.",
    )
    w(lines, "")

    # Síntesis R3
    w(lines, "-- SÍNTESIS R3 --")
    w(lines, f"  INFO DOW×tramo holdout: {len(info_ok)} OK / {len(info_flip)} FLIP")
    if info_ok:
        for _, d, tr, lift_tr, lift_te, *_ in sorted(info_ok, key=lambda x: -x[0])[:3]:
            w(
                lines,
                f"    VIVE INFO: {DOW_ES[d]}/{tr} train {lift_tr:+.0f}% test {lift_te:+.0f}%",
            )
    if costura_vive:
        w(
            lines,
            f"  Costura VIVE: {costura_vive[0][0]} h{costura_vive[0][1]:02d}→h{costura_vive[0][2]:02d}",
        )
    sp_tr, _ = spread_dow(HOD_FOCUS, train)
    w(lines, f"  h08 spread train={sp_tr:.1f} — acumular, no ley")
    w(lines, "  cable dashboard: no · borrador cartel arriba · anti-Jaccard")
    w(lines, "  siguiente: OK humano para 1–2 líneas Brillo calendario")

    out = OUT / "LAB_CALENDARIO_HOD_R3.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(lines, f"escrito: {out}")


if __name__ == "__main__":
    main()
