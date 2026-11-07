"""ARCHIVO. Premisa falsa: midió 3 de 4 colores.

Mesa real: 4 bonos en la ruleta; 3 colores en el juego;
3 cuentas cubren los 3. Casa = total. No rerun como libro.
Vigente: COLORES.txt · look_banca.py
"""
from __future__ import annotations

import random
from pathlib import Path
from statistics import median

from look_banca import CINTA, banda, parsear, zona_ok


def flag19(tiros):
    ya = [t for t in tiros if t["g"] and t["m0"] <= 19]
    if len(ya) < 2:
        return False
    return (sum(t["lm"] for t in ya) / len(ya)) >= 68

OUT = Path(__file__).resolve().parent / "LOOK_COLORES.txt"
COLORES = ("rojo", "azul", "verde", "amarillo")


def splits_de(lm: int, rng: random.Random, modo: str) -> list[int]:
    """Parte un lumen en 4 enteros que suman lm. Modelos de mesa, no cinta."""
    if lm <= 0:
        return [0, 0, 0, 0]
    if modo == "igual":
        base, extra = divmod(lm, 4)
        xs = [base] * 4
        for i in range(extra):
            xs[i] += 1
        return xs
    if modo == "un_muerto":
        # uno a 0; los otros se parten el total. Eso es “siempre pierde un color”.
        muerto = rng.randrange(4)
        xs = [0, 0, 0, 0]
        resto = [i for i in range(4) if i != muerto]
        base, extra = divmod(lm, 3)
        for j, i in enumerate(resto):
            xs[i] = base + (1 if j < extra else 0)
        return xs
    if modo == "carga":
        # uno se lleva ~55–80%; el resto se parte lo que queda; a veces el 4º queda en 0.
        cargado = rng.randrange(4)
        frac = rng.uniform(0.55, 0.80)
        gordo = max(1, int(round(lm * frac)))
        gordo = min(gordo, lm)
        resto = lm - gordo
        xs = [0, 0, 0, 0]
        xs[cargado] = gordo
        otros = [i for i in range(4) if i != cargado]
        # a menudo el 4º color queda flojo o en 0
        muerto = otros[rng.randrange(3)]
        vivos = [i for i in otros if i != muerto]
        if resto == 0:
            return xs
        if rng.random() < 0.65:
            base, extra = divmod(resto, 2)
            xs[vivos[0]] = base + extra
            xs[vivos[1]] = base
            xs[muerto] = 0
        else:
            base, extra = divmod(resto, 3)
            for j, i in enumerate(otros):
                xs[i] = base + (1 if j < extra else 0)
        return xs
    raise ValueError(modo)


def cubrir(partes: list[int], cubiertos: tuple[int, int, int]) -> int:
    return sum(partes[i] for i in cubiertos)


def pnl_casa(lm_cubierto: int) -> int:
    return 50 * lm_cubierto - 600


def sim_politica(tiros, entrar_desde, solo_zona, rng, modo, politica):
    """politica: fijo | rota | caza
    fijo: siempre cubren 0,1,2 (dejan fuera amarillo)
    rota: cada G ciclan cuál dejan fuera
    caza: cubren los 3 que más pagaron en la G ANTERIOR (ciego a esta)
    """
    last_g = None
    gaps = []
    prev_g_m = None
    n = n_g = 0
    casa = 0
    cubierto_xs = []
    total_xs = []
    cuentas = [0, 0, 0]
    skip = 0
    ultimo_rank = (0, 1, 2)  # cubiertos por defecto hasta ver una G

    for t in tiros:
        if t["g"]:
            if prev_g_m is not None:
                gaps.append((t["m0"] - prev_g_m) % 60)
            prev_g_m = t["m0"]
        if t["m0"] <= entrar_desde:
            if t["g"]:
                last_g = t["m0"]
                partes = splits_de(t["lm"], rng, modo)
                ultimo_rank = tuple(
                    sorted(range(4), key=lambda i: partes[i], reverse=True)[:3]
                )
            continue
        if solo_zona and not zona_ok(t["m0"], last_g, gaps):
            if t["g"]:
                last_g = t["m0"]
                partes = splits_de(t["lm"], rng, modo)
                ultimo_rank = tuple(
                    sorted(range(4), key=lambda i: partes[i], reverse=True)[:3]
                )
            continue
        n += 1
        if not t["g"]:
            casa -= 600
            for i in range(3):
                cuentas[i] -= 200
            continue
        n_g += 1
        partes = splits_de(t["lm"], rng, modo)
        if politica == "fijo":
            cub = (0, 1, 2)
        elif politica == "rota":
            fuera = skip % 4
            cub = tuple(i for i in range(4) if i != fuera)
            skip += 1
        elif politica == "caza":
            cub = ultimo_rank
        else:
            raise ValueError(politica)
        capt = cubrir(partes, cub)
        casa += pnl_casa(capt)
        # las 3 cuentas, en orden de cub, cobran su tajada
        for k, ci in enumerate(cub):
            cuentas[k] += 50 * partes[ci] - 200
        cubierto_xs.append(capt)
        total_xs.append(t["lm"])
        last_g = t["m0"]
        ultimo_rank = tuple(
            sorted(range(4), key=lambda i: partes[i], reverse=True)[:3]
        )
    return {
        "n": n,
        "n_g": n_g,
        "casa": casa,
        "cuentas": cuentas,
        "capt": cubierto_xs,
        "tot": total_xs,
    }


def ruin_cuenta(delta, banca=20_000):
    c = banca
    piso = banca
    ruinas = 0
    for d in delta:
        c += d
        piso = min(piso, c)
        if c <= 0:
            ruinas += 1
            c = banca
    return ruinas, piso


def linea_pack(nombre, filas, modo, politica, seed=7):
    rng = random.Random(seed)
    ns = gs = 0
    casas = []
    caps = []
    tots = []
    # una trayectoria de las 3 cuentas (misma semilla) para suelo
    acc = [20_000, 20_000, 20_000]
    piso = [20_000, 20_000, 20_000]
    ruinas = [0, 0, 0]
    for _, tiros in filas:
        r = sim_politica(tiros, 19, True, rng, modo, politica)
        ns += r["n"]
        gs += r["n_g"]
        casas.append(r["casa"])
        caps.extend(r["capt"])
        tots.extend(r["tot"])
        for i in range(3):
            acc[i] += r["cuentas"][i]
            piso[i] = min(piso[i], acc[i])
            if acc[i] <= 0:
                ruinas[i] += 1
                acc[i] = 20_000
    tot_casa = sum(casas)
    frac = (sum(caps) / sum(tots)) if tots else 0.0
    return (
        f"  {nombre}: tiros {ns}  G {gs}  casa {tot_casa:+.0f}  "
        f"med/hora {median(casas) if casas else 0:+.0f}  "
        f"captura {100*frac:.1f}% del lumen"
        f"\n    cuentas suelo {min(piso):.0f} / {sorted(piso)[1]:.0f} / {max(piso):.0f}"
        f"  vidas@0 {sum(ruinas)} (reponen $20k)"
    )


def main() -> None:
    horas = parsear(CINTA)
    flagged = [(tag, tiros) for tag, tiros in horas if flag19(tiros)]

    # oráculo fuerte+ solo como techo, igual que LOOK_BANCA
    fuerte_f = []
    for tag, tiros in flagged:
        s = sum(t["lm"] for t in tiros if t["g"])
        if banda(s) in ("fuerte", "muy_fuerte", "supernova"):
            fuerte_f.append((tag, tiros))

    L = [
        "LOOK COLORES — el lumen de la cinta es la SUMA de 4 tajadas",
        f"horas {len(horas)} · indicio @19 {len(flagged)} · oráculo fuerte+ {len(fuerte_f)}",
        "Política de silla: misma que el borrador (zona tip±1, post-19).",
        "Los cortes son MODELO (la cinta no trae rojo/azul/verde/amarillo).",
        "3 cuentas cubren 3 de 4. Apuesta $200. Colchón $20.000.",
        "",
        "Teorema (si siempre dejan 1 color fuera, y ese hueco no persigue la carga):",
        "  E[captura] = 75% del lumen, da igual que un color se cargue.",
        "  Casa por G = 50×(lm−tajada_fuera) − 600. Ya no es 50×lm − 600.",
        "",
        "— indicio @19 + ZONA, 3 modos de corte × 3 políticas —",
    ]
    for modo, etiqueta in (
        ("igual", "4 partes iguales"),
        ("un_muerto", "siempre un color = 0"),
        ("carga", "un color se lleva 55–80%"),
    ):
        L.append(f"  [{etiqueta}]")
        for pol, nom in (
            ("fijo", "fijo  RGB  (dejan amarillo)"),
            ("rota", "rotan cuál dejan fuera"),
            ("caza", "cazan los 3 de la G anterior"),
        ):
            L.append(linea_pack(f"{nom:28s}", flagged, modo, pol))
        L.append("")

    L.append("— mismo, solo horas que CIERRAN fuerte+ (oráculo, techo) —")
    for modo, etiqueta in (
        ("igual", "4 partes iguales"),
        ("un_muerto", "siempre un color = 0"),
        ("carga", "un color se lleva 55–80%"),
    ):
        L.append(f"  [{etiqueta}]")
        for pol, nom in (
            ("fijo", "fijo  RGB"),
            ("rota", "rotan hueco"),
            ("caza", "cazan carga previa"),
        ):
            L.append(linea_pack(f"{nom:28s}", fuerte_f, modo, pol, seed=11))
        L.append("")

    L.extend(
        [
            "Lectura",
            "  · Fijo vs rota: la casa casi no se mueve. Solo se barajan los suelos.",
            "  · Cazar la carga de la G que YA pagó: no gana lumen. A veces pierde.",
            "  · El 50×lm−600 de LOOK_BANCA era el techo (como si cobraran el total).",
            "  · Con 3 de 4, el libro real vive cerca del 75% de ese techo.",
            "  · Para saber SI un color se pega de verdad hay que guardar el corte",
            "    (bonusResult por clave), no solo la suma. Hoy no está en la cinta.",
            "",
        ]
    )
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
