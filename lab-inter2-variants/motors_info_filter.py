# -*- coding: utf-8 -*-
"""Filtros INFO sobre chips ge2 — umbral sigue ≥2."""
from __future__ import annotations

from motors_inter2 import ref_inter2
from core_info import drop_blocks, keep_blocks


def _ge2(cm):
    return ref_inter2(cm)


def _pass(chips, fn, ctx):
    base = _ge2(ctx["chips_map"])
    if not base:
        return []
    out = fn(base, ctx)
    return sorted(set(out))


# ── H-1 (pre-hora, causal) ──

def f_h1_wrap_boost(base, ctx):
    prev = ctx.get("prev")
    if prev and prev.n_ultra_late >= 1:
        return keep_blocks(base, [(0, 9), (20, 59)])
    return base


def f_h1_sin_early_drop019(base, ctx):
    prev = ctx.get("prev")
    if prev and prev.sin_early:
        return drop_blocks(base, [(0, 19)])
    return base


def f_h1_mostly_late_4059(base, ctx):
    prev = ctx.get("prev")
    if prev and prev.mostly_late:
        return keep_blocks(base, [(40, 59)])
    return base


def f_h1_h14_sin_early(base, ctx):
    prev = ctx.get("prev")
    if prev and prev.hod == 14 and prev.sin_early:
        return keep_blocks(base, [(20, 59)])
    return base


# ── @19 cola (lab-g-cola Tier A) ──

def f_19_cola_a(base, ctx):
    st = ctx["st19"]
    if st["maxG"] >= 85 and not st["has500_0_T"]:
        return keep_blocks(base, [(20, 59)])
    return base


def f_19_cola_b(base, ctx):
    st = ctx["st19"]
    if st["maxG"] >= 85 and st["nG"] >= 2 and not st["has400_0_T"]:
        return keep_blocks(base, [(20, 39)])
    return base


def f_19_no_cola_trim2039(base, ctx):
    st = ctx["st19"]
    if not (st["maxG"] >= 85 and st["nG"] >= 2):
        return drop_blocks(base, [(20, 39)])
    return base


# ── @20 intra (lab-prohibido E3 / hora flaca) ──

def f_20_opaca_drop019(base, ctx):
    st = ctx["st20"]
    if st["nG"] <= 1 or st["meanG"] < 50:
        return drop_blocks(base, [(0, 19)])
    return base


def f_20_opaca_keep2059(base, ctx):
    st = ctx["st20"]
    if st["nG"] <= 1 or st["meanG"] < 50:
        return keep_blocks(base, [(20, 59)])
    return base


def f_20_brill_keep(base, ctx):
    st = ctx["st20"]
    if st["meanG"] >= 70 and st["nG"] >= 3:
        return base
    return drop_blocks(base, [(40, 59)])


def f_20_low_nG_late(base, ctx):
    st = ctx["st20"]
    if st["nG"] <= 2:
        return keep_blocks(base, [(30, 59)])
    return base


def f_20_high_nG_early(base, ctx):
    st = ctx["st20"]
    if st["nG"] >= 4:
        return keep_blocks(base, [(0, 39)])
    return base


# ── Combos ──

def f_19cola_then_20opaca(base, ctx):
    x = f_19_cola_a(base, ctx)
    return f_20_opaca_keep2059(x, {"st20": ctx["st20"]})


def f_h1wrap_19cola(base, ctx):
    x = f_h1_wrap_boost(base, ctx)
    return f_19_cola_a(x, ctx)


def build_info_filters() -> dict[str, callable]:
    return {
        "REF-INTER2-ge2": lambda ctx: _ge2(ctx["chips_map"]),
        "F-H1-wrap-09+20": lambda ctx: _pass(None, f_h1_wrap_boost, ctx),
        "F-H1-sinEarly-drop019": lambda ctx: _pass(None, f_h1_sin_early_drop019, ctx),
        "F-H1-late-4059": lambda ctx: _pass(None, f_h1_mostly_late_4059, ctx),
        "F-H1-h14sinG-2059": lambda ctx: _pass(None, f_h1_h14_sin_early, ctx),
        "F-@19-cola-A-2059": lambda ctx: _pass(None, f_19_cola_a, ctx),
        "F-@19-cola-B-2039": lambda ctx: _pass(None, f_19_cola_b, ctx),
        "F-@19-noCola-trim2039": lambda ctx: _pass(None, f_19_no_cola_trim2039, ctx),
        "F-@20-opaca-drop019": lambda ctx: _pass(None, f_20_opaca_drop019, ctx),
        "F-@20-opaca-2059": lambda ctx: _pass(None, f_20_opaca_keep2059, ctx),
        "F-@20-brill-trim4059": lambda ctx: _pass(None, f_20_brill_keep, ctx),
        "F-@20-lowNG-3059": lambda ctx: _pass(None, f_20_low_nG_late, ctx),
        "F-@20-highNG-039": lambda ctx: _pass(None, f_20_high_nG_early, ctx),
        "F-19cola+20opaca": lambda ctx: _pass(None, f_19cola_then_20opaca, ctx),
        "F-H1wrap+19cola": lambda ctx: _pass(None, f_h1wrap_19cola, ctx),
    }
