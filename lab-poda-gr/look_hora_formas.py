# -*- coding: utf-8 -*-
"""
LOOK: formas LOCALES de CADA hora (no pool de G).
Unidad = la hora. Train y holdout separados. Cero Jaccard.
Cubetas de hueco = paso en TIROS G→G (1=tren, 2=G-R-G, …).
El relato vivo (6–7 R, colas ≥10/15) se contrasta como EVENTO
de esa hora y como moda en R, no como media de anclas.
Cero cable. Cero prod.
"""
from __future__ import annotations

import math
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

TONOS = ("muy_apagado", "opaco", "normal", "fuerte", "muy_fuerte", "supernova")
TONOS_TAB = ("muy_apagado", "opaco", "normal", "fuerte", "muy_fuerte+")
CLIMAS = ("floja", "normal", "rica")

# Paso en tiros: 1 = tren/pegada (0 R), 2 = G-R-G (1 R), 3 = G-R-R-G (2 R).
PASOS = ("1_tren", "2_GRG", "3_GRRG", "4-5", "6-7", "8-10", "11-15", "16+")
# Relato vivo habla en R entre G (k = paso-1).
RS = ("0_tren", "1_GRG", "2_GRRG", "3-4R", "5R", "6-7R", "8-10R", "11-15R", "16R+")


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


def hod_txt(hod: int | None) -> str:
    return f"h{hod:02d}" if hod is not None else "h??"


def cubeta_paso(h: int) -> str:
    if h <= 1:
        return "1_tren"
    if h == 2:
        return "2_GRG"
    if h == 3:
        return "3_GRRG"
    if h <= 5:
        return "4-5"
    if h <= 7:
        return "6-7"
    if h <= 10:
        return "8-10"
    if h <= 15:
        return "11-15"
    return "16+"


def cubeta_r(k: int) -> str:
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


def l1(a: list[float], b: list[float]) -> float:
    return sum(abs(x - y) for x, y in zip(a, b))


def vec_norm(cnt: Counter, keys: tuple[str, ...]) -> list[float]:
    tot = sum(cnt[k] for k in keys)
    if not tot:
        return [0.0] * len(keys)
    return [cnt[k] / tot for k in keys]


def desierto_minutos(mins: set[int]) -> int:
    if not mins:
        return 60
    vacio = [m not in mins for m in range(60)]
    best = cur = 0
    for v in vacio:
        if v:
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 0
    return best


def doc_hora(h) -> dict | None:
    tiros = list(getattr(h, "tiros", None) or [])
    nucleos = [t for t in tiros if es_nucleo(t)]
    extras = [t for t in tiros if es_g(t) and not es_nucleo(t)]
    if not nucleos and not extras:
        return None
    idxs = [i for i, t in enumerate(tiros) if es_nucleo(t)]
    pasos: list[int] = []
    rs: list[int] = []
    for a, b in zip(idxs, idxs[1:]):
        paso = b - a
        pasos.append(paso)
        rs.append(paso - 1)

    cnt_p = Counter(cubeta_paso(p) for p in pasos)
    cnt_r = Counter(cubeta_r(k) for k in rs)
    moda_p, emp_p = moda_de(cnt_p)
    moda_r, emp_r = moda_de(cnt_r)

    # trenes = rachas de 2+ G núcleo seguidas; islas = G sin vecina G
    n_trenes = 0
    n_g_tren = 0
    i = 0
    n_idx = len(idxs)
    while i < n_idx:
        j = i
        while j + 1 < n_idx and idxs[j + 1] == idxs[j] + 1:
            j += 1
        largo = j - i + 1
        if largo >= 2:
            n_trenes += 1
            n_g_tren += largo
        i = j + 1
    n_islas = n_idx - n_g_tren
    if n_trenes and n_g_tren > n_islas:
        patron = "tren"
    elif n_trenes and n_g_tren == n_islas:
        patron = "mix"
    else:
        patron = "isla"

    mins = {int(t.m0) % 60 for t in nucleos}
    ocup = len(mins)
    desert = desierto_minutos(mins)

    tiene_corto = any(k <= 2 for k in rs)  # tren / GRG / GRRG
    tiene_grg = any(k == 1 for k in rs)
    tiene_tren = n_trenes > 0
    tiene_r67 = any(k in (6, 7) for k in rs)
    tiene_r10 = any(k >= 10 for k in rs)
    tiene_r15 = any(k >= 15 for k in rs)
    tiene_p67 = any(6 <= p <= 7 for p in pasos)
    tiene_p11 = any(p >= 11 for p in pasos)
    bimodal = tiene_corto and tiene_r10

    if bimodal:
        mezcla = "corto+cola"
    elif tiene_r10 and not tiene_corto:
        mezcla = "solo_cola"
    elif tiene_corto and not tiene_r10:
        mezcla = "solo_corto"
    elif rs:
        mezcla = "medio"
    else:
        mezcla = "sin_par"

    nG = len(nucleos)
    suma = sum(lumen_de(t) for t in nucleos)
    return {
        "h": h,
        "tag": getattr(h, "tag", "?"),
        "day": day_key(getattr(h, "tag", "")),
        "hod": hod_de(getattr(h, "tag", "")),
        "nG": nG,
        "n_extra": len(extras),
        "n_tiros": len(tiros),
        "suma": suma,
        "tono": tono_suma(suma) if nG else "sin_G",
        "clima": clima_nG(nG),
        "pasos": pasos,
        "rs": rs,
        "cnt_p": cnt_p,
        "cnt_r": cnt_r,
        "moda_p": moda_p,
        "emp_p": emp_p,
        "moda_r": moda_r,
        "emp_r": emp_r,
        "n_huecos": len(pasos),
        "med_r": int(round(median(rs))) if rs else None,
        "n_trenes": n_trenes,
        "n_g_tren": n_g_tren,
        "n_islas": n_islas,
        "patron": patron,
        "ocup": ocup,
        "desert": desert,
        "tiene_corto": tiene_corto,
        "tiene_grg": tiene_grg,
        "tiene_tren": tiene_tren,
        "tiene_r67": tiene_r67,
        "tiene_r10": tiene_r10,
        "tiene_r15": tiene_r15,
        "tiene_p67": tiene_p67,
        "tiene_p11": tiene_p11,
        "bimodal": bimodal,
        "mezcla": mezcla,
        "vec_p": vec_norm(cnt_p, PASOS),
    }


def docs_de(horas) -> list[dict]:
    out = []
    for h in horas:
        d = doc_hora(h)
        if d:
            out.append(d)
    return out


def con_par(docs: list[dict]) -> list[dict]:
    return [d for d in docs if d["n_huecos"] >= 1]


def media_vec(xs: list[dict]) -> list[float] | None:
    ys = [d["vec_p"] for d in xs if d["n_huecos"] >= 1]
    if not ys:
        return None
    n = len(ys[0])
    return [sum(v[i] for v in ys) / len(ys) for i in range(n)]


def mean_intra(xs: list[dict], cap: int = 90) -> float | None:
    vs = [d["vec_p"] for d in xs if d["n_huecos"] >= 2]
    if len(vs) < 2:
        return None
    if len(vs) > cap:
        # muestra regular (no azar de seed): 1 de cada k
        k = math.ceil(len(vs) / cap)
        vs = vs[::k]
    acc = n = 0
    for i in range(len(vs)):
        for j in range(i + 1, len(vs)):
            acc += l1(vs[i], vs[j])
            n += 1
    return acc / n if n else None


def fila_modas(nombre: str, xs: list[dict], campo: str, keys: tuple[str, ...]) -> None:
    n = len(xs)
    if not n:
        return
    c = Counter()
    emp = 0
    sin = 0
    for d in xs:
        if d["n_huecos"] < 1:
            sin += 1
            continue
        if d["emp_p" if campo == "moda_p" else "emp_r"]:
            emp += 1
        elif d[campo]:
            c[d[campo]] += 1
    bits = "  ".join(f"{k}={c[k]}({pct(c[k], n)})" for k in keys if c[k])
    extra = []
    if emp:
        extra.append(f"empate={emp}({pct(emp, n)})")
    if sin:
        extra.append(f"sin_par={sin}({pct(sin, n)})")
    tail = ("  " + "  ".join(extra)) if extra else ""
    w(f"  {nombre:<14} n_h={n:<4}  {bits or '(ninguna moda)'}{tail}")


def bloque_corte(titulo: str, docs: list[dict], key_fn, orden) -> None:
    w(titulo)
    by = defaultdict(list)
    for d in docs:
        by[key_fn(d)].append(d)
    for nombre in orden:
        xs = by[nombre]
        if not xs:
            continue
        pares = con_par(xs)
        w(f"\n── {nombre}  ·  {len(xs)} horas  ·  {len(pares)} con ≥1 hueco G→G ──")
        if len(xs) < 12:
            w(f"   (celda chica: n={len(xs)} HORAS, no n G. No coronar.)")
        w("   Moda del PASO (tiros G→G; 1=tren  2=G-R-G  3=G-R-R-G  6-7=5–6 R):")
        fila_modas("paso", pares, "moda_p", PASOS)
        w("   Moda en R entre G (relato vivo: ¿manda 6–7 R?):")
        fila_modas("R", pares, "moda_r", RS)
        w("   Eventos de ESA hora (sí/no; no es media de huecos):")
        n = len(pares) or 1
        w(
            f"     tren≥1 {pct(sum(1 for d in pares if d['tiene_tren']), len(pares))}  "
            f"G-R-G≥1 {pct(sum(1 for d in pares if d['tiene_grg']), len(pares))}  "
            f"6–7R≥1 {pct(sum(1 for d in pares if d['tiene_r67']), len(pares))}  "
            f"cola≥10R {pct(sum(1 for d in pares if d['tiene_r10']), len(pares))}  "
            f"cola≥15R {pct(sum(1 for d in pares if d['tiene_r15']), len(pares))}"
        )
        w("   Mezcla de la hora (corto≤2R vs cola≥10R, formas del catálogo):")
        cm = Counter(d["mezcla"] for d in pares)
        w(
            "     "
            + "  ".join(
                f"{k}={cm[k]} {pct(cm[k], len(pares))}"
                for k in ("solo_corto", "medio", "corto+cola", "solo_cola", "sin_par")
                if cm[k]
            )
        )
        w("   Patrón tren vs isla (quién tiene más G de esa hora):")
        cp = Counter(d["patron"] for d in xs)
        w(
            "     "
            + "  ".join(f"{k}={cp[k]} {pct(cp[k], len(xs))}" for k in ("isla", "mix", "tren") if cp[k])
        )
        if pares:
            w(
                f"   Cupo/ocupación de esas horas: med nG={median(d['nG'] for d in xs):.0f}  "
                f"med min-lit={median(d['ocup'] for d in xs):.0f}/60  "
                f"med desierto={median(d['desert'] for d in xs):.0f} min  "
                f"med paso={median(d['med_r'] for d in pares if d['med_r'] is not None):.0f} R"
            )


def bloque_parecido(docs: list[dict]) -> None:
    w("\nC. ¿LAS HORAS DEL MISMO TONO SE PARECEN ENTRE SÍ?")
    w("   Vector de cada hora = fracción de SUS huecos en las 8 cubetas de paso.")
    w("   Distancia = L1 (0 = idénticas, 2 = ajenas). No es % poolado de G.")
    w("   Intra = media entre pares de horas del mismo tono (muestra ≤90).")
    w("   Centro = L1 entre el vector medio de un tono y el de otro.")
    pares = [d for d in docs if d["n_huecos"] >= 2]
    by = defaultdict(list)
    for d in pares:
        by[tono_tab(d["tono"])].append(d)
    w(f"   {'tono':<14} {'n_h':>4}  intra_L1  (más bajo = más parecidas)")
    for tono in TONOS_TAB:
        xs = by[tono]
        if len(xs) < 3:
            if xs:
                w(f"   {tono:<14} {len(xs):>4}  —  celda chica")
            continue
        intra = mean_intra(xs)
        w(f"   {tono:<14} {len(xs):>4}  {intra:.3f}" if intra is not None else f"   {tono:<14} {len(xs):>4}")
    cents = {t: media_vec(by[t]) for t in TONOS_TAB if by[t]}
    w("   L1 entre centros de tono (apagada vs generosa):")
    orden = [t for t in TONOS_TAB if t in cents]
    if len(orden) >= 2:
        hdr = "            " + "".join(f"{t[:7]:>8}" for t in orden)
        w(hdr)
        for a in orden:
            row = f"   {a[:9]:<9}"
            for b in orden:
                row += f"{l1(cents[a], cents[b]):8.2f}"
            w(row)
    # también intra global vs intra tono
    glob = mean_intra(pares)
    if glob is not None:
        w(f"   Intra de TODAS las horas (sin cortar tono): {glob:.3f}")
        w("   Si intra-tono ≈ intra-todas, el tono no agrupa la FORMA, solo el cupo.")


def tira_dia(docs: list[dict], day: str, titulo: str) -> None:
    xs = [d for d in docs if d["day"] == day]
    xs = sorted(xs, key=lambda d: (d["hod"] is None, d["hod"] if d["hod"] is not None else 99, d["tag"]))
    w(f"\n{titulo}")
    w(f"   día {day}  ·  {len(xs)} horas  (una fila = una hora, no se promedian)")
    w(
        f"   {'hod':<4} {'tag':<16} {'tono':<12} {'cupo':<6} {'nG':>3} "
        f"{'modaP':<8} {'modaR':<8} {'patr':<5} {'mezcla':<11} "
        f"{'tr':>2} {'GRG':>3} {'67R':>3} {'≥10':>3} {'≥15':>3}  vec(paso)"
    )
    for d in xs:
        mp = "empate" if d["emp_p"] else (d["moda_p"] or "—")
        mr = "empate" if d["emp_r"] else (d["moda_r"] or "—")
        vec = d["cnt_p"]
        bits = ",".join(f"{vec[k]}" for k in PASOS)
        w(
            f"   {hod_txt(d['hod']):<4} {d['tag']:<16} {tono_tab(d['tono']):<12} {d['clima']:<6} {d['nG']:>3} "
            f"{mp:<8} {mr:<8} {d['patron']:<5} {d['mezcla']:<11} "
            f"{int(d['tiene_tren']):>2} {int(d['tiene_grg']):>3} {int(d['tiene_r67']):>3} "
            f"{int(d['tiene_r10']):>3} {int(d['tiene_r15']):>3}  {bits}"
        )
    w("   movimiento hora→hora CONSECUTIVA (hod+1; no se salta un hueco del día):")
    n_ok = 0
    n_corto = 0
    by_hod = {d["hod"]: d for d in xs if d["hod"] is not None}
    for hod in range(24):
        a = by_hod.get(hod)
        b = by_hod.get((hod + 1) % 24) if hod < 23 else None
        if hod == 23:
            continue  # no costura :00 como 'movimiento de forma'
        if not a or not b or a["n_huecos"] < 1 or b["n_huecos"] < 1:
            continue
        n_ok += 1
        va, vb = a["vec_p"], b["vec_p"]
        corto_a = va[0] + va[1]
        corto_b = vb[0] + vb[1]
        if corto_b > corto_a + 0.05:
            n_corto += 1
            glosa = "sube tren/GRG"
        elif corto_b < corto_a - 0.05:
            glosa = "baja tren/GRG"
        else:
            glosa = "misma mezcla corta"
        ma = "emp" if a["emp_p"] else (a["moda_p"] or "—")
        mb = "emp" if b["emp_p"] else (b["moda_p"] or "—")
        w(
            f"     {hod_txt(a['hod'])} {tono_tab(a['tono']):<12} {ma:<8} → "
            f"{hod_txt(b['hod'])} {tono_tab(b['tono']):<12} {mb:<8}  {glosa}"
        )
    if n_ok:
        w(f"   de {n_ok} pasos hod→hod+1, {n_corto} suben tren/GRG ({pct(n_corto, n_ok)}).")


def elegir_dias(docs: list[dict], n: int = 2) -> list[str]:
    by = defaultdict(list)
    for d in docs:
        by[d["day"]].append(d)
    scored = []
    for day, hs in by.items():
        if len(hs) < 8:
            continue
        tonos = {tono_tab(d["tono"]) for d in hs}
        n_apa = sum(1 for d in hs if d["tono"] == "muy_apagado")
        n_gen = sum(1 for d in hs if d["tono"] in ("fuerte", "muy_fuerte", "supernova") or d["clima"] == "rica")
        scored.append((len(tonos), n_apa > 0 and n_gen > 0, len(hs), -abs(len(hs) - 24), day))
    scored.sort(reverse=True)
    out = []
    for row in scored:
        day = row[-1]
        if day not in out:
            out.append(day)
        if len(out) >= n:
            break
    return out


def lectura(tr: list[dict], ho: list[dict]) -> None:
    w("\n════════════════════════════════ LECTURA ════════════════════════════════")
    w("Unidad = HORA. Train y hold no se mezclan en un %.")
    w("")

    def resumen_lote(nombre: str, docs: list[dict]) -> None:
        pares = con_par(docs)
        by = defaultdict(list)
        for d in pares:
            by[tono_tab(d["tono"])].append(d)

        def top_moda(xs, campo):
            c = Counter()
            emp = 0
            for d in xs:
                if d["emp_p" if campo == "moda_p" else "emp_r"]:
                    emp += 1
                elif d[campo]:
                    c[d[campo]] += 1
            if not c:
                return "—", 0, emp
            k, n = c.most_common(1)[0]
            return k, n, emp

        w(f"{nombre}: {len(docs)} h  ·  {len(pares)} con hueco")
        for tono in ("muy_apagado", "opaco", "fuerte", "muy_fuerte+"):
            xs = by[tono]
            if not xs:
                continue
            mp, nmp, emp_p = top_moda(xs, "moda_p")
            mr, nmr, emp_r = top_moda(xs, "moda_r")
            w(
                f"  {tono:<14} {len(xs):>4} h  "
                f"plural-paso {mp} {nmp}/{len(xs)}  empate {emp_p}/{len(xs)}  "
                f"plural-R {mr} {nmr}/{len(xs)}  empate-R {emp_r}/{len(xs)}"
            )
            w(
                f"                 ev 6–7R {pct(sum(1 for d in xs if d['tiene_r67']), len(xs))}  "
                f"ev≥10R {pct(sum(1 for d in xs if d['tiene_r10']), len(xs))}  "
                f"ev≥15R {pct(sum(1 for d in xs if d['tiene_r15']), len(xs))}  "
                f"isla {pct(sum(1 for d in xs if d['patron']=='isla'), len(xs))}  "
                f"corto+cola {pct(sum(1 for d in xs if d['mezcla']=='corto+cola'), len(xs))}"
            )

    resumen_lote("TRAIN", tr)
    resumen_lote("HOLDOUT", ho)
    w("")

    def corte(docs, pred):
        return [d for d in con_par(docs) if pred(d)]

    def n_moda(xs, campo, valor):
        emp = "emp_p" if campo == "moda_p" else "emp_r"
        return sum(1 for d in xs if (not d[emp]) and d[campo] == valor)

    def n_emp(xs, campo):
        emp = "emp_p" if campo == "moda_p" else "emp_r"
        return sum(1 for d in xs if d[emp])

    apa_tr = corte(tr, lambda d: d["tono"] == "muy_apagado")
    opa_tr = corte(tr, lambda d: d["tono"] == "opaco")
    fue_tr = corte(tr, lambda d: d["tono"] == "fuerte")
    ric_tr = corte(tr, lambda d: d["clima"] == "rica")
    apa_ho = corte(ho, lambda d: d["tono"] == "muy_apagado")
    n_apa, n_opa, n_fue, n_ric = len(apa_tr), len(opa_tr), len(fue_tr), len(ric_tr)

    w("CONTRASTE CON EL RELATO VIVO (unidad HORA, no media de G)")
    w(
        f"  Apagada/opaca: NO manda hueco 6–7 R. Train muy_apagado: plural"
    )
    w(
        f"    de moda-R = 3–4 R ({n_moda(apa_tr,'moda_r','3-4R')}/{n_apa}) · "
        f"6–7 R solo {n_moda(apa_tr,'moda_r','6-7R')}/{n_apa} · "
        f"empate {n_emp(apa_tr,'moda_r')}/{n_apa}."
    )
    w(
        f"    Opaco: plural 3–4 R ({n_moda(opa_tr,'moda_r','3-4R')}/{n_opa}) · "
        f"6–7 R {n_moda(opa_tr,'moda_r','6-7R')}/{n_opa}. Hold apagada: "
        f"{len(apa_ho)} h (celda chica); "
        f"plural-paso 6–7 = {n_moda(apa_ho,'moda_p','6-7')}/{len(apa_ho)} "
        f"· empate {n_emp(apa_ho,'moda_p')}/{len(apa_ho)}. No corona."
    )
    w(
        f"  Colas ≥10 / ≥15 SÍ son evento común de ESA hora apagada "
        f"({pct(sum(1 for d in apa_tr if d['tiene_r10']), n_apa)} / "
        f"{pct(sum(1 for d in apa_tr if d['tiene_r15']), n_apa)}), no la moda."
    )
    w("    El vivo las ve porque casi toda apagada tiene UNA cola;")
    w("    no porque la hora SEA una cola.")
    w(
        f"  Generosa: sube tren/G-R-G como EVENTO (fuerte tren "
        f"{pct(sum(1 for d in fue_tr if d['tiene_tren']), n_fue)}, GRG "
        f"{pct(sum(1 for d in fue_tr if d['tiene_grg']), n_fue)}; rica tren "
        f"{pct(sum(1 for d in ric_tr if d['tiene_tren']), n_ric)}, GRG "
        f"{pct(sum(1 for d in ric_tr if d['tiene_grg']), n_ric)}) "
        f"y el plural de moda se va a tren "
        f"(fuerte {n_moda(fue_tr,'moda_p','1_tren')}/{n_fue}, "
        f"rica {n_moda(ric_tr,'moda_p','1_tren')}/{n_ric})."
    )
    w(
        f"    La hora sigue siendo ISLA (fuerte "
        f"{pct(sum(1 for d in fue_tr if d['patron']=='isla'), n_fue)}, rica "
        f"{pct(sum(1 for d in ric_tr if d['patron']=='isla'), n_ric)}): "
        f"hay tren, no manda el tren."
    )
    w(
        f"  La forma que manda de verdad: corto+cola (apagada "
        f"{pct(sum(1 for d in apa_tr if d['mezcla']=='corto+cola'), n_apa)}, "
        f"fuerte {pct(sum(1 for d in fue_tr if d['mezcla']=='corto+cola'), n_fue)})."
    )
    w("    Bimodal de la hora. No es «6–7 luego racimo» ni «todo G-R-G».")
    w("")
    w("YA ESTABA: paso mediano 4 R apagada / 2 R fuerte; islas; hueco")
    w("  bimodal; «apagada ⇒ 6–15 luego racimo» FALSO como ley (LOOK_HUECO).")
    w("NUEVO: la MODA de la hora tampoco es 6–7 R. Empate es lo más")
    w("  frecuente (~40% apagadas): la hora no tiene un gesto único.")
    w("  Horas del mismo tono NO se parecen entre sí (intra L1 ~1.1")
    w("  apagada ≈ intra-todas 1.00). El centro sí se corre un poco")
    w("  (apagada↔muy_fuerte+ L1 0.40): el tono mueve el PROMEDIO del")
    w("  vector, no clona la hora. Cupo (floja/rica) corta más que el tono.")
    w("POR QUÉ G+7 SE VEÍA AZAR: pooló ~9000 anclas de horas bimodales.")
    w("  Cada hora aporta desierto Y silla Y racimo al mismo saco.")
    w("  Cuatro formas ~22% = Jaccard de ventanas, no huella de hora.")
    w("  El G+7 aplastó precisamente esta moda-por-hora (y el empate).")
    w("NO SENTAR: tip · cubetas de día · taxonomía al dashboard ·")
    w("  P(tiro=G) / Jaccard · COVER/SPAN. Hold: celdas de tono chicas.")


def main() -> None:
    w("LOOK · formas de CADA hora (no promedio global)")
    w("Unidad = la hora. Train y holdout separados. Cero Jaccard.")
    w("Tono = suma lumen (cubetas LOOK_HUECO_TONO). Cupo = nG (floja/rica).")
    w("Hueco = tiros G→G núcleo (tipo≠5; extra no sienta).")
    w("  paso 1 = tren/pegada (0 R) · 2 = G-R-G (1 R) · 3 = G-R-R-G (2 R)")
    w("  4–5 · 6–7 (eso son 5–6 R) · 8–10 · 11–15 · ≥16")
    w("Relato vivo «6–7 R / colas ≥10/15» = EVENTO y moda-en-R de ESA hora.")
    w("No se reporta % poolado de todas las G. Cero cable.\n")

    horas, _ = load_horas_y_cinta()
    train, hold = split_holdout(horas, HOLDOUT)
    docs_tr = docs_de(train)
    docs_ho = docs_de(hold)
    w(f"Cinta {len(horas)} h · train {len(train)} · holdout {len(hold)}")
    w(f"Horas con ≥1 G núcleo: train {len(docs_tr)} · hold {len(docs_ho)}")
    w(f"Con ≥1 hueco G→G: train {len(con_par(docs_tr))} · hold {len(con_par(docs_ho))}")
    n_ex = sum(d["n_extra"] for d in docs_tr + docs_ho)
    w(f"Extra (tipo 5, no sienta): {n_ex} en el lote. No entran al vector.\n")

    for nombre, docs in (("TRAIN", docs_tr), ("HOLDOUT", docs_ho)):
        w(f"════════ {nombre}  {len(docs)} horas ════════")
        c_tono = Counter(d["tono"] for d in docs)
        c_cli = Counter(d["clima"] for d in docs)
        w("Horas por tono: " + "  ".join(f"{t}={c_tono[t]}" for t in TONOS if c_tono[t]))
        w("Horas por cupo: " + "  ".join(f"{c}={c_cli[c]}" for c in CLIMAS if c_cli[c]))
        if nombre == "HOLDOUT":
            w("Hold: n = HORAS. fuerte/muy_fuerte+ son celdas chicas. No coronar.")

        bloque_corte(
            "\nA. TONO DE HORA — cuántas HORAS tienen cada moda",
            docs,
            lambda d: tono_tab(d["tono"]),
            TONOS_TAB,
        )
        bloque_corte(
            "\nB. CUPO (nG) — mismo inventario, sin mezclarlo con el tono",
            docs,
            lambda d: d["clima"],
            CLIMAS,
        )
        bloque_parecido(docs)

        dias = elegir_dias(docs, 2)
        w("\nD. TIRAS DE UN DÍA (hora por hora; no se aplastan)")
        w("   vec(paso) = conteos 1_tren,2_GRG,3_GRRG,4-5,6-7,8-10,11-15,16+")
        w("   tr/GRG/67R/≥10/≥15 = 1 si ESA hora tuvo ese evento.")
        if not dias:
            w("   (ningún día con ≥8 h en este lote)")
        for i, day in enumerate(dias, 1):
            titu = "   Tira " + ("hold " if nombre == "HOLDOUT" else "train ") + str(i)
            tira_dia(docs, day, titu)
        w("")

    lectura(docs_tr, docs_ho)

    out = LAB / "reports" / "LOOK_HORA_FORMAS.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"\nGuardado: {out}")


if __name__ == "__main__":
    main()
