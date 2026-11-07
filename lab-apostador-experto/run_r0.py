# -*- coding: utf-8 -*-
"""
Lab Apostador Experto — Ronda 0 (censo + senior fuzzy + Pool8).
  python run_r0.py → reports/LAB_APOSTADOR_EXPERTO_R0.txt
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


def dump_res(label: str, r: dict) -> None:
    w(f"  [{label}]")
    w(
        f"    n={r['n']} go={r['go']} ({100 * r['coverage_go']:.1f}%) "
        f"strong={r['n_strong']} weak={r['n_weak']} nogo={r['n_nogo']}"
    )
    w(
        f"    hit_rate|GO={100 * r['hit_rate_go']:.1f}% "
        f"pnl={r['pnl']:+.1f} avg/event={r['avg_pnl']:+.4f} "
        f"acuerdo_P8={100 * r['acuerdo_rate']:.1f}%"
    )


def main() -> None:
    w("LAB APOSTADOR EXPERTO — Ronda 0")
    w("perfil: senior dinero real · GO/NO_GO · STRONG/WEAK")
    w("señales: Pool7 LC-01 · Pool8 INTER2 · EWMA errores · live prefix")
    w("juez: banda d<=1 · stakes 0/1/3 · odds lab 1:1")
    w("CERO cambios prod")
    w()

    horas, cinta = load_horas_y_cinta()
    w("precompute mesas (classic + INTER2)…")
    mesas = precompute_mesas(cinta)
    w(f"  mesas_for={len(mesas)}")
    train, hold = split_holdout(horas, HOLDOUT)
    w(f"n_horas={len(horas)} train={len(train)} holdout={len(hold)}")
    w()

    policies = ["ALWAYS_TIP", "NEVER", "EWMA_GATE", "SENIOR_FUZZY"]

    w("== H0 CENSO — ALWAYS_TIP (Pool 7) ==")
    dump_res("train", resumen(walk_eventos(train, mesas, ["ALWAYS_TIP"])["ALWAYS_TIP"]))
    if hold:
        dump_res(
            "hold", resumen(walk_eventos(hold, mesas, ["ALWAYS_TIP"])["ALWAYS_TIP"])
        )
    w()

    w("== H1–H3 POLÍTICAS ==")
    for split_name, subset in [("train", train), ("holdout", hold)]:
        if not subset:
            continue
        w(f"  -- {split_name} --")
        res = walk_eventos(subset, mesas, policies)
        for p in policies:
            dump_res(p, resumen(res[p]))
        w()

    if hold:
        r_always = resumen(walk_eventos(hold, mesas, ["ALWAYS_TIP"])["ALWAYS_TIP"])
        r_senior = resumen(walk_eventos(hold, mesas, ["SENIOR_FUZZY"])["SENIOR_FUZZY"])
        r_ewma = resumen(walk_eventos(hold, mesas, ["EWMA_GATE"])["EWMA_GATE"])
        w("== SÍNTESIS HOLDOUT ==")
        w(
            f"  ALWAYS_TIP pnl={r_always['pnl']:+.1f} "
            f"hit={100 * r_always['hit_rate_go']:.1f}% cov={100 * r_always['coverage_go']:.0f}%"
        )
        w(
            f"  EWMA_GATE  pnl={r_ewma['pnl']:+.1f} "
            f"hit={100 * r_ewma['hit_rate_go']:.1f}% cov={100 * r_ewma['coverage_go']:.0f}%"
        )
        w(
            f"  SENIOR    pnl={r_senior['pnl']:+.1f} "
            f"hit={100 * r_senior['hit_rate_go']:.1f}% cov={100 * r_senior['coverage_go']:.0f}% "
            f"strong={r_senior['n_strong']}"
        )
        delta = r_senior["pnl"] - r_always["pnl"]
        w(f"  Δpnl SENIOR − ALWAYS = {delta:+.1f}")
        if r_senior["n_strong"] == 0:
            w("  nota: GO_STRONG=0 en hold — calibrar θ o acuerdo P8 en R1")
        if delta > 0:
            w("  VEREDICTO: OLOR senior (mejor PnL selectivo vs always)")
        else:
            w("  VEREDICTO: FRÍO/OLOR — senior no gana PnL a always")
        w()

    w("== PISTAS ==")
    w("  se ve: tip LC densos; always tip pierde a odds 1:1 (hit~37–38%)")
    w("  se ve: filtros (EWMA/senior) recortan cobertura y mejoran PnL vs always")
    w("  se ve: NEVER pnl=0 (techo bankroll pasivo)")
    w("  ya estaba: Pool7/Pool8 en prod — lab solo lectura")
    w("  es nuevo: contrato GO/NO_GO × STRONG/WEAK + memoria + acuerdo P8")
    w()
    w("== DECISIÓN R0 ==")
    w("  Lab ABIERTO. Mineral: selectividad > tip ciego.")
    w("  R1: calibrar θ STRONG · ML logístico ligero · drawdown.")
    w("  Cero cable dashboard.")
    w()

    path = OUT / "LAB_APOSTADOR_EXPERTO_R0.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"[ok] {path}")


if __name__ == "__main__":
    main()
