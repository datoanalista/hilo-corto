# -*- coding: utf-8 -*-
"""Núcleo lab-supernova — carga horas, SN, utilidades."""
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
OJ = Path(r"c:\operacion-joker")
sys.path.insert(0, str(ROOT))

from src.lectores import cargar_ingesta  # noqa: E402

SN_SUM = 1600
SN_OLOR = 1400
CASI_LO = 1100
CASI_HI = 1599
TAG_RE = re.compile(r"^h(\d{1,2})-(\d{6})$", re.I)

# Puentes hod hold (ACTA_LUMEN_PROF — olor)
PUENTES = [
    (10, 8),
    (4, 13),
    (15, 19),
    (16, 11),
    (5, 17),
]


@dataclass
class HoraSN:
    tag: str
    hod: int
    day: str
    dt: datetime
    nG: int
    sum_g: int
    mean_g: float
    max_g: int
    n200: int
    n500: int
    is_sn: bool
    is_casi: bool
    tiros: list = field(repr=False)


def parse_dt(tag: str) -> datetime:
    m = TAG_RE.match(tag.strip())
    if not m:
        raise ValueError(tag)
    hod = int(m.group(1))
    d = m.group(2)
    return datetime(2000 + int(d[4:6]), int(d[2:4]), int(d[:2]), hod, 0, 0)


def load_horas(path: str | None = None) -> list[HoraSN]:
    cinta, _, _ = cargar_ingesta(path or "")
    out: list[HoraSN] = []
    for tag in cinta.orden:
        h = cinta.get(tag)
        gs = [t for t in (h.tiros_nucleo or []) if t.color == "G" and t.lumen is not None]
        if not gs:
            continue
        lum = [t.lumen for t in gs]
        sg = sum(lum)
        mg = sg / len(lum)
        out.append(
            HoraSN(
                tag=tag,
                hod=int(tag.split("-")[0][1:]),
                day=tag.split("-")[1],
                dt=parse_dt(tag),
                nG=len(h.nucleo),
                sum_g=sg,
                mean_g=mg,
                max_g=max(lum),
                n200=sum(1 for l in lum if l > 200),
                n500=sum(1 for l in lum if l > 500),
                is_sn=sg >= SN_SUM,
                is_casi=CASI_LO <= sg <= CASI_HI,
                tiros=list(h.tiros_nucleo or []),
            )
        )
    return out


def split_holdout(horas: list[HoraSN], holdout: int = 72):
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


def hod_profile(day_horas: list[HoraSN]) -> dict[int, float]:
    by_h = {}
    for h in day_horas:
        by_h[h.hod] = h.mean_g
    return by_h


def metrics_binary(y_true, y_pred):
    tp = sum(1 for a, p in zip(y_true, y_pred) if a and p)
    fp = sum(1 for a, p in zip(y_true, y_pred) if not a and p)
    fn = sum(1 for a, p in zip(y_true, y_pred) if a and not p)
    n = len(y_true)
    base = sum(y_true) / n if n else 0
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    return {
        "n": n,
        "base": base,
        "tp": tp,
        "fp": fp,
        "prec": prec,
        "rec": rec,
        "lift": prec / base if base else 0,
    }
