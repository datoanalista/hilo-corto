# -*- coding: utf-8 -*-
"""
R3 espina: ruteo tip↔P8 por régimen de gap.
  V3 (gap≤3) → tip LC
  SEQ (gap>3) → tip desde P8 (chip más cerca del tip LC)
  python run_r3_ruteo.py
Cero prod.
"""
from __future__ import annotations

import statistics
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
AE = ROOT / "lab-apostador-experto"
sys.path.insert(0, str(AE))
sys.path.insert(0, str(ROOT))

OUT = LAB / "reports"
OUT.mkdir(exist_ok=True)

from core_ae import (  # noqa: E402
    HOLDOUT,
    STAKE_WEAK,
    dist_anillo,
    indices_g_en_tiros,
    load_horas_y_cinta,
    precompute_mesas,
    split_holdout,
    tip_lc01,
)

VENTANA = 3
lines: list[str] = []


def w(s: str = "") -> None:
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def tip_desde_p8(chips: list[int], tip_lc: int | None) -> int | None:
    if not chips:
        return None
    if tip_lc is not None:
        return min(chips, key=lambda c: (dist_anillo(c, tip_lc), c))
    return int(statistics.median(chips))


def walk(horas, mesas: dict) -> list[dict]:
    rows = []
    for h in horas:
        gs = sorted(h.gs, key=lambda g: g.m0)
        if len(gs) < 2:
            continue
        mesa = mesas.get(h.tag)
        chips_p8 = list(
            (mesa.inter2 if mesa else None)
            or (mesa.classic if mesa else None)
            or []
        )
        idxs = indices_g_en_tiros(h)
        luces: list[int] = []
        for i in range(len(gs) - 1):
            luces.append(gs[i].m0)
            tip_lc = tip_lc01(luces)
            if tip_lc is None:
                continue
            if len(idxs) >= i + 2:
                gap = idxs[i + 1] - idxs[i]
            else:
                gap = 1
            real = gs[i + 1].m0
            v3 = gap <= VENTANA
            tip_p8 = tip_desde_p8(chips_p8, tip_lc)
            rows.append(
                {
                    "gap": gap,
                    "v3": v3,
                    "real": real,
                    "tip_lc": tip_lc,
                    "tip_p8": tip_p8,
                    "hit_lc": dist_anillo(tip_lc, real) <= 1,
                    "ex_lc": dist_anillo(tip_lc, real) == 0,
                    "hit_p8": tip_p8 is not None
                    and dist_anillo(tip_p8, real) <= 1,
                    "ex_p8": tip_p8 is not None
                    and dist_anillo(tip_p8, real) == 0,
                }
            )
    return rows


def metrics(decs: list[dict]) -> dict:
    """decs: tip, hit, stake."""
    if not decs:
        return {
            "n": 0,
            "go": 0,
            "cov": 0.0,
            "exacto": 0.0,
            "banda": 0.0,
            "pnl": 0.0,
        }
    goes = [d for d in decs if d["stake"] > 0]
    n = len(decs)
    if not goes:
        return {
            "n": n,
            "go": 0,
            "cov": 0.0,
            "exacto": 0.0,
            "banda": 0.0,
            "pnl": 0.0,
        }
    ex = sum(1 for d in goes if d["ex"])
    bd = sum(1 for d in goes if d["hit"])
    pnl = sum(d["pnl"] for d in decs)
    return {
        "n": n,
        "go": len(goes),
        "cov": 100.0 * len(goes) / n,
        "exacto": 100.0 * ex / len(goes),
        "banda": 100.0 * bd / len(goes),
        "pnl": pnl,
    }


def policy(rows: list[dict], name: str) -> list[dict]:
    out = []
    for r in rows:
        tip = None
        stake = 0
        if name == "ALWAYS_TIP":
            tip = r["tip_lc"]
            stake = STAKE_WEAK
        elif name == "SEQUIA3":
            if r["v3"]:
                tip = r["tip_lc"]
                stake = STAKE_WEAK
        elif name == "ALWAYS_P8":
            tip = r["tip_p8"]
            stake = STAKE_WEAK if tip is not None else 0
        elif name == "SEQUIA3_P8":
            # solo en V3, pero tip = P8 cerca de LC
            if r["v3"] and r["tip_p8"] is not None:
                tip = r["tip_p8"]
                stake = STAKE_WEAK
        elif name == "ROUTE":
            # espina: V3→LC · SEQ→P8
            if r["v3"]:
                tip = r["tip_lc"]
                stake = STAKE_WEAK
            elif r["tip_p8"] is not None:
                tip = r["tip_p8"]
                stake = STAKE_WEAK
        elif name == "ROUTE_INV":
            # control invertido: V3→P8 · SEQ→LC
            if r["v3"] and r["tip_p8"] is not None:
                tip = r["tip_p8"]
                stake = STAKE_WEAK
            else:
                tip = r["tip_lc"]
                stake = STAKE_WEAK
        else:
            continue
        if tip is None or stake == 0:
            out.append(
                {
                    "stake": 0,
                    "hit": False,
                    "ex": False,
                    "pnl": 0.0,
                }
            )
            continue
        hit = dist_anillo(tip, r["real"]) <= 1
        ex = dist_anillo(tip, r["real"]) == 0
        pnl = float(stake if hit else -stake)
        out.append({"stake": stake, "hit": hit, "ex": ex, "pnl": pnl})
    return out


def dump(label: str, m: dict) -> None:
    w(
        f"  [{label}] cov={m['cov']:.1f}% GO={m['go']}/{m['n']} "
        f"exacto={m['exacto']:.1f}% banda={m['banda']:.1f}% pnl={m['pnl']:+.1f}"
    )


def regime_slice(rows: list[dict], v3: bool) -> dict:
    sub = [r for r in rows if r["v3"] == v3]
    if not sub:
        return {"n": 0, "lc_band": 0.0, "p8_band": 0.0, "lc_ex": 0.0, "p8_ex": 0.0}
    n = len(sub)
    return {
        "n": n,
        "lc_band": 100.0 * sum(r["hit_lc"] for r in sub) / n,
        "p8_band": 100.0 * sum(r["hit_p8"] for r in sub) / n,
        "lc_ex": 100.0 * sum(r["ex_lc"] for r in sub) / n,
        "p8_ex": 100.0 * sum(r["ex_p8"] for r in sub) / n,
    }


def main() -> None:
    w("LAB POOL × VENTANA 3 — R3 ruteo tip↔P8 (espina)")
    w("ROUTE: gap≤3 → tip LC · gap>3 → chip P8 más cerca del tip LC")
    w("CERO prod")
    w()

    horas, cinta = load_horas_y_cinta()
    mesas = precompute_mesas(cinta)
    train, hold = split_holdout(horas, HOLDOUT)
    w(f"n={len(horas)} train={len(train)} hold={len(hold)}")
    w()

    hold_rows = walk(hold, mesas)
    train_rows = walk(train, mesas)

    for split_name, rows in [("train", train_rows), ("holdout", hold_rows)]:
        w(f"== {split_name.upper()} · censo tip vs P8 por régimen ==")
        for label, is_v3 in (("V3 gap≤3", True), ("SEQ gap>3", False)):
            s = regime_slice(rows, is_v3)
            w(
                f"  {label}: n={s['n']} "
                f"LC banda={s['lc_band']:.1f}% exacto={s['lc_ex']:.1f}% · "
                f"P8tip banda={s['p8_band']:.1f}% exacto={s['p8_ex']:.1f}%"
            )
        w()
        w(f"== {split_name.upper()} · políticas ==")
        for pol in (
            "ALWAYS_TIP",
            "SEQUIA3",
            "ALWAYS_P8",
            "SEQUIA3_P8",
            "ROUTE",
            "ROUTE_INV",
        ):
            dump(pol, metrics(policy(rows, pol)))
        w()

    # Veredicto holdout
    mh = {p: metrics(policy(hold_rows, p)) for p in (
        "ALWAYS_TIP", "SEQUIA3", "ALWAYS_P8", "SEQUIA3_P8", "ROUTE", "ROUTE_INV"
    )}
    base = mh["SEQUIA3"]
    w("== DELTA holdout vs SEQUIA3 ==")
    for p, m in mh.items():
        if p == "SEQUIA3":
            continue
        w(
            f"  {p}: Δbanda={m['banda']-base['banda']:+.1f}pp "
            f"Δpnl={m['pnl']-base['pnl']:+.1f} Δcov={m['cov']-base['cov']:+.1f}pp"
        )
    w()

    reg_v3 = regime_slice(hold_rows, True)
    reg_seq = regime_slice(hold_rows, False)
    w("== VEREDICTO ==")
    w(
        f"  Régimen hold: V3 LC {reg_v3['lc_band']:.1f}% vs P8 {reg_v3['p8_band']:.1f}% · "
        f"SEQ LC {reg_seq['lc_band']:.1f}% vs P8 {reg_seq['p8_band']:.1f}%"
    )
    # Espina viva si ROUTE gana SEQUIA3 en pnl y banda no cae, o SEQ confirma P8>LC
    olor = []
    if reg_seq["n"] and reg_seq["p8_band"] >= reg_seq["lc_band"] + 3:
        olor.append("en SEQ P8tip > LC (+≥3pp)")
    if reg_v3["n"] and reg_v3["lc_band"] >= reg_v3["p8_band"] + 3:
        olor.append("en V3 LC > P8tip")
    if mh["ROUTE"]["pnl"] >= base["pnl"] + 10 and mh["ROUTE"]["banda"] >= base["banda"] - 1:
        olor.append("ROUTE mejora PnL vs SEQUIA3")
    if mh["ROUTE"]["pnl"] <= base["pnl"] and mh["ROUTE"]["banda"] <= base["banda"] + 1:
        olor.append("ROUTE no gana a SEQUIA3 (espina sacada: no ruteo)")

    if any("ROUTE mejora" in x for x in olor):
        w("  OLOR ruteo: " + " · ".join(olor))
        w("  → anotar; no cable sin OK.")
    else:
        w("  ESPINA CERRADA: " + (" · ".join(olor) if olor else "sin ventaja ROUTE"))
        w("  SEQUIA3 (solo tip en V3, NO_GO en sequía) sigue siendo la política.")
    w("  Tema pools×ventana3 CERRADO.")
    w()

    path = OUT / "LAB_POOL_VENTANA3_R3_RUTEO.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"[ok] {path}")


if __name__ == "__main__":
    main()
