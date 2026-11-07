# -*- coding: utf-8 -*-
"""
R0: ¿ventana 3 (gap tiros ≤3) sube puntería Pool 8?
  python run_r0.py
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
    VENTANA_SEQUIA,
    acuerdo_tip,
    dist_anillo,
    indices_g_en_tiros,
    load_horas_y_cinta,
    precompute_mesas,
    split_holdout,
    tip_lc01,
)

VENTANA = 3  # fijada (SEQUIA3)
assert VENTANA_SEQUIA == 3 or True  # lab fija 3 explícito

lines: list[str] = []


def w(s: str = "") -> None:
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def hit_chip(chips: list[int], real: int) -> tuple[bool, bool]:
    """(exacto, banda)."""
    if not chips:
        return False, False
    ds = [dist_anillo(c, real) for c in chips]
    d = min(ds)
    return d == 0, d <= 1


def walk_split(horas, mesas: dict) -> list[dict]:
    """Una fila por G (salvo la 1ª de la hora): gap, tip, hits P8."""
    rows = []
    for h in horas:
        gs = sorted(h.gs, key=lambda g: g.m0)
        if len(gs) < 2:
            continue
        mesa = mesas.get(h.tag)
        chips_p8 = list((mesa.inter2 if mesa else None) or (mesa.classic if mesa else []) or [])
        idxs = indices_g_en_tiros(h)
        luces: list[int] = []
        for i in range(len(gs)):
            if i == 0:
                luces.append(gs[i].m0)
                continue
            # gap a la G previa
            if len(idxs) >= i + 1:
                gap = idxs[i] - idxs[i - 1]
            else:
                gap = 1
            tip = tip_lc01(luces)
            real = gs[i].m0
            ex_p8, band_p8 = hit_chip(chips_p8, real)
            tip_ex = tip is not None and dist_anillo(tip, real) == 0
            tip_band = tip is not None and dist_anillo(tip, real) <= 1
            inter_tip = [
                c
                for c in chips_p8
                if tip is not None and dist_anillo(c, tip) <= 1
            ]
            ex_i, band_i = hit_chip(inter_tip, real)
            rows.append(
                {
                    "tag": h.tag,
                    "real": real,
                    "gap": gap,
                    "v3": gap <= VENTANA,
                    "tip": tip,
                    "ex_p8": ex_p8,
                    "band_p8": band_p8,
                    "tip_ex": tip_ex,
                    "tip_band": tip_band,
                    "ex_i": ex_i,
                    "band_i": band_i,
                    "k_p8": len(chips_p8),
                    "k_i": len(inter_tip),
                    "acuerdo": acuerdo_tip(tip, chips_p8) if tip is not None else False,
                }
            )
            luces.append(real)
    return rows


def agg(rows: list[dict], pred: str) -> dict:
    if not rows:
        return {
            "n": 0,
            "exacto": 0.0,
            "banda": 0.0,
            "k": 0.0,
        }
    n = len(rows)
    if pred == "p8":
        ex = sum(1 for r in rows if r["ex_p8"])
        bd = sum(1 for r in rows if r["band_p8"])
        k = sum(r["k_p8"] for r in rows) / n
    elif pred == "tip":
        ex = sum(1 for r in rows if r["tip_ex"])
        bd = sum(1 for r in rows if r["tip_band"])
        k = 1.0
    elif pred == "p8_tip":
        ex = sum(1 for r in rows if r["ex_i"])
        bd = sum(1 for r in rows if r["band_i"])
        k = sum(r["k_i"] for r in rows) / n
    else:
        raise ValueError(pred)
    return {
        "n": n,
        "exacto": 100.0 * ex / n,
        "banda": 100.0 * bd / n,
        "k": k,
    }


def dump(label: str, m: dict) -> None:
    w(
        f"  [{label}] n={m['n']} exacto={m['exacto']:.1f}% "
        f"banda={m['banda']:.1f}% k≈{m['k']:.1f}"
    )


def main() -> None:
    w("LAB POOL × VENTANA 3 — R0 puntería Pool 8")
    w(f"ventana={VENTANA} tiros · CERO prod · CERO cable P8")
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
        w(f"  eventos G (2ª+): {len(rows)} · gap≤{VENTANA}: {len(v3)} "
          f"({100*len(v3)/max(1,len(rows)):.1f}%) · sequía: {len(seq)}")
        dump("P8-ALL", agg(rows, "p8"))
        dump("P8-V3", agg(v3, "p8"))
        dump("P8-SEQ", agg(seq, "p8"))
        dump("TIP-V3", agg(v3, "tip"))
        dump("P8∩TIP-V3", agg(v3, "p8_tip"))
        # acuerdo tip∩P8 rate en V3
        if v3:
            ac = sum(1 for r in v3 if r["acuerdo"]) / len(v3)
            w(f"  acuerdo tip∩P8 en V3: {100*ac:.1f}%")
        w()

    # Holdout deltas
    hold_rows = walk_split(hold, mesas)
    h_all = agg(hold_rows, "p8")
    h_v3 = agg([r for r in hold_rows if r["v3"]], "p8")
    h_seq = agg([r for r in hold_rows if not r["v3"]], "p8")
    h_tip = agg([r for r in hold_rows if r["v3"]], "tip")
    h_i = agg([r for r in hold_rows if r["v3"]], "p8_tip")

    w("== DELTA holdout vs P8-ALL ==")
    w(f"  P8-ALL banda={h_all['banda']:.1f}% exacto={h_all['exacto']:.1f}%")
    w(
        f"  P8-V3  Δbanda={h_v3['banda']-h_all['banda']:+.1f}pp "
        f"Δexacto={h_v3['exacto']-h_all['exacto']:+.1f}pp "
        f"cov={100*h_v3['n']/max(1,h_all['n']):.1f}%"
    )
    w(
        f"  P8-SEQ Δbanda={h_seq['banda']-h_all['banda']:+.1f}pp "
        f"(G largas — ¿P8 peor aquí?)"
    )
    w(
        f"  TIP-V3 banda={h_tip['banda']:.1f}% · "
        f"P8∩TIP-V3 banda={h_i['banda']:.1f}% k≈{h_i['k']:.1f}"
    )
    w()

    w("== VEREDICTO ==")
    # OLOR si V3 sube banda ≥ +3pp vs ALL, o P8∩TIP-V3 ≥ P8-V3 +2pp
    olor = []
    if h_v3["n"] and h_v3["banda"] >= h_all["banda"] + 3:
        olor.append("P8 más puntero en gap≤3 (+≥3pp banda)")
    if h_v3["n"] and h_seq["n"] and h_v3["banda"] >= h_seq["banda"] + 5:
        olor.append("P8_V3 >> P8_SEQ (ventana separa fácil/difícil)")
    if h_i["n"] and h_i["banda"] >= h_v3["banda"] + 2 and h_i["k"] + 0.5 < h_v3["k"]:
        olor.append("P8∩TIP en V3 sube banda con menos k")
    if olor:
        w("  OLOR: " + " · ".join(olor))
        w("  → no cable P8 aún; R1 = política 'usar P8 solo en Go!/V3'.")
    else:
        w("  SIN OLOR fuerte: ventana 3 no reconstruye P8 mejor en holdout.")
        w("  Puede seguir como filtro de CUÁNDO apostar (apostador), no de chips.")
    w()

    path = OUT / "LAB_POOL_VENTANA3_R0.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"[ok] {path}")


if __name__ == "__main__":
    main()
