"""
Lectores de data cruda.
Soporta dos formatos:

1. Sillas clásico (solo intervalos de luces):
   h10-230726
   06:44-07:34
   17:01-18:42

2. Cinta detail (el formato real que estás usando):
   h9-230726
   28:57-29:41 G2 30
   29:42-30:30 R
   34:36-35:26 G2 40
   ...

En ambos casos se extrae el set de casillas G del núcleo
(minuto de INICIO de cada tiro G*).
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional


TAG_RE = re.compile(r"^h(\d{1,2})-(\d{6})$")

# línea de cinta detail: 34:36-35:26 G2 40   o   28:57-29:41 R
DETAIL_RE = re.compile(
    r"^(\d{2}):(\d{2})-(\d{2}):(\d{2})\s+(G[1-5]|R)(?:\s+(\d+))?$"
)

# línea de sillas simple: 06:44-07:34
SILLA_RE = re.compile(r"^(\d{2}):(\d{2})-(\d{2}):(\d{2})$")

def parse_tag(tag: str) -> Tuple[int, str]:
    m = TAG_RE.match(tag.strip())
    if not m:
        raise ValueError(f"tag inválido: {tag}")
    return int(m.group(1)), m.group(2)


def tag_sort_key(tag: str) -> Tuple[int, int, int, int]:
    """Clave cronológica real para DDMMAA."""
    h, dia = parse_tag(tag)
    dd = int(dia[0:2])
    mm = int(dia[2:4])
    aa = int(dia[4:6])
    yyyy = 2000 + aa
    return (yyyy, mm, dd, h)


def _next_dia_ddmmaa(dia: str) -> str:
    from datetime import date, timedelta
    dd = int(dia[0:2])
    mm = int(dia[2:4])
    aa = int(dia[4:6])
    yyyy = 2000 + aa
    nxt = date(yyyy, mm, dd) + timedelta(days=1)
    return f"{nxt.day:02d}{nxt.month:02d}{nxt.year % 100:02d}"


def next_tag(tag: str) -> str:
    h, dia = parse_tag(tag)
    if h == 23:
        return f"h0-{_next_dia_ddmmaa(dia)}"
    return f"h{h + 1}-{dia}"
    

def casilla_from_inicio(mm: int) -> int:
    return mm % 60


def load_sillas(path: Path) -> Dict[str, Set[int]]:
    """
    Detecta automáticamente el formato y devuelve:
      { tag: set de minutos (0-59) que prendieron en el núcleo }
    Solo cuenta líneas G (G1..G5). Las R se ignoran para el tablero.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    hours: Dict[str, Set[int]] = {}
    current: Optional[str] = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        if TAG_RE.match(line):
            current = line
            hours[current] = set()
            continue

        if current is None:
            continue

        # intentar detail primero (formato real)
        m = DETAIL_RE.match(line)
        if m:
            tipo = m.group(5)
            if tipo.startswith("G"):
                mm = int(m.group(1))
                hours[current].add(casilla_from_inicio(mm))
            continue

        # fallback: sillas simple
        m = SILLA_RE.match(line)
        if m:
            mm = int(m.group(1))
            hours[current].add(casilla_from_inicio(mm))
            continue

    return hours


def load_cinta_detail(path: Path) -> Dict[str, List[dict]]:
    """
    Carga la cinta completa con tipo y lumen (para análisis futuros).
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    hours: Dict[str, List[dict]] = {}
    current: Optional[str] = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if TAG_RE.match(line):
            current = line
            hours[current] = []
            continue
        if current is None:
            continue
        m = DETAIL_RE.match(line)
        if m:
            tipo = m.group(5)
            lumen = int(m.group(6)) if m.group(6) else None
            hours[current].append({
                "inicio": f"{m.group(1)}:{m.group(2)}",
                "fin": f"{m.group(3)}:{m.group(4)}",
                "mm": int(m.group(1)) % 60,
                "tipo": tipo,
                "lumen": lumen,
                "es_G": tipo.startswith("G"),
            })
    return hours