# -*- coding: utf-8 -*-
"""
Lab tono-paso. Juez: banda d≤1 tip vs mG, hora a hora.
Tono final = foto. Política = solo lo ya visto (causal).
No Jaccard. No P(tiro=G). No filtrar por “cayó en 3 tiros” como victoria.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
AE = ROOT / "lab-apostador-experto"
sys.path.insert(0, str(AE))
sys.path.insert(0, str(ROOT))

from core_ae import HOLDOUT, dist_anillo, load_horas_y_cinta, p30, split_holdout

lines: list[str] = []

# hod que en HOD_TABLA (brilloInfo) tienen moda opaca / P_O alta
HOD_APAG = {0, 1, 9, 10, 11, 12, 13, 14, 17, 18, 22}


def w(s: str = "") -> None:
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def es_g(t) -> bool:
    return str(getattr(t, "color", "")).upper().startswith("G")


def zona_tono(suma: int) -> str:
    if suma < 450:
        return "muy_apagado"
    if suma < 600:
        return "opaco"
    if suma < 850:
        return "normal"
    if suma < 1100:
        return "fuerte"
    return "muy_fuerte+"


def hod_de(tag: str) -> int:
    try:
        return int(str(tag).split("-")[0][1:])
    except (IndexError, ValueError):
        return -1


def pct(a, b) -> str:
    if not b:
        return "—"
    return f"{a / b * 100:.1f}%"


def tip_con_gap(T: int, gap: int) -> int | None:
    if T >= 59:
        return None
    return min(59, T + max(1, int(gap)))


def gs_de(h) -> list:
    out = []
    for t in getattr(h, "tiros", None) or []:
        if es_g(t):
            out.append(t)
    return out


def walk_hora(h) -> dict | None:
    gs = gs_de(h)
    if len(gs) < 2:
        return None
    lumens = [int(getattr(g, "lumen", 0) or 0) for g in gs]
    mins = [int(g.m0) % 60 for g in gs]
    idxs = []
    tiros = getattr(h, "tiros", None) or []
    for i, t in enumerate(tiros):
        if es_g(t):
            idxs.append(i)
    suma = sum(lumens)
    tono = zona_tono(suma)
    hod = hod_de(h.tag)
    eventos = []
    for k in range(1, len(gs)):
        T = mins[k - 1]
        real = mins[k]
        vistos = mins[:k]
        gaps_m = [vistos[i] - vistos[i - 1] for i in range(1, len(vistos))]
        shots = idxs[k] - idxs[k - 1]  # 1 = G pegada
        r_entre = shots - 1
        n_so_far = k
        suma_so = sum(lumens[:k])
        mean_so = suma_so / n_so_far
        med_gap = median(gaps_m) if gaps_m else None
        aletargado = False
        if n_so_far >= 2 and mean_so < 48:
            aletargado = True
        if med_gap is not None and med_gap >= 5:
            aletargado = True
        if T >= 20 and n_so_far <= 3:
            aletargado = True

        g_lc = p30(gaps_m, 5.0) if gaps_m else 5.0
        tips = {
            "LC-01": tip_con_gap(T, max(1, int(round(g_lc)))),
            "FELIZ+2": tip_con_gap(T, 2),
            "PASO_R": tip_con_gap(T, median([idxs[i] - idxs[i - 1] - 1 for i in range(1, k)]) if k >= 2 else 5),
            "FLOOR4": tip_con_gap(T, max(4 if aletargado else 1, int(round(g_lc)))),
            "FLOOR6": tip_con_gap(T, max(6 if aletargado else 1, int(round(g_lc)))),
            "HOD7": tip_con_gap(T, max(7 if (hod in HOD_APAG and not gaps_m) else 1, int(round(g_lc if gaps_m else (7 if hod in HOD_APAG else 5))))),
        }
        # primer tip sin huecos: HOD7 ya cambia fallback; LC-01 usa 5
        row = {
            "k": k,
            "T": T,
            "real": real,
            "r_entre": r_entre,
            "shots": shots,
            "aletargado": aletargado,
            "v3": 1 <= shots <= 3,
            "tips": tips,
        }
        eventos.append(row)
    return {
        "tag": h.tag,
        "tono": tono,
        "nG": len(gs),
        "hod": hod,
        "eventos": eventos,
    }


def agg_banda(eventos, key: str):
    xs = []
    for e in eventos:
        tip = e["tips"].get(key)
        if tip is None:
            continue
        xs.append(dist_anillo(tip, e["real"]) <= 1)
    return xs


def fila(nombre, xs, extra=""):
    n = len(xs)
    hits = sum(1 for x in xs if x)
    w(f"  {nombre:<12} | {n:>5} | {pct(hits, n):>8}{extra}")


def bloque(nombre, docs):
    w(f"\n════════ {nombre}  {len(docs)} horas ════════")
    evs = [e for d in docs for e in d["eventos"]]

    w("\n1. ¿LA PRÓXIMA G CAE EN 3 TIROS? (cobertura SEQUIA3 / P7-V3 / Next 3)")
    w("   Esto es el camino feliz. Se cuenta por EVENTO (tras cada G), y % de HORAS")
    w("   donde la mediana de huecos de ESA hora fue ≤3 tiros.")
    w(f"{'Tono':<14} | {'eventos':>7} | {'G en ≤3 tiros':>13} | {'horas paso≤3':>12} | {'med R-entre':>11}")
    by_t = defaultdict(list)
    for d in docs:
        by_t[d["tono"]].append(d)
    for tono in ("muy_apagado", "opaco", "normal", "fuerte", "muy_fuerte+"):
        xs = by_t[tono]
        if not xs:
            continue
        ev = [e for d in xs for e in d["eventos"]]
        v3 = sum(1 for e in ev if e["v3"])
        horas_feliz = sum(1 for d in xs if median(e["shots"] for e in d["eventos"]) <= 3)
        med_r = median(e["r_entre"] for e in ev) if ev else 0
        w(
            f"{tono:<14} | {len(ev):>7} | {pct(v3, len(ev)):>13} | "
            f"{pct(horas_feliz, len(xs)):>12} | {med_r:>9.0f} R"
        )

    w("\n2. BANDA d≤1 DEL TIP (todas las G-siguientes, sin filtrar por 3 tiros)")
    w(f"  {'política':<12} | {'N':>5} | {'banda':>8}")
    for key in ("LC-01", "FELIZ+2", "PASO_R", "FLOOR4", "FLOOR6", "HOD7"):
        fila(key, agg_banda(evs, key))

    w("\n3. MISMO TIP, PARTIDO POR TONO FINAL (foto · no se usó para decidir)")
    w(f"  {'tono':<14} | {'LC-01':>8} | {'FELIZ+2':>8} | {'FLOOR4':>8} | {'FLOOR6':>8} | {'N':>5}")
    for tono in ("muy_apagado", "opaco", "normal", "fuerte", "muy_fuerte+"):
        ev = [e for d in by_t[tono] for e in d["eventos"]]
        if not ev:
            continue

        def b(key):
            xs = agg_banda(ev, key)
            return pct(sum(xs), len(xs))

        w(
            f"  {tono:<14} | {b('LC-01'):>8} | {b('FELIZ+2'):>8} | "
            f"{b('FLOOR4'):>8} | {b('FLOOR6'):>8} | {len(ev):>5}"
        )

    w("\n4. PRIMER TIP DE LA HORA (aún no hay p30 · fallback)")
    primeros = [e for e in evs if e["k"] == 1]
    w(f"  {'política':<12} | {'N':>5} | {'banda':>8}   ← acá el tono aún no se vio")
    for key in ("LC-01", "FELIZ+2", "HOD7"):
        fila(key, agg_banda(primeros, key))
    w("  por tono final del cierre (lectura):")
    w(f"  {'tono':<14} | {'LC-01 (T+5)':>11} | {'FELIZ+2':>8} | {'HOD7':>8} | {'N':>4}")
    by_pt = defaultdict(list)
    for d in docs:
        for e in d["eventos"]:
            if e["k"] == 1:
                by_pt[d["tono"]].append(e)
    for tono in ("muy_apagado", "opaco", "normal", "fuerte", "muy_fuerte+"):
        ev = by_pt[tono]
        if not ev:
            continue

        def b(key):
            xs = agg_banda(ev, key)
            return pct(sum(xs), len(xs))

        w(f"  {tono:<14} | {b('LC-01'):>11} | {b('FELIZ+2'):>8} | {b('HOD7'):>8} | {len(ev):>4}")

    w("\n5. CUANDO YA SE VE ALETARGADO (causal: mean<48 o paso≥5 o T≥20 y ≤3 G)")
    ale = [e for e in evs if e["aletargado"]]
    vivo = [e for e in evs if not e["aletargado"]]
    w(f"  aletargado {len(ale)} eventos · camino vivo {len(vivo)}")
    w(f"  {'política':<12} | {'aletarg.':>8} | {'vivo':>8}")
    for key in ("LC-01", "FELIZ+2", "FLOOR4", "FLOOR6"):
        a = agg_banda(ale, key)
        v = agg_banda(vivo, key)
        w(f"  {key:<12} | {pct(sum(a), len(a)):>8} | {pct(sum(v), len(v)):>8}")

    # horas: ¿V3 cobró al menos una G de ESA hora?
    w("\n6. HORAS EN LAS QUE V3 TIENE ALGO QUE JUGAR (alguna G siguiente en ≤3 tiros)")
    w(f"  {'tono':<14} | {'horas':>5} | {'con ≥1 V3':>10} | {'med #V3':>8}")
    for tono in ("muy_apagado", "opaco", "normal", "fuerte", "muy_fuerte+"):
        xs = by_t[tono]
        if not xs:
            continue
        con = sum(1 for d in xs if any(e["v3"] for e in d["eventos"]))
        medn = median(sum(1 for e in d["eventos"] if e["v3"]) for d in xs)
        w(f"  {tono:<14} | {len(xs):>5} | {pct(con, len(xs)):>10} | {medn:>8.0f}")


def main() -> None:
    w("LAB TONO-PASO · Next 3 / P7-V3 vs camino aletargado")
    w("Juez: banda d≤1 minuto tip vs ESA G. Unidad: la hora.")
    w("Políticas causales. Tono final solo para leer, no para tipar.\n")

    horas, _ = load_horas_y_cinta()
    train, hold = split_holdout(horas, HOLDOUT)
    w(f"Cinta {len(horas)} h · train {len(train)} · holdout {len(hold)}")

    docs_tr = [d for h in train if (d := walk_hora(h))]
    docs_ho = [d for h in hold if (d := walk_hora(h))]
    bloque("TRAIN", docs_tr)
    bloque("HOLDOUT", docs_ho)

    w("\n════════════════════════════════ LECTURA ════════════════════════════════")
    w("LC-01 ya estira el tip cuando ESA hora ya mostró huecos largos.")
    w("Piso de tono (FLOOR4/6) y prior hod no deberían ganar si el p30 basta.")
    w("FELIZ+2 = Next 3 / V3 en minutos: camino de hora fuerte.")
    w("Si FELIZ pierde en apagada y LC-01 no, Next 3 debe hablar minutos,")
    w("no alargar la ventana de 3 tiros ni pintar color.")

    out = LAB / "reports" / "LAB_TONO_PASO.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    w(f"\nGuardado: {out}")


if __name__ == "__main__":
    main()
