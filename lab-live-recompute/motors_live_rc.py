# -*- coding: utf-8 -*-
"""Motores live-recompute — prefix luces → tip/chips."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


def dist(a: int, b: int) -> int:
    d = abs(a - b) % 60
    return min(d, 60 - d)


def next_chip(chips: list[int], T: int) -> int | None:
    fut = [m for m in chips if m > T]
    return min(fut) if fut else None


def percentile(xs: list[int], p: float, fallback: int = 5) -> int:
    if not xs:
        return fallback
    ys = sorted(xs)
    idx = min(len(ys) - 1, max(0, int(len(ys) * p)))
    return ys[idx]


def pick_closest(pool: list[int], target: int) -> int | None:
    if not pool:
        return None
    return min(pool, key=lambda m: (abs(m - target), m))


def pool_window(chips_map: dict[str, list[int]], T: int, hi: int) -> list[int]:
    out: list[int] = []
    for ch in chips_map.values():
        for m in ch:
            if T < m <= hi:
                out.append(m)
    return out


def tip_reloj(T: int, gaps_hist: list[int], p: float = 0.30) -> int | None:
    if T >= 59:
        return None
    gap = percentile(gaps_hist, p)
    return min(59, max(T + 1, T + gap))


@dataclass
class StepCtx:
    T: int
    prefix: list[int]
    chips_map: dict[str, list[int]]
    inter2: list[int]
    gaps_hist: list[int]
    gaps_hora: list[int]
    nG_hora_prev: int = 10
    tag: str = ""
    mesa_scores: dict[str, float] = field(default_factory=dict)


def tip_ventana(
    ctx: StepCtx, p: float = 0.30, delta: int = 2
) -> int | None:
    gap = percentile(ctx.gaps_hist, p)
    target = min(59, ctx.T + gap)
    hi = min(59, ctx.T + gap + delta)
    pool = pool_window(ctx.chips_map, ctx.T, hi)
    return pick_closest(pool, target)


def ref_inter2_fix(ctx: StepCtx) -> int | None:
    return next_chip(ctx.inter2, ctx.T)


def ref_lc01(ctx: StepCtx) -> int | None:
    return tip_reloj(ctx.T, ctx.gaps_hist)


def rc01_trim(ctx: StepCtx) -> int | None:
    """Chips INTER2 futuros; descarta m≤T (ya pasaron o fallaron)."""
    alive = [m for m in ctx.inter2 if m > ctx.T]
    return min(alive) if alive else None


def rc02_ventana(ctx: StepCtx) -> int | None:
    return tip_ventana(ctx, 0.30, 2)


def rc03_multi24(ctx: StepCtx) -> list[int]:
    gap = percentile(ctx.gaps_hist, 0.30)
    target = min(59, ctx.T + gap)
    hi = min(59, ctx.T + gap + 2)
    pool = sorted(
        set(pool_window(ctx.chips_map, ctx.T, hi)),
        key=lambda m: (abs(m - target), m),
    )
    return pool[:3]


def rc04_multi93(ctx: StepCtx) -> list[int]:
    c = tip_reloj(ctx.T, ctx.gaps_hist)
    if c is None:
        return []
    return [x for x in (c, c + 1, c + 2) if ctx.T < x <= 59]


def rc05_acuerdo(ctx: StepCtx) -> int | None:
    nexts: list[int] = []
    for ch in ctx.chips_map.values():
        n = next_chip(ch, ctx.T)
        if n is not None:
            nexts.append(n)
    cnt = Counter(nexts)
    cands = sorted(m for m, c in cnt.items() if c >= 2)
    if not cands:
        return None
    gap = percentile(ctx.gaps_hist, 0.30)
    target = min(59, ctx.T + gap)
    return min(cands, key=lambda m: (abs(m - target), m))


def rc04_ng_live(ctx: StepCtx) -> int | None:
    """nG visto vs clima: si ritmo alto → reloj; si bajo → ventana."""
    n_seen = len(ctx.prefix)
    rate = n_seen / max(1, (ctx.T + 1) if ctx.T >= 0 else 1)
    expected_total = max(5, round(rate * 60))
    if n_seen >= expected_total * 0.85 and ctx.T >= 20:
        return tip_reloj(ctx.T, ctx.gaps_hora or ctx.gaps_hist)
    return tip_ventana(ctx, 0.30, 2)


def fermion_ok(m: int, prefix: list[int], dist_min: int = 2) -> bool:
    return all(abs(m - g) >= dist_min for g in prefix) if prefix else True


def median_int(xs: list[int], fallback: int = 5) -> int:
    if not xs:
        return fallback
    ys = sorted(xs)
    return ys[len(ys) // 2]


def clima_de(nG: int) -> str:
    if nG <= 7:
        return "floja"
    if nG >= 12:
        return "rica"
    return "normal"


def all_nexts(ctx: StepCtx) -> list[int]:
    out = []
    for ch in ctx.chips_map.values():
        n = next_chip(ch, ctx.T)
        if n is not None:
            out.append(n)
    return out


def tip_prefer_late(ctx: StepCtx, p: float, delta: int) -> int | None:
    gap = percentile(ctx.gaps_hist, p)
    target = min(59, ctx.T + gap)
    hi = min(59, ctx.T + gap + delta)
    pool = [m for m in pool_window(ctx.chips_map, ctx.T, hi) if m >= target]
    return min(pool) if pool else pick_closest(pool_window(ctx.chips_map, ctx.T, hi), target)


def tip_hibrido(ctx: StepCtx, p: float, delta: int) -> int | None:
    clock = tip_reloj(ctx.T, ctx.gaps_hist, p)
    if clock is None:
        return None
    lo = max(ctx.T + 1, clock - delta)
    hi = min(59, clock + delta)
    pool = [m for m in pool_window(ctx.chips_map, ctx.T, 59) if lo <= m <= hi]
    return pick_closest(pool, clock) if pool else clock


def tip_hibrido_ventana(ctx: StepCtx, p: float, delta: int) -> int | None:
    tip = tip_ventana(ctx, p, delta)
    return tip if tip is not None else tip_reloj(ctx.T, ctx.gaps_hist, p)


def rc_lc12(ctx: StepCtx) -> int | None:
    gap = percentile(ctx.gaps_hist, 0.30)
    r = min(59, ctx.T + gap)
    m = next_chip(ctx.chips_map.get("oficial") or [], ctx.T)
    if m is not None and abs(r - m) <= 2:
        return pick_closest([r, m], r)
    return r if r <= 59 else m


def rc_lc13(ctx: StepCtx) -> int | None:
    tips = []
    gap = percentile(ctx.gaps_hist, 0.30)
    target = min(59, ctx.T + gap)
    hi = min(59, ctx.T + gap + 2)
    for ch in ctx.chips_map.values():
        pool = [x for x in ch if ctx.T < x <= hi]
        t = pick_closest(pool, target)
        if t is not None:
            tips.append(t)
    return median_int(tips) if tips else None


def rc_lc22(ctx: StepCtx) -> int | None:
    gap = percentile(ctx.gaps_hist, 0.30)
    target = min(59, ctx.T + gap)
    hi = min(59, ctx.T + gap + 2)
    pool = [m for m in pool_window(ctx.chips_map, ctx.T, hi) if fermion_ok(m, ctx.prefix)]
    return pick_closest(pool, target)


def rc_lc31(ctx: StepCtx) -> int | None:
    if not ctx.prefix:
        n = next_chip(ctx.chips_map.get("oficial") or [], -1)
        if n is not None and n <= 10:
            return n
        return 2
    return tip_ventana(ctx, 0.30, 2)


def rc_lc48(ctx: StepCtx) -> int | None:
    best = "oficial"
    if ctx.mesa_scores:
        best = max(ctx.mesa_scores, key=lambda k: ctx.mesa_scores[k])
    return next_chip(ctx.chips_map.get(best) or [], ctx.T)


def rc_reloj_fermion(ctx: StepCtx) -> int | None:
    tip = tip_reloj(ctx.T, ctx.gaps_hist)
    if tip is None:
        return None
    if fermion_ok(tip, ctx.prefix, 2):
        return tip
    for d in (1, -1, 2, -2, 3, -3):
        cand = tip + d
        if ctx.T < cand <= 59 and fermion_ok(cand, ctx.prefix, 2):
            return cand
    return tip


def rc_multi92(ctx: StepCtx) -> list[int]:
    c = tip_reloj(ctx.T, ctx.gaps_hist)
    if c is None:
        return []
    return [x for x in (c - 1, c, c + 1) if ctx.T < x <= 59]


def make_multi_reloj_band(p: float, band: tuple[int, ...]) -> callable:
    def fn(ctx: StepCtx) -> list[int]:
        c = tip_reloj(ctx.T, ctx.gaps_hist, p)
        if c is None:
            return []
        return [x for x in (c + band[0], c + band[1], c + band[2]) if ctx.T < x <= 59]

    return fn


def make_multi_topk(p: float, delta: int, k: int = 3) -> callable:
    def fn(ctx: StepCtx) -> list[int]:
        gap = percentile(ctx.gaps_hist, p)
        target = min(59, ctx.T + gap)
        hi = min(59, ctx.T + gap + delta)
        pool = sorted(
            set(pool_window(ctx.chips_map, ctx.T, hi)),
            key=lambda m: (abs(m - target), m),
        )
        return pool[:k]

    return fn


def build_all_strategies() -> tuple[dict[str, callable], dict[str, callable]]:
    """R2 exhaustivo: singles + multis + grid ablation."""
    single = dict(SINGLE)
    multi = dict(MULTI)

    single.update(
        {
            "RC-06-HIBRIDO": lambda c: tip_hibrido(c, 0.30, 2),
            "RC-07-HIB-VEN": lambda c: tip_hibrido_ventana(c, 0.30, 2),
            "RC-08-LC12": rc_lc12,
            "RC-09-LC13": rc_lc13,
            "RC-10-LC22": rc_lc22,
            "RC-11-LC23": lambda c: tip_prefer_late(c, 0.30, 2),
            "RC-12-LC26": lambda c: tip_ventana(
                c, 0.50 if clima_de(c.nG_hora_prev) == "floja" else 0.25 if clima_de(c.nG_hora_prev) == "rica" else 0.30, 2
            ),
            "RC-13-LC31": rc_lc31,
            "RC-14-LC48": rc_lc48,
            "RC-15-RELOJ-P25": lambda c: tip_reloj(c.T, c.gaps_hist, 0.25),
            "RC-16-RELOJ-FERM": rc_reloj_fermion,
            "RC-17-ALBUM": lambda c: next_chip(c.chips_map.get("oficial") or [], c.T),
            "RC-18-VENT-P25": lambda c: tip_ventana(c, 0.25, 2),
            "RC-19-VENT-D4": lambda c: tip_ventana(c, 0.30, 4),
            "RC-20-MED-NEXTS": lambda c: median_int(all_nexts(c)) if all_nexts(c) else None,
        }
    )

    multi["RC-06-MULTI92"] = rc_multi92

    for p in (0.25, 0.30, 0.35):
        for d in (2, 3, 4):
            multi[f"RC-M24-p{int(p*100)}-d{d}"] = make_multi_topk(p, d, 3)
            single[f"RC-VEN-p{int(p*100)}-d{d}"] = lambda c, pp=p, dd=d: tip_ventana(c, pp, dd)

    for p in (0.25, 0.30, 0.35):
        multi[f"RC-M93-p{int(p*100)}"] = make_multi_reloj_band(p, (0, 1, 2))
        multi[f"RC-M92-p{int(p*100)}"] = make_multi_reloj_band(p, (-1, 0, 1))

    return single, multi


SINGLE = {
    "REF-INTER2-FIX": ref_inter2_fix,
    "REF-LC01": ref_lc01,
    "RC-01-TRIM": rc01_trim,
    "RC-02-VENTANA": rc02_ventana,
    "RC-05-ACUERDO": rc05_acuerdo,
    "RC-04-NG-LIVE": rc04_ng_live,
}

MULTI = {
    "RC-03-MULTI24": rc03_multi24,
    "RC-04-MULTI93": rc04_multi93,
}


def eval_tip(tip: int | None, nxt: int, st: Counter) -> None:
    st["pasos"] += 1
    if tip is None:
        st["silent"] += 1
        return
    st["hablo"] += 1
    if tip == nxt:
        st["exact"] += 1
    if dist(tip, nxt) <= 1:
        st["banda"] += 1


def eval_multi(tips: list[int], nxt: int, st: Counter) -> None:
    st["pasos"] += 1
    if not tips:
        st["silent"] += 1
        return
    st["hablo"] += 1
    if any(t == nxt for t in tips):
        st["exact"] += 1
    if any(dist(t, nxt) <= 1 for t in tips):
        st["banda"] += 1


def chips_lc01_accum(oficiales: list[int]) -> list[int]:
    """Chips LC-01 retrospectivo (como dashboard chipsLc01)."""
    tips: list[int] = []
    for i in range(len(oficiales)):
        prefix = oficiales[:i]
        T = prefix[-1] if prefix else -1
        gaps_hist = [prefix[k] - prefix[k - 1] for k in range(1, len(prefix))]
        t = tip_reloj(T, gaps_hist)
        if t is not None:
            tips.append(t)
    T = oficiales[-1] if oficiales else -1
    gaps_hist = [oficiales[k] - oficiales[k - 1] for k in range(1, len(oficiales))]
    t = tip_reloj(T, gaps_hist)
    if t is not None:
        tips.append(t)
    return sorted(set(tips))
