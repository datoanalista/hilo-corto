"""Ficha $100/bono · $400/cuenta · $30k arranque. Solo lectura API.

Oficio: indicio @19 × zona tip±1. No spray.
Cobro que dictó el humano:
  R → −400 por cuenta (−1.200 casa).
  G → 100×color − 300 por cuenta  (los 3 bonos que no salieron).
  Casa G → 100×lm − 900.
  Ejemplo: 150+100+50=300 → 15.000+10.000+5.000 − 900 = +29.100.
No escribe LIVE.
"""
from __future__ import annotations

from pathlib import Path
from statistics import median

from look_api import API, NOMBRES, flag19, parsear
from look_banca import banda, zona_ok

OUT = Path(__file__).resolve().parent / "LOOK_FICHA100.txt"


def sim_hora_100(tiros, T=19, solo_zona=True):
    last_g = None
    gaps = []
    prev_g_m = None
    n = n_g = 0
    casa = 0
    acc = [0, 0, 0]
    apostados = []
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
            casa -= 1200
            for i in range(3):
                acc[i] -= 400
            continue
        n_g += 1
        casa += 100 * t["lm"] - 900
        for i in range(3):
            acc[i] += 100 * t["partes"][i] - 300
        apostados.append(t)
        last_g = t["m0"]
    return n, n_g, casa, acc, apostados


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


def pack(nombre, filas, banca_c=30_000, banca_p=90_000):
    ns = gs = 0
    casas = []
    por = [[], [], []]
    for _, tiros in filas:
        n, ng, casa, acc, _ = sim_hora_100(tiros)
        ns += n
        gs += ng
        casas.append(casa)
        for i in range(3):
            por[i].append(acc[i])
    pozo = banca_p
    piso_pozo = pozo
    muertes = 0
    for p in casas:
        pozo += p
        piso_pozo = min(piso_pozo, pozo)
        if pozo <= 0:
            muertes += 1
            pozo = banca_p
    lineas = [
        f"  {nombre}: tiros {ns}  G {gs}  casa {sum(casas):+.0f}  "
        f"med/hora {median(casas) if casas else 0:+.0f}"
    ]
    lineas.append(
        f"    pozo ${banca_p//1000}k: suelo {piso_pozo:.0f}  "
        f"vidas@0 {muertes}  / {len(casas)} h"
    )
    for i, nom in enumerate(NOMBRES):
        r, piso, fin = caminar(por[i], banca_c)
        lineas.append(
            f"    {nom} ${banca_c//1000}k: pnl {sum(por[i]):+.0f}  "
            f"suelo {piso:.0f}  vidas@0 {r}  cierre {fin:.0f}"
        )
    return "\n".join(lineas)


def main() -> None:
    _, total, horas = parsear(API)
    flagged = [(k, t) for k, t in horas if flag19(t)]
    fuerte_f = []
    for k, t in flagged:
        s = sum(x["lm"] for x in t if x["g"])
        if banda(s) in ("fuerte", "muy_fuerte", "supernova"):
            fuerte_f.append((k, t))

    # spray = todo post-19, para contrastar (lo que el casino quiere)
    def pack_spray(filas, banca_c=30_000, banca_p=90_000):
        ns = gs = 0
        casas = []
        por = [[], [], []]
        for _, tiros in filas:
            n, ng, casa, acc, _ = sim_hora_100(tiros, solo_zona=False)
            ns += n
            gs += ng
            casas.append(casa)
            for i in range(3):
                por[i].append(acc[i])
        r_p, piso_p, _ = caminar(casas, banca_p)
        lineas = [
            f"  spray post-19: tiros {ns}  G {gs}  casa {sum(casas):+.0f}  "
            f"med/hora {median(casas) if casas else 0:+.0f}"
        ]
        lineas.append(
            f"    pozo $90k: suelo {piso_p:.0f}  vidas@0 {r_p}  / {len(casas)} h"
        )
        for i, nom in enumerate(NOMBRES):
            r, piso, fin = caminar(por[i], banca_c)
            lineas.append(
                f"    {nom} $30k: pnl {sum(por[i]):+.0f}  "
                f"suelo {piso:.0f}  vidas@0 {r}  cierre {fin:.0f}"
            )
        return "\n".join(lineas)

    gordos = []
    for _, tiros in flagged:
        *_, ap = sim_hora_100(tiros)
        for t in ap:
            if t["lm"] >= 250:
                gordos.append(t)
            if len(gordos) >= 8:
                break
        if len(gordos) >= 8:
            break

    L = [
        "LOOK FICHA100 — $100/bono · $400/cuenta · $30k × 3",
        f"API rondas {total}  horas {len(horas)}  indicio {len(flagged)}  "
        f"fuerte+ {len(fuerte_f)}",
        "R −400/cuenta. G: 100×color − 300  (3 bonos que no salieron).",
        "Casa G: 100×lm − 900. Ejemplo 150+100+50 → +29.100.",
        "Colchón: 75 R seguidos ($30k/$400). A $50/$20k eran 100 R.",
        "",
        "— recibos zona lm≥250 (el caso 300× que nombraste) —",
    ]
    if gordos:
        for t in gordos:
            p = t["partes"]
            L.append(
                f"  {t['ts'][:16]}  {t['tipo']:7s}  lm {t['lm']:4d}  "
                f"{p[0]}+{p[1]}+{p[2]}  "
                f"casa {100*t['lm']-900:+}  "
                f"w {100*p[0]-300:+}/{100*p[1]-300:+}/{100*p[2]-300:+}"
            )
    else:
        L.append("  (no hubo G≥250 en zona+indicio; listo el más alto)")
        tops = []
        for _, tiros in flagged:
            *_, ap = sim_hora_100(tiros)
            tops.extend(ap)
        tops.sort(key=lambda x: x["lm"], reverse=True)
        for t in tops[:6]:
            p = t["partes"]
            L.append(
                f"  {t['ts'][:16]}  {t['tipo']:7s}  lm {t['lm']:4d}  "
                f"{p[0]}+{p[1]}+{p[2]}  casa {100*t['lm']-900:+}"
            )
    L.append("")
    L.append("— oficio (indicio @19 + zona). Esto NO es rociar —")
    L.append(pack("indicio+zona", flagged))
    L.append("")
    L.append("— techo oráculo fuerte+ + zona —")
    L.append(pack("oráculo fuerte+", fuerte_f))
    L.append("")
    L.append("— lo que el casino quiere: TODO tiro post-19 en esas horas —")
    L.append(pack_spray(flagged))
    L.append("")
    L.extend(
        [
            "Lectura",
            "  · $90k no es el doble de $60k: ficha ×2, pozo ×1.5.",
            "    Menos tiros de colchón (75 vs 100).",
            "  · Si el oficio se cumple, el suelo lo dice la API.",
            "  · Spray a $400 seca más rápido que a $50.",
            "",
        ]
    )
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
