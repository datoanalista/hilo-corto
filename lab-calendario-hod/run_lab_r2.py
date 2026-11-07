# -*- coding: utf-8 -*-
"""
Ronda 2 — DOW×tramo · costura opaco · intra @40 · holdout tejido.
  python run_lab_r2.py
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

OUT = LAB / "reports"
OUT.mkdir(exist_ok=True)
MIN_CELL = 10
LIFT_PCT = 5.0
COSTURAS = [(7, 8), (14, 15), (6, 7), (10, 11), (18, 19)]
TEJIDO_TOP = [(10, 8), (4, 13), (15, 19), (22, 9), (9, 10)]


def w(lines, s=""):
    lines.append(s)
    print(s.encode("ascii", "replace").decode("ascii"))


def base_mean(part: list[HoraCal]) -> float:
    return mean(h.mean_g for h in part) if part else 0.0


def dow_tramo_cells(part: list[HoraCal]) -> dict[tuple[int, str], list[HoraCal]]:
    g: dict[tuple[int, str], list[HoraCal]] = defaultdict(list)
    for h in part:
        g[(h.dow, h.tramo)].append(h)
    return g


def cell_lift(rows: list[HoraCal], base: float) -> float:
    if not rows:
        return 0.0
    return 100.0 * (mean(h.mean_g for h in rows) - base) / base if base else 0.0


def costura_lift(
    horas: list[HoraCal],
    ha: int,
    hb: int,
    filt=None,
) -> dict:
    idx = index_day_hod(horas)
    lifts_all, lifts_op, lifts_norm = [], [], []
    for h in horas:
        if h.hod != ha:
            continue
        if filt and not filt(h):
            continue
        b = idx.get((h.day, hb))
        if not b:
            continue
        lift = b.mean_g - h.mean_g
        lifts_all.append(lift)
        if h.is_op:
            lifts_op.append(lift)
        else:
            lifts_norm.append(lift)
    def med(xs):
        return median(xs) if xs else None

    return {
        "n": len(lifts_all),
        "med_all": med(lifts_all),
        "n_op": len(lifts_op),
        "med_op": med(lifts_op),
        "n_norm": len(lifts_norm),
        "med_norm": med(lifts_norm),
    }


def cross_r(horas: list[HoraCal], ha: int, hb: int) -> tuple[float | None, int]:
    idx = {h.tag: h for h in horas}
    xs, ys = [], []
    for h in horas:
        if h.hod != ha:
            continue
        dt2 = h.dt.replace(hour=hb) + timedelta(days=1)
        tag2 = f"h{hb}-{dt2.strftime('%d%m%y')}"
        b = idx.get(tag2)
        if b:
            xs.append(h.mean_g)
            ys.append(b.mean_g)
    return pearson(xs, ys), len(xs)


def main():
    horas = load_horas()
    train, test = split_holdout(horas)
    b_train = base_mean(train)
    b_test = base_mean(test) if test else b_train
    lines: list[str] = []

    w(lines, "LAB CALENDARIO-HOD — RONDA 2")
    w(lines, "=" * 60)
    w(lines, f"train={len(train)} test={len(test)} base mean_G train={b_train:.1f}")
    w(lines, "")

    # R2-H1 DOW×tramo ranking + holdout signo
    w(lines, "-- R2-H1 DOW×tramo · holdout signo --")
    tr_cells = dow_tramo_cells(train)
    te_cells = dow_tramo_cells(test)
    olor_ok, olor_flip = [], []
    for d in range(7):
        for tr in ("man", "tar", "noc"):
            rows = tr_cells.get((d, tr), [])
            if len(rows) < MIN_CELL:
                continue
            lift_tr = cell_lift(rows, b_train)
            if abs(lift_tr) < LIFT_PCT:
                continue
            te = te_cells.get((d, tr), [])
            lift_te = cell_lift(te, b_test) if te else 0.0
            same = lift_tr * lift_te > 0 if te else None
            item = (abs(lift_tr), d, tr, lift_tr, lift_te, len(rows), len(te), same)
            if same is True:
                olor_ok.append(item)
            elif same is False:
                olor_flip.append(item)
            w(
                lines,
                f"  {DOW_ES[d]}/{tr}: train {lift_tr:+.0f}% (n={len(rows)}) "
                f"test {lift_te:+.0f}% (n={len(te)}) "
                f"{'OK' if same else 'FLIP' if same is False else '—'}",
            )
    w(lines, f"  resumen: OK={len(olor_ok)} FLIP={len(olor_flip)}")
    w(lines, "")

    # R2-H2 intra @40 en celdas calientes vs base
    w(lines, "-- R2-H2 mean_G@40 en celdas |lift|>=5% (train) --")
    for _, d, tr, lift_tr, _, n, _, _ in sorted(olor_ok + olor_flip, reverse=True)[:8]:
        rows = [h for h in train if h.dow == d and h.tramo == tr and h.mean_g_40 is not None]
        if len(rows) < 6:
            continue
        m40 = mean(h.mean_g_40 for h in rows)
        w(
            lines,
            f"  {DOW_ES[d]}/{tr} lift={lift_tr:+.0f}%: mean@40={m40:.1f} "
            f"vs base@40={mean(h.mean_g_40 for h in train if h.mean_g_40):.1f} n={len(rows)}",
        )
    w(lines, "")

    # R2-H3 costura opaco dentro de tramo (vie/tar olores P0)
    w(lines, "-- R2-H3 COSTURA opaco→siguiente hod (mismo día) --")
    focus = [("vie", "tar"), ("mar", "man"), (None, "tar")]
    for dow_name, tr_name in focus:
        w(lines, f"  filtro: {dow_name or '*'} / {tr_name}")
        dow_i = DOW_ES.index(dow_name) if dow_name else None

        def filt(h, di=dow_i, tn=tr_name):
            if di is not None and h.dow != di:
                return False
            return h.tramo == tn

        for ha, hb in COSTURAS:
            if tramo_de_hod(ha) != tr_name and tramo_de_hod(hb) != tr_name:
                continue
            c_tr = costura_lift(train, ha, hb, filt=filt)
            c_te = costura_lift(test, ha, hb, filt=filt) if test else {}
            if c_tr["n_op"] < 3:
                continue
            w(
                lines,
                f"    h{ha:02d}→h{hb:02d}: op med={c_tr['med_op']:+.1f} "
                f"(n={c_tr['n_op']}) norm med={c_tr['med_norm'] if c_tr['med_norm'] is not None else '—'} "
                f"test_op={c_te.get('med_op') if c_te else '—'}",
            )
    w(lines, "")

    # R2-H4 lun h8↔h9 acumulado
    w(lines, "-- R2-H4 lun h08↔h09 (acumular) --")
    for label, part in [("train", train), ("test", test), ("all", horas)]:
        xs, ys = [], []
        idx = index_day_hod(part)
        for h in part:
            if h.hod != 8 or h.dow != 1:
                continue
            b = idx.get((h.day, 9))
            if b:
                xs.append(h.mean_g)
                ys.append(b.mean_g)
        r = pearson(xs, ys)
        w(lines, f"  {label}: r={r if r is not None else '—'} n={len(xs)}")
    w(lines, "")

    # R2-H5 tejido top · holdout r
    w(lines, "-- R2-H5 TEJIDO +1d · r train vs test --")
    for ha, hb in TEJIDO_TOP:
        r_tr, n_tr = cross_r(train, ha, hb)
        r_te, n_te = cross_r(test, ha, hb) if test else (None, 0)
        same = r_tr and r_te and r_tr * r_te > 0
        w(
            lines,
            f"  h{ha:02d}→h{hb:02d}: train r={r_tr if r_tr is not None else '—'} n={n_tr} "
            f"test r={r_te if r_te is not None else '—'} n={n_te} "
            f"{'OK' if same else 'FLIP' if r_tr and r_te else '—'}",
        )
    w(lines, "")

    # Síntesis
    w(lines, "-- SÍNTESIS R2 --")
    if olor_ok:
        top = max(olor_ok, key=lambda x: x[0])
        w(lines, f"  DOW×tramo OK: {DOW_ES[top[1]]}/{top[2]} train {top[3]:+.0f}%")
    w(lines, f"  holdout grueso: {len(olor_ok)} OK / {len(olor_flip)} FLIP")
    c1415 = costura_lift(
        train,
        14,
        15,
        filt=lambda h: h.tramo == "tar" and h.dow == 4,
    )
    if c1415["med_op"] is not None:
        w(lines, f"  vie/tar h14 op→h15: med {c1415['med_op']:+.1f} (n_op={c1415['n_op']})")
    w(lines, "  cable: no · INFO Brillo/Eco · anti-Jaccard")

    out = OUT / "LAB_CALENDARIO_HOD_R2.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(lines, f"escrito: {out}")


def tramo_de_hod(hod: int) -> str:
    for name, a, b in TRAMO:
        if a <= hod <= b:
            return name
    return "?"


if __name__ == "__main__":
    main()
