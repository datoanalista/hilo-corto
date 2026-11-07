# -*- coding: utf-8 -*-
"""
R2+R3 sobre SEQUIA3: potencias (P8, EWMA, soft, combos) + espina MISS2.
  python run_r2_r3.py
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


def dump(decs, label: str) -> dict:
    goes = [d for d in decs if d.stake > 0]
    n_all = len(decs)
    if not n_all:
        w(f"  [{label}] vacío")
        return {}
    r = resumen(decs)
    if not goes:
        w(f"  [{label}] cov=0% GO=0/{n_all} pnl={r['pnl']:+.1f}")
        return r
    ex = sum(1 for d in goes if dist_anillo(d.tip, d.real) == 0)
    pm1 = sum(1 for d in goes if dist_anillo(d.tip, d.real) == 1)
    n = len(goes)
    band = ex + pm1
    w(
        f"  [{label}] cov={100 * n / n_all:.1f}% GO={n}/{n_all} "
        f"exacto={100 * ex / n:.1f}% +-1={100 * pm1 / n:.1f}% "
        f"banda={100 * band / n:.1f}% pnl={r['pnl']:+.1f} "
        f"strong={r['n_strong']} weak={r['n_weak']}"
    )
    return {
        **r,
        "exacto": ex / n,
        "pm1": pm1 / n,
        "banda": band / n,
        "label": label,
    }


def main() -> None:
    assert VENTANA_SEQUIA == 3, f"esperado VENTANA=3, got {VENTANA_SEQUIA}"
    w("LAB APOSTADOR EXPERTO — R2+R3 potencias sobre SEQUIA3")
    w(f"ventana fijada={VENTANA_SEQUIA} tiros · CERO prod")
    w()

    horas, cinta = load_horas_y_cinta()
    mesas = precompute_mesas(cinta)
    train, hold = split_holdout(horas, HOLDOUT)
    w(f"n={len(horas)} train={len(train)} hold={len(hold)}")
    w()

    # R2: potencias principales
    r2 = [
        "ALWAYS_TIP",
        "SEQUIA",
        "SEQUIA_P8",
        "SEQUIA_EWMA",
        "SEQUIA_SOFT",
        "SEQUIA_P8_EWMA",
        "SEQUIA_P8_SOFT",
    ]
    # R3: espina — gate racha miss sin P8
    r3 = ["SEQUIA_MISS2"]

    hold_m: dict[str, dict] = {}

    for split_name, subset in [("train", train), ("holdout", hold)]:
        w(f"== R2 {split_name.upper()} ==")
        res = walk_eventos(subset, mesas, r2)
        for p in r2:
            m = dump(res[p], p)
            if split_name == "holdout":
                hold_m[p] = m
        w()

    w("== R3 HOLDOUT (espina miss_streak>=2) ==")
    res3 = walk_eventos(hold, mesas, ["SEQUIA", "SEQUIA_MISS2"])
    for p in ["SEQUIA", "SEQUIA_MISS2"]:
        hold_m[p] = dump(res3[p], p)
    w()

    # Comparar vs SEQUIA base
    base = hold_m.get("SEQUIA") or {}
    bb = float(base.get("banda") or 0)
    bp = float(base.get("pnl") or 0)
    bc = float(base.get("coverage_go") or 0)

    w("== DELTA vs SEQUIA3 (holdout) ==")
    w(f"  base SEQUIA: banda={100*bb:.1f}% pnl={bp:+.1f} cov={100*bc:.1f}%")
    for name, m in hold_m.items():
        if name in ("SEQUIA", "ALWAYS_TIP") or not m:
            continue
        db = 100 * (float(m.get("banda") or 0) - bb)
        dp = float(m.get("pnl") or 0) - bp
        dc = 100 * (float(m.get("coverage_go") or 0) - bc)
        w(f"  {name}: Δbanda={db:+.1f}pp Δpnl={dp:+.1f} Δcov={dc:+.1f}pp")
    w()

    # Veredicto automático
    winners = []
    for name, m in hold_m.items():
        if name in ("SEQUIA", "ALWAYS_TIP") or not m:
            continue
        banda = float(m.get("banda") or 0)
        pnl = float(m.get("pnl") or 0)
        # "nuevo" = sube banda >= +2pp y pnl no empeora, o sube pnl >= +10 con banda no peor
        if (banda >= bb + 0.02 and pnl >= bp - 5) or (
            pnl >= bp + 10 and banda >= bb - 0.01
        ):
            winners.append(name)

    w("== VEREDICTO ==")
    if winners:
        w(f"  HAY OLOR nuevo: {', '.join(winners)}")
        w("  → no cablear solo SEQUIA3; revisar combo ganador.")
    else:
        w("  SIN OLOR nuevo material vs SEQUIA3 sola.")
        w("  P8/EWMA/soft/miss2 no mejoran banda+PnL juntos de forma clara.")
        w("  → candidata a cable: SEQUIA3 (tip LC, TTL 3 tiros, stake WEAK).")
    w()

    path = OUT / "LAB_APOSTADOR_EXPERTO_R2_R3.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"[ok] {path}")


if __name__ == "__main__":
    main()
