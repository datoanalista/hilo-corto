"""Huecos del informe. Juez banda. No Jaccard. No escribe boleto."""

from __future__ import annotations

import json
from collections import Counter

from src.estado import Estado, PRIMERA_UTIL
from src.lectores import cargar_crudo
from src.motor import dist_anillo, emitir_boleto, min_dist_a_conjunto, nG_clima


def dmin(m, s):
    return min_dist_a_conjunto(m, s)


def main() -> None:
    cinta = cargar_crudo()
    i0 = cinta.orden.index(PRIMERA_UTIL)
    estado = Estado()

    chip = Counter()  # (rol, marca)
    chip_n = Counter()
    adyacentes = 0
    horas_ady = 0
    orilla_extra = {"n": 0, "g": 0, "pm1": 0, "ya_cubierta": 0}
    drop = {"n": 0, "g": 0, "pm1": 0}  # islas recortadas por clima
    cierre = {
        True: {"n": 0, "g": 0, "pm1": 0, "k": 0},
        False: {"n": 0, "g": 0, "pm1": 0, "k": 0},
    }
    cols = {}
    clima_err = []
    muertos = 0
    chips_tot = 0
    tibio_exact = tibio_borde = tibio_miss = 0

    for i in range(i0, len(cinta.orden) - 1):
        tag = cinta.orden[i]
        nxt = cinta.orden[i + 1]
        cruda = cinta.get(tag)
        estado.cerrar(cruda)
        doc = emitir_boleto(estado)
        nuc = set(cinta.get(nxt).nucleo)
        bol = doc["boleto"]
        bs = set(bol)
        h1 = set(cruda.nucleo)
        meta = doc["meta"]
        largo = bool(meta.get("prev_largo"))

        gg = p1 = 0
        for x in nuc:
            d = dmin(x, bs) if bs else 99
            if d == 0:
                gg += 1
            elif d == 1:
                p1 += 1
        c = cierre[largo]
        c["n"] += 1
        c["g"] += gg
        c["pm1"] += p1
        c["k"] += len(bol)

        cn = meta.get("columnas") or 0
        cols.setdefault(cn, {"n": 0, "g": 0, "pm1": 0, "k": 0})
        cols[cn]["n"] += 1
        cols[cn]["g"] += gg
        cols[cn]["pm1"] += p1
        cols[cn]["k"] += len(bol)

        clima_err.append(nG_clima(estado) - len(nuc))

        pares = 0
        for a in bol:
            for b in bol:
                if a < b and dist_anillo(a, b) == 1:
                    pares += 1
        if pares:
            horas_ady += 1
            adyacentes += pares

        for t in doc.get("tiros") or []:
            m = t["minuto"]
            cubre = set(t.get("cubre") or [m])
            rol = t.get("rol") or "?"
            chips_tot += 1
            if m in nuc:
                marca = "exacto"
            elif any(dist_anillo(m, x) == 1 for x in nuc):
                marca = "borde"
            else:
                marca = "muerto"
                muertos += 1
            chip[(rol, marca)] += 1
            chip_n[rol] += 1
            if rol != "costura":
                if marca == "exacto":
                    tibio_exact += 1
                elif marca == "borde":
                    tibio_borde += 1
                else:
                    tibio_miss += 1

        # orilla como chip extra
        for o in doc.get("orillas") or []:
            m = o["minuto"]
            orilla_extra["n"] += 1
            if m in bs or any(dist_anillo(m, c) <= 1 for c in bs):
                orilla_extra["ya_cubierta"] += 1
                continue
            if m in nuc:
                orilla_extra["g"] += 1
            elif dmin(m, nuc) == 1:
                orilla_extra["pm1"] += 1

        # islas de H-1 que el tope recorto
        emitidos = set(bol)
        recortadas = [s for s in h1 if s not in emitidos]
        for s in recortadas:
            drop["n"] += 1
            if s in nuc:
                drop["g"] += 1
            elif dmin(s, nuc) == 1:
                drop["pm1"] += 1

    def rates(rol):
        n = chip_n[rol] or 1
        return {
            "n": chip_n[rol],
            "exacto": chip[(rol, "exacto")] / n,
            "borde": chip[(rol, "borde")] / n,
            "muerto": chip[(rol, "muerto")] / n,
            "banda": (chip[(rol, "exacto")] + chip[(rol, "borde")]) / n,
        }

    n_h = len(cinta.orden) - 1 - i0
    tib = tibio_exact + tibio_borde + tibio_miss or 1
    out = {
        "por_chip": {
            "costura": rates("costura"),
            "isla": rates("isla"),
        },
        "tibio_mix": {
            "exacto": tibio_exact / tib,
            "borde": tibio_borde / tib,
            "muerto": tibio_miss / tib,
        },
        "chips_muertos_pct": muertos / chips_tot if chips_tot else 0,
        "chips_tot": chips_tot,
        "adyacentes": {"pares_total": adyacentes, "horas": horas_ady, "pct_horas": horas_ady / n_h},
        "cierre": {
            "largo": {
                "n": cierre[True]["n"],
                "score": (cierre[True]["g"] + cierre[True]["pm1"]) / cierre[True]["n"],
                "G": cierre[True]["g"] / cierre[True]["n"],
                "k": cierre[True]["k"] / cierre[True]["n"],
            },
            "corto": {
                "n": cierre[False]["n"],
                "score": (cierre[False]["g"] + cierre[False]["pm1"]) / cierre[False]["n"],
                "G": cierre[False]["g"] / cierre[False]["n"],
                "k": cierre[False]["k"] / cierre[False]["n"],
            },
        },
        "orilla_si_fuera_chip": {
            "n": orilla_extra["n"],
            "ya_en_banda_del_boleto": orilla_extra["ya_cubierta"] / orilla_extra["n"] if orilla_extra["n"] else 0,
            "G_extra": orilla_extra["g"] / n_h,
            "pm1_extra": orilla_extra["pm1"] / n_h,
        },
        "islas_recortadas_por_clima": {
            "n": drop["n"],
            "por_hora": drop["n"] / n_h,
            "banda_si_se_hubieran_quedado": (drop["g"] + drop["pm1"]) / drop["n"] if drop["n"] else 0,
        },
        "clima_vs_nG": sum(clima_err) / len(clima_err),
        "columnas": {
            str(k): {
                "n": v["n"],
                "score": (v["g"] + v["pm1"]) / v["n"],
                "k": v["k"] / v["n"],
            }
            for k, v in sorted(cols.items())
        },
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
