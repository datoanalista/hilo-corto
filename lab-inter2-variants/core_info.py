# -*- coding: utf-8 -*-
"""Señales INFO para filtrar ge2 — cola @19, intra @20, H-1."""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
sys.path.insert(0, str(ROOT))

from src.lectores import cinta_desde_bloques, leer_bloques_texto  # noqa: E402

TAG_RE = re.compile(r"^h(\d{1,2})-(\d{6})$", re.I)
UMBRAL_COLA = 500
UMBRAL_ALTO = 400


@dataclass
class GShot:
    m0: int
    lumen: int


@dataclass
class HoraInfo:
    tag: str
    hod: int
    gs: list[GShot] = field(default_factory=list)

    def estado(self, T: int) -> dict:
        gs = [g for g in self.gs if g.m0 <= T]
        lum = [g.lumen for g in gs]
        acum = sum(lum)
        n = len(gs)
        mx = max(lum) if lum else 0
        mg = acum / n if n else 0.0
        return {
            "T": T,
            "nG": n,
            "acum": acum,
            "maxG": mx,
            "meanG": mg,
            "n400": sum(1 for l in lum if l > UMBRAL_ALTO),
            "n500": sum(1 for l in lum if l > UMBRAL_COLA),
            "has400_0_T": any(g.lumen > UMBRAL_ALTO and g.m0 <= T for g in gs),
            "has500_0_T": any(g.lumen > UMBRAL_COLA and g.m0 <= T for g in gs),
        }

    @property
    def sin_early(self) -> bool:
        return not any(g.m0 <= 9 for g in self.gs)

    @property
    def n_ultra_late(self) -> int:
        return sum(1 for g in self.gs if g.m0 >= 58)

    @property
    def mostly_late(self) -> bool:
        early = sum(1 for g in self.gs if g.m0 <= 9)
        late = sum(1 for g in self.gs if g.m0 >= 50)
        return late > early * 1.5 and late >= 2


def load_horas_detail(path: Path) -> dict[str, HoraInfo]:
    orden, bloques = leer_bloques_texto(path.read_text(encoding="utf-8"))
    cinta, _ = cinta_desde_bloques(orden, bloques)
    out: dict[str, HoraInfo] = {}
    for tag in cinta.orden:
        h = cinta.get(tag)
        gs = []
        for t in h.tiros_nucleo or []:
            if t.color != "G" or t.lumen is None:
                continue
            gs.append(GShot(m0=t.m0, lumen=int(t.lumen)))
        if not gs:
            continue
        out[tag.lower()] = HoraInfo(
            tag=tag.lower(),
            hod=int(tag.split("-")[0][1:]),
            gs=gs,
        )
    return out


def parse_dt(tag: str) -> datetime:
    m = TAG_RE.match(tag.strip())
    if not m:
        raise ValueError(tag)
    d = m.group(2)
    return datetime(2000 + int(d[4:6]), int(d[2:4]), int(d[:2]), int(m.group(1)), 0, 0)


def prev_tag(tag: str, horas: dict[str, HoraInfo]) -> HoraInfo | None:
    keys = sorted(horas.keys(), key=lambda t: parse_dt(t))
    tags = [t.lower() for t in keys]
    try:
        i = tags.index(tag.lower())
    except ValueError:
        return None
    if i <= 0:
        return None
    return horas.get(tags[i - 1])


def in_range(m: int, lo: int, hi: int) -> bool:
    return lo <= m <= hi

def keep_blocks(chips: list[int], blocks: list[tuple[int, int]]) -> list[int]:
    return sorted(c for c in chips if any(in_range(c, lo, hi) for lo, hi in blocks))

def drop_blocks(chips: list[int], blocks: list[tuple[int, int]]) -> list[int]:
    return sorted(
        c for c in chips if not any(in_range(c, lo, hi) for lo, hi in blocks)
    )
