"""Diagnostico de corrimiento. No usa Jaccard."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from src.estado import Estado, PRIMERA_UTIL
from src.lectores import cargar_crudo
from src.motor import (
    dist_anillo,
    emitir_boleto,
    min_dist_a_conjunto,
    nG_clima,
)


def _stick_len(casilla: int, columnas: list[set[int]]) -> int:
    n = 0
    for col in reversed(columnas):
        if casilla in col:
            n += 1
        else:
            break
    return n


def _padre(s: int, h2: set[int]) -> tuple[int | None, int, int]:
    if not h2:
        return None, 99, 0
    t = min(h2, key=lambda x: dist_anillo(x, s))
    d = dist_anillo(t, s)
    paso = (s - t) % 60
    if paso > 30:
        paso -= 60
    return t, d, paso if d <= 2 else 0


def dmin(m, s):
    return min(dist_anillo(m, x) for x in s) if s else 99


def main() -> None:
    cinta = cargar_crudo()
    i0 = cinta.orden.index(PRIMERA_UTIL)
    estado = Estado()

    rol_hits = defaultdict(lambda: Counter())
    rol_n = Counter()
    por_cols = defaultdict(lambda: {"n": 0, "g": 0, "pm1": 0, "k": 0, "nG": 0})
    por_cierre = {
        True: {"n": 0, "g": 0, "pm1": 0, "costura_g": 0, "costura_n": 0},
        False: {"n": 0, "g": 0, "pm1": 0},
    }
    clima_err = []
    cats = Counter()

    # verdad del corrimiento de cada hilo H-1 -> H (nearest official)
    verdad = Counter()  # (clase_h1, destino_real)
    pred_ok = Counter()  # rol -> exactos de ese gesto vs n emitidos ya en rol_hits

    pega_sigue = []  # slen1: persistio?
    despega_ok = []  # slen2: se fue y cayo a ±1?
    stick3_murio = []
    camina_inercia = []
    puente_cae = []
    fermion_skip_era_g = []

    for i in range(i0, len(cinta.orden) - 1):
        tag = cinta.orden[i]
        nxt = cinta.orden[i + 1]
        cruda = cinta.get(tag)
        estado.cerrar(cruda)
        doc = emitir_boleto(estado)
        boleto = doc["boleto"]
        roles = {r["minuto"]: r["rol"] for r in doc["meta"]["roles"]}
        nuc = set(cinta.get(nxt).nucleo)
        h1 = set(cruda.nucleo)
        h2 = set(cinta.get(cinta.orden[i - 1]).nucleo) if i > i0 else set()
        cols = [set(estado.horas[j].nucleo) for j in range(len(estado.horas))]
        cols_n = estado.calentamiento()
        largo = bool(cruda.tiros_nucleo[-1].largo) if cruda.tiros_nucleo else False
        cas0 = int(estado.ultima().t0_proxima) // 60

        g = pm1 = 0
        for m in boleto:
            rol = roles.get(m, "?")
            d = dmin(m, nuc)
            if d == 0:
                marca = "G"
                g += 1
            elif d == 1:
                marca = "pm1"
                pm1 += 1
            else:
                marca = "miss"
            rol_hits[rol][marca] += 1
            rol_n[rol] += 1

        if g and pm1:
            cats["ambos"] += 1
        elif g:
            cats["solo_G"] += 1
        elif pm1:
            cats["solo_pm1"] += 1
        else:
            cats["nada"] += 1

        pc = por_cols[cols_n]
        pc["n"] += 1
        pc["g"] += g
        pc["pm1"] += pm1
        pc["k"] += len(boleto)
        pc["nG"] += len(nuc)

        pcier = por_cierre[largo]
        pcier["n"] += 1
        pcier["g"] += g
        pcier["pm1"] += pm1
        if largo:
            por_cierre[True]["costura_n"] += 1
            if cas0 in nuc:
                por_cierre[True]["costura_g"] += 1

        clima_err.append(nG_clima(estado) - len(nuc))

        # verdad por hilo
        for s in h1:
            slen = _stick_len(s, cols)
            _p, d, vel = _padre(s, h2)
            if not nuc:
                continue
            dest = min(nuc, key=lambda x: dist_anillo(x, s))
            dd = dist_anillo(dest, s)
            if d == 1:
                clase = "camina"
                inercia = (s + vel) % 60
                camina_inercia.append(1 if dest == inercia else 0)
            elif d == 2:
                clase = "salto"
            elif slen >= 3:
                clase = "stick3"
                stick3_murio.append(1 if s not in nuc else 0)
            elif slen == 2:
                clase = "stick2"
                despega_ok.append(1 if s not in nuc and dd == 1 else 0)
            else:
                clase = "seed"
                pega_sigue.append(1 if s in nuc else 0)
            if dd == 0:
                verdad[f"{clase}->pega"] += 1
            elif dd == 1:
                verdad[f"{clase}->paso1"] += 1
            elif dd == 2:
                verdad[f"{clase}->paso2"] += 1
            else:
                verdad[f"{clase}->lejos"] += 1

        if h2:
            for t in h2:
                if min_dist_a_conjunto(t, h1) >= 3:
                    puente_cae.append(1 if dmin(t, nuc) <= 1 else 0)

    def tasa(xs):
        return sum(xs) / len(xs) if xs else 0.0

    roles_tab = []
    for rol in sorted(rol_n, key=lambda r: -rol_n[r]):
        h = rol_hits[rol]
        n = rol_n[rol]
        roles_tab.append(
            {
                "rol": rol,
                "n": n,
                "por_hora": n / (len(cinta.orden) - 1 - i0),
                "G": h["G"] / n,
                "pm1": h["pm1"] / n,
                "le1": (h["G"] + h["pm1"]) / n,
                "miss": h["miss"] / n,
                "G_abs": h["G"],
                "pm1_abs": h["pm1"],
            }
        )

    cols_tab = []
    for k in sorted(por_cols):
        d = por_cols[k]
        nn = d["n"]
        cols_tab.append(
            {
                "columnas": k,
                "n": nn,
                "G": d["g"] / nn,
                "pm1": d["pm1"] / nn,
                "k": d["k"] / nn,
                "nG": d["nG"] / nn,
            }
        )

    n_h = len(cinta.orden) - 1 - i0
    out = {
        "n_horas": n_h,
        "roles": roles_tab,
        "columnas": cols_tab,
        "cierre_largo": {
            "n": por_cierre[True]["n"],
            "G": por_cierre[True]["g"] / por_cierre[True]["n"],
            "pm1": por_cierre[True]["pm1"] / por_cierre[True]["n"],
            "costura_acierta": por_cierre[True]["costura_g"] / por_cierre[True]["costura_n"],
        },
        "cierre_corto": {
            "n": por_cierre[False]["n"],
            "G": por_cierre[False]["g"] / por_cierre[False]["n"],
            "pm1": por_cierre[False]["pm1"] / por_cierre[False]["n"],
        },
        "cats": dict(cats),
        "clima_bias": sum(clima_err) / len(clima_err),
        "hilos": {
            "seed_pega": tasa(pega_sigue),
            "n_seed": len(pega_sigue),
            "stick2_despega_a_paso1": tasa(despega_ok),
            "n_stick2": len(despega_ok),
            "stick3_se_apaga": tasa(stick3_murio),
            "n_stick3": len(stick3_murio),
            "camina_sigue_inercia": tasa(camina_inercia),
            "n_camina": len(camina_inercia),
            "puente_cae_d_le1": tasa(puente_cae),
            "n_puente": len(puente_cae),
        },
        "verdad": dict(verdad),
    }
    Path("reports/diagnostico_corrimiento.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
