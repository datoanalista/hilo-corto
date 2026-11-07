# -*- coding: utf-8 -*-
"""
R2: boleto diseñado desde histórico de G con gap≤3 (causal).
  ¿Sube banda vs P0 classic / hist-all?
  python run_r2_hist_v3.py
Cero prod.
"""
from __future__ import annotations

import sys
from collections import Counter
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
    dist_anillo,
    indices_g_en_tiros,
    load_horas_y_cinta,
    precompute_mesas,
    tip_lc01,
)

VENTANA = 3
LOOKBACK = 80  # horas hacia atrás (misma forma que HIST_WALK beta)
K_P0 = 9  # tope típico P0; también medimos k libre top-freq

lines: list[str] = []


def w(s: str = "") -> None:
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def g_events(h) -> list[tuple[int, int]]:
    """[(m0, gap_desde_prev)]. 1ª G de la hora: gap=None→omit gap filter as 1."""
    gs = sorted(h.gs, key=lambda g: g.m0)
    idxs = indices_g_en_tiros(h)
    out = []
    for i, g in enumerate(gs):
        if i == 0:
            out.append((g.m0, 1))  # ancla: cuenta como "corta" mínima
            continue
        if len(idxs) >= i + 1:
            gap = idxs[i] - idxs[i - 1]
        else:
            gap = 1
        out.append((g.m0, gap))
    return out


def hist_chips(
    past_horas: list,
    *,
    solo_v3: bool,
    k: int | None,
    min_count: int = 1,
) -> list[int]:
    """Minutos más frecuentes en el histórico (causal)."""
    cnt: Counter[int] = Counter()
    for h in past_horas:
        for m0, gap in g_events(h):
            if solo_v3 and gap > VENTANA:
                continue
            cnt[m0 % 60] += 1
    if not cnt:
        return []
    items = [(m, c) for m, c in cnt.items() if c >= min_count]
    items.sort(key=lambda x: (-x[1], x[0]))
    if k is not None:
        items = items[:k]
    return sorted(m for m, _ in items)


def hit(chips: list[int], real: int) -> tuple[bool, bool]:
    if not chips:
        return False, False
    d = min(dist_anillo(c, real) for c in chips)
    return d == 0, d <= 1


def score_hour(chips: list[int], oficiales: list[int]) -> dict:
    if not oficiales:
        return {"n": 0, "ex": 0, "bd": 0, "k": len(chips)}
    ex = bd = 0
    for m in oficiales:
        e, b = hit(chips, m)
        ex += int(e)
        bd += int(b)
    n = len(oficiales)
    return {
        "n": n,
        "ex": ex,
        "bd": bd,
        "exacto": 100.0 * ex / n,
        "banda": 100.0 * bd / n,
        "k": len(chips),
    }


def merge_scores(xs: list[dict]) -> dict:
    n = sum(x["n"] for x in xs)
    if not n:
        return {"n": 0, "exacto": 0.0, "banda": 0.0, "k": 0.0, "horas": 0}
    ex = sum(x["ex"] for x in xs)
    bd = sum(x["bd"] for x in xs)
    return {
        "n": n,
        "exacto": 100.0 * ex / n,
        "banda": 100.0 * bd / n,
        "k": sum(x["k"] for x in xs) / len(xs),
        "horas": len(xs),
    }


def dump(label: str, m: dict) -> None:
    w(
        f"  [{label}] horas={m['horas']} G={m['n']} "
        f"exacto={m['exacto']:.1f}% banda={m['banda']:.1f}% k≈{m['k']:.1f}"
    )


def main() -> None:
    w("LAB POOL × VENTANA 3 — R2 boleto desde histórico V3")
    w(
        f"diseño: freq minutos de G con gap≤{VENTANA} en lookback={LOOKBACK}h "
        f"(causal) · CERO prod"
    )
    w()

    horas, cinta = load_horas_y_cinta()
    mesas = precompute_mesas(cinta)
    # orden causal = orden de cinta / aparición
    # load_cinta de core_ex suele venir cronológico
    n = len(horas)
    hold_n = min(HOLDOUT, max(0, n - LOOKBACK - 10))
    i_hold0 = n - hold_n
    w(f"n_horas={n} lookback={LOOKBACK} hold={hold_n} (desde idx {i_hold0})")
    w()

    # Acumuladores por política
    pols = [
        "P0",
        "P8",
        "HIST-ALL-k9",
        "HIST-V3-k9",
        "HIST-V3-k14",
        "HIST-V3-top20",
        "HIST-ALL-top20",
        "TIP",
    ]
    bucket_all: dict[str, list] = {p: [] for p in pols}
    bucket_v3g: dict[str, list] = {p: [] for p in pols}  # solo G gap≤3 de la hora

    for i in range(LOOKBACK, n):
        h = horas[i]
        past = horas[max(0, i - LOOKBACK) : i]
        mesa = mesas.get(h.tag)
        p0 = list((mesa.classic if mesa else None) or [])
        p8 = list((mesa.inter2 if mesa else None) or p0 or [])
        hist_all_k9 = hist_chips(past, solo_v3=False, k=K_P0)
        hist_v3_k9 = hist_chips(past, solo_v3=True, k=K_P0)
        hist_v3_k14 = hist_chips(past, solo_v3=True, k=14)
        hist_v3_t20 = hist_chips(past, solo_v3=True, k=20)
        hist_all_t20 = hist_chips(past, solo_v3=False, k=20)

        events = g_events(h)
        ofc_all = [m for m, _ in events]
        ofc_v3 = [m for m, g in events if g <= VENTANA]
        if len(ofc_all) < 1:
            continue

        # tip LC walk (última tip de la hora ≈ tip tras todas menos última)
        luces = []
        tip_hits_all = {"n": 0, "ex": 0, "bd": 0, "k": 1}
        tip_hits_v3 = {"n": 0, "ex": 0, "bd": 0, "k": 1}
        for j, (real, gap) in enumerate(events):
            if j == 0:
                luces.append(real)
                continue
            tip = tip_lc01(luces)
            e, b = (False, False) if tip is None else hit([tip], real)
            tip_hits_all["n"] += 1
            tip_hits_all["ex"] += int(e)
            tip_hits_all["bd"] += int(b)
            if gap <= VENTANA:
                tip_hits_v3["n"] += 1
                tip_hits_v3["ex"] += int(e)
                tip_hits_v3["bd"] += int(b)
            luces.append(real)
        for d in (tip_hits_all, tip_hits_v3):
            if d["n"]:
                d["exacto"] = 100.0 * d["ex"] / d["n"]
                d["banda"] = 100.0 * d["bd"] / d["n"]
            else:
                d["exacto"] = d["banda"] = 0.0

        chips_map = {
            "P0": p0,
            "P8": p8,
            "HIST-ALL-k9": hist_all_k9,
            "HIST-V3-k9": hist_v3_k9,
            "HIST-V3-k14": hist_v3_k14,
            "HIST-V3-top20": hist_v3_t20,
            "HIST-ALL-top20": hist_all_t20,
        }

        in_hold = i >= i_hold0
        if not in_hold:
            continue

        for name, chips in chips_map.items():
            bucket_all[name].append(score_hour(chips, ofc_all))
            if ofc_v3:
                bucket_v3g[name].append(score_hour(chips, ofc_v3))
        if tip_hits_all["n"]:
            bucket_all["TIP"].append(tip_hits_all)
        if tip_hits_v3["n"]:
            bucket_v3g["TIP"].append(tip_hits_v3)

    w("== HOLDOUT · juez = todas las G de la hora ==")
    hold_m = {}
    for p in pols:
        m = merge_scores(bucket_all[p])
        hold_m[p] = m
        dump(p, m)
    w()
    w("== HOLDOUT · juez = solo G gap≤3 de la hora ==")
    for p in pols:
        dump(p, merge_scores(bucket_v3g[p]))
    w()

    base = hold_m.get("P0") or {}
    bb = float(base.get("banda") or 0)
    w("== DELTA vs P0 (juez todas las G) ==")
    for p in pols:
        if p == "P0":
            continue
        m = hold_m[p]
        w(
            f"  {p}: Δbanda={m['banda']-bb:+.1f}pp "
            f"banda={m['banda']:.1f}% exacto={m['exacto']:.1f}% k≈{m['k']:.1f}"
        )
    w()

    w("== VEREDICTO ==")
    winners = []
    for p in ("HIST-V3-k9", "HIST-V3-k14", "HIST-V3-top20"):
        m = hold_m[p]
        if m["banda"] >= bb + 3:
            winners.append(f"{p} (+{m['banda']-bb:.1f}pp vs P0)")
        # también vs HIST-ALL mismo k
    ha = hold_m["HIST-ALL-k9"]["banda"]
    hv = hold_m["HIST-V3-k9"]["banda"]
    if hv >= ha + 2:
        winners.append(f"HIST-V3-k9 > HIST-ALL-k9 (+{hv-ha:.1f}pp)")
    elif ha >= hv + 2:
        winners.append(f"HIST-ALL-k9 ≥ HIST-V3-k9 (V3 no aporta al diseño freq)")

    if winners and any("vs P0" in x for x in winners):
        w("  OLOR diseño: " + " · ".join(winners))
        w("  → candidato sombra; no cable P0 sin OK.")
    elif winners:
        w("  LECTURA: " + " · ".join(winners))
        w("  Filtro V3 en el histograma no gana claro a hist-all.")
    else:
        w("  FRÍO: boleto freq-histórico V3 no supera P0 (+≥3pp) en holdout.")
    w("  Tip LC sigue siendo otro oficio (no es boleto de k fichas).")
    w()

    path = OUT / "LAB_POOL_VENTANA3_R2_HIST.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"[ok] {path}")


if __name__ == "__main__":
    main()
