"""Ejercicio histórico sobre consolidado-jocker.json (solo lectura).

API: bonusResult 0/1/2 = las 3 tajadas de color.
Cobro: $50 × mult. Casa = suma. Color a muerte.
Silla: zona tip±1. Bandera: media @19 ≥68 y ≥2 G.
No escribe LIVE. No toca depuracion.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import median

from look_banca import banda, zona_ok

API = Path(r"C:\operacion-joker\depuracion\consolidado-jocker.json")
OUT = Path(__file__).resolve().parent / "LOOK_API.txt"
BONOS = {"luck", "deluxe", "dice", "wheel"}
NOMBRES = ("c0", "c1", "c2")  # índices API; Luck en pantalla: izq/centro/der


def parsear(path: Path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    rondas = raw.get("rondas") or []
    horas = []
    cur = None
    tiros = []
    for r in rondas:
        ts = r.get("ts")
        if not ts:
            continue
        dt = datetime.fromisoformat(ts)
        key = dt.strftime("%Y-%m-%d-%H")
        wr = str(r.get("wheelResult") or "").lower()
        es_g = wr in BONOS
        partes = [0, 0, 0]
        if es_g:
            br = ((r.get("bono") or {}).get("bonusResult")) or {}
            for i in range(3):
                try:
                    partes[i] = int(br.get(str(i), br.get(i, 0)) or 0)
                except (TypeError, ValueError):
                    partes[i] = 0
        tiro = {
            "m0": dt.minute,
            "g": es_g,
            "lm": sum(partes),
            "partes": partes,
            "tipo": wr if es_g else "R",
            "id": r.get("roundId"),
            "ts": ts,
        }
        if key != cur:
            if cur is not None:
                horas.append((cur, tiros))
            cur = key
            tiros = [tiro]
        else:
            tiros.append(tiro)
    if cur is not None:
        horas.append((cur, tiros))
    return raw.get("actualizado"), raw.get("total_rondas"), horas


def flag19(tiros):
    ya = [t for t in tiros if t["g"] and t["m0"] <= 19]
    if len(ya) < 2:
        return False
    return (sum(t["lm"] for t in ya) / len(ya)) >= 68


def sim_hora(tiros, T=19, solo_zona=True):
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
            casa -= 600
            for i in range(3):
                acc[i] -= 200
            continue
        n_g += 1
        casa += 50 * t["lm"] - 600
        for i in range(3):
            acc[i] += 50 * t["partes"][i] - 200
        apostados.append(t)
        last_g = t["m0"]
    return n, n_g, casa, acc, apostados


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


def pack(nombre, filas):
    ns = gs = 0
    casas = []
    por = [[], [], []]
    for _, tiros in filas:
        n, ng, casa, acc, _ = sim_hora(tiros)
        ns += n
        gs += ng
        casas.append(casa)
        for i in range(3):
            por[i].append(acc[i])
    pozo = 60_000
    piso_pozo = pozo
    muertes = 0
    for p in casas:
        pozo += p
        piso_pozo = min(piso_pozo, pozo)
        if pozo <= 0:
            muertes += 1
            pozo = 60_000
    lineas = [
        f"  {nombre}: tiros {ns}  G {gs}  casa {sum(casas):+.0f}  "
        f"med/hora {median(casas) if casas else 0:+.0f}"
    ]
    lineas.append(
        f"    pozo $60k: suelo {piso_pozo:.0f}  vidas@0 {muertes}  / {len(casas)} h"
    )
    for i, nom in enumerate(NOMBRES):
        r, piso, fin = caminar(por[i])
        lineas.append(
            f"    {nom} $20k: pnl {sum(por[i]):+.0f}  "
            f"suelo {piso:.0f}  vidas@0 {r}  cierre {fin:.0f}"
        )
    return "\n".join(lineas)


def foto_colores(gs):
    if not gs:
        return ["  (sin G)"]
    n = len(gs)
    ceros = [sum(1 for t in gs if t["partes"][i] == 0) for i in range(3)]
    min_idx = Counter()
    max_idx = Counter()
    suma_p = [0, 0, 0]
    gordo = 0
    for t in gs:
        p = t["partes"]
        for i in range(3):
            suma_p[i] += p[i]
        mn = min(p)
        mx = max(p)
        for i in range(3):
            if p[i] == mn:
                min_idx[i] += 1
                break
        for i in range(3):
            if p[i] == mx:
                max_idx[i] += 1
                break
        if mx >= 0.55 * t["lm"] and t["lm"] > 0:
            gordo += 1
    tot = sum(suma_p) or 1
    L = [
        f"  G con corte {n}  ·  un color ≥55% del total: {gordo} ({100*gordo/n:.1f}%)",
        "  tajada media / % del lumen / veces 0 / veces el mínimo / veces el máximo:",
    ]
    for i, nom in enumerate(NOMBRES):
        media = suma_p[i] / n
        L.append(
            f"    {nom}: media {media:.1f}  "
            f"{100*suma_p[i]/tot:.1f}%  "
            f"cero {ceros[i]} ({100*ceros[i]/n:.1f}%)  "
            f"min {min_idx[i]}  max {max_idx[i]}"
        )
    return L


def main() -> None:
    actualizado, total, horas = parsear(API)
    flagged = [(k, t) for k, t in horas if flag19(t)]
    fuerte_f = []
    for k, t in flagged:
        s = sum(x["lm"] for x in t if x["g"])
        if banda(s) in ("fuerte", "muy_fuerte", "supernova"):
            fuerte_f.append((k, t))

    todos_g = [x for _, tiros in horas for x in tiros if x["g"] and x["lm"] > 0]
    flag_g = [x for _, tiros in flagged for x in tiros if x["g"] and x["lm"] > 0]
    zona_g = []
    for _, tiros in flagged:
        *_, ap = sim_hora(tiros)
        zona_g.extend(ap)

    recibos = []
    for t in zona_g:
        if 75 <= t["lm"] <= 90:
            recibos.append(t)
        if len(recibos) >= 8:
            break

    L = [
        "LOOK API — consolidado-jocker.json · corte real 0/1/2",
        f"actualizado {actualizado}  rondas {total}  horas {len(horas)}",
        f"indicio @19 {len(flagged)}  ·  de esas, cierran fuerte+ {len(fuerte_f)}",
        "Cobro: $50 × mult. 80× → $4.000 brutos. Casa = c0+c1+c2.",
        "Color a muerte. Silla zona tip±1 post-19.",
        "Solo lectura. Cero escritura a depuracion.",
        "",
        "— foto de las tajadas (toda la API, G con lumen>0) —",
    ]
    L.extend(foto_colores(todos_g))
    L.append("")
    L.append("— foto en horas con indicio @19 —")
    L.extend(foto_colores(flag_g))
    L.append("")
    L.append("— foto solo en tiros ZONA de esas horas —")
    L.extend(foto_colores(zona_g))
    L.append("")
    L.append("— recibos zona (G ~80, corte real) —")
    if recibos:
        for t in recibos:
            p = t["partes"]
            L.append(
                f"  {t['ts'][:16]}  {t['tipo']:7s}  lm {t['lm']:3d}  "
                f"c0={p[0]} c1={p[1]} c2={p[2]}  "
                f"bruto ${50*t['lm']}  neto ${50*t['lm']-600:+}  "
                f"wallets {50*p[0]-200:+}/{50*p[1]-200:+}/{50*p[2]-200:+}"
            )
    else:
        L.append("  (no hubo G 75–90 en zona+indicio)")
    L.append("")
    L.append("— libro: indicio @19 + zona (lo que se puede detectar) —")
    L.append(pack("indicio+zona", flagged))
    L.append("")
    L.append("— techo: esas que además cierran fuerte+ (oráculo) —")
    L.append(pack("oráculo fuerte+", fuerte_f))
    L.append("")
    L.extend(
        [
            "Lectura",
            "  · Casa usa el corte REAL. Ya no es 2/50/60 inventado.",
            "  · Si un índice se come el 0 más que los otros, ESA wallet",
            "    es la que puede secarse a muerte. Si los 0 rotan, no.",
            "  · c0/c1/c2 = claves API. Luck en pantalla: izq / centro / der.",
            "",
        ]
    )
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
