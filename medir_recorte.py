"""Recorte de fichas: islas vs racimo+costura vs costura. Juez banda. No Jaccard."""

from __future__ import annotations

import json

from src.estado import Estado, PRIMERA_UTIL
from src.lectores import cargar_crudo
from src.motor import dist_anillo, emitir_boleto


def cubrir(boleto, nuc):
    if not boleto:
        return 0, 0
    bs = set(boleto)
    g = pm1 = 0
    for x in nuc:
        d = min(dist_anillo(x, b) for b in bs)
        if d == 0:
            g += 1
        elif d == 1:
            pm1 += 1
    return g, pm1


def recorte_racimo(doc: dict) -> list[int]:
    calientes = set()
    for z in doc.get("zonas_racimo") or []:
        a, b = z["desde"], z["hasta"]
        if a <= b:
            calientes.update(range(a, b + 1))
        else:
            calientes.update(range(a, 60))
            calientes.update(range(0, b + 1))
    out = []
    for t in doc.get("tiros") or []:
        if t["rol"] == "costura" or t["minuto"] in calientes:
            out.append(t["minuto"])
    return sorted(set(out))


def recorte_seguro(doc: dict) -> list[int]:
    return sorted(t["minuto"] for t in doc.get("tiros") or [] if t["flag"] == "SEGURO")


def main() -> None:
    cinta = cargar_crudo()
    i0 = cinta.orden.index(PRIMERA_UTIL)
    estado = Estado()
    names = ("islas", "racimo_costura", "solo_costura")
    acc = {n: {"n": 0, "k": 0, "g": 0, "pm1": 0, "col": 0, "vacio": 0} for n in names}

    for i in range(i0, len(cinta.orden) - 1):
        estado.cerrar(cinta.get(cinta.orden[i]))
        doc = emitir_boleto(estado)
        nuc = set(cinta.get(cinta.orden[i + 1]).nucleo)
        bols = {
            "islas": doc["boleto"],
            "racimo_costura": recorte_racimo(doc),
            "solo_costura": recorte_seguro(doc),
        }
        for name, bol in bols.items():
            acc[name]["n"] += 1
            if not bol:
                acc[name]["vacio"] += 1
            acc[name]["k"] += len(bol)
            g, pm1 = cubrir(bol, nuc)
            acc[name]["g"] += g
            acc[name]["pm1"] += pm1
            if g + pm1 == 0:
                acc[name]["col"] += 1

    out = {}
    for name, d in acc.items():
        n = d["n"] or 1
        score = d["g"] + d["pm1"]
        out[name] = {
            "k_medio": d["k"] / n,
            "G_hora": d["g"] / n,
            "pm1_hora": d["pm1"] / n,
            "score_hora": score / n,
            "score_por_ficha": (score / d["k"]) if d["k"] else 0,
            "colapso": d["col"] / n,
            "horas_sin_tiro": d["vacio"] / n,
        }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    from pathlib import Path

    Path("reports/recorte_fichas.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
