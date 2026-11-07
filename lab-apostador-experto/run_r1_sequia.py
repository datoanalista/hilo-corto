# -*- coding: utf-8 -*-
"""
R1 sequía-5: tras G, ventana ≤5 tiros para la siguiente G.
Si no llega → sequía → NO_GO (perder esa G) y nuevo ancla.
  python run_r1_sequia.py
Cero prod.
"""
from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))
OUT = LAB / "reports"
OUT.mkdir(exist_ok=True)

from core_ae import (  # noqa: E402
    HOLDOUT,
    VENTANA_SEQUIA,
    dist_anillo,
    load_horas_y_cinta,
    precompute_mesas,
    resumen,
    split_holdout,
    walk_eventos,
)

lines: list[str] = []


def w(s: str = "") -> None:
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def brk(decs, label: str) -> None:
    goes = [d for d in decs if d.stake > 0]
    n_all = len(decs)
    nogo = sum(1 for d in decs if d.stake == 0)
    if not n_all:
        w(f"  [{label}] vacío")
        return
    w(
        f"  [{label}] eventos={n_all} GO={len(goes)} NO_GO={nogo} "
        f"cov={100 * len(goes) / n_all:.1f}%"
    )
    if not goes:
        return
    ex = sum(1 for d in goes if dist_anillo(d.tip, d.real) == 0)
    pm1 = sum(1 for d in goes if dist_anillo(d.tip, d.real) == 1)
    n = len(goes)
    r = resumen(decs)
    w(f"    Exacto d=0:  {ex} ({100 * ex / n:.1f}%)")
    w(f"    Borde  d=1:  {pm1} ({100 * pm1 / n:.1f}%)")
    w(f"    Banda d<=1:  {ex + pm1} ({100 * (ex + pm1) / n:.1f}%)")
    w(f"    pnl={r['pnl']:+.1f} avg={r['avg_pnl']:+.4f}")


def censo_gaps(horas) -> None:
    from core_ae import indices_g_en_tiros

    gaps = []
    for h in horas:
        idxs = indices_g_en_tiros(h)
        for a, b in zip(idxs, idxs[1:]):
            gaps.append(b - a)
    if not gaps:
        w("  sin gaps")
        return
    le = sum(1 for g in gaps if g <= VENTANA_SEQUIA)
    w(f"  n_gaps={len(gaps)} · gap<=5: {le} ({100 * le / len(gaps):.1f}%) · "
      f"sequia gap>5: {len(gaps) - le} ({100 * (len(gaps) - le) / len(gaps):.1f}%)")
    for k in range(1, 9):
        c = sum(1 for g in gaps if g == k)
        w(f"    gap={k}: {c} ({100 * c / len(gaps):.1f}%)")
    c9 = sum(1 for g in gaps if g >= 9)
    w(f"    gap>=9: {c9} ({100 * c9 / len(gaps):.1f}%)")


def main() -> None:
    w("LAB APOSTADOR EXPERTO — R1 SEQUIA-5")
    w(f"regla: tras G, ventana <={VENTANA_SEQUIA} tiros; si no → sequía NO_GO")
    w("objetivo: no cazar todas · ancla primera G · más exactitud en GO")
    w("CERO prod")
    w()

    horas, cinta = load_horas_y_cinta()
    mesas = precompute_mesas(cinta)
    train, hold = split_holdout(horas, HOLDOUT)
    w(f"n={len(horas)} train={len(train)} hold={len(hold)}")
    w()

    w("== CENSO gap tiros entre G consecutivas ==")
    w("  -- train --")
    censo_gaps(train)
    w("  -- holdout --")
    censo_gaps(hold)
    w()

    pols = ["ALWAYS_TIP", "SEQUIA5", "SEQUIA5_EWMA"]
    for split_name, subset in [("train", train), ("holdout", hold)]:
        w(f"== {split_name.upper()} ==")
        res = walk_eventos(subset, mesas, pols)
        for p in pols:
            brk(res[p], p)
        w()

    w("== LECTURA ==")
    w("  SEQUIA5 vs ALWAYS: menos cobertura (se pierden G en sequía),")
    w("  ¿sube exacto y banda en los GO que sí se toman?")
    w()

    path = OUT / "LAB_APOSTADOR_EXPERTO_R1_SEQUIA.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"[ok] {path}")


if __name__ == "__main__":
    main()
