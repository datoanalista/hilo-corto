# -*- coding: utf-8
"""Nucleo lab-costura."""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from statistics import median

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
sys.path.insert(0, str(ROOT))

from src.lectores import cargar_ingesta  # noqa: E402

SUM_FUERTE = 850
SUM_OPACO = 450
MEAN_OPACO = 42.0
HOLDOUT = 72
TAG_RE = re.compile(r"^h(\d{1,2})-(\d{6})$", re.I)


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
    is_gen: bool
    is_op: bool
    is_sn: bool
    tiros: list = field(repr=False)


def parse_dt(tag: str) -> datetime:
    m = TAG_RE.match(tag.strip())
    if not m:
        raise ValueError(tag)
    d = m.group(2)
    return datetime(2000 + int(d[4:6]), int(d[2:4]), int(d[:2]), int(m.group(1)), 0, 0)


def load_horas(path: str | None = None) -> list[HoraRow]:
    cinta, _, _ = cargar_ingesta(path or "")
    out: list[HoraRow] = []
    for tag in cinta.orden:
        h = cinta.get(tag)
        gs = [t for t in (h.tiros_nucleo or []) if t.color == "G" and t.lumen is not None]
        if not gs:
            continue
        lum = [t.lumen for t in gs]
        sg = sum(lum)
        mg = sg / len(lum)
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
                is_gen=sg >= SUM_FUERTE,
                is_op=sg < SUM_OPACO or mg < MEAN_OPACO,
                is_sn=sg >= 1600,
                tiros=list(h.tiros_nucleo or []),
            )
        )
    return out


def split_holdout(horas: list[HoraRow], holdout: int = HOLDOUT):
    if len(horas) <= holdout:
        return horas, []
    return horas[:-holdout], horas[-holdout:]


def costura_pairs(horas, a, b):
    by_day = {}
    for h in horas:
        by_day.setdefault(h.day, {})[h.hod] = h
    return [(d[a], d[b]) for d in by_day.values() if a in d and b in d]


def strata_lifts(pairs):
    if not pairs:
        return None
    lifts = [b.sum_g - a.sum_g for a, b in pairs]
    op = [b.sum_g - a.sum_g for a, b in pairs if a.sum_g < SUM_OPACO]
    no = [b.sum_g - a.sum_g for a, b in pairs if SUM_OPACO <= a.sum_g < SUM_FUERTE]
    fu = [b.sum_g - a.sum_g for a, b in pairs if a.sum_g >= SUM_FUERTE]
    return {
        "n": len(pairs),
        "lift": median(lifts),
        "med_a": median([a.sum_g for a, _ in pairs]),
        "med_b": median([b.sum_g for _, b in pairs]),
        "op": (len(op), median(op) if op else None),
        "no": (len(no), median(no) if no else None),
        "fu": (len(fu), median(fu) if fu else None),
    }


def veredicto(signal_tr, signal_te, n_tr, n_te, min_n=5):
    if n_tr < min_n:
        return "FRIO"
    if signal_tr and signal_te and n_te >= 2:
        return "VIVE"
    if signal_tr:
        return "OLOR"
    return "FRIO"
