"""Contrasta el informe contra lo que pico. Juez banda. No Jaccard."""

from __future__ import annotations

import json
from pathlib import Path

from src.estado import Estado, PRIMERA_UTIL
from src.lectores import cargar_crudo
from src.motor import dist_anillo, emitir_boleto


def dmin(m, s):
    return min(dist_anillo(m, x) for x in s) if s else 99


def en_racimo(m: int, z: dict) -> bool:
    a, b = z["desde"], z["hasta"]
    if a <= b:
        return a <= m <= b
    return m >= a or m <= b


def main() -> None:
    cinta = cargar_crudo()
    i0 = cinta.orden.index(PRIMERA_UTIL)
    estado = Estado()

    n = 0
    g = pm1 = 0
    of = 0
    col = 0
    cost_n = cost_g = 0
    rac_n = 0
    rac_of = 0
    rac_hit = 0
    and_abs = []
    muestras = []

    for i in range(i0, len(cinta.orden) - 1):
        tag = cinta.orden[i]
        nxt = cinta.orden[i + 1]
        estado.cerrar(cinta.get(tag))
        doc = emitir_boleto(estado)
        nuc = set(cinta.get(nxt).nucleo)
        bol = doc["boleto"]
        n += 1
        of += len(nuc)
        gg = p1 = 0
        for x in nuc:
            d = dmin(x, set(bol)) if bol else 99
            if d == 0:
                gg += 1
            elif d == 1:
                p1 += 1
        g += gg
        pm1 += p1
        if gg + p1 == 0:
            col += 1

        for t in doc.get("tiros") or []:
            if t.get("rol") == "costura":
                cost_n += 1
                if t["minuto"] in nuc:
                    cost_g += 1

        for z in doc.get("zonas_racimo") or []:
            rac_n += 1
            caen = [x for x in nuc if en_racimo(x, z)]
            rac_of += z["n_islas"]
            rac_hit += len(caen)

        real_and = [
            sum(1 for x in nuc if 0 <= x <= 19),
            sum(1 for x in nuc if 20 <= x <= 39),
            sum(1 for x in nuc if 40 <= x <= 59),
        ]
        pred_and = [z["esperadas"] for z in doc.get("zonas_anden") or []]
        if len(pred_and) == 3:
            and_abs.append(sum(abs(a - b) for a, b in zip(pred_and, real_and)))

        # guardar 3 tipos de muestra
        largo = bool(doc["meta"].get("prev_largo"))
        tiene_rac = bool(doc.get("zonas_racimo"))
        pobre = len(nuc) <= 7
        want = None
        if largo and not any(m["tipo"] == "largo" for m in muestras):
            want = "largo"
        elif tiene_rac and not any(m["tipo"] == "racimo" for m in muestras):
            want = "racimo"
        elif pobre and not any(m["tipo"] == "pobre" for m in muestras):
            want = "pobre"
        if want and len(muestras) < 6:
            muestras.append(
                {
                    "tipo": want,
                    "for": nxt,
                    "oficiales": sorted(nuc),
                    "G": gg,
                    "pm1": p1,
                    "lectura": doc.get("lectura"),
                }
            )

    out = {
        "n": n,
        "G_hora": g / n,
        "pm1_hora": pm1 / n,
        "score_hora": (g + pm1) / n,
        "pct_banda": (g + pm1) / of,
        "colapso": col / n,
        "costura_G": cost_g / cost_n if cost_n else 0,
        "costura_n": cost_n,
        "racimo": {
            "n_zonas": rac_n,
            "G_en_zona_vs_cupo_prometido": rac_hit / rac_of if rac_of else 0,
            "G_en_zona_hora": rac_hit / n,
        },
        "anden_desvio_medio": sum(and_abs) / len(and_abs) if and_abs else 0,
        "muestras": muestras,
    }
    Path("reports/coherencia_informe.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in out.items() if k != "muestras"}, ensure_ascii=False, indent=2))
    print()
    for m in muestras:
        print("---", m["tipo"], m["for"], "oficiales", m["oficiales"], "G", m["G"], "+-1", m["pm1"])
        print(m["lectura"])
        print()


if __name__ == "__main__":
    main()
