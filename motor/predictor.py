"""
Predictor AnilloCorto v3 — Cobertura compacta +/-1
"""
from __future__ import annotations
from typing import Dict, List, Set, Tuple, Optional
from .estado import TableroEstado


def _window(p: int) -> Set[int]:
    return {(p - 1) % 60, p % 60, (p + 1) % 60}


def boleto_cobertura(
    h1: Set[int],
    h2: Optional[Set[int]] = None,
    k_min: int = 6,
    k_max: int = 8,
) -> Tuple[List[int], Dict[int, str]]:
    h1 = set(h1)
    h2 = set(h2 or [])
    flags: Dict[int, str] = {}

    if not h1 and not h2:
        step = max(1, 60 // k_min)
        boleto = list(range(0, 60, step))[:k_min]
        return boleto, {m: "FRIO" for m in boleto}

    target: Set[int] = set()
    for m in h1:
        target |= _window(m)
    if not target and h2:
        for m in h2:
            target |= _window(m)

    core = sorted(h1)
    anillo = sorted(
        ({(m + 1) % 60 for m in h1} | {(m - 1) % 60 for m in h1}) - h1
    )
    puente = sorted(h2 - h1 - set(anillo))
    pool = core + anillo + puente

    selected: List[int] = []
    covered: Set[int] = set()

    def gain(p: int) -> float:
        g = float(len((_window(p) & target) - covered))
        if p in h1 and p in h2:
            g += 0.30
        elif p in h1:
            g += 0.20
        elif p in anillo:
            g += 0.05
        return g

    remaining = list(pool)
    while len(selected) < k_max and remaining:
        best = None
        best_g = 0.0
        for p in remaining:
            g = gain(p)
            if g > best_g:
                best_g = g
                best = p
        if best is None or best_g <= 0:
            break
        selected.append(best)
        covered |= _window(best) & target
        remaining.remove(best)

    for p in pool:
        if len(selected) >= k_min:
            break
        if p not in selected:
            selected.append(p)

    if len(selected) < k_min:
        for m in range(60):
            if len(selected) >= k_min:
                break
            if m not in selected:
                selected.append(m)
                flags[m] = "RELLENO"

    selected = selected[:k_max]

    for m in selected:
        if m in flags:
            continue
        if m in h1:
            flags[m] = "NUCLEO"
        elif m in anillo:
            flags[m] = "ANILLO"
        elif m in h2:
            flags[m] = "PUENTE"
        else:
            flags[m] = "OTRO"

    return selected, flags


def _zonas(boleto: List[int]) -> List[str]:
    if not boleto:
        return []
    s = sorted(set(boleto))
    grupos = []
    actual = [s[0]]
    for m in s[1:]:
        if m == actual[-1] + 1:
            actual.append(m)
        else:
            grupos.append(actual)
            actual = [m]
    grupos.append(actual)
    if len(grupos) >= 2 and grupos[0][0] == 0 and grupos[-1][-1] == 59:
        fusion = grupos[-1] + grupos[0]
        grupos = grupos[1:-1] + [fusion]
    out = []
    for g in grupos:
        if len(g) == 1:
            out.append(str(g[0]))
        else:
            out.append("%d-%d" % (g[0], g[-1]))
    return out


def score_casillas(
    estado: TableroEstado,
    k_min: int = 6,
    k_max: int = 8,
    **_ignored,
) -> Tuple[List[int], Dict[int, float], dict]:
    prev = estado.previas(n=4)
    h1 = prev[0][1] if prev else set()
    h2 = prev[1][1] if len(prev) > 1 else set()
    boleto, flags = boleto_cobertura(h1, h2, k_min=k_min, k_max=k_max)
    peso = {
        "NUCLEO": 3.0,
        "ANILLO": 2.0,
        "PUENTE": 1.5,
        "RELLENO": 0.5,
        "FRIO": 0.3,
        "OTRO": 0.4,
    }
    scores = {m: peso.get(flags.get(m, "OTRO"), 0.4) for m in boleto}
    meta = {
        "k_usado": len(boleto),
        "k_min": k_min,
        "k_max": k_max,
        "n_h1": len(h1),
        "n_h2": len(h2),
        "flags": flags,
        "motivo": "cobertura_v3",
        "zonas": _zonas(boleto),
    }
    return boleto, scores, meta


def emitir_boleto(
    estado: TableroEstado,
    based_on: str,
    for_tag: str,
    k: Optional[int] = None,
    k_min: int = 6,
    k_max: int = 8,
    **_ignored,
) -> dict:
    if k is not None:
        k_min = k
        k_max = k
    boleto, scores, meta_extra = score_casillas(
        estado, k_min=k_min, k_max=k_max
    )
    return {
        "based_on": based_on,
        "for": for_tag,
        "boleto": boleto,
        "meta": {
            "motor": "AnilloCorto_v3_cobertura",
            "ventana": estado.ventana,
            "n_previas": estado.n_horas(),
            "scores_top": scores,
            **meta_extra,
        },
    }