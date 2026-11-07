# -*- coding: utf-8 -*-
"""
LOOK: la hora como cosa elástica (bloques / vida).
Unidad = la hora. Dentro de la hora = racha de cubos, no pool de G.
Cuerpo = train histórico (mismo corte que LOOK_HORA_FORMAS).
Hold 72 = testigo chico. Cero Jaccard. Cero tip. Cero cable.
"""
from __future__ import annotations

import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
AE = ROOT / "lab-apostador-experto"
GEXP = ROOT / "lab-g-explosion"
sys.path.insert(0, str(GEXP))
sys.path.insert(0, str(AE))
sys.path.insert(0, str(ROOT))

from core_ae import HOLDOUT, load_horas_y_cinta, split_holdout
from core_ex import DATA_DETAIL, EXTRA

lines: list[str] = []

TONOS = ("muy_apagado", "opaco", "normal", "fuerte", "muy_fuerte", "supernova")
TONOS_TAB = ("muy_apagado", "opaco", "normal", "fuerte", "muy_fuerte+")
CLIMAS = ("floja", "normal", "rica")

# Oficio: 5 cubos. Colapsa el catálogo de LOOK_HORA_FORMAS (R entre G).
# No se inventan 20. 9–10 R (resto de 8-10R) entra en cola con G-12R-G.
CUBOS = ("pegada", "corto", "medio", "cola", "sequia")
CUBO_TXT = {
    "pegada": "pegada 0–1 R  (0_tren + 1_GRG · 2G / casi)",
    "corto": "corto  2–4 R  (2_GRRG + 3-4R · G-RR-G / paso 4)",
    "medio": "medio  5–8 R  (5R + 6-7R + el 8 de 8-10R · G-6R-G)",
    "cola": "cola   9–15 R (9-10 + 11-15R · G-12R-G / 12–15)",
    "sequia": "sequia ≥16 R  (16R+ · 20 R y más)",
}


def w(s: str = "") -> None:
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def pct(a, b, dec: int = 1) -> str:
    if not b:
        return "—"
    return f"{a / b * 100:.{dec}f}%"


def es_g(t) -> bool:
    return str(getattr(t, "color", "")).upper().startswith("G")


def es_nucleo(t) -> bool:
    if not es_g(t):
        return False
    return getattr(t, "tipo", None) != 5


def lumen_de(t) -> int:
    lm = getattr(t, "lumen", None)
    if lm is None:
        lm = getattr(t, "vecino", None)
    try:
        return int(lm or 0)
    except (TypeError, ValueError):
        return 0


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


def tono_tab(tono: str) -> str:
    if tono in ("muy_fuerte", "supernova"):
        return "muy_fuerte+"
    return tono


def clima_nG(n: int) -> str:
    if n <= 7:
        return "floja"
    if n >= 13:
        return "rica"
    return "normal"


def day_key(tag: str) -> str:
    cuerpo = str(tag).strip().lower()
    if cuerpo.startswith("h") and "-" in cuerpo:
        return cuerpo.split("-", 1)[1]
    return cuerpo


def hod_de(tag: str) -> int | None:
    cuerpo = str(tag).strip().lower()
    if cuerpo.startswith("h") and "-" in cuerpo:
        raw = cuerpo.split("-", 1)[0][1:]
        try:
            return int(raw)
        except ValueError:
            return None
    return None


def cubo_r(k: int) -> str:
    if k <= 1:
        return "pegada"
    if k <= 4:
        return "corto"
    if k <= 8:
        return "medio"
    if k <= 15:
        return "cola"
    return "sequia"


def cubeta_r_cat(k: int) -> str:
    if k <= 0:
        return "0_tren"
    if k == 1:
        return "1_GRG"
    if k == 2:
        return "2_GRRG"
    if k <= 4:
        return "3-4R"
    if k == 5:
        return "5R"
    if k <= 7:
        return "6-7R"
    if k <= 10:
        return "8-10R"
    if k <= 15:
        return "11-15R"
    return "16R+"


def moda_de(cnt: Counter) -> tuple[str | None, bool]:
    if not cnt:
        return None, False
    nombre, n = cnt.most_common(1)[0]
    empate = sum(1 for _, c in cnt.items() if c == n) > 1
    return (None if empate else nombre), empate


def rachas_de(cubos: list[str]) -> list[tuple[str, int, int, int]]:
    """(cubo, largo, i0, i1) sobre la lista de huecos."""
    out: list[tuple[str, int, int, int]] = []
    if not cubos:
        return out
    i0 = 0
    cur = cubos[0]
    for i, c in enumerate(cubos[1:], start=1):
        if c != cur:
            out.append((cur, i - i0, i0, i - 1))
            i0 = i
            cur = c
    out.append((cur, len(cubos) - i0, i0, len(cubos) - 1))
    return out


def max_ventana20(mins: list[int]) -> tuple[int, int]:
    """Máx G en una ventana lineal de 20 min. Devuelve (n, start).
    Empates: start = mediana de los lo que empatan (no el primero: eso
    apilaba calor en 00–09)."""
    if not mins:
        return 0, 0
    scores = [(sum(1 for m in mins if lo <= m < lo + 20), lo) for lo in range(0, 41)]
    best_n = max(n for n, _ in scores)
    ties = [lo for n, lo in scores if n == best_n]
    return best_n, ties[len(ties) // 2]


def span_mitad_densa(mins: list[int]) -> int | None:
    """Minutos que ocupan el grupo más apretado de ceil(n/2) G consecutivas."""
    if len(mins) < 2:
        return None
    ys = sorted(mins)
    k = max(2, math.ceil(len(ys) / 2))
    best = 60
    for i in range(0, len(ys) - k + 1):
        best = min(best, ys[i + k - 1] - ys[i] + 1)
    return best


def mejor_corte(mins: list[int]) -> tuple[int, float, float, float] | None:
    """Split s en 12..48 que maximiza |dens_der - dens_izq|."""
    if len(mins) < 4:
        return None
    best = None
    for s in range(12, 49):
        iz = sum(1 for m in mins if m < s)
        de = len(mins) - iz
        di = iz / s
        dd = de / (60 - s)
        score = abs(dd - di)
        if best is None or score > best[1]:
            best = (s, score, di, dd)
    return best


def score_corte_en(mins: list[int], s: int) -> float:
    iz = sum(1 for m in mins if m < s)
    de = len(mins) - iz
    if s <= 0 or s >= 60:
        return 0.0
    return abs(de / (60 - s) - iz / s)


def nulo_max20(nG: int, nsim: int = 2500) -> tuple[float, float]:
    """Mediana y p90 de (máx G en ventana 20) / nG si los minutos son uniformes."""
    if nG < 2:
        return 0.0, 0.0
    rng = random.Random(nG * 31 + 7)
    fracs: list[float] = []
    slots = list(range(60))
    for _ in range(nsim):
        ms = rng.sample(slots, nG)
        mx, _ = max_ventana20(ms)
        fracs.append(mx / nG)
    fracs.sort()
    med = fracs[len(fracs) // 2]
    p90 = fracs[int(len(fracs) * 0.90)]
    return med, p90


_NULO20: dict[int, tuple[float, float]] = {}


def nulo20(nG: int) -> tuple[float, float]:
    if nG not in _NULO20:
        _NULO20[nG] = nulo_max20(nG)
    return _NULO20[nG]


def binom_p_ge(n: int, k: int) -> float:
    """P(X>=k) X~Bin(n, 1/2)."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    acc = 0
    for i in range(k, n + 1):
        acc += math.comb(n, i)
    return acc / (2 ** n)


def doc_hora(h) -> dict | None:
    tiros = list(getattr(h, "tiros", None) or [])
    nucleos = [t for t in tiros if es_nucleo(t)]
    extras = [t for t in tiros if es_g(t) and not es_nucleo(t)]
    if not nucleos:
        return None
    idxs = [i for i, t in enumerate(tiros) if es_nucleo(t)]
    mins = [int(t.m0) % 60 for t in nucleos]
    lums = [lumen_de(t) for t in nucleos]
    pasos: list[int] = []
    rs: list[int] = []
    for a, b in zip(idxs, idxs[1:]):
        paso = b - a
        pasos.append(paso)
        rs.append(paso - 1)

    cubos = [cubo_r(k) for k in rs]
    cnt_c = Counter(cubos)
    cnt_r = Counter(cubeta_r_cat(k) for k in rs)
    moda_r, emp_r = moda_de(cnt_r)
    rachas = rachas_de(cubos)

    n_hue = len(cubos)
    n_cubos = len(cnt_c)
    top = cnt_c.most_common()
    top2 = sum(c for _, c in top[:2]) if top else 0
    top3 = sum(c for _, c in top[:3]) if top else 0
    cubren2 = (top2 / n_hue >= (2 / 3)) if n_hue else False
    cubren3 = (top3 / n_hue >= 0.85) if n_hue else False

    bloques = [r for r in rachas if r[1] >= 2]
    n_bloques = len(bloques)
    hue_en_bloque = sum(r[1] for r in bloques)
    frac_bloque = (hue_en_bloque / n_hue) if n_hue else 0.0
    cubos_bloque = {r[0] for r in bloques}

    tiene_peg = "pegada" in cnt_c
    tiene_med = "medio" in cnt_c
    tiene_col = "cola" in cnt_c
    bloque_med = "medio" in cubos_bloque
    bloque_col = "cola" in cubos_bloque
    bloque_peg = "pegada" in cubos_bloque

    # pegada en medio de dos rachas distintas (no solo “hay una pegada”)
    peg_entre = False
    for i, r in enumerate(rachas):
        if r[0] != "pegada":
            continue
        if 0 < i < len(rachas) - 1:
            peg_entre = True
            break

    nG = len(nucleos)
    n1 = sum(1 for m in mins if m < 30)
    n2 = nG - n1
    lum1 = sum(lm for m, lm in zip(mins, lums) if m < 30)
    lum2 = sum(lums) - lum1
    t0 = sum(1 for m in mins if m < 20)
    t1 = sum(1 for m in mins if 20 <= m < 40)
    t2 = nG - t0 - t1
    max_ter = max(t0, t1, t2) if nG else 0
    ter_gana = None
    if nG:
        if t0 == max_ter and t0 > t1 and t0 > t2:
            ter_gana = "00-19"
        elif t1 == max_ter and t1 > t0 and t1 > t2:
            ter_gana = "20-39"
        elif t2 == max_ter and t2 > t0 and t2 > t1:
            ter_gana = "40-59"

    mx20, start20 = max_ventana20(mins)
    span50 = span_mitad_densa(mins)
    cut = mejor_corte(mins)
    cut_s = cut[0] if cut else None
    cut_score = cut[1] if cut else None
    score30 = score_corte_en(mins, 30) if nG >= 4 else 0.0

    # bordes de racha = minuto de la G que cierra un cubo y abre otro
    bordes: list[int] = []
    for i in range(1, len(rachas)):
        # la G compartida es el extremo derecho del hueco anterior = nucleos[rachas[i-1][3]+1]
        g_idx = rachas[i - 1][3] + 1
        if 0 <= g_idx < len(mins):
            bordes.append(mins[g_idx])

    cut_cerca_racha = False
    cut_cerca_30 = False
    if cut_s is not None and nG >= 6 and n_hue >= 3:
        d30 = abs(cut_s - 30)
        if bordes:
            d_r = min(abs(cut_s - b) for b in bordes)
            cut_cerca_racha = d_r <= 6 and d_r < d30
            cut_cerca_30 = d30 <= 6 and d30 <= d_r
        else:
            cut_cerca_30 = d30 <= 6

    # vuelco de densidad (mitad). Umbral crudo; el nulo se discute en lectura.
    dlt = n2 - n1
    vuelco_a_gen = n1 <= 2 and n2 >= 5 and nG >= 6
    vuelco_a_apa = n2 <= 2 and n1 >= 5 and nG >= 6
    inclina = abs(dlt) >= 3 and nG >= 6

    # tono de mitad (suma lumen de ESA mitad; no es cubeta de hora)
    def tono_mitad(suma: int, n: int) -> str:
        if n == 0:
            return "vacia"
        if suma < 180:
            return "apagada"
        if suma < 350:
            return "opaca"
        return "generosa"

    tm1, tm2 = tono_mitad(lum1, n1), tono_mitad(lum2, n2)
    vida_tono = tm1 == "apagada" and tm2 == "generosa"
    vida_tono_inv = tm1 == "generosa" and tm2 == "apagada"

    nulo_med, nulo_p90 = nulo20(nG) if nG >= 4 else (0.0, 0.0)
    frac20 = (mx20 / nG) if nG else 0.0
    caliente_vs_nulo = nG >= 6 and frac20 >= nulo_p90 and nulo_p90 > 0

    return {
        "h": h,
        "tag": getattr(h, "tag", "?"),
        "day": day_key(getattr(h, "tag", "")),
        "hod": hod_de(getattr(h, "tag", "")),
        "nG": nG,
        "n_extra": len(extras),
        "suma": sum(lums),
        "tono": tono_suma(sum(lums)),
        "clima": clima_nG(nG),
        "mins": mins,
        "lums": lums,
        "rs": rs,
        "cubos": cubos,
        "cnt_c": cnt_c,
        "n_hue": n_hue,
        "n_cubos": n_cubos,
        "top2": top2,
        "top3": top3,
        "cubren2": cubren2,
        "cubren3": cubren3,
        "rachas": rachas,
        "n_rachas": len(rachas),
        "n_bloques": n_bloques,
        "frac_bloque": frac_bloque,
        "cubos_bloque": cubos_bloque,
        "emp_r": emp_r,
        "moda_r": moda_r,
        "tiene_peg": tiene_peg,
        "tiene_med": tiene_med,
        "tiene_col": tiene_col,
        "bloque_med": bloque_med,
        "bloque_col": bloque_col,
        "bloque_peg": bloque_peg,
        "peg_entre": peg_entre,
        "n1": n1,
        "n2": n2,
        "lum1": lum1,
        "lum2": lum2,
        "t0": t0,
        "t1": t1,
        "t2": t2,
        "max_ter": max_ter,
        "ter_gana": ter_gana,
        "mx20": mx20,
        "start20": start20,
        "frac20": frac20,
        "span50": span50,
        "cut_s": cut_s,
        "cut_score": cut_score,
        "score30": score30,
        "cut_cerca_racha": cut_cerca_racha,
        "cut_cerca_30": cut_cerca_30,
        "dlt": dlt,
        "vuelco_a_gen": vuelco_a_gen,
        "vuelco_a_apa": vuelco_a_apa,
        "inclina": inclina,
        "tm1": tm1,
        "tm2": tm2,
        "vida_tono": vida_tono,
        "vida_tono_inv": vida_tono_inv,
        "nulo20_med": nulo_med,
        "nulo20_p90": nulo_p90,
        "caliente_vs_nulo": caliente_vs_nulo,
        "bordes": bordes,
    }


def docs_de(horas) -> list[dict]:
    out = []
    for h in horas:
        d = doc_hora(h)
        if d:
            out.append(d)
    return out


def con_hue(docs: list[dict], n: int = 1) -> list[dict]:
    return [d for d in docs if d["n_hue"] >= n]


def fila_n(xs: list[dict], pred, n: int | None = None) -> str:
    n = n if n is not None else len(xs)
    k = sum(1 for d in xs if pred(d))
    return f"{k}/{n} ({pct(k, n)})"


def tabla_mezcla(xs: list[dict], titulo: str) -> None:
    w(titulo)
    if not xs:
        w("   (vacío)")
        return
    n = len(xs)
    c_n = Counter(min(d["n_cubos"], 4) for d in xs)
    w(
        f"   n_cubos distintos:  1={c_n[1]}  2={c_n[2]}  3={c_n[3]}  4+={c_n[4]}"
        f"   · de {n} h"
    )
    w(
        f"   2 cubos cubren ≥2/3 de SUS huecos: {fila_n(xs, lambda d: d['cubren2'])}"
    )
    w(
        f"   3 cubos cubren ≥85% de SUS huecos: {fila_n(xs, lambda d: d['cubren3'])}"
    )
    c_b = Counter(min(d["n_bloques"], 3) for d in xs)
    w(
        f"   n_bloques (racha ≥2 del mismo cubo):  0={c_b[0]}  1={c_b[1]}  "
        f"2={c_b[2]}  3+={c_b[3]}"
    )
    w(
        f"   ≥ mitad de huecos viven en alguna racha≥2: "
        f"{fila_n(xs, lambda d: d['frac_bloque'] >= 0.5)}"
    )

    w("   rejilla n_cubos × n_bloques (n HORAS, no % de G):")
    w("            bloques0  bloques1  bloques2  bloques3+")
    for nc, etq in ((1, "1 cubo "), (2, "2 cubos"), (3, "3 cubos"), (4, "4+    ")):
        row = f"     {etq}  "
        for nb in (0, 1, 2, 3):
            k = sum(
                1
                for d in xs
                if (d["n_cubos"] == nc if nc < 4 else d["n_cubos"] >= 4)
                and min(d["n_bloques"], 3) == nb
            )
            row += f"{k:>9} "
        w(row)

    w(
        f"   monotipo (1 cubo): {c_n[1]}/{n}   "
        f"mezcla 2: {c_n[2]}/{n}   mezcla 3: {c_n[3]}/{n}   4+: {c_n[4]}/{n}"
    )
    w(
        f"   presencia medio+cola (huecos, no racha): "
        f"{fila_n(xs, lambda d: d['tiene_med'] and d['tiene_col'])}"
    )
    w(
        f"   presencia medio+cola+pegada: "
        f"{fila_n(xs, lambda d: d['tiene_med'] and d['tiene_col'] and d['tiene_peg'])}"
    )
    w(
        f"   BLOQUE medio (≥2) y BLOQUE cola (≥2): "
        f"{fila_n(xs, lambda d: d['bloque_med'] and d['bloque_col'])}"
    )
    w(
        f"   esos dos bloques + pegada en la hora: "
        f"{fila_n(xs, lambda d: d['bloque_med'] and d['bloque_col'] and d['tiene_peg'])}"
    )
    w(
        f"   pegada EN MEDIO de dos rachas (no solo al borde): "
        f"{fila_n(xs, lambda d: d['peg_entre'])}"
    )


def bloque_cortes(docs: list[dict], key_fn, orden, titulo: str, min_hue: int = 3) -> None:
    w(titulo)
    w(f"   (solo horas con ≥{min_hue} huecos G→G; si no, no hay 2–3 tipos que mezclar)")
    by = defaultdict(list)
    for d in docs:
        if d["n_hue"] >= min_hue:
            by[key_fn(d)].append(d)
    for nombre in orden:
        xs = by[nombre]
        if not xs:
            continue
        w(f"\n── {nombre}  ·  {len(xs)} horas ──")
        if len(xs) < 12:
            w(f"   (celda chica: n={len(xs)} HORAS. No coronar.)")
        tabla_mezcla(xs, "")


def bloque_empate(docs: list[dict]) -> None:
    w("\nA2. EL EMPATE DE LOOK_HORA_FORMAS ¿ES MEZCLA DE 2–3 BLOQUES?")
    w("   Empate = dos cubetas del CATÁLOGO (0_tren…16R+) empatan en ESA hora.")
    w("   Aquí se cruza con n_cubos de oficio y con rachas≥2.")
    pares = con_hue(docs, 3)
    emp = [d for d in pares if d["emp_r"]]
    noemp = [d for d in pares if not d["emp_r"]]
    w(f"   horas ≥3 huecos: {len(pares)}  ·  empate-catálogo: {len(emp)}  ·  con moda: {len(noemp)}")
    if emp:
        w("   — entre las EMPATE —")
        tabla_mezcla(emp, "")
    if noemp:
        w("   — entre las que SÍ tienen moda de catálogo —")
        c = Counter(min(d["n_cubos"], 4) for d in noemp)
        w(
            f"   n_cubos 1={c[1]}  2={c[2]}  3={c[3]}  4+={c[4]}  "
            f"· bloques≥2: {sum(1 for d in noemp if d['n_bloques'] >= 2)}/{len(noemp)}"
        )


def bloque_vida(docs: list[dict], titulo: str) -> None:
    w(titulo)
    w("   Densidad DENTRO de la hora. No es “zona manda el aterrizaje del hueco”.")
    xs = [d for d in docs if d["nG"] >= 6]
    if not xs:
        w("   (pocas horas con nG≥6)")
        return
    n = len(xs)
    w(f"   horas nG≥6: {n}  (nG chico inventa “concentración”; por eso el corte)")

    w("\n   B1. Mitades 0–29 vs 30–59  (nG de ESA mitad)")
    eq = sum(1 for d in xs if abs(d["dlt"]) <= 1)
    mas2 = sum(1 for d in xs if d["dlt"] >= 3)
    mas1 = sum(1 for d in xs if d["dlt"] <= -3)
    w(f"     equilibrada |Δ|≤1: {eq}/{n} ({pct(eq, n)})")
    w(f"     inclina 2ª mitad (nG_30-59 ≥ nG_0-29 + 3): {mas2}/{n} ({pct(mas2, n)})")
    w(f"     inclina 1ª mitad (simétrico): {mas1}/{n} ({pct(mas1, n)})")
    vg = sum(1 for d in xs if d["vuelco_a_gen"])
    va = sum(1 for d in xs if d["vuelco_a_apa"])
    w(f"     vuelco apagado→generoso (1ª ≤2 G y 2ª ≥5): {vg}/{n} ({pct(vg, n)})")
    w(f"     vuelco generoso→apagado: {va}/{n} ({pct(va, n)})")
    vt = sum(1 for d in xs if d["vida_tono"])
    vti = sum(1 for d in xs if d["vida_tono_inv"])
    w(f"     tono-mitad apagada→generosa (lumen): {vt}/{n} ({pct(vt, n)})")
    w(f"     tono-mitad generosa→apagada: {vti}/{n} ({pct(vti, n)})")
    # nulo binomial a nG mediano
    med_n = int(median(d["nG"] for d in xs))
    lo = math.floor((med_n - 3) / 2)
    p_inclina = (1 - binom_p_ge(med_n, lo + 1)) + binom_p_ge(med_n, math.ceil((med_n + 3) / 2))
    w(
        f"     nulo (G iid uniformes, nG med={med_n}): P(|Δ|≥3) ≈ {p_inclina * 100:.0f}%. "
        f"Si lo observado ≈ eso, la “mitad” es ruido de nG."
    )

    w("\n   B2. Tercios 00–19 / 20–39 / 40–59 · densidad de G, no hueco")
    gana = Counter(d["ter_gana"] for d in xs if d["ter_gana"])
    emp_t = n - sum(gana.values())
    w(
        f"     tercio con más G (sin empate):  00-19={gana['00-19']}  "
        f"20-39={gana['20-39']}  40-59={gana['40-59']}  empate={emp_t}"
    )
    conc50 = sum(1 for d in xs if d["max_ter"] * 2 >= d["nG"])
    w(
        f"     un tercio se lleva ≥50% de las G: {conc50}/{n} ({pct(conc50, n)})"
    )
    med_frac_t = median(d["max_ter"] / d["nG"] for d in xs)
    w(f"     mediana de (máx tercio / nG): {med_frac_t:.2f}  (uniforme ≈ 0.40–0.45)")
    if gana["00-19"] + gana["20-39"] + gana["40-59"] >= 12:
        totg = gana["00-19"] + gana["20-39"] + gana["40-59"]
        w(
            "     si los tres tercios se reparte el “quién gana” ≈ igual, "
            f"el reloj 00/20/40 NO corta densidad ({gana['00-19']}/{gana['20-39']}/{gana['40-59']} de {totg})."
        )

    w("\n   B3. Tramo caliente (ventana 20 min que MÁS G junta, start libre)")
    w("     No es zona 00/20/40: el start puede ser cualquier minuto 0..40.")
    med_f = median(d["frac20"] for d in xs)
    p50 = sum(1 for d in xs if d["frac20"] >= 0.5)
    p60 = sum(1 for d in xs if d["frac20"] >= 0.6)
    cal = sum(1 for d in xs if d["caliente_vs_nulo"])
    w(f"     mediana máx-ventana20 / nG: {med_f:.2f}")
    w(f"     horas con ≥50% G en algún tramo de 20 min: {p50}/{n} ({pct(p50, n)})")
    w(f"     horas con ≥60% G en algún tramo de 20 min: {p60}/{n} ({pct(p60, n)})")
    w(
        f"     por encima del p90 del nulo (minutos iid): {cal}/{n} ({pct(cal, n)})"
        "  ← si ≈10%, es el nulo"
    )
    # dónde arranca el tramo caliente
    bins = Counter()
    for d in xs:
        bins[f"{(d['start20'] // 10) * 10:02d}-{ (d['start20'] // 10) * 10 + 9:02d}"] += 1
    w(
        "     start del tramo caliente (decenas): "
        + "  ".join(f"{k}={bins[k]}" for k in sorted(bins))
    )
    w("     si el start se reparte, el calor NO es el reloj 00/20/40.")

    sp = [d["span50"] for d in xs if d["span50"] is not None]
    if sp:
        w(
            f"     span de la mitad más apretada de G: med {median(sp):.0f} min  "
            f"· ≤15 min {sum(1 for x in sp if x <= 15)}/{len(sp)}  "
            f"· ≤20 min {sum(1 for x in sp if x <= 20)}/{len(sp)}"
        )

    w("\n   B4. Corte (mejor split 12..48) vs :30 vs borde de racha")
    cortes = [d for d in xs if d["cut_s"] is not None]
    if cortes:
        med_s = median(d["cut_s"] for d in cortes)
        cerca30 = sum(1 for d in cortes if abs(d["cut_s"] - 30) <= 6)
        mejor_que_30 = sum(
            1
            for d in cortes
            if d["cut_score"] is not None and d["score30"] > 0 and d["cut_score"] >= 1.5 * d["score30"]
        )
        w(f"     horas con corte: {len(cortes)}  · mediana del split: min {med_s:.0f}")
        w(f"     split cae cerca de :30 (±6): {cerca30}/{len(cortes)} ({pct(cerca30, len(cortes))})")
        w(
            f"     el mejor split es ≥1.5× más marcado que partir en 30: "
            f"{mejor_que_30}/{len(cortes)} ({pct(mejor_que_30, len(cortes))})"
        )
        cr = sum(1 for d in cortes if d["cut_cerca_racha"])
        c30 = sum(1 for d in cortes if d["cut_cerca_30"])
        w(
            f"     split más cerca de un BORDE DE RACHA que de :30: "
            f"{cr}/{len(cortes)} ({pct(cr, len(cortes))})"
        )
        w(f"     split más cerca de :30 que de un borde: {c30}/{len(cortes)} ({pct(c30, len(cortes))})")
        # histograma del split
        hb = Counter((d["cut_s"] // 10) * 10 for d in cortes)
        w(
            "     dónde cae el split (decenas): "
            + "  ".join(f"{k:02d}-{k+9:02d}={hb[k]}" for k in sorted(hb))
        )


def tira_hora(d: dict) -> None:
    cubos = d["cubos"]
    rs = d["rs"]
    mins = d["mins"]
    bits_r = "  ".join(f"{k:>2}" for k in rs)
    bits_c = "  ".join(f"{c[:3]:>3}" for c in cubos)
    bits_m = " ".join(f"{m:02d}" for m in mins)
    rach = "  ".join(f"[{c}×{n}]" for c, n, *_ in d["rachas"])
    w(
        f"── {d['tag']}  {tono_tab(d['tono'])}  {d['clima']}  "
        f"nG={d['nG']}  huecos={d['n_hue']}  cubos={d['n_cubos']}  "
        f"bloques={d['n_bloques']}  empate-cat={'sí' if d['emp_r'] else 'no'}"
    )
    w(f"   minutos G: {bits_m}")
    w(f"   R entre G:   {bits_r}")
    w(f"   cubo:        {bits_c}")
    w(f"   rachas:      {rach}")
    w(
        f"   mitades nG {d['n1']}|{d['n2']}  lumen {d['lum1']}|{d['lum2']}  "
        f"({d['tm1']} → {d['tm2']})  tercios {d['t0']}|{d['t1']}|{d['t2']}  "
        f"ventana20 {d['mx20']}/{d['nG']} @{d['start20']:02d}"
    )


def elegir_tiras(docs: list[dict], n_train_total: int) -> list[dict]:
    """Horas del cuerpo histórico (primera mitad del train), no la cola."""
    corte = max(80, n_train_total // 2)
    pool = [d for d in docs[:corte] if d["n_hue"] >= 4]
    picked: list[dict] = []
    seen_day: set[str] = set()

    def take(pred, prefer_day: str | None = None) -> dict | None:
        cand = [d for d in pool if pred(d) and d["tag"] not in {x["tag"] for x in picked}]
        if prefer_day:
            pref = [d for d in cand if d["day"] == prefer_day]
            if pref:
                cand = pref
        # diversificar día
        otros = [d for d in cand if d["day"] not in seen_day]
        if otros:
            cand = otros
        if not cand:
            return None
        # preferir las que se VEN: medio+cola, o vuelco, o 2-3 cubos
        def score(d):
            return (
                int(d["tiene_med"] and d["tiene_col"]),
                int(d["n_cubos"] in (2, 3)),
                d["n_bloques"],
                int(d["emp_r"]),
                d["n_hue"],
            )

        cand.sort(key=score, reverse=True)
        return cand[0]

    for pred in (
        lambda d: d["tono"] == "muy_apagado" and d["tiene_med"] and d["tiene_col"],
        lambda d: d["tono"] == "opaco" and d["n_cubos"] in (2, 3),
        lambda d: d["tono"] in ("fuerte", "muy_fuerte", "supernova") or d["clima"] == "rica",
        lambda d: d["vuelco_a_gen"] or d["vida_tono"] or d["n_bloques"] >= 2,
    ):
        d = take(pred)
        if d:
            picked.append(d)
            seen_day.add(d["day"])
        if len(picked) >= 4:
            break
    if len(picked) < 3:
        for d in pool:
            if d["tag"] not in {x["tag"] for x in picked}:
                picked.append(d)
                if len(picked) >= 4:
                    break
    return picked[:4]


def lectura(tr: list[dict], ho: list[dict]) -> None:
    w("\n════════════════════════════════ LECTURA ════════════════════════════════")
    w("Unidad = HORA. Cuerpo = TRAIN histórico. Hold = testigo. Cero Jaccard.\n")

    def lote(nombre: str, docs: list[dict]) -> None:
        xs = con_hue(docs, 3)
        w(f"{nombre}: {len(docs)} h con G  ·  {len(xs)} con ≥3 huecos")
        by = defaultdict(list)
        for d in xs:
            by[tono_tab(d["tono"])].append(d)
        for tono in ("muy_apagado", "opaco", "fuerte", "muy_fuerte+"):
            ys = by[tono]
            if not ys:
                continue
            c = Counter(min(d["n_cubos"], 4) for d in ys)
            w(
                f"  {tono:<14} {len(ys):>4} h  "
                f"mono {c[1]}  mez2 {c[2]}  mez3 {c[3]}  4+ {c[4]}  "
                f"bloques≥2 {sum(1 for d in ys if d['n_bloques']>=2)}  "
                f"med+col {sum(1 for d in ys if d['tiene_med'] and d['tiene_col'])}  "
                f"BLOQUE med+col {sum(1 for d in ys if d['bloque_med'] and d['bloque_col'])}"
            )

    lote("TRAIN", tr)
    lote("HOLD (testigo)", ho)
    w("")

    apa = [d for d in con_hue(tr, 3) if d["tono"] == "muy_apagado"]
    opa = [d for d in con_hue(tr, 3) if d["tono"] == "opaco"]
    emp = [d for d in con_hue(tr, 3) if d["emp_r"]]
    vida = [d for d in tr if d["nG"] >= 6]

    w("CONTRASTE CON LOOK_HORA_FORMAS (no se esconde)")
    w("  Ya: apagada plural 3–4 R, no 6–7; empate ~40%; colas = evento;")
    w("      corto+cola bimodal; horas del mismo tono no se parecen.")
    if apa:
        c = Counter(min(d["n_cubos"], 4) for d in apa)
        w(
            f"  NUEVO sobre el empate: de {len(apa)} apagadas con ≥3 huecos, "
            f"mono {c[1]} · 2 cubos {c[2]} · 3 cubos {c[3]} · 4+ {c[4]}."
        )
        w(
            f"    Empate-catálogo en esas: {sum(1 for d in apa if d['emp_r'])}/{len(apa)}. "
            f"De TODO el train ≥3 huecos, empate {len(emp)}/"
            f"{len(con_hue(tr, 3))}."
        )
        if emp:
            ce = Counter(min(d["n_cubos"], 4) for d in emp)
            nb = sum(1 for d in emp if d["n_bloques"] >= 2)
            sopa = sum(1 for d in emp if d["n_cubos"] >= 3 and d["n_bloques"] <= 1)
            w(
                f"    El empate NO es monotipo: 1 cubo {ce[1]}/{len(emp)} · "
                f"2 {ce[2]} · 3 {ce[3]} · 4+ {ce[4]}."
            )
            w(
                f"    ¿Son BLOQUES (racha≥2) o sopa de huecos sueltos? "
                f"empate con ≥2 bloques: {nb}/{len(emp)} · "
                f"empate 3+ cubos y 0–1 bloque (sopa): {sopa}/{len(emp)}."
            )
    if apa and opa:
        w(
            f"  Relato vivo G-6R-G + G-12R-G + pegadas: presencia medio+cola+pegada "
            f"apagada {sum(1 for d in apa if d['tiene_med'] and d['tiene_col'] and d['tiene_peg'])}/{len(apa)} "
            f"· opaca {sum(1 for d in opa if d['tiene_med'] and d['tiene_col'] and d['tiene_peg'])}/{len(opa)}."
        )
        w(
            f"    Como RACHAS≥2 (un bloque 6 y un bloque 12): apagada "
            f"{sum(1 for d in apa if d['bloque_med'] and d['bloque_col'])}/{len(apa)} "
            f"· opaca {sum(1 for d in opa if d['bloque_med'] and d['bloque_col'])}/{len(opa)}. "
            f"Eso es más raro que “aparecen los dos cubos”."
        )
    if vida:
        n = len(vida)
        w(
            f"  Vida / mitad: de {n} h nG≥6, vuelco 1ª-apagada→2ª-generosa "
            f"{sum(1 for d in vida if d['vuelco_a_gen'])}/{n} · "
            f"inclina |Δ|≥3 {sum(1 for d in vida if d['inclina'])}/{n} · "
            f"calor > p90 nulo {sum(1 for d in vida if d['caliente_vs_nulo'])}/{n}."
        )
        cortes = [d for d in vida if d["cut_s"] is not None]
        if cortes:
            w(
                f"    Corte: mediana min {median(d['cut_s'] for d in cortes):.0f} · "
                f"cerca de racha {sum(1 for d in cortes if d['cut_cerca_racha'])}/{len(cortes)} · "
                f"cerca de :30 {sum(1 for d in cortes if d['cut_cerca_30'])}/{len(cortes)}."
            )
            w("    Ojo: con 3–4 cubos hay muchos bordes; “cerca de racha” es fácil.")
            w("    No corona que el corte SEA la racha. El :30 tampoco manda.")
    w("")
    w("YA ESTABA: corto+cola como mezcla de la hora (evento, no moda);")
    w("  zona 00/20/40 no manda aterrizaje del hueco; islas; paso med 4/2.")
    w("NUEVO: el empate no es monotipo NI dos bloques G-6 + G-12.")
    w("  Es sopa de 3–4 cubos (a veces 2 cubren la mayoría de huecos).")
    w("  La pegada entre rachas sí es frecuente. El vuelco a mitad no.")
    w("  Tramo caliente ≈ nulo de nG chico. Tercios no cortan densidad.")
    w("NO SENTAR: tip · d≤1 · COVER/SPAN · cubetas de día · “la hora")
    w("  siempre parte a mitad” · taxonomía al dashboard. Hold chico.")


def main() -> None:
    w("LOOK · hora elástica (bloques / vida). NO predicción.")
    w("Unidad = HORA. Dentro = RACHA de cubos, no pool de anclas.")
    w("Tono = suma lumen (cubetas LOOK_HUECO_TONO). Cupo = nG.")
    w("Hueco = R entre G núcleo (tipo≠5). Extra no sienta.")
    w("Cero tip. Cero d≤1 como juez. Cero Jaccard. Cero cable.\n")

    w("MAPA DE CUBOS (oficio de esta mirada; colapsa LOOK_HORA_FORMAS):")
    for c in CUBOS:
        w(f"  {CUBO_TXT[c]}")
    w("  9–10 R no tenía cubo propio en el relato vivo; se va con cola")
    w("  (mismo “elástico largo” que G-12R-G). No se abre un 6º cubo.\n")

    horas, _ = load_horas_y_cinta()
    train, hold = split_holdout(horas, HOLDOUT)
    docs_tr = docs_de(train)
    docs_ho = docs_de(hold)

    w("DATA")
    w(f"  archivo: {DATA_DETAIL}")
    w("  loader: load_horas_y_cinta = detail + horas live AUSENTES en detail")
    w(f"  extra live (solo tags nuevos): {EXTRA}")
    w(f"  cinta {len(horas)} h · train {len(train)} · holdout {len(hold)}")
    w(f"  con ≥1 G núcleo: train {len(docs_tr)} · hold {len(docs_ho)}")
    w(f"  con ≥1 hueco: train {len(con_hue(docs_tr))} · hold {len(con_hue(docs_ho))}")
    w(f"  con ≥3 huecos (mezcla 2–3): train {len(con_hue(docs_tr, 3))} · hold {len(con_hue(docs_ho, 3))}")
    w("  CUERPO = train histórico. NO es la cola de ~900 anclas G+7")
    w("  ni las ~559 ventanas hold de LOOK_G7. Hold 72 = testigo chico")
    w("  (últimas 72 h del corpus; corte ya existente).")
    n_ex = sum(d["n_extra"] for d in docs_tr + docs_ho)
    w(f"  extra tipo 5: {n_ex} en el lote. No entran.\n")

    for nombre, docs in (("TRAIN · CUERPO HISTÓRICO", docs_tr), ("HOLDOUT · TESTIGO", docs_ho)):
        w(f"════════ {nombre}  {len(docs)} horas ════════")
        c_tono = Counter(d["tono"] for d in docs)
        c_cli = Counter(d["clima"] for d in docs)
        w("Horas por tono: " + "  ".join(f"{t}={c_tono[t]}" for t in TONOS if c_tono[t]))
        w("Horas por cupo: " + "  ".join(f"{c}={c_cli[c]}" for c in CLIMAS if c_cli[c]))
        if "HOLDOUT" in nombre:
            w("Hold: n = HORAS. Celdas chicas. No coronar.\n")
        else:
            w("")

        bloque_cortes(
            docs,
            lambda d: tono_tab(d["tono"]),
            TONOS_TAB,
            "A. TONO — mezcla de cubos / rachas (n HORAS)",
        )
        bloque_cortes(
            docs,
            lambda d: d["clima"],
            CLIMAS,
            "\nA1. CUPO — lo mismo, sin mezclarlo con el tono",
        )
        bloque_empate(docs)
        bloque_vida(docs, "\nB. VIDA DE LA HORA (densidad intra-hora)")

        if "TRAIN" in nombre:
            w("\nC. TIRAS DE HORAS CONCRETAS (histórico, primera mitad del train)")
            w("   No son las últimas 900 anclas ni el hold. Una tira = una hora.")
            tiras = elegir_tiras(docs, len(docs))
            if not tiras:
                w("   (no hubo horas con ≥4 huecos en la primera mitad)")
            for d in tiras:
                w("")
                tira_hora(d)
        w("")

    lectura(docs_tr, docs_ho)

    out = LAB / "reports" / "LOOK_HORA_ELASTICO.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"\nGuardado: {out}")


if __name__ == "__main__":
    main()
