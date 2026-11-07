"""Ficha $50–$250, racha R solo zona, chispa temprana vs @19.

API real. Oficio: zona tip±1. No spray. No escribe LIVE.
"""
from __future__ import annotations

from pathlib import Path
from statistics import median

from look_api import API, NOMBRES, flag19, parsear
from look_banca import banda, zona_ok
from look_escala import caminar, pack, sim

OUT = Path(__file__).resolve().parent / "LOOK_OPTIMO.txt"


def sim_desde(tiros, ficha, desde_m, solo_zona=True):
    """Apuesta desde minuto desde_m (inclusive), zona tip±1."""
    last_g = None
    gaps = []
    prev_g_m = None
    n = n_g = 0
    casa = 0
    racha_r = max_r = 0
    for t in tiros:
        if t["g"]:
            if prev_g_m is not None:
                gaps.append((t["m0"] - prev_g_m) % 60)
            prev_g_m = t["m0"]
        if t["m0"] < desde_m:
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
            racha_r += 1
            max_r = max(max_r, racha_r)
            continue
        n_g += 1
        racha_r = 0
        casa += ficha * t["lm"] - 9 * ficha
        last_g = t["m0"]
    return n, n_g, casa, max_r


def gs_de(tiros):
    return [t for t in tiros if t["g"]]


def chispa(tiros, umbral, seguidos=2):
    """Dos G ≥ umbral, una detrás de la otra (pueden haber R en medio)."""
    gs = gs_de(tiros)
    for i in range(len(gs) - seguidos + 1):
        bloque = gs[i : i + seguidos]
        if all(g["lm"] >= umbral for g in bloque):
            return bloque[-1]["m0"]
    return None


def tren_g(tiros, umbral):
    """Dos TIROS seguidos que son G y ambos ≥ umbral (sin R en medio)."""
    for i in range(len(tiros) - 1):
        a, b = tiros[i], tiros[i + 1]
        if a["g"] and b["g"] and a["lm"] >= umbral and b["lm"] >= umbral:
            return b["m0"]
    return None


def pack_lista(nombre, filas, ficha, entrar_en):
    """entrar_en(tiros) → minuto o None."""
    ns = gs = 0
    casas = []
    n_h = 0
    for _, tiros in filas:
        m = entrar_en(tiros)
        if m is None:
            continue
        n, ng, casa, _ = sim_desde(tiros, ficha, m)
        n_h += 1
        ns += n
        gs += ng
        casas.append(casa)
    if not casas:
        return f"  {nombre}: 0 horas"
    rp, pp, _ = caminar(casas, 90_000)
    return (
        f"  {nombre}: horas {n_h}  tiros {ns}  G {gs}  "
        f"casa {sum(casas):+.0f}  med/hora {median(casas):+.0f}  "
        f"pozo suelo {pp:.0f}  vidas@0 {rp}"
    )


def main() -> None:
    _, total, horas = parsear(API)
    flagged = [(k, t) for k, t in horas if flag19(t)]

    por_banda = {b: [] for b in (
        "muy_apagado", "opaco", "normal", "fuerte", "muy_fuerte", "supernova"
    )}
    for k, t in horas:
        s = sum(x["lm"] for x in t if x["g"])
        por_banda[banda(s)].append((k, t))

    L = [
        "LOOK OPTIMO — ficha, racha ZONA, chispa vs @19",
        f"API rondas {total}  horas {len(horas)}  indicio @19 {len(flagged)}",
        "Racha R = tiros APOSTADOS en zona que salen R. No es la hora entera.",
        "Nunca se apuesta fuera de tip±1.",
        "",
        "— ficha de 50 en 50, mismo $30k × 3, SOLO indicio+zona —",
    ]
    for f in (50, 100, 150, 200, 250):
        aire = 30000 // (4 * f)
        L.append(f"  [${f}/bono = ${4*f}/cuenta  aire {aire} R]")
        L.append(pack(f"indicio+zona ${f}", flagged, f)[0])
        L.append("")

    L.append("— Pool 7 (zona) según cómo CIERRA la hora. Toda la cinta —")
    for b in ("muy_apagado", "opaco", "normal", "fuerte", "muy_fuerte", "supernova"):
        filas = por_banda[b]
        if not filas:
            continue
        # zona toda la hora, sin esperar @19
        ns = gs = 0
        casas = []
        for _, tiros in filas:
            n, ng, casa, *_ = sim(tiros, 100, T=-1, usar_flag_minuto=False)
            ns += n
            gs += ng
            casas.append(casa)
        L.append(
            f"  {b:<12} h={len(filas):4d}  tiros {ns:5d}  G {gs:4d}  "
            f"casa {sum(casas):+.0f}  med/hora {median(casas) if casas else 0:+.0f}"
        )
    L.append("")

    # cola tras 1ª G alta
    L.append("— ¿un G alto levanta los que siguen? (toda la API) —")
    for umbral, et in ((100, "1ª G≥100"), (200, "1ª G≥200"), (40, "1ª G<40 control")):
        rest = []
        for _, tiros in horas:
            gs = gs_de(tiros)
            if umbral == 40:
                idx = next((i for i, g in enumerate(gs) if g["lm"] < 40), None)
            else:
                idx = next((i for i, g in enumerate(gs) if g["lm"] >= umbral), None)
            if idx is None or idx + 1 >= len(gs):
                continue
            rest.extend(g["lm"] for g in gs[idx + 1 :])
        if rest:
            altos = sum(1 for x in rest if x >= 100)
            L.append(
                f"  {et}: cola n={len(rest)}  med {median(rest):.0f}  "
                f"%≥100 {100*altos/len(rest):.1f}%"
            )
    L.append("")

    L.append("— chispa: 2 G altos y se entra YA (zona), ficha $150 —")
    L.append(pack_lista(
        "2 G≥100 seguidas (G-G, R en medio ok)",
        horas,
        150,
        lambda t: chispa(t, 100),
    ))
    L.append(pack_lista(
        "2 G≥200 seguidas",
        horas,
        150,
        lambda t: chispa(t, 200),
    ))
    L.append(pack_lista(
        "tren: 2 TIROS G≥100 pegados",
        horas,
        150,
        lambda t: tren_g(t, 100),
    ))
    L.append(pack_lista(
        "control: indicio @19 (misma ficha)",
        flagged,
        150,
        lambda t: 19,
    ))
    L.append("")

    # de las chispas, ¿cuántas cierran fuerte+?
    for umbral, et in ((100, "2×G≥100"), (200, "2×G≥200")):
        n = fu = 0
        min_med = []
        for _, tiros in horas:
            m = chispa(tiros, umbral)
            if m is None:
                continue
            n += 1
            min_med.append(m)
            s = sum(x["lm"] for x in tiros if x["g"])
            if banda(s) in ("fuerte", "muy_fuerte", "supernova"):
                fu += 1
        if n:
            L.append(
                f"  {et}: {n} h  cierra fuerte+ {100*fu/n:.1f}%  "
                f"minuto de la 2ª G med {median(min_med):.0f}"
            )
    L.append(
        f"  base cinta: fuerte+ {100*sum(1 for _,t in horas if banda(sum(x['lm'] for x in t if x['g'])) in ('fuerte','muy_fuerte','supernova'))/len(horas):.1f}%"
    )
    L.append("")
    L.extend(
        [
            "Lectura",
            "  · 16 R = 16 apuestas de zona seguidas que fueron R.",
            "    No son 16 rojos de la hora. Pool 7 no se ensancha.",
            "  · Óptimo de ficha = aire vs racha máx, no el techo.",
            "  · Chispa 2 altos: si el resto no sube, es momento suelto.",
            "  · Pool 7 en apagada: el med/hora lo dice la fila de arriba.",
            "",
        ]
    )
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
