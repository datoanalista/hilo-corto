"""Techo de la banda d<=1. No Jaccard. No escribe boleto."""

from __future__ import annotations

import json
from collections import Counter

from src.estado import PRIMERA_UTIL
from src.lectores import cargar_crudo
from src.motor import dist_anillo, min_dist_a_conjunto


def dmin(m, s):
    return min_dist_a_conjunto(m, s)


def cubrir(boleto, nuc):
    g = pm1 = 0
    for x in nuc:
        d = dmin(x, set(boleto)) if boleto else 99
        if d == 0:
            g += 1
        elif d == 1:
            pm1 += 1
    return g, pm1


def main() -> None:
    cinta = cargar_crudo()
    i0 = cinta.orden.index(PRIMERA_UTIL)
    acc = {
        "n": 0,
        "copia": [0, 0, 0, 0],  # g, pm1, score, collapse
        "anillo": [0, 0, 0, 0],
        "persist": [0, 0, 0, 0],
        "cruce": [0, 0, 0, 0],
        "costura": [0, 0, 0],  # n, g, horas_largo
        "techo_anillo": [0, 0],  # oficiales en anillo de H-1, oficiales
        "k": Counter(),
        "pobre": {"n": 0, "copia_score": 0, "copia_col": 0},
    }

    for i in range(i0, len(cinta.orden) - 1):
        h1 = set(cinta.get(cinta.orden[i]).nucleo)
        nuc = set(cinta.get(cinta.orden[i + 1]).nucleo)
        cruda = cinta.get(cinta.orden[i])
        largo = bool(cruda.tiros_nucleo[-1].largo) if cruda.tiros_nucleo else False
        from src.lectores import arranque_proxima

        cas0 = None
        if cruda.tiros_nucleo:
            cas0 = arranque_proxima(cruda.tiros_nucleo[-1]) // 60

        anillo = set()
        for s in h1:
            anillo.add((s + 1) % 60)
            anillo.add((s - 1) % 60)
        cruce = {m for m in anillo if sum(1 for s in h1 if dist_anillo(m, s) == 1) >= 2}

        acc["n"] += 1
        nG = len(nuc)
        acc["techo_anillo"][1] += nG
        acc["techo_anillo"][0] += sum(1 for x in nuc if dmin(x, h1) <= 1)

        for name, bol in (
            ("copia", list(h1)),
            ("anillo", list(anillo)),
            ("persist", list(h1)),
            ("cruce", list(cruce)),
        ):
            g, pm1 = cubrir(bol, nuc)
            score = g + pm1
            acc[name][0] += g
            acc[name][1] += pm1
            acc[name][2] += score
            if score == 0:
                acc[name][3] += 1
            acc["k"][name] += len(bol)

        if largo and cas0 is not None:
            acc["costura"][2] += 1
            acc["costura"][0] += 1
            if cas0 in nuc:
                acc["costura"][1] += 1

        if nG <= 7:
            acc["pobre"]["n"] += 1
            g, pm1 = cubrir(list(h1), nuc)
            acc["pobre"]["copia_score"] += g + pm1
            if g + pm1 == 0:
                acc["pobre"]["copia_col"] += 1

    n = acc["n"]
    out = {
        "n_horas": n,
        "techo_oficiales_en_banda_de_H1": {
            "oficiales": acc["techo_anillo"][1],
            "en_d_le1_de_H1": acc["techo_anillo"][0],
            "pct": acc["techo_anillo"][0] / acc["techo_anillo"][1],
        },
        "estrategias": {},
        "costura": {
            "n": acc["costura"][0],
            "G": acc["costura"][1] / acc["costura"][0] if acc["costura"][0] else 0,
        },
        "horas_pobres_nG_le7": {
            "n": acc["pobre"]["n"],
            "score_medio_copia": acc["pobre"]["copia_score"] / acc["pobre"]["n"] if acc["pobre"]["n"] else 0,
            "colapso": acc["pobre"]["copia_col"] / acc["pobre"]["n"] if acc["pobre"]["n"] else 0,
        },
    }
    for name, label_k in (
        ("copia", "copia"),
        ("anillo", "anillo"),
        ("cruce", "cruce"),
    ):
        g, pm1, score, col = acc[name]
        out["estrategias"][name] = {
            "k_medio": acc["k"][name] / n,
            "G_hora": g / n,
            "pm1_hora": pm1 / n,
            "score_hora": score / n,
            "pct_oficiales": score / acc["techo_anillo"][1],
            "colapso": col / n,
        }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
