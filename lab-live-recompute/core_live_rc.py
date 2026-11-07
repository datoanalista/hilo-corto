# -*- coding: utf-8 -*-
"""Carga cinta detail · merged extracción-en-vivo."""
from __future__ import annotations

import re
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
GCOLA = ROOT / "lab-g-cola"
RZ = ROOT / "lab-ruleta-zero"
OJ = Path(r"c:\operacion-joker")

sys.path.insert(0, str(LAB))
sys.path.insert(0, str(RZ))
sys.path.insert(0, str(GCOLA))
sys.path.insert(0, str(ROOT))

from core_rz import DETAIL, load_cinta as load_detail  # noqa: E402
from src.lectores import cargar_ingesta, leer_bloques_texto  # noqa: E402

EXTRA = ROOT / "dashboard" / "extraccion" / "extraccion-en-vivo.txt"


def sanitizar_extra(texto: str) -> str:
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


def load_merged():
    extra = ""
    if EXTRA.exists():
        extra = sanitizar_extra(EXTRA.read_text(encoding="utf-8", errors="replace"))
    return cargar_ingesta(extra)[0]


def tag_sets() -> dict[str, set[str]]:
    detail_txt = DETAIL.read_text(encoding="utf-8", errors="replace")
    o_d, _ = leer_bloques_texto(detail_txt)
    d_tags = set(o_d)
    extra = sanitizar_extra(
        EXTRA.read_text(encoding="utf-8", errors="replace")
    ) if EXTRA.exists() else ""
    o_e, _ = leer_bloques_texto(extra) if extra.strip() else ([], {})
    e_tags = set(o_e)
    return {
        "detail": d_tags,
        "extra_file": e_tags,
        "only_extra": e_tags - d_tags,
        "extra_overlap": e_tags & d_tags,
    }
