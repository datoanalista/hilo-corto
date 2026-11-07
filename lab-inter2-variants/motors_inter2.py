# -*- coding: utf-8 -*-
"""Motores INTER2 variantes — umbral, peso, P9. Sombra; no toca Pool 8 prod."""
from __future__ import annotations

from collections import Counter
from statistics import mean

from src.mesas_beta import BOLETO_IDS, acuerdo_ge2

POOL9_ID = "pool-9"


def _vote_counter(listas: list[list], weights: list[float] | None = None) -> Counter:
    cnt: Counter = Counter()
    if weights is None:
        weights = [1.0] * len(listas)
    for xs, w in zip(listas, weights):
        for c in xs or []:
            try:
                cnt[int(c)] += float(w)
            except (TypeError, ValueError):
                pass
    return cnt


def acuerdo_ge_n(listas: list[list], n: int) -> list[int]:
    cnt = _vote_counter(listas)
    return sorted(m for m, v in cnt.items() if v >= n)


def acuerdo_weighted(listas: list[list], weights: list[float], min_w: float) -> list[int]:
    cnt = _vote_counter(listas, weights)
    return sorted(m for m, v in cnt.items() if v >= min_w)


def acuerdo_cap(listas: list[list], n: int, max_k: int) -> list[int]:
    cnt = _vote_counter(listas)
    ranked = sorted(
        ((m, v) for m, v in cnt.items() if v >= n),
        key=lambda x: (-x[1], x[0]),
    )
    return sorted(m for m, _ in ranked[: max(0, max_k)])


def acuerdo_intersect(a: list[int], b: list[int]) -> list[int]:
    sa, sb = set(a or []), set(b or [])
    return sorted(sa & sb)


def chips_by_from_row(chips_map: dict[str, list[int]]) -> dict[str, list[int]]:
    return {pid: list(chips_map.get(pid) or []) for pid in BOLETO_IDS}


def listas_p0_p5(chips_map: dict[str, list[int]]) -> list[list[int]]:
    return [list(chips_map.get(pid) or []) for pid in BOLETO_IDS]


def ref_inter2(chips_map: dict[str, list[int]]) -> list[int]:
    return acuerdo_ge2(listas_p0_p5(chips_map))


def pool_train_weights(rows_train: list[dict]) -> dict[str, float]:
    """Peso por pool ∝ banda media en train (walk, no leakage en holdout)."""
    from src.tablero import score

    acc: dict[str, list[float]] = {pid: [] for pid in BOLETO_IDS}
    for row in rows_train:
        ofc = row["oficiales"]
        if len(ofc) < 2:
            continue
        n = len(ofc)
        for pid in BOLETO_IDS:
            ch = row["chips_map"].get(pid) or []
            g, pm1 = score(ch, ofc)
            acc[pid].append((g + pm1) / n)
    raw = {pid: (mean(v) if v else 0.05) for pid, v in acc.items()}
    s = sum(raw.values()) or 1.0
    # Escala a suma 6 (= nº votantes unitarios)
    return {pid: 6.0 * raw[pid] / s for pid in BOLETO_IDS}


def build_strategies(
    train_weights: dict[str, float] | None = None,
) -> dict[str, callable]:
    tw = train_weights or {pid: 1.0 for pid in BOLETO_IDS}
    w_p0x2 = [2.0 if pid == "oficial" else 1.0 for pid in BOLETO_IDS]
    w_v1x2 = [2.0 if pid == "beta-v1" else 1.0 for pid in BOLETO_IDS]
    w_p0_v1 = [
        2.0 if pid == "oficial" else (2.0 if pid == "beta-v1" else 1.0)
        for pid in BOLETO_IDS
    ]
    w_train = [tw.get(pid, 1.0) for pid in BOLETO_IDS]

    def mk(fn):
        return fn

    out: dict[str, callable] = {
        "REF-INTER2-ge2": mk(lambda cm: ref_inter2(cm)),
        # H1 — umbral / menos fichas
        "I8-ge3": mk(lambda cm: acuerdo_ge_n(listas_p0_p5(cm), 3)),
        "I8-ge4": mk(lambda cm: acuerdo_ge_n(listas_p0_p5(cm), 4)),
        "I8-ge5": mk(lambda cm: acuerdo_ge_n(listas_p0_p5(cm), 5)),
        "I8-ge2-cap8": mk(lambda cm: acuerdo_cap(listas_p0_p5(cm), 2, 8)),
        "I8-ge2-cap10": mk(lambda cm: acuerdo_cap(listas_p0_p5(cm), 2, 10)),
        "I8-ge3-cap10": mk(lambda cm: acuerdo_cap(listas_p0_p5(cm), 3, 10)),
        "I8-ge3-cap8": mk(lambda cm: acuerdo_cap(listas_p0_p5(cm), 3, 8)),
        # H2 — peso desigual
        "W-P0x2-min3": mk(
            lambda cm: acuerdo_weighted(listas_p0_p5(cm), w_p0x2, 3.0)
        ),
        "W-P0x2-min2.5": mk(
            lambda cm: acuerdo_weighted(listas_p0_p5(cm), w_p0x2, 2.5)
        ),
        "W-P0x3-min4": mk(
            lambda cm: acuerdo_weighted(
                listas_p0_p5(cm),
                [3.0 if pid == "oficial" else 1.0 for pid in BOLETO_IDS],
                4.0,
            )
        ),
        "W-V1x2-min3": mk(
            lambda cm: acuerdo_weighted(listas_p0_p5(cm), w_v1x2, 3.0)
        ),
        "W-P0+V1-min3.5": mk(
            lambda cm: acuerdo_weighted(listas_p0_p5(cm), w_p0_v1, 3.5)
        ),
        "W-TRAIN-min2": mk(
            lambda cm: acuerdo_weighted(listas_p0_p5(cm), w_train, 2.0)
        ),
        "W-TRAIN-min2.5": mk(
            lambda cm: acuerdo_weighted(listas_p0_p5(cm), w_train, 2.5)
        ),
        "W-TRAIN-min3": mk(
            lambda cm: acuerdo_weighted(listas_p0_p5(cm), w_train, 3.0)
        ),
    }

    # H3 — incluir P9
    def listas7(cm):
        p9 = list(cm.get(POOL9_ID) or cm.get("pool-9") or [])
        return listas_p0_p5(cm) + [p9]

    out.update(
        {
            "I8+P9-ge2": mk(lambda cm: acuerdo_ge_n(listas7(cm), 2)),
            "I8+P9-ge3": mk(lambda cm: acuerdo_ge_n(listas7(cm), 3)),
            "I8+P9-ge4": mk(lambda cm: acuerdo_ge_n(listas7(cm), 4)),
            "I8+P9-ge2-cap10": mk(lambda cm: acuerdo_cap(listas7(cm), 2, 10)),
            "I8∩P9": mk(
                lambda cm: acuerdo_intersect(
                    ref_inter2(cm), list(cm.get(POOL9_ID) or [])
                )
            ),
            "I8+P9-wP9half-ge2": mk(
                lambda cm: acuerdo_weighted(
                    listas_p0_p5(cm) + [list(cm.get(POOL9_ID) or [])],
                    [1.0] * 6 + [0.5],
                    2.0,
                )
            ),
        }
    )
    return out
