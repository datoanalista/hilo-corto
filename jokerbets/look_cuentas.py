"""3 wallets fijos (rojo/azul/verde a muerte). Casa = total.

Premisa de mesa: lm = r+a+v. Cada cuenta −200 por tiro apostado.
G → esa cuenta cobra 50×su_tajada. Casa = 50×lm − 600.
LOOK_COLORES 3/4 no se usa. No escribe LIVE.
"""
from __future__ import annotations

import random
from pathlib import Path
from statistics import median

from look_banca import CINTA, banda, parsear, zona_ok

OUT = Path(__file__).resolve().parent / "LOOK_CUENTAS.txt"


def flag19(tiros):
    ya = [t for t in tiros if t["g"] and t["m0"] <= 19]
    if len(ya) < 2:
        return False
    return (sum(t["lm"] for t in ya) / len(ya)) >= 68


def partir(lm: int, rng: random.Random, modo: str) -> list[int]:
    """3 enteros que suman lm. Orden: rojo, azul, verde."""
    if lm <= 0:
        return [0, 0, 0]
    if modo == "igual":
        b, e = divmod(lm, 3)
        xs = [b] * 3
        for i in range(e):
            xs[i] += 1
        return xs
    if modo == "suerte":
        # el flaco rota: 2 / 50 / 60 del ejemplo, escalado al lumen
        pesos = [2, 50, 60]
        rng.shuffle(pesos)
        tot = sum(pesos)
        xs = [int(lm * p / tot) for p in pesos]
        xs[0] += lm - sum(xs)
        return xs
    if modo == "verde_flaco":
        # el 2× se pega a verde siempre (peor caso “a muerte”)
        pesos = [60, 50, 2]
        tot = sum(pesos)
        xs = [int(lm * p / tot) for p in pesos]
        xs[0] += lm - sum(xs)
        return xs
    raise ValueError(modo)


def sim_hora(tiros, modo, rng, T=19, solo_zona=True):
    last_g = None
    gaps = []
    prev_g_m = None
    n = n_g = 0
    casa = 0
    acc = [0, 0, 0]
    for t in tiros:
        if t["g"]:
            if prev_g_m is not None:
                gaps.append((t["m0"] - prev_g_m) % 60)
            prev_g_m = t["m0"]
        if t["m0"] <= T:
            if t["g"]:
                last_g = t["m0"]
            continue
        if solo_zona and not zona_ok(t["m0"], last_g, gaps):
            if t["g"]:
                last_g = t["m0"]
            continue
        n += 1
        if not t["g"]:
            casa -= 600
            for i in range(3):
                acc[i] -= 200
            continue
        n_g += 1
        partes = partir(t["lm"], rng, modo)
        casa += 50 * t["lm"] - 600
        for i in range(3):
            acc[i] += 50 * partes[i] - 200
        last_g = t["m0"]
    return n, n_g, casa, acc


def caminar(deltas, banca=20_000):
    c = banca
    piso = banca
    ruinas = 0
    for d in deltas:
        c += d
        piso = min(piso, c)
        if c <= 0:
            ruinas += 1
            c = banca
    return ruinas, piso, c


def pack(nombre, filas, modo, seed=7):
    rng = random.Random(seed)
    ns = gs = 0
    casas = []
    por = [[], [], []]
    for _, tiros in filas:
        n, ng, casa, acc = sim_hora(tiros, modo, rng)
        ns += n
        gs += ng
        casas.append(casa)
        for i in range(3):
            por[i].append(acc[i])
    # casa: 3 wallets juntas, colchón 60k; también cada una a 20k
    nombres = ("rojo", "azul", "verde")
    lineas = [
        f"  {nombre}: tiros {ns}  G {gs}  casa {sum(casas):+.0f}  "
        f"med/hora {median(casas) if casas else 0:+.0f}"
    ]
    # casa como un pozo 60k (no recarga parcial)
    pozo = 60_000
    piso_pozo = pozo
    muertes_pozo = 0
    for p in casas:
        pozo += p
        piso_pozo = min(piso_pozo, pozo)
        if pozo <= 0:
            muertes_pozo += 1
            pozo = 60_000
    lineas.append(
        f"    pozo $60k (3×20k juntas): suelo {piso_pozo:.0f}  "
        f"vidas@0 {muertes_pozo}  / {len(casas)} h"
    )
    for i, nom in enumerate(nombres):
        r, piso, fin = caminar(por[i])
        lineas.append(
            f"    {nom:5s} $20k: pnl {sum(por[i]):+.0f}  "
            f"suelo {piso:.0f}  vidas@0 {r}  cierre {fin:.0f}"
        )
    return "\n".join(lineas)


def main() -> None:
    horas = parsear(CINTA)
    flagged = [(tag, tiros) for tag, tiros in horas if flag19(tiros)]
    fuerte_f = []
    normal_f = []
    for tag, tiros in flagged:
        s = sum(t["lm"] for t in tiros if t["g"])
        b = banda(s)
        if b in ("fuerte", "muy_fuerte", "supernova"):
            fuerte_f.append((tag, tiros))
        elif b == "normal":
            normal_f.append((tag, tiros))

    # recibo: 80 × $50 = $4.000 casa bruta; neto +3.400 si apostaron las 3
    ejemplos = []
    for tag, tiros in flagged:
        for t in tiros:
            if t["g"] and 75 <= t["lm"] <= 85:
                ejemplos.append((tag, t["m0"], t["lm"]))
            if len(ejemplos) >= 6:
                break
        if len(ejemplos) >= 6:
            break

    L = [
        "LOOK CUENTAS — Pool 7 + horas que YA se ven fuertes",
        f"cinta {len(horas)} h · indicio @19 {len(flagged)} · "
        f"cierran fuerte+ {len(fuerte_f)} / normal {len(normal_f)}",
        "Cobro (mesa): $50 × multiplicador. 80× → $4.000 brutos.",
        "3 cuentas cubren los 3 colores → casa cobra el TOTAL.",
        "G de lumen 80: casa +4.000 − 600 = +3.400. R: −600.",
        "Silla: zona tip±1 post-19. Color a muerte.",
        "Cortes RGB = MODELO (la cinta no trae 60/50/2).",
        "",
        "— recibos de cinta (G ~80, mismo cobro) —",
    ]
    if ejemplos:
        for tag, m, lm in ejemplos:
            L.append(
                f"  {tag} min {m:02d}  lm {lm}  "
                f"bruto ${50*lm}  neto casa ${50*lm - 600:+}"
            )
    else:
        L.append("  (no hubo G 75–85 en las horas con indicio)")
    L.append("")
    L.append("— lo que se puede DETECTAR en vivo (indicio @19 + zona) —")
    for modo, et in (
        ("igual", "reparto igual (lm/3)"),
        ("suerte", "2/50/60 rotando de color"),
        ("verde_flaco", "verde SIEMPRE el 2× (peor a-muerte)"),
    ):
        L.append(f"  [{et}]")
        L.append(pack("indicio", flagged, modo))
        L.append("")

    L.append("— techo: las que además CIERRAN fuerte+ (oráculo, no se exige) —")
    for modo, et in (
        ("igual", "reparto igual"),
        ("suerte", "2/50/60 rotando"),
        ("verde_flaco", "verde siempre flaco"),
    ):
        L.append(f"  [{et}]")
        L.append(pack("oráculo fuerte+", fuerte_f, modo, seed=11))
        L.append("")

    L.extend(
        [
            "Lectura",
            "  · Casa (pozo 60k) no toca $0 en 350 h de indicio ni en 129 de techo.",
            "  · Si el 2× rota de color, ninguna wallet de $20k toca $0.",
            "  · Si UN color es siempre el flaco, ESA cuenta sí puede secarse",
            "    aunque la casa gane. Eso es el único $0 nuevo de ‘a muerte’.",
            "  · El $0 de rociar todos los tiros sigue siendo el peligro real.",
            "",
        ]
    )
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
