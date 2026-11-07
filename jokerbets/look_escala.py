"""Ventana de la API, ritmo, y ficha $250 / $1000 con el mismo $30k.

Oficio: indicio @19 × zona. No spray. No escribe LIVE.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from statistics import median

from look_api import API, NOMBRES, flag19, parsear
from look_banca import zona_ok

OUT = Path(__file__).resolve().parent / "LOOK_ESCALA.txt"


def sim(tiros, ficha, T=19, solo_zona=True, usar_flag_minuto=True):
    """ficha = $ por bono. Cuenta apuesta 4×ficha.
    R → −4F. G → F×color − 3F. Casa G → F×lm − 9F. Casa R → −12F.
    """
    last_g = None
    gaps = []
    prev_g_m = None
    n = n_g = 0
    casa = 0
    acc = [0, 0, 0]
    racha_r = 0
    max_r = 0
    for t in tiros:
        if t["g"]:
            if prev_g_m is not None:
                gaps.append((t["m0"] - prev_g_m) % 60)
            prev_g_m = t["m0"]
        if usar_flag_minuto and t["m0"] <= T:
            if t["g"]:
                last_g = t["m0"]
            continue
        if solo_zona and not zona_ok(t["m0"], last_g, gaps):
            if t["g"]:
                last_g = t["m0"]
            continue
        n += 1
        if not t["g"]:
            casa -= 12 * ficha
            for i in range(3):
                acc[i] -= 4 * ficha
            racha_r += 1
            max_r = max(max_r, racha_r)
            continue
        n_g += 1
        racha_r = 0
        casa += ficha * t["lm"] - 9 * ficha
        for i in range(3):
            acc[i] += ficha * t["partes"][i] - 3 * ficha
        last_g = t["m0"]
    return n, n_g, casa, acc, max_r


def caminar(deltas, banca):
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


def pack(nombre, filas, ficha, banca_c=30_000, banca_p=90_000, **kw):
    ns = gs = 0
    casas = []
    por = [[], [], []]
    max_r = 0
    for _, tiros in filas:
        n, ng, casa, acc, mr = sim(tiros, ficha, **kw)
        ns += n
        gs += ng
        casas.append(casa)
        max_r = max(max_r, mr)
        for i in range(3):
            por[i].append(acc[i])
    rp, pp, _ = caminar(casas, banca_p)
    lineas = [
        f"  {nombre}: tiros {ns}  G {gs}  casa {sum(casas):+.0f}  "
        f"med/hora {median(casas) if casas else 0:+.0f}  "
        f"racha R máx {max_r}"
    ]
    lineas.append(
        f"    pozo ${banca_p//1000}k: suelo {pp:.0f}  "
        f"({100*pp/banca_p:.0f}% del arranque)  vidas@0 {rp} / {len(casas)} h"
    )
    for i, nom in enumerate(NOMBRES):
        r, piso, fin = caminar(por[i], banca_c)
        lineas.append(
            f"    {nom} ${banca_c//1000}k: pnl {sum(por[i]):+.0f}  "
            f"suelo {piso:.0f} ({100*piso/banca_c:.0f}%)  "
            f"vidas@0 {r}  cierre {fin:.0f}"
        )
    return "\n".join(lineas), sum(casas), len(filas)


def main() -> None:
    actualizado, total, horas = parsear(API)
    first = horas[0][1][0]["ts"]
    last = horas[-1][1][-1]["ts"]
    t0 = datetime.fromisoformat(first)
    t1 = datetime.fromisoformat(last)
    dias = max((t1 - t0).total_seconds() / 86400, 1)
    flagged = [(k, t) for k, t in horas if flag19(t)]

    L = [
        "LOOK ESCALA — ventana, ritmo, $250 y $1.000/bono",
        f"API {first[:16]} → {last[:16]}  ({dias:.1f} días)  "
        f"rondas {total}  horas {len(horas)}",
        f"actualizado {actualizado}",
        f"Horas con indicio @19: {len(flagged)}  "
        f"({100*len(flagged)/len(horas):.1f}% de las horas de cinta)",
        f"Indicio por día de calendario: {len(flagged)/dias:.1f} h",
        "0 en una muestra ≠ 0 para siempre. Es esta cinta, este oficio.",
        "",
        "— ritmo del oficio (ficha $100, ya medido) —",
    ]
    txt, casa100, nh = pack("indicio+zona $100", flagged, 100)
    L.append(txt)
    por_dia = casa100 / dias
    por_mes = por_dia * 30
    L.append(
        f"    ritmo: {casa100:+.0f} en {dias:.1f} d  →  "
        f"{por_dia:+.0f}/día  ·  {por_mes:+.0f} / 30 días "
        f"(si se repite la densidad de indicio)"
    )
    L.append(
        "    Eso NO es “cada mes cae eso”. Es regla de tres sobre "
        f"{dias:.0f} días. 24/7 MIRAR ≠ 24/7 APOSTAR."
    )
    L.append("")
    L.append("— mismo $30k × 3, oficio, ficha más alta —")
    for f, et in ((250, "$250/bono = $1.000/cuenta"), (1000, "$1.000/bono = $4.000/cuenta")):
        L.append(f"  [{et}  colchón {30000//(4*f)} R]")
        L.append(pack(f"indicio+zona {et}", flagged, f)[0])
        L.append("")

    L.append("— si se deja 24/7 APOSTANDO cada hora (zona, SIN bandera) —")
    L.append(pack("todas las horas + zona $100", horas, 100)[0])
    L.append(pack("todas las horas + zona $250", horas, 250)[0])
    L.append("")
    L.append("— colchón que deja el mismo aire que $100/$30k (75 R) —")
    L.append("  $250/bono ($1.000/cuenta): $75.000 / cuenta  ·  pozo $225k")
    L.append("  $1.000/bono ($4.000/cuenta): $300.000 / cuenta  ·  pozo $900k")
    L.append("  Subir ficha y dejar el mismo $30k = menos aire, no el mismo riesgo 0.")
    L.append("")
    L.extend(
        [
            "Lectura",
            "  · El +2.25M es de ESTA ventana (~43 d), no un sueldo mensual.",
            "  · 24/7 el reloj puede correr. La ficha solo con bandera × zona.",
            "  · $250 en este $30k: la API dice si roza la mitad o no.",
            "  · $1.000 en este $30k: 7 R de aire. Eso sí puede ir a $0.",
            "",
        ]
    )
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
