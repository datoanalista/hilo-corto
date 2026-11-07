# -*- coding: utf-8 -*-
"""
R1: Pool 0 (classic) × ventana 3 live — ¿punta mejor en gap≤3?
  python run_r1_pool0.py
Cero prod.
"""
from __future__ import annotations

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
    acuerdo_tip,
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


def hit_chip(chips: list[int], real: int) -> tuple[bool, bool]:
    if not chips:
        return False, False
    d = min(dist_anillo(c, real) for c in chips)
    return d == 0, d <= 1


def walk_split(horas, mesas: dict) -> list[dict]:
    rows = []
    for h in horas:
        gs = sorted(h.gs, key=lambda g: g.m0)
        if len(gs) < 2:
            continue
        mesa = mesas.get(h.tag)
        chips_p0 = list((mesa.classic if mesa else None) or [])
        chips_p8 = list(
            (mesa.inter2 if mesa else None) or chips_p0 or []
        )
        idxs = indices_g_en_tiros(h)
        luces: list[int] = []
        for i in range(len(gs)):
            if i == 0:
                luces.append(gs[i].m0)
                continue
            if len(idxs) >= i + 1:
                gap = idxs[i] - idxs[i - 1]
            else:
                gap = 1
            tip = tip_lc01(luces)
            real = gs[i].m0
            ex0, b0 = hit_chip(chips_p0, real)
            ex8, b8 = hit_chip(chips_p8, real)
            tip_ex = tip is not None and dist_anillo(tip, real) == 0
            tip_band = tip is not None and dist_anillo(tip, real) <= 1
            inter0 = [
                c
                for c in chips_p0
                if tip is not None and dist_anillo(c, tip) <= 1
            ]
            ex_i, b_i = hit_chip(inter0, real)
            rows.append(
                {
                    "gap": gap,
                    "v3": gap <= VENTANA,
                    "ex_p0": ex0,
                    "band_p0": b0,
                    "ex_p8": ex8,
                    "band_p8": b8,
                    "tip_ex": tip_ex,
                    "tip_band": tip_band,
                    "ex_i": ex_i,
                    "band_i": b_i,
                    "k_p0": len(chips_p0),
                    "k_i": len(inter0),
                    "acuerdo": acuerdo_tip(tip, chips_p0) if tip is not None else False,
                }
            )
            luces.append(real)
    return rows


def agg(rows: list[dict], pred: str) -> dict:
    if not rows:
        return {"n": 0, "exacto": 0.0, "banda": 0.0, "k": 0.0}
    n = len(rows)
    if pred == "p0":
        ex = sum(1 for r in rows if r["ex_p0"])
        bd = sum(1 for r in rows if r["band_p0"])
        k = sum(r["k_p0"] for r in rows) / n
    elif pred == "p8":
        ex = sum(1 for r in rows if r["ex_p8"])
        bd = sum(1 for r in rows if r["band_p8"])
        k = 0.0
    elif pred == "tip":
        ex = sum(1 for r in rows if r["tip_ex"])
        bd = sum(1 for r in rows if r["tip_band"])
        k = 1.0
    elif pred == "p0_tip":
        ex = sum(1 for r in rows if r["ex_i"])
        bd = sum(1 for r in rows if r["band_i"])
        k = sum(r["k_i"] for r in rows) / n
    else:
        raise ValueError(pred)
    return {"n": n, "exacto": 100.0 * ex / n, "banda": 100.0 * bd / n, "k": k}


def dump(label: str, m: dict) -> None:
    w(
        f"  [{label}] n={m['n']} exacto={m['exacto']:.1f}% "
        f"banda={m['banda']:.1f}% k≈{m['k']:.1f}"
    )


def main() -> None:
    w("LAB POOL × VENTANA 3 — R1 Pool 0 (classic) live")
    w(f"ventana={VENTANA} · chips = boleto H-1 classic · CERO prod")
    w()

    horas, cinta = load_horas_y_cinta()
    mesas = precompute_mesas(cinta)
    train, hold = split_holdout(horas, HOLDOUT)
    w(f"n_horas={len(horas)} train={len(train)} hold={len(hold)}")
    w()

    for split_name, subset in [("train", train), ("holdout", hold)]:
        rows = walk_split(subset, mesas)
        v3 = [r for r in rows if r["v3"]]
        seq = [r for r in rows if not r["v3"]]
        w(f"== {split_name.upper()} ==")
        w(
            f"  G 2ª+: {len(rows)} · gap≤{VENTANA}: {len(v3)} "
            f"({100 * len(v3) / max(1, len(rows)):.1f}%) · sequía: {len(seq)}"
        )
        dump("P0-ALL", agg(rows, "p0"))
        dump("P0-V3", agg(v3, "p0"))
        dump("P0-SEQ", agg(seq, "p0"))
        dump("TIP-V3", agg(v3, "tip"))
        dump("P0∩TIP-V3", agg(v3, "p0_tip"))
        dump("P8-V3 (ref)", agg(v3, "p8"))
        if v3:
            ac = sum(1 for r in v3 if r["acuerdo"]) / len(v3)
            w(f"  acuerdo tip∩P0 en V3: {100 * ac:.1f}%")
        w()

    hold_rows = walk_split(hold, mesas)
    h_all = agg(hold_rows, "p0")
    h_v3 = agg([r for r in hold_rows if r["v3"]], "p0")
    h_seq = agg([r for r in hold_rows if not r["v3"]], "p0")
    h_tip = agg([r for r in hold_rows if r["v3"]], "tip")
    h_i = agg([r for r in hold_rows if r["v3"]], "p0_tip")
    h_p8 = agg([r for r in hold_rows if r["v3"]], "p8")

    w("== DELTA holdout vs P0-ALL ==")
    w(f"  P0-ALL banda={h_all['banda']:.1f}% exacto={h_all['exacto']:.1f}%")
    w(
        f"  P0-V3  Δbanda={h_v3['banda'] - h_all['banda']:+.1f}pp "
        f"Δexacto={h_v3['exacto'] - h_all['exacto']:+.1f}pp "
        f"cov={100 * h_v3['n'] / max(1, h_all['n']):.1f}%"
    )
    w(
        f"  P0-SEQ Δbanda={h_seq['banda'] - h_all['banda']:+.1f}pp"
    )
    w(
        f"  TIP-V3 banda={h_tip['banda']:.1f}% · "
        f"P0∩TIP-V3 banda={h_i['banda']:.1f}% · "
        f"P8-V3 banda={h_p8['banda']:.1f}%"
    )
    w()

    w("== VEREDICTO ==")
    olor = []
    if h_v3["n"] and h_v3["banda"] >= h_all["banda"] + 3:
        olor.append("P0 más puntero en gap≤3 (+≥3pp)")
    if h_v3["n"] and h_seq["n"] and h_v3["banda"] >= h_seq["banda"] + 5:
        olor.append("P0_V3 >> P0_SEQ")
    if h_tip["banda"] >= h_v3["banda"] + 1:
        olor.append("tip LC ≥ P0 en V3 (mismo oficio apostador)")
    if olor:
        w("  OLOR: " + " · ".join(olor))
    else:
        w("  SIN OLOR fuerte para reconstruir P0 con V3.")
        w("  Misma lectura que P8: ventana 3 = CUÁNDO tip, no chips P0.")
    w()

    path = OUT / "LAB_POOL_VENTANA3_R1_POOL0.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"[ok] {path}")


if __name__ == "__main__":
    main()
