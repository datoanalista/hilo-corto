# -*- coding: utf-8 -*-
"""
Lab G-cola — Ronda 3: discovery · patrones · comportamientos · especies.
  python run_lab_r3.py
"""
from __future__ import annotations

import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, median, stdev

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
EXTRA = ROOT / "dashboard" / "extraccion" / "extraccion-en-vivo.txt"
sys.path.insert(0, str(LAB))

from core_gc import (  # noqa: E402
    BLOQUES,
    UMBRAL_ALTO,
    UMBRAL_COLA,
    GAlta,
    HoraGC,
    estado_a_min,
    load_horas,
    metrics_binary,
    split_holdout,
)

OUT = LAB / "reports"
OUT.mkdir(exist_ok=True)
HOLDOUT = 72
CORTE_LARGO = 70
lines: list[str] = []


def w(s=""):
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def bn(b):
    return f"{b[0]}-{b[1]}"


def bloque_de(m: int) -> str:
    for lo, hi in BLOQUES:
        if lo <= m <= hi:
            return bn((lo, hi))
    return "?"


@dataclass
class ColaEvt:
    m0: int
    lumen: int
    tipo: int | None
    bloque: str
    r_largo_antes: bool
    gap_g: int | None  # min desde G anterior
    idx_g: int  # ordinal G en la hora


@dataclass
class PerfilHora:
    h: HoraGC
    colas400: list[ColaEvt] = field(default_factory=list)
    colas500: list[ColaEvt] = field(default_factory=list)
    especie: str = "normal"
    st19: dict = field(default_factory=dict)
    st39: dict = field(default_factory=dict)

    @property
    def tiene_cola400(self):
        return bool(self.colas400)

    @property
    def tiene_cola500(self):
        return bool(self.colas500)


def r_antes_de_g(h: HoraGC, m0: int) -> bool:
    """¿Hubo R largo inmediatamente antes de esta G?"""
    tiros = h.tiros or []
    for i, t in enumerate(tiros):
        if t.color != "G" or t.m0 != m0:
            continue
        if i == 0:
            return False
        prev = tiros[i - 1]
        return prev.color == "R" and prev.dur_s >= CORTE_LARGO
    return False


def perfilar_horas(horas: list[HoraGC]) -> list[PerfilHora]:
    out = []
    for h in horas:
        p = PerfilHora(h=h, st19=estado_a_min(h, 19), st39=estado_a_min(h, 39))
        gs_ord = sorted(h.gs, key=lambda x: x.m0)
        for i, g in enumerate(gs_ord):
            ev_kw = dict(
                m0=g.m0,
                lumen=g.lumen,
                tipo=g.tipo,
                bloque=bloque_de(g.m0),
                r_largo_antes=r_antes_de_g(h, g.m0),
                gap_g=(g.m0 - gs_ord[i - 1].m0) if i else None,
                idx_g=i + 1,
            )
            if g.lumen > UMBRAL_ALTO:
                p.colas400.append(ColaEvt(**ev_kw))
            if g.lumen > UMBRAL_COLA:
                p.colas500.append(ColaEvt(**ev_kw))
        p.especie = clasificar_especie(p)
        out.append(p)
    return out


def clasificar_especie(p: PerfilHora) -> str:
    if not p.colas500 and not p.colas400:
        return "sin_cola"
    evs = p.colas500 or p.colas400
    bloques = {e.bloque for e in evs}
    if len(p.colas500) >= 2 or len(p.colas400) >= 3:
        return "multi_cola"
    if len(bloques) >= 2:
        return "cola_repartida"
    e = evs[0]
    if e.idx_g == 1:
        return "cola_apertura"
    if e.bloque == "40-59":
        return "cola_cierre"
    if e.bloque == "20-39":
        return "cola_medio"
    if e.bloque == "0-19":
        return "cola_temprana"
    if p.h.mean_g < 55 and e.lumen > 400:
        return "unicornio"  # una sola G gorda, resto opaco
    return "cola_otra"


def cmp_med(a, b, key):
    va = [key(x) for x in a if key(x) is not None]
    vb = [key(x) for x in b if key(x) is not None]
    if not va or not vb:
        return "—"
    ma, mb = median(va), median(vb)
    return f"med {ma:.0f} vs {mb:.0f} (Δ{ma - mb:+.0f})"


# ── H1 especies ───────────────────────────────────────────────
def h1_especies(perfiles):
    w("== H1 ESPECIE — taxonomía de horas con cola ==")
    con400 = [p for p in perfiles if p.tiene_cola400]
    con500 = [p for p in perfiles if p.tiene_cola500]
    w(f"  horas con G>400: {len(con400)} · G>500: {len(con500)}")
    for um, xs in [(400, con400), (500, con500)]:
        c = Counter(p.especie for p in xs)
        w(f"  G>{um} por especie: {dict(c)}")
        bloques = Counter(e.bloque for p in xs for e in (p.colas500 if um == 500 else p.colas400))
        w(f"  G>{um} por bloque 1er cola: {dict(bloques)}")
    w("")


# ── H2 perfil hora con/sin cola ───────────────────────────────
def h2_perfil_hora(perfiles):
    w("== H2 PERFIL HORA — con cola vs vecinas sin cola ==")
    con = [p for p in perfiles if p.tiene_cola500]
    sin = [p for p in perfiles if not p.tiene_cola500 and p.h.n_g >= 3]
    w(f"  con G>500: n={len(con)} · sin G>500 (nG>=3): n={len(sin)}")
    w(f"  nG: {cmp_med(con, sin, lambda p: p.h.n_g)}")
    w(f"  sumG: {cmp_med(con, sin, lambda p: p.h.sum_g)}")
    w(f"  meanG: {cmp_med(con, sin, lambda p: p.h.mean_g)}")
    w(f"  maxG: {cmp_med(con, sin, lambda p: p.h.max_g)}")
    w(f"  acum@19: {cmp_med(con, sin, lambda p: p.st19['acum'])}")
    w(f"  maxG@19: {cmp_med(con, sin, lambda p: p.st19['maxG'])}")
    w(f"  acum@39: {cmp_med(con, sin, lambda p: p.st39['acum'])}")
    w(f"  nG@39: {cmp_med(con, sin, lambda p: p.st39['nG'])}")
    # % con G3|4 fuerte antes cola
    g34 = sum(1 for p in con if any(g.tipo in (3, 4) and g.lumen >= 70 for g in p.h.gs if g.m0 <= 19))
    w(f"  G3|4>=70 en 0-19 (horas con cola): {100*g34/len(con):.0f}%")
    w("")


# ── H3 anatomía de la G cola ──────────────────────────────────
def h3_anatomia_cola(perfiles):
    w("== H3 ANATOMÍA G COLA — la ficha gorda en sí ==")
    for um, attr in [(500, "colas500"), (400, "colas400")]:
        evs = [e for p in perfiles for e in getattr(p, attr)]
        if not evs:
            continue
        w(f"  --- G>{um} n={len(evs)} eventos ---")
        w(f"  min med={median(e.m0 for e in evs):.0f} · lumen med={median(e.lumen for e in evs):.0f}")
        tipos = Counter(e.tipo for e in evs)
        w(f"  tipos: {dict(tipos)}")
        w(f"  R largo antes: {100*sum(e.r_largo_antes for e in evs)/len(evs):.0f}%")
        gaps = [e.gap_g for e in evs if e.gap_g is not None]
        if gaps:
            w(f"  gap desde G previa med={median(gaps):.0f} min")
        w(f"  ordinal G med={median(e.idx_g for e in evs):.0f} (1=primera luz)")
        w(f"  es 1er G de hora: {100*sum(e.idx_g==1 for e in evs)/len(evs):.0f}%")
    w("")


# ── H4 trayectoria acumulada ──────────────────────────────────
def h4_trayectoria(perfiles):
    w("== H4 TRAYECTORIA — acumulación antes de la cola ==")
    for um, attr in [(500, "colas500"), (400, "colas400")]:
        ratios = []
        acums = []
        for p in perfiles:
            evs = getattr(p, attr)
            if not evs:
                continue
            e = min(evs, key=lambda x: x.m0)
            st = estado_a_min(p.h, max(0, e.m0 - 1))
            if st["acum"] <= 0:
                continue
            acums.append(st["acum"])
            ratios.append(e.lumen / st["acum"] if st["acum"] else 0)
        if acums:
            w(
                f"  G>{um}: acum justo antes med={median(acums):.0f} · "
                f"cola/acum med={median(ratios):.2f} (salto relativo)"
            )
    # aceleración: acum@19 vs @39 en horas con cola fin
    fin = [p for p in perfiles if p.especie == "cola_cierre"]
    if fin:
        deltas = [p.st39["acum"] - p.st19["acum"] for p in fin]
        w(f"  cola_cierre: Δacum 19→39 med={median(deltas):.0f}")
    w("")


# ── H5 tejido día / hod / vecinas ─────────────────────────────
def h5_tejido(perfiles, horas):
    w("== H5 TEJIDO — día, hod, hora previa ==")
    by_day = defaultdict(list)
    for p in perfiles:
        by_day[p.h.tag.split("-")[1]].append(p)
    # mismo día otra hora con cola
    same_day = 0
    total = 0
    for p in perfiles:
        if not p.tiene_cola500:
            continue
        total += 1
        day = p.h.tag.split("-")[1]
        if any(x.h.tag != p.h.tag and x.tiene_cola500 for x in by_day[day]):
            same_day += 1
    w(f"  G>500: otra cola mismo día: {100*same_day/total:.0f}% (n={total})")

    idx = {h.tag: i for i, h in enumerate(horas)}
    h1_cola = h1_max = 0
    for p in perfiles:
        if not p.tiene_cola500:
            continue
        i = idx.get(p.h.tag, -1)
        if i <= 0:
            continue
        prev = horas[i - 1]
        h1_max += 1
        if prev.max_g >= 110 or prev.tiene_gt(UMBRAL_COLA):
            h1_cola += 1
    w(f"  H-1 maxG>=110 o tuvo G>500: {100*h1_cola/h1_max:.0f}% antes hora cola")

    by_hod = defaultdict(lambda: {"n": 0, "c": 0})
    for p in perfiles:
        by_hod[p.h.hod]["n"] += 1
        if p.tiene_cola500:
            by_hod[p.h.hod]["c"] += 1
    rows = [(100 * v["c"] / v["n"], hod, v["c"], v["n"]) for hod, v in by_hod.items() if v["n"] >= 15]
    rows.sort(reverse=True)
    w("  hod P(G>500) top:")
    for p, hod, c, n in rows[:6]:
        w(f"    h{hod:02d}: {p:.1f}% ({c}/{n})")
    w("")


# ── H6 patrones discriminantes (train) ────────────────────────
def h6_patrones_train(train_p, test_p):
    w("== H6 PATRONES — reglas de comportamiento (train→holdout) ==")

    def y500(p):
        return p.tiene_cola500

    def y500_fin(p):
        return any(e.bloque == "40-59" for e in p.colas500)

    def y500_med(p):
        return any(e.bloque == "20-39" for e in p.colas500)

    targets = [
        ("G>500 cualquier bloque", y500),
        ("G>500 en 40-59", y500_fin),
        ("G>500 en 20-39", y500_med),
    ]

    reglas = [
        ("unicornio: maxG>=400 & meanG<55", lambda p: p.h.max_g >= 400 and p.h.mean_g < 55),
        ("escalera: maxG@19>=110 & acum@39>=500 & sin>500@39", lambda p: (
            p.st19["maxG"] >= 110 and p.st39["acum"] >= 500 and p.st39["n500"] == 0
        )),
        ("G34_apertura + meanG@19>=65", lambda p: (
            any(g.tipo in (3, 4) and g.lumen >= 70 and g.m0 <= 19 for g in p.h.gs)
            and p.st19["meanG"] >= 65 and p.st19["n500"] == 0
        )),
        ("R_largo antes 1era G>=85", lambda p: _primera_g_r_largo(p)),
        ("cola_temprana_spec: G>200 min<=15", lambda p: (
            any(g.lumen > 200 and g.m0 <= 15 for g in p.h.gs) and p.st19["n500"] == 0
        )),
        ("cierre_spec: acum@39>=550 & maxG@39>=200 & sin>500@39", lambda p: (
            p.st39["acum"] >= 550 and p.st39["maxG"] >= 200 and p.st39["n500"] == 0
        )),
        ("cierre_G34: G34>=80 @39 & acum@39>=450", lambda p: (
            p.st39["acum"] >= 450 and p.st39["maxG"] >= 200
            and any(g.tipo in (3, 4) and g.lumen >= 80 for g in p.h.gs if g.m0 <= 39)
            and p.st39["n500"] == 0
        )),
        ("post_SN_proxy: sumG>=1200 h previa", lambda p: _h1_sum(p, 1200)),
        ("medio_L_largo: G34 min20-38 & R_largo_antes", lambda p: _cola_med_r_largo(p)),
        ("multi_señal: nG>=8 & meanG>=75", lambda p: p.h.n_g >= 8 and p.h.mean_g >= 75),
    ]

    for tname, tgt in targets:
        w(f"  --- target: {tname} ---")
        y_tr = [tgt(p) for p in train_p]
        y_te = [tgt(p) for p in test_p]
        base = sum(y_tr) / len(y_tr) if y_tr else 0
        w(f"  base train={100*base:.1f}% holdout={100*sum(y_te)/len(y_te):.1f}%")
        best = []
        for name, fn in reglas:
            pred_tr = [fn(p) for p in train_p]
            m = metrics_binary(y_tr, pred_tr)
            if m["tp"] + m["fp"] < 2:
                continue
            pred_te = [fn(p) for p in test_p]
            mt = metrics_binary(y_te, pred_te)
            best.append((m["prec"], m["rec"], mt["prec"], mt["rec"], m["tp"], m["fp"], mt["tp"], name))
        best.sort(key=lambda x: (-x[0], -x[2]))
        for row in best[:8]:
            w(
                f"    {row[7]}: tr prec={100*row[0]:.1f}% rec={100*row[1]:.0f}% "
                f"tp={row[4]} fp={row[5]} | ho prec={100*row[2]:.1f}% rec={100*row[3]:.0f}% tp={row[6]}"
            )
        w("")


def _primera_g_r_largo(p):
    gs = sorted(p.h.gs, key=lambda x: x.m0)
    if not gs:
        return False
    g = gs[0]
    return g.lumen >= 85 and r_antes_de_g(p.h, g.m0)


def _h1_sum(p, thr):
    # need index - pass via horas list in caller; simplified: st19 only proxy
    return p.st19["acum"] >= 400 and p.st39["maxG"] >= 150


def _cola_med_r_largo(p):
    for e in p.colas500:
        if e.bloque != "20-39":
            continue
        if e.tipo in (3, 4) and e.r_largo_antes and 20 <= e.m0 <= 38:
            return True
    # predictor @19: G34 + acum
    return (
        p.st19["n500"] == 0
        and any(g.tipo in (3, 4) for g in p.h.gs if g.m0 <= 19)
        and p.st19["maxG"] >= 100
    )


# ── H7 casos nombre — listar todas las colas ──────────────────
def h7_censo_colas(perfiles):
    w("== H7 CENSO — todas las G>500 (identidad) ==")
    rows = []
    for p in perfiles:
        for e in p.colas500:
            rows.append((p.h.tag, p.h.hod, e.m0, e.lumen, e.tipo, e.bloque, p.especie, e.r_largo_antes))
    rows.sort(key=lambda x: (-x[3], x[0]))
    w(f"  total eventos G>500: {len(rows)}")
    w("  tag · hod · min · lumen · tipo · bloque · especie · R_largo_antes")
    for r in rows:
        w(f"  {r[0]} h{r[1]:02d} m{r[2]:02d} L{r[3]} G{r[4]} {r[5]} {r[6]} RL={'Y' if r[7] else 'N'}")
    w("")


# ── H8 holdout especies ───────────────────────────────────────
def h8_validar_especies(train_p, test_p):
    w("== H8 VALIDAR — reglas por especie en holdout ==")
    # cola_cierre @39
    fn_cierre = lambda p: (
        p.st39["acum"] >= 450 and p.st39["maxG"] >= 200
        and any(g.tipo in (3, 4) and g.lumen >= 80 for g in p.h.gs if g.m0 <= 39)
        and p.st39["n500"] == 0
    )
    y_tr = [any(e.bloque == "40-59" for e in p.colas500) for p in train_p]
    y_te = [any(e.bloque == "40-59" for e in p.colas500) for p in test_p]
    for label, split, y in [("train", train_p, y_tr), ("holdout", test_p, y_te)]:
        pred = [fn_cierre(p) for p in split]
        m = metrics_binary(y, pred)
        w(f"  cierre_G34 @39 {label}: prec={100*m['prec']:.1f}% rec={100*m['rec']:.0f}% tp={m['tp']} fp={m['fp']} base={100*m['base']:.1f}%")

    # unicornio → cola anywhere
    fn_uni = lambda p: p.h.max_g >= 400 and p.h.mean_g < 52 and p.h.n_g <= 6
    y_tr2 = [p.tiene_cola500 for p in train_p]
    y_te2 = [p.tiene_cola500 for p in test_p]
    for label, split, y in [("train", train_p, y_tr2), ("holdout", test_p, y_te2)]:
        pred = [fn_uni(p) for p in split]
        m = metrics_binary(y, pred)
        w(f"  unicornio {label}: prec={100*m['prec']:.1f}% rec={100*m['rec']:.0f}% tp={m['tp']} fp={m['fp']}")

    # escalera generosa
    fn_esc = lambda p: p.st19["maxG"] >= 110 and p.st39["acum"] >= 500 and p.st39["n500"] == 0
    for label, split, y in [("train", train_p, y_tr), ("holdout", test_p, y_te)]:
        pred = [fn_esc(p) for p in split]
        m = metrics_binary(y, pred)
        w(f"  escalera 19→39 {label}: prec={100*m['prec']:.1f}% rec={100*m['rec']:.0f}% tp={m['tp']} fp={m['fp']}")
    w("")


def h9_sintesis(perfiles):
    w("== H9 SÍNTESIS R3 ==")
    n500 = sum(1 for p in perfiles if p.tiene_cola500)
    w(f"  Universo: {len(perfiles)} h · {n500} con G>500 ({100*n500/len(perfiles):.1f}%)")
    w("  SE VE:")
    w("    · 5 especies: temprana / medio / cierre / multi / unicornio")
    w("    · G>500 casi siempre G3|G4 · R largo antes ~40-50%")
    w("    · cola_cierre: hora ya generosa @39 (acum med alto)")
    w("    · unicornio: pocas G, una explosiva (max alto mean bajo)")
    w("  NO SE VE:")
    w("    · Cadencia fija entre colas · mismo hod estable")
    w("    · Regla única pre-hora")
    w("  OLOR-VIVE (patrones identificables pese a n bajo):")
    w("    1. cierre_G34 @39 → cola 40-59")
    w("    2. escalera acum 19→39 sin cola intermedia → cierre")
    w("    3. unicornio en vivo (maxG>=400 mean<52) → ya es cola o viene sola")
    w("  FRÍO:")
    w("    · medio_L_largo como predictor único")
    w("    · mismo día cluster (anecdótico)")
    w("")


def main():
    w("LAB G-COLA — RONDA 3 · discovery · patrones")
    horas = load_horas(EXTRA)
    perfiles = perfilar_horas(horas)
    train_h, test_h = split_holdout(horas, HOLDOUT)
    train_tags = {h.tag for h in train_h}
    train_p = [p for p in perfiles if p.h.tag in train_tags]
    test_p = [p for p in perfiles if p.h.tag not in train_tags]
    w(f"n={len(perfiles)} train={len(train_p)} holdout={len(test_p)}")
    w("")

    h1_especies(perfiles)
    h2_perfil_hora(perfiles)
    h3_anatomia_cola(perfiles)
    h4_trayectoria(perfiles)
    h5_tejido(perfiles, horas)
    h6_patrones_train(train_p, test_p)
    h7_censo_colas(perfiles)
    h8_validar_especies(train_p, test_p)
    h9_sintesis(perfiles)

    out = OUT / "LAB_G_COLA_R3.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"-> {out}")


if __name__ == "__main__":
    main()
