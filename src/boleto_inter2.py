"""Boleto LIVE modo A — INTER2 (acuerdo exacto ≥2 de P0–P5).

Cero LIVE escrito fuera de hilo-corto. No es A01.
"""

from __future__ import annotations

import random
from collections import defaultdict

from src.estado import PRIMERA_UTIL, siguiente_tag
from src.lectores import Cinta
from src.mesas_beta import (
    BOLETO_IDS,
    CATALOGO,
    _a_tiros_sim,
    _cargar_lab,
    _chips_a_tiros,
    _generar,
    acuerdo_ge2,
)
from src.motor import texto_informe

LIVE_MODO = "inter2"


def precompute_beta_chips(cinta: Cinta) -> dict[str, dict[str, list[int]]]:
    """tag_for → {beta_id: chips}. Walk completo desde PRIMERA_UTIL."""
    try:
        lab = _cargar_lab()
    except Exception:
        return {}
    TiroSim = lab["TiroSim"]
    estimar_nG = lab["estimar_nG"]
    orden = cinta.orden
    if PRIMERA_UTIL in orden:
        i_first = orden.index(PRIMERA_UTIL)
    else:
        i_first = 0
    i_end = len(orden) - 1
    prev_sims: dict[str, object] = {}
    by_for: dict[str, dict[str, list[int]]] = defaultdict(dict)

    for i in range(i_first, i_end):
        tag = orden[i]
        nxt = orden[i + 1]
        prev_real = _a_tiros_sim(cinta.get(tag), TiroSim)
        for meta in CATALOGO:
            if not meta.get("beta"):
                continue
            pid = meta["id"]
            emu = lab["factories"][pid]
            seed_base = 4000 + sum(ord(c) for c in pid)
            prev_use = prev_sims.get(pid)
            if prev_use is None:
                prev_use = prev_real
            nG = estimar_nG(prev_use, random.Random(seed_base + i))
            chips, tiros_sim = _generar(emu, nxt, seed_base + i, prev_use, nG)
            by_for[nxt][pid] = list(chips)
            prev_sims[pid] = tiros_sim

    return dict(by_for)


def chips_inter2_all6(
    chips_p0: list[int], beta_map: dict[str, list[int]]
) -> tuple[list[int], dict[str, list[int]]]:
    chips_by: dict[str, list[int]] = {"oficial": list(chips_p0 or [])}
    for pid in BOLETO_IDS:
        if pid == "oficial":
            continue
        if pid in beta_map:
            chips_by[pid] = list(beta_map[pid])
    inter2 = acuerdo_ge2([chips_by.get(pid) or [] for pid in BOLETO_IDS])
    return inter2, chips_by


def _lectura_inter2(
    doc: dict, inter2: list[int], chips_classic: list[int], fallback: bool
) -> str:
    destino = doc.get("for") or "?"
    origen = doc.get("based_on") or "?"
    k = len(inter2)
    n_classic = len(chips_classic)
    lineas = [
        f"Mesa {destino}",
        f"(en la anterior, {origen}, ya se vieron las luces)",
        "",
        "Boleto LIVE · INTER2 (acuerdo exacto ≥2 de P0–P5).",
        f"Minutos con acuerdo: {k}. Pool 9 tenía {n_classic}.",
    ]
    if fallback:
        lineas.append(
            "Sin acuerdo ≥2 esta hora — se usó el boleto clásico P0 (fallback)."
        )
    lineas.extend(
        [
            "",
            "1) Número seguro",
            "INTER2 no usa SEGURO de costura: todas las fichas son banda (±1).",
            "",
            "2) ¿Te sentás a esta mesa?",
        ]
    )
    if k <= 0:
        lineas.append("No. Sin minutos de acuerdo. Plantate.")
    elif k <= 3:
        lineas.append(
            f"Con cautela. Solo {k} minutos coincidieron entre mesas. "
            "Si el primer tercio queda en blanco, plantate."
        )
    else:
        lineas.append(
            f"Sí. {k} fichas donde al menos dos pools (P0–P5) "
            "pusieron el mismo minuto. No agregues de más."
        )
    lineas.append("")
    lineas.append("3) Tus fichas")
    lineas.append(
        "Cada una cobra si sale ESE minuto o el de al lado (tres números pegados)."
    )
    for m in sorted(inter2):
        lineas.append(
            f"  {m:02d}  cobra {(m - 1) % 60:02d}, {m:02d} y {(m + 1) % 60:02d}"
        )
    lineas.append("")
    lineas.append(
        "Pool 9 (motor clásico) sigue visible en sombra para comparar."
    )
    return "\n".join(lineas) + "\n"


def aplicar_inter2_live(
    doc: dict,
    chips_classic: list[int],
    beta_map: dict[str, list[int]],
) -> dict:
    """Sustituye boleto/tiros por INTER2; conserva meta del motor clásico."""
    inter2, chips_by = chips_inter2_all6(chips_classic, beta_map)
    fallback = not inter2
    if fallback:
        inter2 = list(chips_classic)

    tiros = _chips_a_tiros(inter2)
    meta = dict(doc.get("meta") or {})
    meta.update(
        {
            "live_modo": LIVE_MODO,
            "chips_classic": list(chips_classic),
            "chips_inter2": list(inter2),
            "inter2_fallback": fallback,
            "inter2_k": len(inter2),
            "inter2_pools": {k: len(v) for k, v in chips_by.items()},
            "maquina": "hilo-corto · INTER2 live (A)",
            "nota": (
                "Boleto LIVE = minuto exacto en ≥2 de P0–P5. "
                "P0 clásico en sombra. Juez banda d≤1."
            ),
        }
    )

    out = dict(doc)
    out["boleto"] = inter2
    out["tiros"] = tiros
    out["meta"] = meta
    out["lectura_classic"] = doc.get("lectura") or texto_informe(doc)
    out["lectura"] = _lectura_inter2(doc, inter2, chips_classic, fallback)
    return out
