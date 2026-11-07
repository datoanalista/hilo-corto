# -*- coding: utf-8 -*-
"""Motores incrementales desde física Show."""
from __future__ import annotations

import random
from statistics import median

from src.estado import Estado, VENTANA_CILINDRO
from src.motor import (
    min_dist_a_conjunto,
    nG_clima,
    proponer_som02_chip,
)
from src.tablero import score

from show_physics import CORTE_LARGO_S, MENU_L_BANDS, P_G


def _ultima(estado: Estado):
    return estado.ultima()


def _h1(estado: Estado) -> list[int]:
    u = _ultima(estado)
    return sorted(set(u.nucleo)) if u else []


def _prev_largo(estado: Estado) -> bool:
    u = _ultima(estado)
    return bool(u and u.last_largo)


def _cas0(estado: Estado) -> int:
    u = _ultima(estado)
    return int(u.t0_proxima) // 60 if u else 0


def _clima(estado: Estado) -> int:
    return nG_clima(estado)


def _pick_islas_fermion(islas: list[int], cupo: int) -> list[int]:
    if len(islas) <= cupo:
        return sorted(islas)
    h1s = set(islas)
    return sorted(
        islas,
        key=lambda s: (-min_dist_a_conjunto(s, h1s - {s}), s),
    )[:cupo]


def chips_plato54_uniform(tag_for: str, n_tiros_prev: int, k_override: int | None = None) -> list[int]:
    """M0: plato 54 — k spins G esperados · minutos iid."""
    k = k_override if k_override is not None else max(0, min(15, round(n_tiros_prev * P_G)))
    if k <= 0:
        return []
    rng = random.Random(hash(("plato", tag_for.lower())) & 0xFFFFFFFF)
    pool = list(range(60))
    rng.shuffle(pool)
    return sorted(pool[:k])


def chips_mapa(estado: Estado) -> list[int]:
    """M1: solo islas H-1."""
    islas = _h1(estado)
    if not islas:
        return []
    cupo = _clima(estado)
    return _pick_islas_fermion(islas, cupo)


def chips_cierre(estado: Estado) -> list[int]:
    """M2: mapa + SEGURO costura."""
    out: list[int] = []
    if _prev_largo(estado):
        cas0 = _cas0(estado)
        out.append(cas0)
    clima = _clima(estado)
    cupo = max(0, clima - len(out))
    for m in _pick_islas_fermion(_h1(estado), cupo):
        if m not in out:
            out.append(m)
    return sorted(set(out))


def chips_som02(estado: Estado) -> list[int]:
    """M3: cierre + mapa + SOM02."""
    out = chips_cierre(estado)
    usados = set(out)
    clima = _clima(estado)
    if len(usados) >= clima:
        return sorted(out)
    h1 = _h1(estado)
    cand, _, _ = proponer_som02_chip(h1, usados, clima)
    if cand is not None and cand not in usados:
        out.append(cand)
    return sorted(set(out))


def chips_show_v1(estado: Estado, n_tiros_prev: int) -> list[int]:
    """M6: motor nuevo — plato calibra cupo · cierre · mapa · sombra."""
    if not _ultima(estado):
        return []
    h1 = _h1(estado)
    clima = _clima(estado)
    k_plato = max(1, round(n_tiros_prev * P_G)) if n_tiros_prev else clima
    # cupo efectivo: clima del cilindro, techo plato 54
    tope = min(clima, max(k_plato, len(h1) + (1 if _prev_largo(estado) else 0)))

    out: list[int] = []
    if _prev_largo(estado):
        out.append(_cas0(estado))

    if not h1 and not _prev_largo(estado):
        return []  # plantate show: sin mapa ni cierre

    cupo = max(0, tope - len(out))
    for m in _pick_islas_fermion(h1, cupo):
        if m not in out:
            out.append(m)

    usados = set(out)
    if len(usados) < tope:
        cand, _, _ = proponer_som02_chip(h1, usados, tope)
        if cand is not None:
            out.append(cand)
    return sorted(set(out))


def banda_metrics(chips: list[int], oficiales: list[int]) -> dict:
    if not oficiales:
        return {"banda": None, "g": 0, "pm1": 0, "exact": 0, "n": 0, "hit": False, "k": len(chips)}
    g, pm1 = score(chips, oficiales)
    n = len(oficiales)
    return {
        "banda": (g + pm1) / n,
        "g": g,
        "pm1": pm1,
        "exact": g / n,
        "n": n,
        "hit": (g + pm1) > 0,
        "k": len(chips),
    }


def seguro_hit(estado: Estado, oficiales: list[int]) -> bool | None:
    """¿Casilla SEGURO acertó pleno? Solo si cierre largo."""
    if not _prev_largo(estado) or not oficiales:
        return None
    cas0 = _cas0(estado)
    return cas0 in oficiales


def menu_l_predict_tinta(dur_s: int) -> str:
    for lo, hi, tint in MENU_L_BANDS:
        if lo <= dur_s <= hi:
            return tint
    return "G3"  # default corto


def tinta_actual(letra: str) -> str:
    if letra.startswith("G"):
        return letra[:2] if len(letra) >= 2 else letra
    return "R"


def median_n_tiros(cinta, tags: list[str]) -> int:
    vals = []
    for t in tags:
        if t in cinta.horas:
            vals.append(len(cinta.horas[t].tiros_nucleo))
    return int(round(median(vals))) if vals else 50


# ── R2: orden · plato · híbridos ──────────────────────────────────────────


def chips_mapa_cierre(estado: Estado) -> list[int]:
    """M7: islas H-1 antes que SEGURO (orden invertido vs clásico)."""
    out = chips_mapa(estado)
    if _prev_largo(estado):
        cas0 = _cas0(estado)
        if cas0 not in out:
            out = [cas0] + out
    return sorted(set(out))


def chips_show_k_plato(estado: Estado, n_tiros_prev: int) -> list[int]:
    """M8: clásico con tope = min(clima, k plato 54)."""
    from src.motor import construir_informe

    clima = _clima(estado)
    k_plato = max(1, round(n_tiros_prev * P_G)) if n_tiros_prev else clima
    tope = min(clima, k_plato)
    return list(construir_informe(estado, tope=tope).get("boleto") or [])


def chips_plato_x_mapa(estado: Estado, tag_for: str, n_tiros_prev: int) -> list[int]:
    """M9: plato 54 ∩ H-1 · fermión si falta cupo."""
    clima = _clima(estado)
    k = max(1, round(n_tiros_prev * P_G)) if n_tiros_prev else clima
    plato = set(chips_plato54_uniform(tag_for, n_tiros_prev, k_override=k))
    h1 = _h1(estado)
    out: list[int] = sorted(plato & set(h1))
    if _prev_largo(estado):
        cas0 = _cas0(estado)
        if cas0 not in out:
            out = [cas0] + out
    cupo = clima
    if len(out) < cupo:
        for m in _pick_islas_fermion(h1, cupo):
            if m not in out:
                out.append(m)
            if len(out) >= cupo:
                break
    return sorted(set(out))


def chips_mapa_som_sin_cierre(estado: Estado) -> list[int]:
    """M10: mapa + SOM02 sin SEGURO costura."""
    out = chips_mapa(estado)
    usados = set(out)
    clima = _clima(estado)
    if len(usados) >= clima:
        return sorted(out)
    h1 = _h1(estado)
    cand, _, _ = proponer_som02_chip(h1, usados, clima)
    if cand is not None and cand not in usados:
        out.append(cand)
    return sorted(set(out))


def union_chips(*listas: list[int]) -> list[int]:
    s: set[int] = set()
    for xs in listas:
        s.update(xs or [])
    return sorted(s)


def inter2_acuerdo(listas: list[list[int]]) -> list[int]:
    from src.mesas_beta import acuerdo_ge2

    return acuerdo_ge2(listas)


def inter2_show_p0(chips_show: list[int], beta_map: dict[str, list[int]]) -> list[int]:
    """H1: P0 = show (M3) · betas igual · acuerdo ≥2."""
    from src.mesas_beta import BOLETO_IDS

    chips_by: dict[str, list[int]] = {"oficial": list(chips_show)}
    for pid in BOLETO_IDS:
        if pid == "oficial":
            continue
        if pid in beta_map:
            chips_by[pid] = list(beta_map[pid])
    return inter2_acuerdo([chips_by.get(pid) or [] for pid in BOLETO_IDS])


def inter2_show_plus(
    chips_classic: list[int], chips_show: list[int], beta_map: dict[str, list[int]]
) -> list[int]:
    """H2: 7 pools — clásico + show + betas · acuerdo ≥2."""
    from src.mesas_beta import BOLETO_IDS

    listas = [list(chips_classic), list(chips_show)]
    for pid in BOLETO_IDS:
        if pid == "oficial":
            continue
        listas.append(list(beta_map.get(pid) or []))
    return inter2_acuerdo(listas)


def inter2_show_classic_only(chips_classic: list[int], chips_show: list[int]) -> list[int]:
    """H3: acuerdo solo clásico + show (intersección exacta)."""
    return inter2_acuerdo([list(chips_classic), list(chips_show)])

