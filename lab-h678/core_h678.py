# -*- coding: utf-8 -*-
"""Nucleo lab-h678 — carga horas, perfiles, utilidades."""
from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, median

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
sys.path.insert(0, str(ROOT))

from src.lectores import cargar_ingesta  # noqa: E402

SUM_FUERTE = 850
SUM_OPACO = 450
SUM_SN = 1600
CASI_LO, CASI_HI = 1100, 1599
MEAN_OPACO = 42.0
MEAN_Q25 = 48.0
MEAN_Q75 = 74.0
ECO_MEAN_MIN = 85.0
GEN_DIA_PCT = 0.25
BLOQUE = (6, 7, 8)
TAG_RE = re.compile(r"^h(\d{1,2})-(\d{6})$", re.I)
DOW_ES = ["dom", "lun", "mar", "mie", "jue", "vie", "sab"]


@dataclass
class HoraRow:
    tag: str
    hod: int
    day: str
    dt: datetime
    dow: int
    nG: int
    sum_g: int
    mean_g: float
    max_g: int
    is_gen: bool
    is_op: bool
    is_sn: bool
    is_casi: bool
    mean_g_20: float | None
    mean_g_40: float | None
    nG_40: int
    sum_early: int
    sum_late: int
    tiros: list = field(repr=False)


def parse_dt(tag: str) -> datetime:
    m = TAG_RE.match(tag.strip())
    if not m:
        raise ValueError(tag)
    hod = int(m.group(1))
    d = m.group(2)
    return datetime(2000 + int(d[4:6]), int(d[2:4]), int(d[:2]), hod, 0, 0)


def mean_g_tiros(tiros, max_min: int | None = None):
    gs = [t for t in tiros if t.color == "G" and t.lumen is not None]
    if max_min is not None:
        gs = [t for t in gs if t.m0 <= max_min]
    if not gs:
        return None, 0
    lum = [t.lumen for t in gs]
    return sum(lum) / len(lum), len(lum)


def load_horas(path: str | None = None) -> list[HoraRow]:
    cinta, _, _ = cargar_ingesta(path or "")
    out: list[HoraRow] = []
    for tag in cinta.orden:
        h = cinta.get(tag)
        tiros = list(h.tiros_nucleo or [])
        gs = [t for t in tiros if t.color == "G" and t.lumen is not None]
        if not gs:
            continue
        lum = [t.lumen for t in gs]
        sg = sum(lum)
        mg = sg / len(lum)
        m20, n20 = mean_g_tiros(tiros, 20)
        m40, n40 = mean_g_tiros(tiros, 40)
        early = sum(t.lumen for t in gs if t.m0 <= 29)
        late = sg - early
        dt = parse_dt(tag)
        out.append(
            HoraRow(
                tag=tag,
                hod=int(tag.split("-")[0][1:]),
                day=tag.split("-")[1],
                dt=dt,
                dow=(dt.weekday() + 1) % 7,
                nG=len(gs),
                sum_g=sg,
                mean_g=mg,
                max_g=max(lum),
                is_gen=sg >= SUM_FUERTE,
                is_op=sg < SUM_OPACO or mg < MEAN_OPACO,
                is_sn=sg >= SUM_SN,
                is_casi=CASI_LO <= sg <= CASI_HI,
                mean_g_20=m20 if n20 >= 2 else None,
                mean_g_40=m40 if n40 >= 2 else None,
                nG_40=n40,
                sum_early=early,
                sum_late=late,
                tiros=tiros,
            )
        )
    return out


def split_holdout(horas: list[HoraRow], holdout: int = 72):
    if len(horas) <= holdout:
        return horas, []
    return horas[:-holdout], horas[-holdout:]


def pearson(xs, ys):
    n = len(xs)
    if n < 3 or n != len(ys):
        return None
    mx, my = mean(xs), mean(ys)
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    if not den:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den


def by_hod(horas, hod):
    return [h for h in horas if h.hod == hod]


def perfil_hod(horas, hod):
    xs = by_hod(horas, hod)
    if not xs:
        return None
    sums = sorted(h.sum_g for h in xs)
    return {
        "n": len(xs),
        "med_sum": median(sums),
        "p_gen": sum(h.is_gen for h in xs) / len(xs),
        "med_nG": median(h.nG for h in xs),
        "med_meanG": median(h.mean_g for h in xs),
        "p_op": sum(h.is_op for h in xs) / len(xs),
        "rank_med": 0,
    }


def rank_hods(horas):
    prof = {}
    for hod in range(24):
        p = perfil_hod(horas, hod)
        if p:
            prof[hod] = p
    ranked = sorted(prof.items(), key=lambda x: -x[1]["med_sum"])
    for i, (hod, p) in enumerate(ranked):
        prof[hod]["rank_med"] = i + 1
    return prof


def dias_generosos(horas, min_horas=12):
    by_day = {}
    for h in horas:
        by_day.setdefault(h.day, []).append(h)
    gen_days = set()
    for day, hs in by_day.items():
        if len(hs) < min_horas:
            continue
        if sum(x.is_gen for x in hs) / len(hs) >= GEN_DIA_PCT:
            gen_days.add(day)
    return gen_days


def costura_pairs(horas, a, b):
    by_day = {}
    for h in horas:
        by_day.setdefault(h.day, {})[h.hod] = h
    pairs = []
    for day, d in by_day.items():
        if a in d and b in d:
            pairs.append((d[a], d[b]))
    return pairs


def strata_lifts(pairs):
    lifts = [b.sum_g - a.sum_g for a, b in pairs]
    op = [b.sum_g - a.sum_g for a, b in pairs if a.sum_g < SUM_OPACO]
    no = [b.sum_g - a.sum_g for a, b in pairs if SUM_OPACO <= a.sum_g < SUM_FUERTE]
    fu = [b.sum_g - a.sum_g for a, b in pairs if a.sum_g >= SUM_FUERTE]
    return {
        "n": len(pairs),
        "lift": median(lifts) if lifts else None,
        "med_a": median([a.sum_g for a, _ in pairs]) if pairs else None,
        "med_b": median([b.sum_g for _, b in pairs]) if pairs else None,
        "op": (len(op), median(op) if op else None),
        "no": (len(no), median(no) if no else None),
        "fu": (len(fu), median(fu) if fu else None),
    }
