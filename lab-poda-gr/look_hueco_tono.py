# -*- coding: utf-8 -*-
"""
LOOK: tipo de hueco (R entre G) × tono de hora × zona.
Unidad: la hora. Juez descriptivo de paso, no color global.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
AE = ROOT / "lab-apostador-experto"
sys.path.insert(0, str(AE))
sys.path.insert(0, str(ROOT))

from core_ae import HOLDOUT, load_horas_y_cinta, split_holdout

lines: list[str] = []


def w(s: str = "") -> None:
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def es_g(t) -> bool:
    return str(getattr(t, "color", "")).upper().startswith("G")


def zona(m: int) -> str:
    m = int(m) % 60
    if m <= 19:
        return "00-19"
    if m <= 39:
        return "20-39"
    return "40-59"


def tono_suma(suma: int) -> str:
    if suma < 450:
        return "muy_apagado"
    if suma < 600:
        return "opaco"
    if suma < 850:
        return "normal"
    if suma < 1100:
        return "fuerte"
    if suma < 1600:
        return "muy_fuerte"
    return "supernova"


def cubeta_r(n: int) -> str:
    if n <= 2:
        return "0-2"
    if n <= 5:
        return "3-5"
    if n <= 9:
        return "6-9"
    if n <= 14:
        return "10-14"
    return "15+"


def pct(a, b) -> str:
    if not b:
        return "—"
    return f"{a / b * 100:.1f}%"


def doc_hora(h) -> dict | None:
    tiros = getattr(h, "tiros", None) or []
    gs = [t for t in tiros if es_g(t)]
    if len(gs) < 2:
        return None
    idxs = [i for i, t in enumerate(tiros) if es_g(t)]
    huecos = []
    for a, b in zip(idxs, idxs[1:]):
        k = b - a - 1
        gb = tiros[b]
        lum = getattr(gb, "lumen", None) or 0
        huecos.append(
            {
                "k": k,
                "mG": int(gb.m0) % 60,
                "zona": zona(gb.m0),
                "lumen": int(lum),
                "tipo": getattr(gb, "tipo", None),
            }
        )
    suma = sum(x["lumen"] for x in huecos) + int(getattr(gs[0], "lumen", 0) or 0)
    mean = suma / len(gs) if gs else 0
    nG = len(gs)
    if nG <= 7:
        clima = "floja"
    elif nG >= 13:
        clima = "rica"
    else:
        clima = "normal"
    return {
        "tag": h.tag,
        "nG": nG,
        "clima": clima,
        "suma": suma,
        "mean": mean,
        "tono": tono_suma(suma),
        "huecos": huecos,
        "med_k": int(round(median(x["k"] for x in huecos))),
        "g0_m": int(gs[0].m0) % 60,
        "g0_lum": int(getattr(gs[0], "lumen", 0) or 0),
        "g0_tipo": getattr(gs[0], "tipo", None),
    }


def main() -> None:
    w("LOOK · hueco (R entre G) × tono × zona")
    w("Una hora = una ficha. No se unionan huecos de toda la cinta como juez.\n")

    horas, _ = load_horas_y_cinta()
    train, hold = split_holdout(horas, HOLDOUT)

    for nombre, lote in (("TRAIN", train), ("HOLDOUT", hold)):
        docs = [d for h in lote if (d := doc_hora(h))]
        w(f"════════ {nombre}  {len(docs)} horas con ≥2 G ════════")

        # 1) tono × paso de ESA hora + brillo medio de sus G
        w("\n1. TONO DE LA HORA (suma lumen G) × paso (mediana R-entre-G de ESA hora)")
        w(f"{'Tono':<13} | {'Horas':>5} | {'med nG':>7} | {'med meanG':>9} | {'med paso':>8} | {'paso 6+':>7} | {'paso 10+':>8}")
        w(f"{'-'*13}-+-{'-'*5}-+-{'-'*7}-+-{'-'*9}-+-{'-'*8}-+-{'-'*7}-+-{'-'*8}")
        by_t = defaultdict(list)
        for d in docs:
            by_t[d["tono"]].append(d)
        for tono in ("muy_apagado", "opaco", "normal", "fuerte", "muy_fuerte", "supernova"):
            xs = by_t[tono]
            if not xs:
                continue
            w(
                f"{tono:<13} | {len(xs):>5} | {median(x['nG'] for x in xs):>7.0f} | "
                f"{median(x['mean'] for x in xs):>9.0f} | {median(x['med_k'] for x in xs):>6.0f} R | "
                f"{pct(sum(1 for x in xs if x['med_k']>=6), len(xs)):>7} | "
                f"{pct(sum(1 for x in xs if x['med_k']>=10), len(xs)):>8}"
            )

        # 2) zona: en qué andén caen las G de cada tono (promedio de FRACCIÓN por hora)
        w("\n2. ZONA · fracción media de las G de ESA hora (no se tiran todas las G a un saco)")
        w(f"{'Tono':<13} | {'00-19':>8} | {'20-39':>8} | {'40-59':>8} | hueco med al caer en cada zona")
        for tono in ("muy_apagado", "opaco", "normal", "fuerte", "muy_fuerte"):
            xs = by_t[tono]
            if not xs:
                continue
            f19, f39, f59 = [], [], []
            k19, k39, k59 = [], [], []
            for d in xs:
                n = len(d["huecos"]) + 1
                # G0 no tiene hueco previo intra-hora; las demás sí
                c = Counter()
                c[zona(d["g0_m"])] += 1
                for hco in d["huecos"]:
                    c[hco["zona"]] += 1
                    if hco["zona"] == "00-19":
                        k19.append(hco["k"])
                    elif hco["zona"] == "20-39":
                        k39.append(hco["k"])
                    else:
                        k59.append(hco["k"])
                f19.append(c["00-19"] / n)
                f39.append(c["20-39"] / n)
                f59.append(c["40-59"] / n)
            def md(a):
                return f"{median(a):.0f}" if a else "—"
            w(
                f"{tono:<13} | {median(f19)*100:6.0f}% | {median(f39)*100:6.0f}% | {median(f59)*100:6.0f}% | "
                f"k {md(k19)} / {md(k39)} / {md(k59)}"
            )

        # 3) Relato: sequía larga y DESPUÉS racimo corto EN LA MISMA HORA
        w("\n3. RELATO (misma hora): ¿hay un hueco ≥6 y los 2 siguientes son cortos (≤3)?")
        w("   Eso es 'apagón y luego 2–3 G juntas'. Se cuenta HORAS que lo cumplen, no huecos.")
        w(f"{'Tono':<13} | {'Horas':>5} | {'tuvo k≥6':>9} | {'y luego racimo':>14} | {'k≥11 y racimo':>14}")
        for tono in ("muy_apagado", "opaco", "normal", "fuerte", "muy_fuerte"):
            xs = by_t[tono]
            if not xs:
                continue
            tuvo6 = rac = rac11 = 0
            for d in xs:
                ks = [h["k"] for h in d["huecos"]]
                ok6 = False
                ok_rac = False
                ok11 = False
                for i, k in enumerate(ks):
                    if k >= 6:
                        ok6 = True
                        sig = ks[i + 1 : i + 3]
                        if len(sig) >= 1 and all(x <= 3 for x in sig):
                            ok_rac = True
                        if k >= 11 and len(sig) >= 1 and all(x <= 3 for x in sig):
                            ok11 = True
                if ok6:
                    tuvo6 += 1
                if ok_rac:
                    rac += 1
                if ok11:
                    rac11 += 1
            w(
                f"{tono:<13} | {len(xs):>5} | {pct(tuvo6, len(xs)):>9} | {pct(rac, len(xs)):>14} | {pct(rac11, len(xs)):>14}"
            )

        # 4) ¿Las G de horas apagadas son de lumen bajo? (mean de ESA hora)
        w("\n4. ¿G chicas en hora apagada? mean lumen de las G de ESA hora")
        w("   Cuidado: el tono ES la suma. Mean bajo + pocas G = apagada por construcción.")
        w("   Por eso se mira también el clima (nG), que no es el tono.")
        for tono in ("muy_apagado", "opaco", "normal", "fuerte", "muy_fuerte"):
            xs = by_t[tono]
            if not xs:
                continue
            bajos = sum(1 for x in xs if x["mean"] < 50)
            tipos = Counter()
            for d in xs:
                if d["g0_tipo"] is not None:
                    tipos[int(d["g0_tipo"])] += 1
                for hco in d["huecos"]:
                    if hco["tipo"] is not None:
                        tipos[int(hco["tipo"])] += 1
            tot_t = sum(tipos.values()) or 1
            mix = "  ".join(f"G{t}:{tipos[t]/tot_t*100:.0f}%" for t in (1, 2, 3, 4) if tipos[t])
            w(
                f"  {tono:<13}  mediana meanG={median(x['mean'] for x in xs):.0f}"
                f"  · meanG<50: {pct(bajos, len(xs))}  · tinta {mix}"
            )

        # 5) Mismo relato, pero por CUPO (floja/normal/rica), no por suma
        w("\n5. CUPO (nG) — el mismo relato, sin mezclarlo con el tono de luz")
        by_c = defaultdict(list)
        for d in docs:
            by_c[d["clima"]].append(d)
        w(f"{'Clima':<8} | {'Horas':>5} | {'med paso':>8} | {'k≥6':>7} | {'k≥6+racimo':>11} | {'med meanG':>9}")
        for clima in ("floja", "normal", "rica"):
            xs = by_c[clima]
            if not xs:
                continue
            rac = 0
            tuvo6 = 0
            for d in xs:
                ks = [h["k"] for h in d["huecos"]]
                ok6 = False
                ok_rac = False
                for i, k in enumerate(ks):
                    if k >= 6:
                        ok6 = True
                        sig = ks[i + 1 : i + 3]
                        if len(sig) >= 1 and all(x <= 3 for x in sig):
                            ok_rac = True
                if ok6:
                    tuvo6 += 1
                if ok_rac:
                    rac += 1
            w(
                f"{clima:<8} | {len(xs):>5} | {median(x['med_k'] for x in xs):>6.0f} R | "
                f"{pct(tuvo6, len(xs)):>7} | {pct(rac, len(xs)):>11} | {median(x['mean'] for x in xs):>9.0f}"
            )

        # 6) Tras sequía ≥6: lumen de ESA G vs lumen de las 2 que siguen (misma hora)
        w("\n6. Tras el primer hueco ≥6 de la hora: ¿esa G es chica? ¿las que siguen también?")
        w(f"{'Tono':<13} | {'Horas c/k≥6':>12} | {'med lum G-corte':>15} | {'med lum 2 sig':>13}")
        for tono in ("muy_apagado", "opaco", "normal", "fuerte", "muy_fuerte"):
            xs = by_t[tono]
            lum_corte, lum_sig = [], []
            n6 = 0
            for d in xs:
                for i, hco in enumerate(d["huecos"]):
                    if hco["k"] < 6:
                        continue
                    n6 += 1
                    lum_corte.append(hco["lumen"])
                    sigs = [x["lumen"] for x in d["huecos"][i + 1 : i + 3]]
                    if sigs:
                        lum_sig.append(median(sigs))
                    break
            if not n6:
                continue
            w(
                f"{tono:<13} | {n6:>12} | {median(lum_corte):>15.0f} | "
                f"{(median(lum_sig) if lum_sig else 0):>13.0f}"
            )

    w("\n════════════════════════════════ LECTURA ════════════════════════════════")
    w("El tono (suma) y el paso (R entre G) se mueven juntos porque la hora")
    w("apagada suele tener menos G: el palo se estira. No es una zona del reloj")
    w("que 'prefiera' el hueco largo.")
    w("El racimo corto DESPUÉS de un hueco ≥6 existe, pero no es ley de las")
    w("apagadas: también pasa en fuertes. No sentar.")

    out = LAB / "reports" / "LOOK_HUECO_TONO.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    w(f"\nGuardado: {out}")


if __name__ == "__main__":
    main()
