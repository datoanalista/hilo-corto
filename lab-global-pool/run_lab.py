# -*- coding: utf-8 -*-
"""
Lab global-pool — recomendación ir/no ir (👍/👎) agregando todos los pools.
No boleto · no pool nuevo · juez banda d≤1 sobre resto de hora (P8 prod).

  python run_lab.py
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
RZ = ROOT / "lab-ruleta-zero"
sys.path.insert(0, str(RZ))
sys.path.insert(0, str(ROOT))

from src.boleto_inter2 import precompute_beta_chips  # noqa: E402
from src.estado import PRIMERA_UTIL  # noqa: E402
from src.lectores import cargar_ingesta  # noqa: E402
from src.mesas_beta import BOLETO_IDS, acuerdo_ge2  # noqa: E402
from src.motor import dist_anillo  # noqa: E402
from src.tablero import recorrer, score  # noqa: E402
from core_rz import HOLDOUT, split_tags, tag_key  # noqa: E402

OUT = LAB / "reports"
OUT.mkdir(exist_ok=True)

# Pesos heurísticos (P8 prod > P0 > betas > P9 sombra)
WEIGHTS = {
    "inter2": 2.0,
    "oficial": 1.5,
    "live-rc": 1.2,
    "lc-01": 1.0,
    "pool-9": 0.7,
    "beta-v1": 0.85,
    "beta-v2": 0.85,
    "beta-v3": 0.85,
    "beta-v4": 0.85,
    "beta-v5": 0.85,
}


def pct(n, d) -> str:
    return f"{100 * n / d:.1f}%" if d else "—"


def pp(a, b) -> str:
    return f"{100 * (a - b):+.1f}pp"


def percentile(xs, p, fallback=5):
    if not xs:
        return fallback
    ys = sorted(xs)
    idx = min(len(ys) - 1, max(0, int(len(ys) * p)))
    return ys[idx]


def chips_live_rc(luces):
    sorted_l = sorted(set(luces or []))
    tips = set()
    for i in range(len(sorted_l) + 1):
        prefix = sorted_l[:i]
        T = prefix[-1] if prefix else -1
        gh = [prefix[k] - prefix[k - 1] for k in range(1, len(prefix))]
        if T >= 59:
            continue
        gap = percentile(gh, 0.3)
        c = min(59, max(T + 1, T + gap))
        for x in (c, c + 1, c + 2):
            if T < x <= 59:
                tips.add(x)
    return sorted(tips)


def lc_tip(luces):
    sorted_l = sorted(set(luces or []))
    gaps = [sorted_l[i] - sorted_l[i - 1] for i in range(1, len(sorted_l))]
    T = sorted_l[-1] if sorted_l else -1
    gap = percentile(gaps, 0.3)
    return min(59, max(T + 1, T + gap))


def banda_prefix(chips, prefix_ofc):
    if not prefix_ofc:
        return None
    g, pm1 = score(chips, prefix_ofc)
    return (g + pm1) / len(prefix_ofc)


def banda_rest(chips, ofc, j):
    rest = ofc[j:]
    if not rest:
        return None
    g, pm1 = score(chips, rest)
    return (g + pm1) / len(rest)


def next_chip(chips, T):
    fut = [m for m in chips if m > T]
    return min(fut) if fut else None


@dataclass
class StepCtx:
    tag: str
    j: int
    prefix: list[int]
    ofc: list[int]
    chips_map: dict[str, list[int]]
    p10: list[int]
    lc: int | None
    live: dict[str, float | None]
    T: int


def build_rows(cinta):
    rec = recorrer(cinta)
    hist = {f["for"]: f for f in rec["historico"] if f.get("for")}
    beta_by = precompute_beta_chips(cinta)
    rows = []
    for tag, f in hist.items():
        cm = {"oficial": list(f.get("chips_classic") or f.get("chips") or [])}
        ok = True
        for pid in BOLETO_IDS:
            if pid == "oficial":
                continue
            ch = (beta_by.get(tag) or {}).get(pid)
            if ch is None:
                ok = False
                break
            cm[pid] = list(ch)
        if not ok:
            continue
        inter2 = list(f.get("chips") or [])
        classic = list(f.get("chips_classic") or cm["oficial"])
        ofc = sorted(f.get("oficiales") or [])
        if len(ofc) < 3 or not inter2:
            continue
        cm["inter2"] = inter2
        cm["pool-9"] = classic
        rows.append({"tag": tag, "chips_map": cm, "ofc": ofc, "p8": inter2})
    return rows


def make_ctx(row, j):
    ofc = row["ofc"]
    prefix = ofc[:j]
    cm = row["chips_map"]
    T = prefix[-1] if prefix else -1
    p10 = chips_live_rc(prefix)
    lc = lc_tip(prefix) if prefix else None
    live = {}
    for pid, ch in cm.items():
        live[pid] = banda_prefix(ch, prefix)
    live["live-rc"] = banda_prefix(p10, prefix)
    live["lc-01"] = None  # tip-only; se usa aparte
    return StepCtx(
        tag=row["tag"],
        j=j,
        prefix=prefix,
        ofc=ofc,
        chips_map=cm,
        p10=p10,
        lc=lc,
        live=live,
        T=T,
    )


def weighted_live(ctx: StepCtx) -> float | None:
    num = den = 0.0
    for pid, w in WEIGHTS.items():
        b = ctx.live.get(pid)
        if b is None or ctx.j == 0:
            continue
        num += w * b
        den += w
    return num / den if den else None


def pools_warm(ctx: StepCtx, thr=0.5) -> int:
    return sum(1 for pid, b in ctx.live.items() if b is not None and b >= thr)


def n_blank_0019(ctx: StepCtx) -> int:
    return sum(1 for m in ctx.prefix if m < 20)


def last_k_miss_p8(ctx: StepCtx, k=2) -> bool:
    if len(ctx.prefix) < k:
        return False
    tail = ctx.prefix[-k:]
    p8 = ctx.chips_map.get("inter2") or []
    g, pm1 = score(p8, tail)
    return (g + pm1) == 0


def quorum_near_lc(ctx: StepCtx, need=5, delta=2) -> bool:
    if ctx.lc is None:
        return False
    n = 0
    for pid, ch in ctx.chips_map.items():
        nc = next_chip(ch, ctx.T)
        if nc is not None and dist_anillo(nc, ctx.lc) <= delta:
            n += 1
    if dist_anillo(ctx.lc, ctx.lc) <= delta and ctx.p10:
        n += 1
    return n >= need


# ── Estrategias: True = 👍 ir · False = 👎 plantarse ──

def strat_always(_ctx: StepCtx) -> bool:
    return True


def strat_h1_blank20(ctx: StepCtx) -> bool:
    """H1: plantate @20 si 00-19 vacío y mesa fría global."""
    if ctx.T < 20:
        return True
    if n_blank_0019(ctx) > 0:
        return True
    wl = weighted_live(ctx)
    return wl is None or wl >= 0.30


def strat_h2_warm3(ctx: StepCtx) -> bool:
    """H2: ir si ≥3 pools calientes en el prefix."""
    if ctx.j < 2:
        return True
    return pools_warm(ctx, 0.5) >= 3


def strat_h3_p8_gate(ctx: StepCtx) -> bool:
    """H3: ir si P8 prefix ≥45% o claramente > P0."""
    if ctx.j < 2:
        return True
    p8 = ctx.live.get("inter2")
    p0 = ctx.live.get("oficial")
    if p8 is None:
        return True
    if p8 >= 0.45:
        return True
    if p0 is not None and p8 >= p0 + 0.12:
        return True
    return False


def strat_h4_quorum(ctx: StepCtx) -> bool:
    """H4: ≥5 mesas apuntan cerca del tip LC."""
    if ctx.j < 1:
        return True
    return quorum_near_lc(ctx, need=5, delta=2)


def strat_h5_weighted(ctx: StepCtx) -> bool:
    """H5: media ponderada prefix ≥48%."""
    if ctx.j < 2:
        return True
    wl = weighted_live(ctx)
    return wl is None or wl >= 0.48


def strat_h6_cold_streak(ctx: StepCtx) -> bool:
    """H6: plantarse si P8 falló las últimas 2 G."""
    if ctx.j < 3:
        return True
    return not last_k_miss_p8(ctx, 2)


def strat_h7_p10_p8(ctx: StepCtx) -> bool:
    """H7: P10 y P8 prefix ambos ≥40%."""
    if ctx.j < 2:
        return True
    p8 = ctx.live.get("inter2")
    p10 = ctx.live.get("live-rc")
    if p8 is None or p10 is None:
        return True
    return p8 >= 0.40 and p10 >= 0.40


def strat_h8_combo(ctx: StepCtx) -> bool:
    """H8: combo — no plantarse salvo frío fuerte."""
    if ctx.T >= 20 and n_blank_0019(ctx) == 0 and weighted_live(ctx) is not None:
        if weighted_live(ctx) < 0.25 and last_k_miss_p8(ctx, 2):
            return False
    if ctx.j >= 3 and pools_warm(ctx, 0.45) <= 1 and last_k_miss_p8(ctx, 2):
        return False
    return True


STRATS = [
    ("ALWAYS_GO", strat_always),
    ("H1-blank@20", strat_h1_blank20),
    ("H2-warm≥3", strat_h2_warm3),
    ("H3-P8-gate", strat_h3_p8_gate),
    ("H4-quorum-LC", strat_h4_quorum),
    ("H5-weight≥48", strat_h5_weighted),
    ("H6-no-cold2", strat_h6_cold_streak),
    ("H7-P10+P8", strat_h7_p10_p8),
    ("H8-combo", strat_h8_combo),
]


@dataclass
class Eval:
    decisions: int = 0
    go: int = 0
    rest_g: int = 0
    rest_pm1: int = 0
    rest_of: int = 0
    go_banda_sum: float = 0.0
    go_banda_n: int = 0
    nogo_banda_sum: float = 0.0
    nogo_banda_n: int = 0
    correct_nogo: int = 0
    wrong_nogo: int = 0


def eval_strategy(rows, fn, prod_chips_key="inter2"):
    ev = Eval()
    for row in rows:
        ofc = row["ofc"]
        prod = row["chips_map"][prod_chips_key]
        for j in range(len(ofc)):
            if j >= len(ofc) - 1:
                continue
            ctx = make_ctx(row, j)
            go = fn(ctx)
            rest_b = banda_rest(prod, ofc, j + 1)
            if rest_b is None:
                continue
            ev.decisions += 1
            if go:
                ev.go += 1
                ev.go_banda_sum += rest_b
                ev.go_banda_n += 1
            else:
                ev.nogo_banda_sum += rest_b
                ev.nogo_banda_n += 1
                if rest_b < 0.45:
                    ev.correct_nogo += 1
                else:
                    ev.wrong_nogo += 1
            rest = ofc[j + 1 :]
            g, pm1 = score(prod, rest)
            ev.rest_g += g
            ev.rest_pm1 += pm1
            ev.rest_of += len(rest)
    return ev


def banda_block(chips, ofc, lo, hi=60):
    sub = [m for m in ofc if lo <= m < hi]
    if not sub:
        return None
    g, pm1 = score(chips, sub)
    return (g + pm1) / len(sub)


def first_j_at(ofc, cut_min):
    return next((j for j, m in enumerate(ofc) if m >= cut_min), None)


def eval_at_cut(rows, fn, cut_min):
    """Una decision/hora al cruzar cut · banda resto >= cut."""
    ev = Eval()
    for row in rows:
        ofc = row["ofc"]
        prod = row["p8"]
        j_cut = first_j_at(ofc, cut_min)
        if j_cut is None:
            continue
        rest = [m for m in ofc[j_cut:] if m >= cut_min]
        if len(rest) < 1:
            continue
        g, pm1 = score(prod, rest)
        rest_b = (g + pm1) / len(rest)
        ctx = make_ctx(row, j_cut)
        go = fn(ctx)
        ev.decisions += 1
        if go:
            ev.go += 1
            ev.go_banda_sum += rest_b
            ev.go_banda_n += 1
        else:
            ev.nogo_banda_sum += rest_b
            ev.nogo_banda_n += 1
            if rest_b < 0.45:
                ev.correct_nogo += 1
            else:
                ev.wrong_nogo += 1
    return ev


def eval_forced_skip_then(rows, fn, cut_min):
    """Fijo: no jugar antes de cut. Desde cut: paso a paso SI/NO."""
    ev = Eval()
    for row in rows:
        ofc = row["ofc"]
        prod = row["p8"]
        playing = False
        for j in range(len(ofc)):
            if j >= len(ofc) - 1:
                continue
            ctx = make_ctx(row, j)
            if ctx.T < cut_min:
                continue
            if not playing:
                playing = fn(ctx)
                if not playing:
                    continue
            rest_b = banda_rest(prod, ofc, j + 1)
            if rest_b is None:
                continue
            # solo cuenta oficiales >= cut en el resto
            rest = [m for m in ofc[j + 1 :] if m >= cut_min]
            if not rest:
                continue
            g, pm1 = score(prod, rest)
            rest_b = (g + pm1) / len(rest)
            ev.decisions += 1
            ev.go += 1
            ev.go_banda_sum += rest_b
            ev.go_banda_n += 1
            if not fn(ctx):
                playing = False
    return ev


def eval_forced_skip_once(rows, fn, cut_min):
    """Fijo: pierde bloque 0..cut-1. Una decision @cut · juega resto si SI."""
    ev = Eval()
    for row in rows:
        ofc = row["ofc"]
        prod = row["p8"]
        j_cut = first_j_at(ofc, cut_min)
        if j_cut is None:
            continue
        rest = [m for m in ofc[j_cut:] if m >= cut_min]
        if len(rest) < 1:
            continue
        g, pm1 = score(prod, rest)
        rest_b = (g + pm1) / len(rest)
        ctx = make_ctx(row, j_cut)
        go = fn(ctx)
        ev.decisions += 1
        if go:
            ev.go += 1
            ev.go_banda_sum += rest_b
            ev.go_banda_n += 1
        else:
            ev.nogo_banda_sum += rest_b
            ev.nogo_banda_n += 1
    return ev


def block_baselines(rows):
    blocks = [
        (0, 20, "00-19"),
        (20, 40, "20-39"),
        (40, 60, "40-59"),
        (0, 60, "00-59 full"),
        (20, 60, "20-59"),
        (30, 60, "30-59"),
        (40, 60, "40-59+"),
    ]
    out = []
    for lo, hi, label in blocks:
        bs = []
        ns = []
        for row in rows:
            b = banda_block(row["p8"], row["ofc"], lo, hi)
            n = sum(1 for m in row["ofc"] if lo <= m < hi)
            if b is not None and n:
                bs.append(b)
                ns.append(n)
        out.append(
            (
                label,
                mean(bs) if bs else 0,
                sum(ns) / len(rows) if rows else 0,
                sum(1 for b in bs if b >= 0.5) / len(bs) if bs else 0,
            )
        )
    return out


def strat_h4_quorum_loose(ctx):
    return quorum_near_lc(ctx, need=4, delta=2)


def strat_h4_quorum_tight(ctx):
    return quorum_near_lc(ctx, need=6, delta=2)


def strat_h4_p8_only(ctx):
    if ctx.j < 2:
        return True
    p8 = ctx.live.get("inter2")
    p10 = ctx.live.get("live-rc")
    if p8 is None:
        return True
    return p8 >= 0.50 or (p10 is not None and p10 >= 0.50 and p8 >= 0.35)


EXTRA_STRATS = [
    ("H4-quorum-4", strat_h4_quorum_loose),
    ("H4-quorum-6", strat_h4_quorum_tight),
    ("H9-P8|P10", strat_h4_p8_only),
]

ALL_STRATS = STRATS + EXTRA_STRATS
CUTS = [0, 10, 20, 30, 40, 50]


def main():
    cinta, _, _ = cargar_ingesta("")
    rows = build_rows(cinta)
    lines: list[str] = []

    def w(s=""):
        lines.append(s)
        try:
            print(s)
        except UnicodeEncodeError:
            print(s.encode("ascii", "replace").decode("ascii"))

    w("LAB GLOBAL-POOL — recomendacion SI/NO (no boleto)")
    w(f"Cinta: {len(cinta.orden)} tags · horas evaluables: {len(rows)}")
    w(f"Desde {PRIMERA_UTIL} · prod proxy = P8 INTER2 · juez banda d≤1 resto hora")
    w()

    w("=== HIPÓTESIS ===")
    w("  H1  plantate @20 si 00-19 vacío + mesa global fría (<30%)")
    w("  H2  ir si ≥3 pools con banda prefix ≥50%")
    w("  H3  ir si P8 prefix ≥45% o P8 >> P0")
    w("  H4  ir si ≥5 pools apuntan cerca tip LC (±2)")
    w("  H5  ir si media ponderada prefix ≥48%")
    w("  H6  plantarse si P8 falló últimas 2 G")
    w("  H7  ir si P10 y P8 prefix ≥40%")
    w("  H8  combo frío fuerte (blank+miss / warm≤1+miss)")
    w()

    w("=== BLOQUES FIJOS (P8 · sin señal · perder bloque = no medir ese tramo) ===")
    w(f"  {'bloque':10s}  banda P8   G/h media   horas banda>=50%")
    full_banda = None
    for label, b, n_g, hit50 in block_baselines(rows):
        if label == "00-59 full":
            full_banda = b
        w(f"  {label:10s}  {pct(b, 1):>7s}   {n_g:5.1f}       {pct(hit50, 1):>6s}")
    w()

    w("=== SWEEP CORTE @cut (1 decision/hora · resto >= cut · todas las estrategias) ===")
    w("  cut = minuto desde el cual se evalua SI/NO · resto = oficiales en [cut..59]")
    w(f"  {'cut':>4s}  {'estrategia':18s}  play%   banda@GO   lift vs full")
    sweep_cut = []
    for cut in CUTS:
        base_ev = eval_at_cut(rows, strat_always, cut)
        base_b = base_ev.go_banda_sum / base_ev.go_banda_n if base_ev.go_banda_n else 0
        for name, fn in ALL_STRATS:
            if name == "ALWAYS_GO":
                continue
            ev = eval_at_cut(rows, fn, cut)
            play = ev.go / ev.decisions if ev.decisions else 0
            b_go = ev.go_banda_sum / ev.go_banda_n if ev.go_banda_n else 0
            lift = b_go - base_b
            sweep_cut.append((cut, name, play, b_go, lift, base_b))
    sweep_cut.sort(key=lambda x: x[4], reverse=True)
    for cut, name, play, b_go, lift, base_b in sweep_cut[:20]:
        w(
            f"  @{cut:02d}  {name:18s}  {pct(play, 1):>5s}  "
            f"{pct(b_go, 1):>7s}  {pp(lift, 0):>8s}"
        )
    w()

    w("=== MEJOR @cut por estrategia (lift banda@GO vs ALWAYS@ mismo cut) ===")
    by_strat = defaultdict(list)
    for cut, name, play, b_go, lift, base_b in sweep_cut:
        by_strat[name].append((cut, play, b_go, lift))
    w(f"  {'estrategia':18s}  best@   play%   banda@GO   lift")
    for name, fn in ALL_STRATS:
        if name == "ALWAYS_GO":
            continue
        items = by_strat.get(name, [])
        if not items:
            continue
        cut, play, b_go, lift = max(items, key=lambda x: x[3])
        w(
            f"  {name:18s}  @{cut:02d}   {pct(play, 1):>5s}  "
            f"{pct(b_go, 1):>7s}  {pp(lift, 0):>8s}"
        )
    w()

    w("=== PIERDE BLOQUE + 1 decision @cut (00..cut-1 fuera · SI juega cut..59) ===")
    w(f"  {'cut':>4s}  {'estrategia':18s}  play%   banda si SI   lift vs jugar cut..59 siempre")
    skip_sweep = []
    for cut in [20, 30, 40, 50]:
        base_ev = eval_forced_skip_once(rows, strat_always, cut)
        base_b = base_ev.go_banda_sum / base_ev.go_banda_n if base_ev.go_banda_n else 0
        w(f"  --- baseline siempre-SI desde @{cut:02d}: banda {pct(base_b, 1)} ---")
        for name, fn in ALL_STRATS:
            if name == "ALWAYS_GO":
                continue
            ev = eval_forced_skip_once(rows, fn, cut)
            play = ev.go / ev.decisions if ev.decisions else 0
            b_go = ev.go_banda_sum / ev.go_banda_n if ev.go_banda_n else 0
            lift = b_go - base_b
            skip_sweep.append((cut, name, play, b_go, lift, base_b))
            if lift >= 0.5 / 100:  # >= 0.5pp
                w(
                    f"  @{cut:02d}  {name:18s}  {pct(play, 1):>5s}  "
                    f"{pct(b_go, 1):>7s}  {pp(lift, 0):>8s}"
                )
    skip_sweep.sort(key=lambda x: x[4], reverse=True)
    w()
    w("  Top 8 pierde-bloque:")
    for cut, name, play, b_go, lift, base_b in skip_sweep[:8]:
        w(
            f"    @{cut:02d} {name:18s}  play={pct(play,1)}  "
            f"banda@GO={pct(b_go,1)}  lift={pp(lift,0)}  (base@{cut}={pct(base_b,1)})"
        )
    w()

    w("=== MATRIZ lift @cut x H4-quorum (celda = lift pp vs always@cut) ===")
    w(f"  {'cut':>4s}  " + "  ".join(f"@{c:02d}" for c in CUTS))
    for name in ["H4-quorum-LC", "H4-quorum-4", "H4-quorum-6", "H3-P8-gate", "H7-P10+P8"]:
        cells = []
        for cut in CUTS:
            base_ev = eval_at_cut(rows, strat_always, cut)
            base_b = base_ev.go_banda_sum / base_ev.go_banda_n if base_ev.go_banda_n else 0
            fn = dict(ALL_STRATS)[name]
            ev = eval_at_cut(rows, fn, cut)
            b_go = ev.go_banda_sum / ev.go_banda_n if ev.go_banda_n else 0
            lift = 100 * (b_go - base_b)
            cells.append(f"{lift:+4.1f}")
        w(f"  {name:16s}  " + "  ".join(cells))
    w()

    w("=== PASO A PASO (cada G → resto de hora) ===")
    w(f"  {'estrategia':18s}  play%   banda@GO   banda@NO   lift@GO   NO-GO ok")
    results = []
    base_banda = None
    for name, fn in STRATS:
        ev = eval_strategy(rows, fn)
        play = ev.go / ev.decisions if ev.decisions else 0
        b_go = ev.go_banda_sum / ev.go_banda_n if ev.go_banda_n else 0
        b_no = ev.nogo_banda_sum / ev.nogo_banda_n if ev.nogo_banda_n else 0
        if name == "ALWAYS_GO":
            base_banda = b_go
        lift = b_go - base_banda if base_banda is not None and name != "ALWAYS_GO" else 0
        nogo_ok = (
            pct(ev.correct_nogo, ev.correct_nogo + ev.wrong_nogo)
            if (ev.correct_nogo + ev.wrong_nogo)
            else "—"
        )
        w(
            f"  {name:18s}  {pct(ev.go, ev.decisions):>5s}  "
            f"{pct(b_go, 1):>7s}  {pct(b_no, 1):>7s}  "
            f"{pp(b_go, base_banda) if name != 'ALWAYS_GO' else '  base':>8s}  {nogo_ok:>7s}"
        )
        results.append((name, play, b_go, b_no, lift, ev))
    w()

    w("=== CORTE @20 (una decision/hora · resto 20-59) ===")
    w(f"  {'estrategia':18s}  play%   banda@GO   banda@NO   lift@GO")
    base20 = None
    for name, fn in ALL_STRATS:
        ev = eval_at_cut(rows, fn, 20)
        play = ev.go / ev.decisions if ev.decisions else 0
        b_go = ev.go_banda_sum / ev.go_banda_n if ev.go_banda_n else 0
        b_no = ev.nogo_banda_sum / ev.nogo_banda_n if ev.nogo_banda_n else 0
        if name == "ALWAYS_GO":
            base20 = b_go
        lift = b_go - base20 if base20 is not None and name != "ALWAYS_GO" else 0
        w(
            f"  {name:18s}  {pct(ev.go, ev.decisions):>5s}  "
            f"{pct(b_go, 1):>7s}  {pct(b_no, 1):>7s}  "
            f"{pp(b_go, base20) if name != 'ALWAYS_GO' else '  base':>8s}"
        )
    w()

    # Mejor candidato por lift@GO con play≥60%
    cands = [
        (name, b_go, play, lift)
        for name, play, b_go, b_no, lift, ev in results
        if name != "ALWAYS_GO" and play >= 0.55
    ]
    cands.sort(key=lambda x: x[3], reverse=True)
    w("=== CANDIDATOS UI (play≥55% · lift banda@GO) ===")
    for name, b_go, play, lift in cands[:5]:
        w(f"  {name:18s}  play={pct(play,1)}  banda@GO={pct(b_go,1)}  lift={pp(lift,0)}")
    w()

    best = max(sweep_cut, key=lambda x: x[4]) if sweep_cut else None
    best_skip = max(skip_sweep, key=lambda x: x[4]) if skip_sweep else None
    w("=== VEREDICTO VENTANAS ===")
    if full_banda is not None:
        w(f"  Hora completa P8: {pct(full_banda, 1)}")
    for label, b, n_g, hit50 in block_baselines(rows):
        if label in ("20-59", "30-59", "40-59+"):
            w(f"  Bloque fijo {label}: {pct(b, 1)} (pierdes el tramo anterior)")
    if best:
        cut, name, play, b_go, lift, base_b = best
        w(
            f"  Mejor 1-shot @cut: @{cut:02d} {name}  "
            f"play={pct(play,1)} banda={pct(b_go,1)} lift={pp(lift,0)}"
        )
    if best_skip:
        cut, name, play, b_go, lift, base_b = best_skip
        w(
            f"  Mejor pierde-bloque: @{cut:02d} {name}  "
            f"play={pct(play,1)} banda={pct(b_go,1)} lift={pp(lift,0)} vs siempre@{cut}"
        )
    w()

    w("=== LECTURA ===")
    w("  · ALWAYS_GO = baseline (seguir siempre).")
    w("  · banda@GO > baseline = filtrar NO-GO mejoró lo que queda.")
    w("  · banda@NO < banda@GO = el NO acierta (resto era peor).")
    w("  · NO-GO ok = % veces que al plantarse el resto era <45%.")
    w()
    w("INFO sombra. No boleto LIVE. Siguiente: cablear SI/NO en barra live.")

    (OUT / "LAB_GLOBAL_POOL.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"\n→ {OUT / 'LAB_GLOBAL_POOL.txt'}")


def split_rows(rows):
    tags = sorted({r["tag"] for r in rows}, key=tag_key)
    train_tags, hold_tags = split_tags(tags)
    train_set = set(train_tags)
    hold_set = set(hold_tags)
    train = [r for r in rows if r["tag"] in train_set]
    hold = [r for r in rows if r["tag"] in hold_set]
    return train, hold, train_tags, hold_tags


def eval_config(rows, cut, name):
    fn = dict(ALL_STRATS)[name]
    base_ev = eval_at_cut(rows, strat_always, cut)
    ev = eval_at_cut(rows, fn, cut)
    base_b = base_ev.go_banda_sum / base_ev.go_banda_n if base_ev.go_banda_n else 0
    b_go = ev.go_banda_sum / ev.go_banda_n if ev.go_banda_n else 0
    play = ev.go / ev.decisions if ev.decisions else 0
    return {
        "cut": cut,
        "name": name,
        "play": play,
        "b_go": b_go,
        "base_b": base_b,
        "lift": b_go - base_b,
        "decisions": ev.decisions,
        "go": ev.go,
    }


def sweep_train(rows):
    out = []
    for cut in CUTS:
        base_ev = eval_at_cut(rows, strat_always, cut)
        base_b = base_ev.go_banda_sum / base_ev.go_banda_n if base_ev.go_banda_n else 0
        for name, fn in ALL_STRATS:
            if name == "ALWAYS_GO":
                continue
            ev = eval_at_cut(rows, fn, cut)
            b_go = ev.go_banda_sum / ev.go_banda_n if ev.go_banda_n else 0
            out.append(
                {
                    "cut": cut,
                    "name": name,
                    "play": ev.go / ev.decisions if ev.decisions else 0,
                    "b_go": b_go,
                    "lift": b_go - base_b,
                    "decisions": ev.decisions,
                    "go": ev.go,
                }
            )
    out.sort(key=lambda x: x["lift"], reverse=True)
    return out


def run_holdout():
    cinta, _, _ = cargar_ingesta("")
    rows = build_rows(cinta)
    train, hold, train_tags, hold_tags = split_rows(rows)
    lines: list[str] = []

    def w(s=""):
        lines.append(s)
        try:
            print(s)
        except UnicodeEncodeError:
            print(s.encode("ascii", "replace").decode("ascii"))

    w("LAB GLOBAL-POOL — HOLDOUT 72h")
    w(f"Train: {len(train)} h · Holdout: {len(hold)} h (ultimas {HOLDOUT})")
    if hold_tags:
        w(f"Holdout: {hold_tags[0]} .. {hold_tags[-1]}")
    w("Reglas fijadas en train · sin re-tune en holdout")
    w()

    train_sweep = sweep_train(train)
    w("=== TOP 10 TRAIN ===")
    w(f"  {'cut':>4s}  {'estrategia':18s}  play%   banda@GO   lift")
    for r in train_sweep[:10]:
        w(
            f"  @{r['cut']:02d}  {r['name']:18s}  "
            f"{pct(r['go'], r['decisions']):>5s}  {pct(r['b_go'], 1):>7s}  {pp(r['lift'], 0):>8s}"
        )
    w()

    fixed = []
    seen = set()
    for r in train_sweep[:5]:
        k = (r["cut"], r["name"])
        if k not in seen:
            fixed.append(k)
            seen.add(k)
    for k in [(40, "H4-quorum-6"), (50, "H4-quorum-6"), (40, "H4-quorum-LC"), (50, "H4-quorum-LC")]:
        if k not in seen:
            fixed.append(k)
            seen.add(k)

    w("=== TRAIN vs HOLDOUT ===")
    w(f"  {'cut':>4s}  {'estrategia':18s}  train lift  hold lift  hold play  hold banda")
    results = []
    for cut, name in fixed:
        tr = eval_config(train, cut, name)
        ho = eval_config(hold, cut, name)
        results.append((cut, name, tr, ho))
        w(
            f"  @{cut:02d}  {name:18s}  "
            f"{pp(tr['lift'], 0):>8s}  {pp(ho['lift'], 0):>8s}  "
            f"{pct(ho['go'], ho['decisions']):>7s}  {pct(ho['b_go'], 1):>7s}"
        )
    w()

    w("=== HOLDOUT baseline siempre-SI ===")
    for cut in [20, 30, 40, 50]:
        ho = eval_config(hold, cut, "ALWAYS_GO")
        w(f"  @{cut:02d}  banda={pct(ho['b_go'], 1)}  n={ho['decisions']}")
    w()

    w("=== HOLDOUT pierde-bloque @cut ===")
    skip_results = []
    for cut in [30, 40, 50]:
        base_ev = eval_forced_skip_once(hold, strat_always, cut)
        base_b = base_ev.go_banda_sum / base_ev.go_banda_n if base_ev.go_banda_n else 0
        for name in ["H4-quorum-6", "H4-quorum-LC", "H4-quorum-4"]:
            fn = dict(ALL_STRATS)[name]
            ev = eval_forced_skip_once(hold, fn, cut)
            play = ev.go / ev.decisions if ev.decisions else 0
            b_go = ev.go_banda_sum / ev.go_banda_n if ev.go_banda_n else 0
            lift = b_go - base_b
            skip_results.append((cut, name, play, b_go, lift))
            w(
                f"  @{cut:02d}  {name:18s}  play={pct(play,1)}  "
                f"banda={pct(b_go,1)}  lift={pp(lift,0)}"
            )
    w()

    best_hold = max(results, key=lambda x: x[3]["lift"]) if results else None
    best_skip = max(skip_results, key=lambda x: x[4]) if skip_results else None
    w("=== VEREDICTO HOLDOUT ===")
    if train_sweep:
        t0 = train_sweep[0]
        w(f"  Mejor train: @{t0['cut']:02d} {t0['name']}  lift={pp(t0['lift'], 0)}")
    if best_hold:
        cut, name, tr, ho = best_hold
        w(
            f"  Mejor holdout 1-shot: @{cut:02d} {name}  "
            f"lift={pp(ho['lift'], 0)}  play={pct(ho['go'], ho['decisions'])}  "
            f"banda={pct(ho['b_go'], 1)}  (train {pp(tr['lift'], 0)})"
        )
    if best_skip:
        cut, name, play, b_go, lift = best_skip
        w(
            f"  Mejor holdout pierde-bloque: @{cut:02d} {name}  "
            f"lift={pp(lift, 0)}  play={pct(play,1)}  banda={pct(b_go,1)}"
        )
    if best_hold and best_hold[3]["lift"] > 0:
        w("  OK: lift positivo en 72h ciegas.")
    elif best_hold:
        w("  FRIO: lift no se sostiene en holdout.")
    w()
    w("INFO sombra. No boleto LIVE.")

    path = OUT / "LAB_GLOBAL_POOL_HOLDOUT.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"-> {path}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "holdout":
        run_holdout()
    else:
        main()
