# -*- coding: utf-8 -*-
"""Núcleo lab-g-explosion — G extrema por bloque (INFO · no boleto)."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

LAB = Path(__file__).resolve().parent
GCOLA = LAB.parent / "lab-g-cola"
ROOT = LAB.parent
OJ = Path(r"c:\operacion-joker")
EXTRA = ROOT / "dashboard" / "extraccion" / "extraccion-en-vivo.txt"
DATA_DETAIL = OJ / "depuracion" / "depurar-all-4G-detail.txt"

sys.path.insert(0, str(GCOLA))
sys.path.insert(0, str(OJ / "experimento-mente-en-blanco" / "lab-piso"))

from core_gc import (  # noqa: E402
    BLOQUES,
    GAlta,
    HoraGC,
    estado_a_min,
    load_horas,
    metrics_binary,
    parse_dt,
    split_holdout,
)

try:
    from piso_core import _cargar_indice  # noqa: E402
except ImportError:
    _cargar_indice = None  # type: ignore

# Umbrales explorados (lumen de UNA G)
UMBRAL_TIERS = [500, 800, 1000, 1200, 1500]

B_APE = (0, 19)
B_MED = (20, 39)
B_FIN = (40, 59)


@dataclass
class ExplosionEvt:
    tag: str
    hod: int
    m0: int
    lumen: int
    tipo: int | None
    bloque: str
    idx_g: int  # ordinal G en la hora (1-based)


@dataclass
class PerfilExplosion:
    h: HoraGC
    eventos: dict[int, list[ExplosionEvt]] = field(default_factory=dict)
    st19: dict = field(default_factory=dict)
    st39: dict = field(default_factory=dict)

    def max_tier(self) -> int:
        best = 0
        for u, evs in self.eventos.items():
            if evs:
                best = max(best, u)
        return best


def bn(b: tuple[int, int]) -> str:
    return f"{b[0]}-{b[1]}"


def bloque_de(m: int) -> str:
    for lo, hi in BLOQUES:
        if lo <= m <= hi:
            return bn((lo, hi))
    return "?"


def eventos_en_hora(h: HoraGC, umbral: int) -> list[ExplosionEvt]:
    out: list[ExplosionEvt] = []
    for i, g in enumerate(h.gs, start=1):
        if g.lumen < umbral:
            continue
        out.append(
            ExplosionEvt(
                tag=h.tag,
                hod=h.hod,
                m0=g.m0,
                lumen=g.lumen,
                tipo=g.tipo,
                bloque=bloque_de(g.m0),
                idx_g=i,
            )
        )
    return out


def perfilar(horas: list[HoraGC]) -> list[PerfilExplosion]:
    out: list[PerfilExplosion] = []
    for h in horas:
        evmap = {u: eventos_en_hora(h, u) for u in UMBRAL_TIERS}
        out.append(
            PerfilExplosion(
                h=h,
                eventos=evmap,
                st19=estado_a_min(h, 19),
                st39=estado_a_min(h, 39),
            )
        )
    return out


def cola_en_bloque(h: HoraGC, umbral: int, bloque: tuple[int, int]) -> bool:
    lo, hi = bloque
    return any(lo <= g.m0 <= hi and g.lumen >= umbral for g in h.gs)


def cola_futura_en_bloque(h: HoraGC, T: int, umbral: int, bloque: tuple[int, int]) -> bool:
    """¿Hay G>=umbral en bloque después del minuto T?"""
    lo, hi = bloque
    return any(g.m0 > T and lo <= g.m0 <= hi and g.lumen >= umbral for g in h.gs)


def horas_con_tier(perfiles: list[PerfilExplosion], umbral: int) -> list[PerfilExplosion]:
    return [p for p in perfiles if p.eventos.get(umbral)]


def load_cinta_detail(path: Path | None = None, merge_live: bool = True) -> list[HoraGC]:
    """Cinta larga depurar-all-4G-detail.txt (+ live opcional para horas nuevas)."""
    path = path or DATA_DETAIL
    if not path.is_file():
        raise FileNotFoundError(path)
    if _cargar_indice is None:
        raise RuntimeError("piso_core no disponible")
    raw = _cargar_indice(path)
    tags = sorted(raw.keys(), key=lambda t: parse_dt(t))
    by_tag: dict[str, HoraGC] = {}
    for tag in tags:
        h = _hora_desde_piso(tag, raw[tag])
        if h:
            by_tag[tag.lower()] = h

    if merge_live and EXTRA.is_file():
        for h in load_horas(EXTRA):
            key = h.tag.lower()
            if key not in by_tag:
                by_tag[key] = h

    return [by_tag[k] for k in sorted(by_tag.keys(), key=lambda t: parse_dt(t))]


def _hora_desde_piso(tag: str, tiros_piso) -> HoraGC | None:
    gs: list[GAlta] = []
    tiros_adapt = []
    for t in tiros_piso or []:
        lab = getattr(t, "lab", "R")
        color = "G" if str(lab).upper().startswith("G") else "R"
        lm = int(t.lumen_total) if color == "G" else 0
        tipo = getattr(t, "tipo", None)
        m0 = int(t.m0)
        dur = int(getattr(t, "dur", 0) or 0)
        largo = bool(getattr(t, "largo", dur >= 70))
        tiros_adapt.append(
            type(
                "T",
                (),
                {
                    "color": color,
                    "m0": m0,
                    "dur_s": dur,
                    "largo": largo,
                    "tipo": tipo,
                    "lumen": lm if color == "G" else None,
                },
            )()
        )
        if color == "G" and lm > 0:
            gs.append(GAlta(m0=m0, lumen=lm, tipo=tipo, largo=largo))
    if not gs:
        return None
    return HoraGC(
        tag=tag,
        hod=int(tag.split("-")[0][1:]),
        dt=parse_dt(tag),
        gs=gs,
        tiros=tiros_adapt,
    )


def load_cinta(extra: Path | None = None) -> list[HoraGC]:
    """Default: depurar-all-4G-detail + horas live no presentes en detail."""
    return load_cinta_detail(DATA_DETAIL, merge_live=True)
