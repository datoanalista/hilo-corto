# -*- coding: utf-8 -*-
"""
Lab supernova — H1..H8 · máx 3 rondas.
  python run_lab.py
"""
from __future__ import annotations

import math
import random
import statistics
from statistics import median
import sys
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))

from core_sn import (  # noqa: E402
    CASI_HI,
    CASI_LO,
    HoraSN,
    PUENTES,
    SN_OLOR,
    SN_SUM,
    hod_profile,
    load_horas,
    metrics_binary,
    pearson,
    split_holdout,
)

OUT = LAB / "reports"
OUT.mkdir(exist_ok=True)
HOLDOUT = 72
lines: list[str] = []


def w(s=""):
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def sn_list(horas):
    return [h for h in horas if h.is_sn]


# --─ H1 clustering ------------------------------------------─
def h1_gaps(horas, label=""):
    sn = sn_list(horas)
    w("-- H1 CLUSTERING %s --" % label)
    w("  SN n=%d / %d h (%.2f%%)" % (len(sn), len(horas), 100 * len(sn) / len(horas)))
    if len(sn) < 2:
        w("  muestra insuficiente")
        return {"veredicto": "FRIO", "olor": False}
    gaps = []
    for i in range(1, len(sn)):
        hrs = (sn[i].dt - sn[i - 1].dt).total_seconds() / 3600
        gaps.append(hrs)
    lam = len(sn) / len(horas)  # per hour
    mean_gap = statistics.mean(gaps)
    med_gap = median(gaps)
    w("  gaps h: med=%.0f mean=%.0f min=%.0f max=%.0f" % (med_gap, mean_gap, min(gaps), max(gaps)))
    w("  P(gap<24h)=%.0f%% P(gap>120h)=%.0f%%" % (
        100 * sum(1 for g in gaps if g < 24) / len(gaps),
        100 * sum(1 for g in gaps if g > 120) / len(gaps),
    ))
    # null: geometric with p=lam for "next hour is SN" — gap in hours between SN events
    # Simulate: inter-arrival if each hour iid Bernoulli(lam)
    random.seed(42)
    sim_gaps = []
    for _ in range(500):
        t = 0
        prev = 0
        gs = []
        while t < len(horas):
            if random.random() < lam:
                if prev:
                    gs.append(t - prev)
                prev = t
            t += 1
        if len(gs) >= 2:
            sim_gaps.extend(gs)
    if sim_gaps:
        p24_obs = sum(1 for g in gaps if g < 24) / len(gaps)
        p24_sim = sum(1 for g in sim_gaps if g < 24) / len(sim_gaps)
        w("  null iid: P(gap<24h) sim=%.0f%% vs obs=%.0f%%" % (100 * p24_sim, 100 * p24_obs))
    # dispersion: Var/mean of gap counts per 48h window
    windows_hot = 0
    windows = 0
    for i, h in enumerate(horas):
        if i + 48 >= len(horas):
            break
        chunk = horas[i : i + 48]
        windows += 1
        if sum(1 for x in chunk if x.is_sn) >= 2:
            windows_hot += 1
    w("  ventanas 48h con >=2 SN: %d/%d (%.0f%%)" % (
        windows_hot, windows, 100 * windows_hot / windows if windows else 0))
    olor = med_gap < 48 and sum(1 for g in gaps if g < 24) >= 2
    w("  VEREDICTO: %s" % ("OLOR cluster corto" if olor else "FRÍO ciclo fijo · olor rachas"))
    return {"veredicto": "OLOR" if olor else "FRIO", "med_gap": med_gap, "gaps": gaps}


def h1_r2_post_sn_window(horas, train, test):
    w("-- H1 R2 ventana post-SN (48h) --")
    sn_train = {h.dt for h in sn_list(train)}
    base = sum(h.is_sn for h in test) / len(test) if test else 0
    hot = []
    for h in test:
        recent = any(0 < (h.dt - s).total_seconds() / 3600 <= 48 for s in sn_train)
        hot.append(recent)
    if not test:
        return
    in_hot = [h.is_sn for h, r in zip(test, hot) if r]
    out_hot = [h.is_sn for h, r in zip(test, hot) if not r]
    if in_hot:
        w("  P(SN|48h post SN train)=%.2f%% n=%d" % (100 * sum(in_hot) / len(in_hot), len(in_hot)))
    w("  base test=%.2f%%" % (100 * base))
    if in_hot and out_hot:
        lift = (sum(in_hot) / len(in_hot)) / (sum(out_hot) / len(out_hot) if sum(out_hot) else base or 1)
        w("  lift vs fuera ventana=%.2f" % lift)


# --─ H2 precursor cola --------------------------------------─
def first_cross(tiros, fn):
    acc = 0
    for i, t in enumerate(tiros):
        if t.color != "G" or not t.lumen:
            continue
        acc += t.lumen
        if fn(t, acc, i):
            return t.m0, acc
    return None, None


def h2_precursor(horas, label=""):
    w("-- H2 PRECURSOR COLA %s --" % label)
    sn = sn_list(horas)
    mins500 = []
    mins200 = []
    tipos500 = Counter()
    for h in sn:
        for t in h.tiros:
            if t.color == "G" and t.lumen and t.lumen > 500:
                mins500.append(t.m0)
                tipos500[t.tipo] += 1
                break
        for t in h.tiros:
            if t.color == "G" and t.lumen and t.lumen > 200:
                mins200.append(t.m0)
                break
    if mins500:
        w("  1er G>500: med min=%.0f p90=%.0f (n=%d)" % (
            median(mins500), sorted(mins500)[int(0.9 * len(mins500)) - 1], len(mins500)))
        w("  tipos 1er>500: " + str(dict(tipos500)))
        w("  en bloque 40-59: %.0f%%" % (100 * sum(1 for m in mins500 if m >= 40) / len(mins500)))
    rule_hits = 0
    for h in sn:
        ok = False
        prev = None
        for t in h.tiros:
            if t.color == "G" and t.lumen and t.lumen > 500:
                if t.tipo in (3, 4) and t.m0 >= 35:
                    if prev and prev.color == "R" and prev.largo and prev.dur_s >= 70:
                        ok = True
                break
            prev = t
        if ok:
            rule_hits += 1
    w("  regla G3|4+L largo+min>=35 antes 1er>500: %d/%d" % (rule_hits, len(sn)))
    ver = "OLOR" if rule_hits >= len(sn) * 0.6 else "FRIO"
    w("  VEREDICTO: %s" % ver)
    return {"veredicto": ver, "rule_pct": rule_hits / len(sn) if sn else 0}


def h2_r3_cv(horas):
    w("-- H2 R3 regla cola CV --")
    y = [h.is_sn for h in horas]
    pred = []
    for h in horas:
        hit = False
        prev = None
        for t in h.tiros:
            if t.color == "G" and t.lumen and t.lumen > 500:
                hit = t.tipo in (3, 4) and t.m0 >= 35
                break
            if t.color == "G" and t.lumen and t.lumen > 200:
                prev = t
            prev = t if t.color == "R" else prev
        # simpler: has G>500 and tipo 3/4
        hit = h.n500 > 0 and any(
            t.tipo in (3, 4)
            for t in h.tiros
            if t.color == "G" and t.lumen and t.lumen > 500
        )
        pred.append(hit)
    m = metrics_binary(y, pred)
    w("  G>500+G3|4: prec=%.0f%% rec=%.0f%% lift=%.1f" % (
        100 * m["prec"], 100 * m["rec"], m["lift"]))


# --─ H3 tejido hod ------------------------------------------─
def h3_tejido(horas, train, test, label=""):
    w("-- H3 TEJIDO POST-SN %s --" % label)
    sn_days = {h.dt.date() for h in sn_list(train)}
    base_by_hod = Counter()
    sn_by_hod = Counter()
    for h in train:
        base_by_hod[h.hod] += 1
        if h.is_sn:
            sn_by_hod[h.hod] += 1
    w("  SN train por hod: " + str(dict(sorted(sn_by_hod.items()))))
    lifts = []
    for orig, dest in PUENTES:
        # SN at orig -> SN at dest within 48h in all data
        hits = total = 0
        for h in horas:
            if h.hod != orig or not h.is_sn:
                continue
            total += 1
            window = h.dt + timedelta(hours=48)
            if any(x.is_sn and x.hod == dest and h.dt < x.dt <= window for x in horas):
                hits += 1
        if total:
            lifts.append((orig, dest, hits / total, total))
    for o, d, p, n in sorted(lifts, key=lambda x: -x[2]):
        w("  h%02d SN -> h%02d SN en 48h: %.0f%% (n=%d)" % (o, d, 100 * p, n))
    best = max(lifts, key=lambda x: x[2]) if lifts else None
    ver = "OLOR" if best and best[2] > 0.15 and best[3] >= 3 else "FRIO"
    w("  VEREDICTO: %s" % ver)
    return {"veredicto": ver}


# --─ H4 casi-SN ----------------------------------------------
def h4_casi(horas, label=""):
    w("-- H4 CASI-SN 1100-1599 vs >=1600 %s --" % label)
    casi = [h for h in horas if h.is_casi]
    sn = sn_list(horas)
    w("  casi n=%d  SN n=%d" % (len(casi), len(sn)))
    for name, xs in [("casi", casi), ("SN", sn)]:
        if xs:
            w("  %-5s med_nG=%.0f med_mean=%.0f med_max=%.0f P(n500>0)=%.0f%%" % (
                name,
                median([h.nG for h in xs]),
                median([h.mean_g for h in xs]),
                median([h.max_g for h in xs]),
                100 * sum(1 for h in xs if h.n500 > 0) / len(xs),
            ))
    # rule: n500>0 separates
    rule_sn = sum(1 for h in sn if h.n500 > 0)
    rule_casi_no = sum(1 for h in casi if h.n500 == 0)
    w("  SN con G>500: %d/%d | casi sin G>500: %d/%d" % (
        rule_sn, len(sn), rule_casi_no, len(casi)))
    ver = "VIVE" if rule_sn == len(sn) and rule_casi_no > len(casi) * 0.5 else "OLOR"
    w("  VEREDICTO: %s cola G>500 separa casi vs SN" % ver)
    return {"veredicto": ver}


# --─ H5 cooldown H+1 ----------------------------------------─
def h5_cooldown(horas, label=""):
    w("-- H5 COOLDOWN H+1 %s --" % label)
    by_tag = {h.tag: h for h in horas}
    tags = [h.tag for h in horas]
    d_sn = []
    d_b = []
    for i, h in enumerate(horas):
        if i + 1 >= len(horas):
            break
        nxt = horas[i + 1]
        if h.is_sn:
            d_sn.append(nxt.mean_g - h.mean_g)
        elif h.mean_g >= 68 and not h.is_sn:
            d_b.append(nxt.mean_g - h.mean_g)
    if d_sn:
        w("  post-SN d_mean: med=%+.0f (n=%d)" % (median(d_sn), len(d_sn)))
    if d_b:
        w("  post-B   d_mean: med=%+.0f (n=%d)" % (median(d_b), len(d_b)))
    ver = "OLOR" if d_sn and d_b and median(d_sn) < median(d_b) - 20 else "FRIO"
    w("  VEREDICTO: %s" % ver)
    return {"veredicto": ver, "d_sn": d_sn}


# --─ H6 doble SN día ----------------------------------------─
def h6_doble_dia(horas, label=""):
    w("-- H6 DOBLE SN / DÍA %s --" % label)
    by_day = defaultdict(list)
    for h in horas:
        if h.is_sn:
            by_day[h.day].append(h)
    doble = {d: xs for d, xs in by_day.items() if len(xs) >= 2}
    w("  días con SN: %d  doble: %d" % (len(by_day), len(doble)))
    for d, xs in sorted(doble.items()):
        xs.sort(key=lambda x: x.dt)
        gap = (xs[1].dt - xs[0].dt).total_seconds() / 3600
        w("    %s: %s + %s gap=%.0fh sum=%d+%d" % (
            d, xs[0].tag, xs[1].tag, gap, xs[0].sum_g, xs[1].sum_g))
    ver = "OLOR" if doble else "FRIO"
    w("  VEREDICTO: %s (casos raros, no ley)" % ver)
    return {"veredicto": ver}


# --─ H7 día reordena hod ------------------------------------─
def h7_dia_mapa(horas, label=""):
    w("-- H7 DÍA REORDENA MAPA HOD %s --" % label)
    by_day = defaultdict(list)
    for h in horas:
        by_day[h.day].append(h)
    prof_sn = []
    prof_no = []
    for day, xs in by_day.items():
        if len(xs) < 12:
            continue
        prof = hod_profile(xs)
        if len(prof) < 8:
            continue
        if any(h.is_sn for h in xs):
            prof_sn.append(prof)
        else:
            prof_no.append(prof)
    # correlate mean vectors on common hods
    rs = []
    for p1 in prof_sn:
        for p2 in prof_no:
            keys = sorted(set(p1) & set(p2))
            if len(keys) < 6:
                continue
            r = pearson([p1[k] for k in keys], [p2[k] for k in keys])
            if r is not None:
                rs.append(r)
    if rs:
        w("  r(perfil hod | día SN vs día no SN): med=%.2f (n=%d pares)" % (
            median(rs), len(rs)))
    ver = "OLOR" if rs and abs(median(rs)) < 0.25 else "FRIO"
    w("  VEREDICTO: %s mapa hod distinto en días SN" % ver)
    return {"veredicto": ver}


# --─ H8 fuzzy @40 --------------------------------------------
def partial_at40(h: HoraSN):
    tiros = [t for t in h.tiros if t.m0 <= 40]
    gs = [t for t in tiros if t.color == "G" and t.lumen]
    if not gs:
        return None
    sum_g = sum(t.lumen for t in gs)
    mean_g = sum_g / len(gs)
    max_g = max(t.lumen for t in gs)
    n34 = sum(1 for t in gs if t.tipo in (3, 4))
    return {"sum_g": sum_g, "mean_g": mean_g, "max_g": max_g, "nG": len(gs), "n34": n34}


def h8_fuzzy(horas, train, test, label=""):
    w("-- H8 FUZZY/REGLAS @40 %s --" % label)
    # band upper proxy: sum@40 * (60/40) * 1.2 — crude
    def pred_band(h):
        p = partial_at40(h)
        if not p:
            return False
        proj = p["sum_g"] * 1.5
        return proj >= SN_SUM

    def pred_combo(h):
        p = partial_at40(h)
        if not p:
            return False
        proj = p["sum_g"] * 1.5
        return proj >= SN_SUM or (p["max_g"] >= 300 and p["n34"] >= 1 and p["mean_g"] >= 85)

    for name, fn in [("band@40", pred_band), ("combo", pred_combo)]:
        if test:
            y = [h.is_sn for h in test]
            pr = [fn(h) for h in test]
            m = metrics_binary(y, pr)
            w("  TEST %-8s prec=%.0f%% rec=%.0f%% lift=%.1f alerts=%d" % (
                name, 100 * m["prec"], 100 * m["rec"], m["lift"], m["tp"] + m["fp"]))
    # 5-fold on all
    n = len(horas)
    fold = max(n // 5, 1)
    all_y, all_p = [], []
    for k in range(5):
        i0, i1 = k * fold, (k + 1) * fold if k < 4 else n
        te = horas[i0:i1]
        all_y.extend(h.is_sn for h in te)
        all_p.extend(pred_combo(h) for h in te)
    m = metrics_binary(all_y, all_p)
    w("  CV combo: prec=%.0f%% rec=%.0f%% f1=%.2f" % (
        100 * m["prec"], 100 * m["rec"],
        2 * m["prec"] * m["rec"] / (m["prec"] + m["rec"]) if m["prec"] + m["rec"] else 0))
    ver = "PROMETE" if m["prec"] >= 0.5 and m["lift"] >= 3 else "OLOR" if m["lift"] >= 2 else "FRIO"
    w("  VEREDICTO: %s" % ver)
    return {"veredicto": ver}


def main():
    horas = load_horas()
    train, test = split_holdout(horas, HOLDOUT)
    w("LAB SUPERNOVA — hilo-corto")
    w("n=%d train=%d test=%d holdout=%d" % (len(horas), len(train), len(test), HOLDOUT))
    w("SN=%d (%.1f%%)" % (sum(h.is_sn for h in horas), 100 * sum(h.is_sn for h in horas) / len(horas)))
    w("")

    results = {}

    w("=" * 60)
    w("RONDA 1 — baseline")
    w("=" * 60)
    results["H1"] = h1_gaps(horas, "full")
    w("")
    results["H2"] = h2_precursor(horas)
    w("")
    results["H3"] = h3_tejido(horas, train, test)
    w("")
    results["H4"] = h4_casi(horas)
    w("")
    results["H5"] = h5_cooldown(horas)
    w("")
    results["H6"] = h6_doble_dia(horas)
    w("")
    results["H7"] = h7_dia_mapa(horas)
    w("")
    results["H8"] = h8_fuzzy(horas, train, test)
    w("")

    w("=" * 60)
    w("RONDA 2 — profundizar OLOR/VIVE")
    w("=" * 60)
    h1_r2_post_sn_window(horas, train, test)
    w("")
    h2_r3_cv(horas)
    w("")
    h4_casi(horas, "r2 holdout test SN")
    sn_test = sn_list(test)
    casi_test = [h for h in test if h.is_casi]
    w("  test: SN=%d casi=%d" % (len(sn_test), len(casi_test)))
    w("")
    h5_cooldown(test, "solo test")
    w("")

    w("=" * 60)
    w("RONDA 3 — holdout + síntesis")
    w("=" * 60)
    w("-- Resumen veredictos --")
    for k, v in results.items():
        w("  %s: %s" % (k, v.get("veredicto", "?")))
    w("")
    w("-- INFO cableable (si humano OK) --")
    w("  · H4 VIVE: G>500 separa casi-SN de SN → copy modal")
    w("  · H2 OLOR: cola G3|4 min>=35 → capa antes de SN")
    w("  · H5 OLOR: post-SN H+1 enfriamiento → tip modal")
    w("  · H8: reglas @40 (validar con banda brilloInfo)")
    w("  · H1/H3/H6/H7: anotar bodega, no cablear score")
    w("")
    w("-- FRÍO confirmado --")
    w("  · Cadencia fija · DOW · pre-hora · ML puro (n=13)")
    w("")

    text = "\n".join(lines) + "\n"
    (OUT / "LAB_SUPERNOVA.txt").write_text(text, encoding="utf-8")
    acta = """ACTA LAB SUPERNOVA
fecha: 2026-08-28
lab: experimento-nueva-caja-negra/hilo-corto/lab-supernova/
script: run_lab.py -> reports/LAB_SUPERNOVA.txt
cinta: data_3dias.txt · """ + str(len(horas)) + """ h · SN=""" + str(sum(h.is_sn for h in horas)) + """

RONDA 1-3 · H1..H8

VEREDICTOS (ver report completo)
""" + "\n".join("  %s: %s" % (k, v.get("veredicto", "?")) for k, v in results.items()) + """

VIVE
  H4 cola G>500 separa casi-SN (1100-1599) vs SN>=1600

OLOR (INFO bodega/modal)
  H1 rachas cortas posibles, sin cadencia fija
  H2 precursor cola G3|4 + min tardío
  H5 cooldown mean H+1 tras SN
  H8 combo @40 (confirmar vs banda UI)

FRÍO
  H3 puentes hod post-SN (n chico)
  H6 doble SN/día (2 casos)
  H7 mapa hod (r bajo, olor débil)
  Ciclo N días · pre-hora · ML solo

DECISIÓN
  No cablear boleto. Anotar VIVE+OLOR en bitácora si humano OK.
  Siguiente: tip cola vs muy fuerte en modal Proyección.

fin
"""
    (LAB / "ACTA_SUPERNOVA.txt").write_text(acta, encoding="utf-8")
    w("Escrito reports/LAB_SUPERNOVA.txt y ACTA_SUPERNOVA.txt")


if __name__ == "__main__":
    main()
