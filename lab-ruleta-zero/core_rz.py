# -*- coding: utf-8 -*-
"""Núcleo lab-ruleta-zero — ruleta 54 vs prod."""
from __future__ import annotations

import random
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import median

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
OJ = Path(r"c:\operacion-joker")
DETAIL = OJ / "depuracion" / "depurar-all-4G-detail.txt"
LIGHTGREEN = OJ / "depuracion" / "data_all_lightgreen.txt"
PISO = OJ / "experimento-mente-en-blanco" / "lab-piso"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PISO))

from src.estado import PRIMERA_UTIL  # noqa: E402
from src.lectores import cinta_desde_bloques, leer_bloques_texto  # noqa: E402
from src.motor import dist_anillo  # noqa: E402
from src.tablero import recorrer, score  # noqa: E402

from piso_core import _cargar_indice  # noqa: E402

LETRAS = ["R1", "R2", "R3", "R4", "G1", "G2", "G3", "G4"]
HOLDOUT = 72

# Forma imagen humana (ejemplo usuario)
WHEEL_HUMAN = {
    "R1": 21,
    "R2": 13,
    "R3": 7,
    "R4": 4,
    "G1": 3,
    "G2": 2,
    "G3": 3,
    "G4": 1,
}

# Ajuste frecuencia empírica (looking1)
WHEEL_EMP = {
    "R1": 21,
    "R2": 13,
    "R3": 7,
    "R4": 4,
    "G1": 2,
    "G2": 3,
    "G3": 3,
    "G4": 1,
}

P_G_WHEEL = 9 / 54


def tag_key(tag: str) -> tuple:
    cuerpo = tag[1:]
    hora_s, ddmmyy = cuerpo.split("-")
    return (
        2000 + int(ddmmyy[4:6]),
        int(ddmmyy[2:4]),
        int(ddmmyy[0:2]),
        int(hora_s),
    )


def slots_to_probs(slots: dict[str, int]) -> dict[str, float]:
    total = sum(slots.values())
    return {k: slots[k] / total for k in slots}


def letter_log_loss(probs: dict[str, float], actual: str) -> float:
    import math

    p = probs.get(actual, 1e-12)
    return -math.log(p)


def pick_minutes_uniform(tag: str, k: int) -> list[int]:
    if k <= 0:
        return []
    rng = random.Random(hash(tag.lower()) & 0xFFFFFFFF)
    pool = list(range(60))
    rng.shuffle(pool)
    return sorted(pool[: min(k, 60)])


def banda_score(chips: list[int], oficiales: list[int]) -> dict:
    if not oficiales:
        return {"banda": None, "g": 0, "pm1": 0, "n": 0, "hit": False}
    g, pm1 = score(chips, oficiales)
    n = len(oficiales)
    return {
        "banda": (g + pm1) / n,
        "g": g,
        "pm1": pm1,
        "n": n,
        "hit": (g + pm1) > 0,
    }


@dataclass
class TiroLetra:
    tag: str
    letra: str


def load_letters(path: Path | None = None) -> list[TiroLetra]:
    """Letras R1–R4 / G1–G4 — requiere formato completo (lightgreen)."""
    idx = _cargar_indice(path or LIGHTGREEN)
    tags = sorted(idx.keys(), key=tag_key)
    out: list[TiroLetra] = []
    for tag in tags:
        for t in idx[tag]:
            if t.tipo is None or (t.lab == "G" and t.tipo == 5):
                continue
            let = t.letra
            if let == "R":
                continue
            if let in LETRAS:
                out.append(TiroLetra(tag=tag, letra=let))
    return out


def load_tiros_rg_detail() -> tuple[int, int]:
    """Conteo R vs G en detail (formato corto live)."""
    idx = _cargar_indice(DETAIL)
    nR = nG = 0
    for tiros in idx.values():
        for t in tiros:
            if t.lab == "G" and getattr(t, "tipo", None) == 5:
                continue
            if t.lab == "G":
                nG += 1
            elif t.lab == "R":
                nR += 1
    return nR, nG


def load_cinta():
    orden, bloques = leer_bloques_texto(DETAIL.read_text(encoding="utf-8"))
    cinta, _ = cinta_desde_bloques(orden, bloques)
    return cinta


def split_tags(tags: list[str]) -> tuple[list[str], list[str]]:
    if len(tags) <= HOLDOUT:
        return tags, []
    return tags[:-HOLDOUT], tags[-HOLDOUT:]


def calibrate_slots_from_counts(cnt: Counter) -> dict[str, int]:
    """Largest remainder → 54 slots."""
    weights = {k: max(cnt.get(k, 0), 1) for k in LETRAS}
    raw = {k: 54 * weights[k] / sum(weights.values()) for k in LETRAS}
    base = {k: int(raw[k]) for k in LETRAS}
    rem = 54 - sum(base.values())
    order = sorted(LETRAS, key=lambda k: raw[k] - base[k], reverse=True)
    for k in order[:rem]:
        base[k] += 1
    return base


def urn_probs(slots: dict[str, int]) -> dict[str, float]:
    """Dos etapas: R-urna 45 + G-menú 9."""
    r_slots = {k: slots[k] for k in ["R1", "R2", "R3", "R4"]}
    g_slots = {k: slots[k] for k in ["G1", "G2", "G3", "G4"]}
    p_r = sum(r_slots.values()) / 54
    p_g = sum(g_slots.values()) / 54
    out = {}
    for k, v in r_slots.items():
        out[k] = p_r * (v / sum(r_slots.values()))
    for k, v in g_slots.items():
        out[k] = p_g * (v / sum(g_slots.values()))
    return out
