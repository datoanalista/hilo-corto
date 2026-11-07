# -*- coding: utf-8 -*-
"""Comparar ventana sequía 3 / 4 / 5 tiros. Cero prod."""
from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))
OUT = LAB / "reports"
OUT.mkdir(exist_ok=True)

import core_ae as ae
from core_ae import (
    HOLDOUT,
    dist_anillo,
    indices_g_en_tiros,
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


def metrics(decs):
    goes = [d for d in decs if d.stake > 0]
    n_all = len(decs)
    if not goes:
        return None
    ex = sum(1 for d in goes if dist_anillo(d.tip, d.real) == 0)
    pm1 = sum(1 for d in goes if dist_anillo(d.tip, d.real) == 1)
    n = len(goes)
    r = resumen(decs)
    return {
        "cov": n / n_all,
        "n_go": n,
        "n_all": n_all,
        "exacto": ex / n,
        "pm1": pm1 / n,
        "banda": (ex + pm1) / n,
        "pnl": r["pnl"],
    }


def dump(label: str, m: dict) -> None:
    w(
        f"  [{label}] cov={100 * m['cov']:.1f}% GO={m['n_go']}/{m['n_all']} "
        f"exacto={100 * m['exacto']:.1f}% +-1={100 * m['pm1']:.1f}% "
        f"banda={100 * m['banda']:.1f}% pnl={m['pnl']:+.1f}"
    )


def censo(horas, name: str) -> None:
    gaps = []
    for h in horas:
        idxs = indices_g_en_tiros(h)
        for a, b in zip(idxs, idxs[1:]):
            gaps.append(b - a)
    w(f"  -- {name} n_gaps={len(gaps)} --")
    for v in range(1, 8):
        le = sum(1 for g in gaps if g <= v)
        w(
            f"    gap<={v}: {le} ({100 * le / len(gaps):.1f}%) "
            f"sequia={100 * (len(gaps) - le) / len(gaps):.1f}%"
        )


def main() -> None:
    w("COMPARATIVA SEQUIA ventana 1..7 tiros (rango completo)")
    w("CERO prod")
    w()
    horas, cinta = load_horas_y_cinta()
    mesas = precompute_mesas(cinta)
    train, hold = split_holdout(horas, HOLDOUT)
    w(f"n={len(horas)} train={len(train)} hold={len(hold)}")
    w()
    w("== CENSO holdout ==")
    censo(hold, "holdout")
    # detalle gap=1 y 2
    gaps = []
    for h in hold:
        idxs = indices_g_en_tiros(h)
        for a, b in zip(idxs, idxs[1:]):
            gaps.append(b - a)
    for k in range(1, 8):
        c = sum(1 for g in gaps if g == k)
        w(f"    gap={k} solo: {c} ({100 * c / len(gaps):.1f}%)")
    w()

    w("== HOLDOUT curva ==")
    always = metrics(walk_eventos(hold, mesas, ["ALWAYS_TIP"])["ALWAYS_TIP"])
    dump("ALWAYS", always)
    for v in range(1, 8):
        ae.VENTANA_SEQUIA = v
        m = metrics(walk_eventos(hold, mesas, ["SEQUIA5"])["SEQUIA5"])
        dump(f"SEQUIA{v}", m)
    w()
    w("== LECTURA ==")
    w("  gap=1: G seguida de G (mínimo físico). Ventana 2 = casi mínimo útil.")
    w("  Ventana 6+: se acerca a always (más cobertura, baja precisión).")
    w("  Equilibrio práctico observado: 3–5.")
    w()
    path = OUT / "LAB_APOSTADOR_EXPERTO_SEQUIA_RANGO.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"[ok] {path}")


if __name__ == "__main__":
    main()
