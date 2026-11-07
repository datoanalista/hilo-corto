# -*- coding: utf-8 -*-
"""Nucleo lab-g-cola — G alta (>400 / >500) por bloque."""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from statistics import mean, median

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
sys.path.insert(0, str(ROOT))

from src.lectores import cargar_ingesta, leer_bloques_texto, mezclar_bloques  # noqa: E402

TAG_RE = re.compile(r"^h(\d{1,2})-(\d{6})$", re.I)
UMBRAL_ALTO = 400
UMBRAL_COLA = 500
BLOQUES = [(0, 19), (20, 39), (40, 59)]


@dataclass
class GAlta:
    m0: int
    lumen: int
    tipo: int | None
    largo: bool


@dataclass
class HoraGC:
    tag: str
    hod: int
    dt: datetime
    gs: list[GAlta] = field(default_factory=list)
    tiros: list = field(repr=False, default_factory=list)

    @property
    def n_g(self) -> int:
        return len(self.gs)

    @property
    def max_g(self) -> int:
        return max((g.lumen for g in self.gs), default=0)

    @property
    def sum_g(self) -> int:
        return sum(g.lumen for g in self.gs)

    @property
    def mean_g(self) -> float:
        return self.sum_g / self.n_g if self.n_g else 0.0

    def tiene_gt(self, umbral: int, bloque: tuple[int, int] | None = None) -> bool:
        for g in self.gs:
            if g.lumen <= umbral:
                continue
            if bloque and not (bloque[0] <= g.m0 <= bloque[1]):
                continue
            return True
        return False

    def gs_en_bloque(self, bloque: tuple[int, int]) -> list[GAlta]:
        lo, hi = bloque
        return [g for g in self.gs if lo <= g.m0 <= hi]

    def gs_gt_en_bloque(self, umbral: int, bloque: tuple[int, int]) -> list[GAlta]:
        return [g for g in self.gs_en_bloque(bloque) if g.lumen > umbral]


def parse_dt(tag: str) -> datetime:
    m = TAG_RE.match(tag.strip())
    if not m:
        raise ValueError(tag)
    hod = int(m.group(1))
    d = m.group(2)
    return datetime(2000 + int(d[4:6]), int(d[2:4]), int(d[:2]), hod, 0, 0)


def _sanitizar_extra(texto: str) -> str:
    out = []
    for ln in (texto or "").splitlines():
        s = ln.strip()
        if not s:
            out.append("")
            continue
        if "en juego" in s.lower():
            continue
        if re.match(r"^h\d{1,2}-\d{6}$", s, re.I):
            out.append(s)
            continue
        if re.match(r"^\d{1,2}:\d{2}-\d{1,2}:\d{2}\s", s):
            out.append(s)
    return "\n".join(out)


def load_horas(extra_path: Path | None = None) -> list[HoraGC]:
    extra = ""
    if extra_path and extra_path.exists():
        extra = _sanitizar_extra(
            extra_path.read_text(encoding="utf-8", errors="replace")
        )
    cinta, _, _ = cargar_ingesta(extra)
    out: list[HoraGC] = []
    for tag in cinta.orden:
        h = cinta.get(tag)
        gs: list[GAlta] = []
        for t in h.tiros_nucleo or []:
            if t.color != "G" or t.lumen is None:
                continue
            gs.append(GAlta(m0=t.m0, lumen=t.lumen, tipo=t.tipo, largo=t.largo))
        if not gs:
            continue
        out.append(
            HoraGC(
                tag=tag,
                hod=int(tag.split("-")[0][1:]),
                dt=parse_dt(tag),
                gs=gs,
                tiros=list(h.tiros_nucleo or []),
            )
        )
    return out


def estado_a_min(h: HoraGC, T: int) -> dict:
    """Tiros G cerrados hasta minuto T inclusive."""
    gs = [g for g in h.gs if g.m0 <= T]
    lum = [g.lumen for g in gs]
    acum = sum(lum)
    n = len(gs)
    mx = max(lum) if lum else 0
    mg = acum / n if n else 0.0
    n400 = sum(1 for l in lum if l > UMBRAL_ALTO)
    n500 = sum(1 for l in lum if l > UMBRAL_COLA)
    return {
        "T": T,
        "nG": n,
        "acum": acum,
        "maxG": mx,
        "meanG": mg,
        "n400": n400,
        "n500": n500,
        "gs": gs,
    }


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
        "fn": fn,
        "prec": prec,
        "rec": rec,
        "lift": prec / base if base else 0,
    }


def split_holdout(horas: list[HoraGC], holdout: int = 72):
    if len(horas) <= holdout:
        return horas, []
    return horas[:-holdout], horas[-holdout:]
