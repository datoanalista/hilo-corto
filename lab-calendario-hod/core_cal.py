# -*- coding: utf-8 -*-
"""Núcleo lab-calendario-hod — cinta larga, sin Jaccard."""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean, median

OJ = Path(r"c:\operacion-joker")
DATA_DEFAULT = OJ / "depuracion" / "depurar-all-4G-detail.txt"
sys.path.insert(0, str(OJ / "experimento-mente-en-blanco" / "lab-piso"))
from piso_core import _cargar_indice  # noqa: E402

TAG_RE = re.compile(r"^h(\d{1,2})-(\d{6})$", re.I)
DOW_ES = ["dom", "lun", "mar", "mie", "jue", "vie", "sab"]
HOLDOUT = 72
TRAMO = [("man", 0, 7), ("tar", 8, 15), ("noc", 16, 23)]
SUM_OPACO = 450
SUM_FUERTE = 850
MEAN_OPACO = 42.0


def tramo_de(hod: int) -> str:
    for name, a, b in TRAMO:
        if a <= hod <= b:
            return name
    return "?"


@dataclass
class HoraCal:
    tag: str
    hod: int
    day: str
    dt: datetime
    dow: int  # 0=dom
    nG: int
    sum_g: int
    mean_g: float
    sum_all: int
    tramo: str = ""
    is_op: bool = False
    is_fuerte: bool = False
    mean_g_20: float | None = None
    mean_g_40: float | None = None
    nG_40: int = 0


def parse_dt(tag: str) -> datetime:
    m = TAG_RE.match(tag.strip())
    if not m:
        raise ValueError(tag)
    hod = int(m.group(1))
    d = m.group(2)
    return datetime(2000 + int(d[4:6]), int(d[2:4]), int(d[:2]), hod, 0, 0)


def mean_g_until(tiros, max_min: int | None = None):
    gs = [t for t in tiros if t.lab == "G" and t.lumen_total > 0]
    if max_min is not None:
        gs = [t for t in gs if t.m0 <= max_min]
    if len(gs) < 2:
        return None, len(gs)
    lum = [t.lumen_total for t in gs]
    return sum(lum) / len(lum), len(lum)


def load_horas(path: Path | None = None) -> list[HoraCal]:
    raw = _cargar_indice(path or DATA_DEFAULT)
    out: list[HoraCal] = []
    for tag, tiros in raw.items():
        if not TAG_RE.match(tag) or not tiros:
            continue
        gs = [t for t in tiros if t.lab == "G" and t.lumen_total > 0]
        if len(gs) < 3:
            continue
        lum = [t.lumen_total for t in gs]
        sg = sum(lum)
        mg = sg / len(lum)
        sum_all = sum(t.lumen_total for t in tiros)
        dt = parse_dt(tag)
        hod = int(tag.split("-")[0][1:])
        m20, n20 = mean_g_until(tiros, 20)
        m40, n40 = mean_g_until(tiros, 40)
        out.append(
            HoraCal(
                tag=tag,
                hod=hod,
                day=tag.split("-")[1],
                dt=dt,
                dow=(dt.weekday() + 1) % 7,
                nG=len(gs),
                sum_g=sg,
                mean_g=mg,
                sum_all=sum_all,
                tramo=tramo_de(hod),
                is_op=sg < SUM_OPACO or mg < MEAN_OPACO,
                is_fuerte=sg >= SUM_FUERTE,
                mean_g_20=m20,
                mean_g_40=m40,
                nG_40=n40,
            )
        )
    out.sort(key=lambda h: h.dt)
    return out


def split_holdout(horas: list[HoraCal], holdout: int = HOLDOUT):
    if len(horas) <= holdout:
        return horas, []
    return horas[:-holdout], horas[-holdout:]


def index_day_hod(horas: list[HoraCal]) -> dict[tuple[str, int], HoraCal]:
    return {(h.day, h.hod): h for h in horas}


def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 5 or n != len(ys):
        return None
    mx, my = mean(xs), mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    if not dx or not dy:
        return None
    return num / (dx * dy)
