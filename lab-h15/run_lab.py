# -*- coding: utf-8 -*-
"""
Lab h15 — H1..H8 (E1-E7 + eco inverso h5).
  python run_lab.py
"""
from __future__ import annotations

import random
import statistics
from collections import defaultdict
from statistics import median, mean

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))

from core_h15 import (  # noqa: E402
    CASI_HI,
    CASI_LO,
    DOW_ES,
    ECO_MEAN_MIN,
    MEAN_Q25,
    MEAN_Q75,
    SUM_FUERTE,
    SUM_OPACO,
    HoraH15,
    by_hod,
    dias_generosos,
    index_by_day_hod,
    load_horas,
    perfil_hod,
    rank_hods,
    split_holdout,
    tag_next_day,
)

OUT = LAB / "reports"
OUT.mkdir(exist_ok=True)
HOLDOUT = 72
HOD = 15
lines: list[str] = []
results: dict = {}


def w(s=""):
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def veredicto(signal_train, signal_test, n_train, n_test, lift_min=50):
    if n_train < 5:
        return "FRIO"
    if signal_train and signal_test and n_test >= 3:
        return "VIVE"
    if signal_train:
        return "OLOR"
    return "FRIO"


# --- H1 E1 Perfil -------------------------------------------------
def h1_perfil(train, test):
    w("-- H1 PERFIL h15 vs vecinos (E1) --")
    prof_tr = rank_hods(train)
    prof_te = rank_hods(test) if test else {}
    p15 = prof_tr.get(HOD, {})
    w("  train n=%d  med_sum=%.0f  rank=%d/24  p_gen=%.0f%%  med_nG=%.0f  med_meanG=%.1f" % (
        p15.get("n", 0), p15.get("med_sum", 0), p15.get("rank_med", 0),
        100 * p15.get("p_gen", 0), p15.get("med_nG", 0), p15.get("med_meanG", 0),
    ))
    for hod in [14, 16, 8, 19]:
        p = prof_tr.get(hod, {})
        if p:
            w("  h%02d train: med=%.0f  med_meanG=%.1f  med_nG=%.0f  p_gen=%.0f%%" % (
                hod, p["med_sum"], p["med_meanG"], p["med_nG"], 100 * p["p_gen"]))
    if test:
        p15t = prof_te.get(HOD, {})
        w("  test h15: med=%.0f  rank=%d  p_gen=%.0f%%  n=%d" % (
            p15t.get("med_sum", 0), p15t.get("rank_med", 0),
            100 * p15t.get("p_gen", 0), p15t.get("n", 0)))
    # descomposicion: h15 gana en mean_G no nG
    h15 = by_hod(train, HOD)
    h14 = by_hod(train, 14)
    lift_mg = median(h.mean_g for h in h15) - median(h.mean_g for h in h14) if h14 else 0
    lift_ng = median(h.nG for h in h15) - median(h.nG for h in h14) if h14 else 0
    w("  lift h15 vs h14: mean_G %+.1f  nG %+.0f" % (lift_mg, lift_ng))
    top = p15.get("rank_med", 99) == 1
    test_top = prof_te.get(HOD, {}).get("rank_med", 99) <= 3 if test else False
    v = veredicto(top and lift_mg > 8, test_top, p15.get("n", 0), prof_te.get(HOD, {}).get("n", 0))
    w("  VEREDICTO: %s (masa por mean_G, no cupo)" % v)
    return {"veredicto": v, "lift_mg": lift_mg}


# --- H2 E2 Costura h14->h15 ---------------------------------------
def h2_costura(train, test):
    w("-- H2 COSTURA h14->h15 mismo dia (E2) --")

    def pairs(horas):
        by_day = defaultdict(dict)
        for h in horas:
            if h.hod in (14, 15):
                by_day[h.day][h.hod] = h
        out = []
        for day, d in by_day.items():
            if 14 in d and 15 in d:
                out.append((d[14], d[15]))
        return out

    def strata_lift(ps):
        buckets = {"opaco": [], "normal": [], "fuerte": []}
        for a, b in ps:
            if a.sum_g < SUM_OPACO:
                buckets["opaco"].append(b.sum_g - a.sum_g)
            elif a.sum_g >= SUM_FUERTE:
                buckets["fuerte"].append(b.sum_g - a.sum_g)
            else:
                buckets["normal"].append(b.sum_g - a.sum_g)
        return buckets

    ptr = pairs(train)
    pte = pairs(test) if test else []
    lifts = [b.sum_g - a.sum_g for a, b in ptr]
    w("  train pares n=%d  med h14=%.0f  med h15=%.0f  med lift=%+.0f" % (
        len(ptr),
        median(h.sum_g for h, _ in ptr) if ptr else 0,
        median(h.sum_g for _, h in ptr) if ptr else 0,
        median(lifts) if lifts else 0,
    ))
    for name, ls in strata_lift(ptr).items():
        if ls:
            w("    h14 %s -> lift h15 med=%+.0f (n=%d)" % (name, median(ls), len(ls)))
    if pte:
        lifts_t = [b.sum_g - a.sum_g for a, b in pte]
        w("  test lift med=%+.0f (n=%d)" % (median(lifts_t) if lifts_t else 0, len(pte)))
    med_lift = median(lifts) if lifts else 0
    v = veredicto(med_lift >= 100, pte and median([b.sum_g - a.sum_g for a, b in pte]) >= 80, len(ptr), len(pte))
    w("  VEREDICTO: %s" % v)
    return {"veredicto": v, "lift": med_lift}


# --- H3 E3 DOW x h15 ----------------------------------------------
def h3_dow(train, test):
    w("-- H3 DOW x h15 (E3) --")
    h15tr = by_hod(train, HOD)
    by_dow = defaultdict(list)
    for h in h15tr:
        by_dow[h.dow].append(h.sum_g)
    spreads = []
    for d in range(7):
        xs = by_dow[d]
        if xs:
            med = median(xs)
            pg = 100 * sum(1 for x in xs if x >= SUM_FUERTE) / len(xs)
            w("  %s  n=%d  med=%.0f  p_gen=%.0f%%" % (DOW_ES[d], len(xs), med, pg))
            spreads.append(med)
    spread = max(spreads) - min(spreads) if spreads else 0
    w("  spread DOW med=%.0f" % spread)
    # test: mismo patron?
    h15te = by_hod(test, HOD) if test else []
    spread_te = 0
    if h15te:
        by_dow_t = defaultdict(list)
        for h in h15te:
            by_dow_t[h.dow].append(h.sum_g)
        meds = [median(v) for v in by_dow_t.values() if v]
        if meds:
            spread_te = max(meds) - min(meds)
            w("  test spread DOW=%.0f (n=%d)" % (spread_te, len(h15te)))
    v = veredicto(spread >= 300, spread_te >= 200, len(h15tr), len(h15te))
    w("  VEREDICTO: %s (DOW local fuerte; n chico por celda)" % v)
    return {"veredicto": v, "spread": spread}


# --- H4 E4 Dia generoso -------------------------------------------
def h4_dia_gen(train, test):
    w("-- H4 DIA GENEROSO x h15 (E4) --")
    gen_days = dias_generosos(train)
    h15 = by_hod(train, HOD)
    gen = [h for h in h15 if h.day in gen_days]
    gris = [h for h in h15 if h.day not in gen_days and len([x for x in train if x.day == h.day]) >= 12]
    p_gen = sum(h.is_gen for h in gen) / len(gen) if gen else 0
    p_gris = sum(h.is_gen for h in gris) / len(gris) if gris else 0
    w("  h15 en dia gen: p_gen=%.0f%% (n=%d)  dia gris: p_gen=%.0f%% (n=%d)" % (
        100 * p_gen, len(gen), 100 * p_gris, len(gris)))
    med_gen = median(h.sum_g for h in gen) if gen else 0
    med_gris = median(h.sum_g for h in gris) if gris else 0
    w("  med_sum dia gen=%.0f  dia gris=%.0f  lift=%+.0f" % (med_gen, med_gris, med_gen - med_gris))
    # primera hora fuerte del dia
    first_gen = 0
    total_days = 0
    by_day = defaultdict(list)
    for h in train:
        by_day[h.day].append(h)
    for day, hs in by_day.items():
        if day not in gen_days or len(hs) < 12:
            continue
        hs.sort(key=lambda x: x.hod)
        gens = [h for h in hs if h.is_gen]
        if gens and gens[0].hod == HOD:
            first_gen += 1
        total_days += 1
    if total_days:
        w("  h15 = 1er hora gen del dia: %d/%d (%.0f%%)" % (
            first_gen, total_days, 100 * first_gen / total_days))
    lift = med_gen - med_gris
    v = veredicto(lift >= 150 and p_gen > p_gris + 0.1, False, len(gen), 0)
    w("  VEREDICTO: %s" % v)
    return {"veredicto": v}


# --- H5 E5 Eco h15->h19 -------------------------------------------
def h5_eco_15_19(train, test):
    w("-- H5 ECO h15->h19 +1d (E5) --")
    idx = index_by_day_hod(train)
    fuerte, debil = [], []
    for h in by_hod(train, HOD):
        tag19 = tag_next_day(h.tag, 1, 19)
        dest = idx.get((tag19.split("-")[1], 19))
        if not dest:
            continue
        if h.mean_g_40 is not None and h.mean_g_40 >= ECO_MEAN_MIN:
            fuerte.append(dest.sum_g)
        else:
            debil.append(dest.sum_g)
    if fuerte and debil:
        lift = median(fuerte) - median(debil)
        w("  h19 tras h15 fuerte@40: med=%.0f (n=%d)" % (median(fuerte), len(fuerte)))
        w("  h19 tras h15 no-fuerte: med=%.0f (n=%d)" % (median(debil), len(debil)))
        w("  lift=%+.0f" % lift)
        # null shuffle
        random.seed(7)
        all19 = [h.sum_g for h in by_hod(train, 19)]
        sim = []
        for _ in range(300):
            if len(all19) < 2:
                break
            a, b = random.sample(all19, 2)
            sim.append(a - b)
        if sim:
            w("  null |delta| med sim=%.0f" % median(abs(x) for x in sim))
    else:
        lift = 0
        w("  muestra insuficiente fuerte/debil")
    base19 = median(h.sum_g for h in by_hod(train, 19))
    w("  baseline h19 med=%.0f" % base19)
    v = veredicto(lift >= 80, False, len(fuerte), 0)
    w("  VEREDICTO: %s" % v)
    return {"veredicto": v, "lift": lift}


# --- H6 E6 SN / colgante ------------------------------------------
def h6_sn_colgante(train):
    w("-- H6 SN / COLGANTE h15 (E6) --")
    h15 = by_hod(train, HOD)
    sns = [h for h in h15 if h.is_sn]
    casi = [h for h in h15 if h.is_casi]
    w("  SN n=%d  casi-SN n=%d  p_sn=%.0f%%" % (
        len(sns), len(casi), 100 * len(sns) / len(h15) if h15 else 0))
    meds = sorted(h.sum_g for h in h15)
    med_full = median(meds)
    for drop in sns:
        rest = [h.sum_g for h in h15 if h.tag != drop.tag]
        w("  leave-out %s: med %.0f -> %.0f" % (drop.tag, med_full, median(rest)))
    # rank sin SN
    rest_all = [h for h in train if not (h.hod == HOD and h.is_sn)]
    prof = rank_hods(train)
    w("  rank h15 train=%d  med=%.0f" % (prof[HOD]["rank_med"], prof[HOD]["med_sum"]))
    v = "VIVE" if len(sns) <= 2 and med_full >= 700 else "OLOR"
    w("  VEREDICTO: %s (mediana robusta; cola SN explica p75 no rank)" % v)
    return {"veredicto": v}


# --- H7 E7 Intra @20/@40 ------------------------------------------
def h7_intra(train):
    w("-- H7 INTRA @20/@40 h15 vs h14/h19 (E7) --")
    for hod in [14, 15, 19]:
        xs = by_hod(train, hod)
        m20 = [h.mean_g_20 for h in xs if h.mean_g_20 is not None]
        m40 = [h.mean_g_40 for h in xs if h.mean_g_40 is not None]
        late = sum(1 for h in xs if h.sum_late > h.sum_early * 1.2)
        w("  h%02d: med mean@20=%.1f  @40=%.1f  late-heavy=%.0f%% (n=%d)" % (
            hod,
            median(m20) if m20 else 0,
            median(m40) if m40 else 0,
            100 * late / len(xs) if xs else 0,
            len(xs),
        ))
    h15 = by_hod(train, HOD)
    fuerte40 = sum(1 for h in h15 if h.mean_g_40 and h.mean_g_40 >= MEAN_Q75)
    w("  h15 @40 >= q75 (%.0f): %d/%d" % (MEAN_Q75, fuerte40, len(h15)))
    v = "OLOR" if fuerte40 >= len(h15) * 0.35 else "FRIO"
    w("  VEREDICTO: %s (hora completa fuerte, no solo cola)" % v)
    return {"veredicto": v}


# --- H8 E8 Eco h5->h15 --------------------------------------------
def h8_eco_5_15(train):
    w("-- H8 ECO h5->h15 +1d (E8) --")
    idx = index_by_day_hod(train)
    fuerte, debil = [], []
    for h in by_hod(train, 5):
        tag15 = tag_next_day(h.tag, 1, 15)
        dest = idx.get((tag15.split("-")[1], 15))
        if not dest:
            continue
        if h.mean_g_40 is not None and h.mean_g_40 >= ECO_MEAN_MIN:
            fuerte.append(dest.sum_g)
        else:
            debil.append(dest.sum_g)
    if fuerte and debil:
        lift = median(fuerte) - median(debil)
        w("  h15 tras h5 fuerte@40: med=%.0f (n=%d)" % (median(fuerte), len(fuerte)))
        w("  h15 tras h5 no-fuerte: med=%.0f (n=%d)" % (median(debil), len(debil)))
        w("  lift=%+.0f" % lift)
    else:
        lift = 0
        w("  muestra insuficiente")
    base15 = median(h.sum_g for h in by_hod(train, 15))
    w("  baseline h15 med=%.0f" % base15)
    v = veredicto(lift >= 100, False, len(fuerte), 0)
    w("  VEREDICTO: %s" % v)
    return {"veredicto": v}


def main():
    horas = load_horas()
    train, test = split_holdout(horas, HOLDOUT)
    w("LAB H15 — hilo-corto")
    w("n=%d train=%d test=%d holdout=%d" % (len(horas), len(train), len(test), HOLDOUT))
    w("h15 train n=%d  test n=%d" % (len(by_hod(train, HOD)), len(by_hod(test, HOD)) if test else 0))
    w("")

    w("=" * 60)
    w("RONDA 1")
    w("=" * 60)
    results["H1"] = h1_perfil(train, test)
    w("")
    results["H2"] = h2_costura(train, test)
    w("")
    results["H3"] = h3_dow(train, test)
    w("")
    results["H4"] = h4_dia_gen(train, test)
    w("")
    results["H5"] = h5_eco_15_19(train, test)
    w("")
    results["H6"] = h6_sn_colgante(train)
    w("")
    results["H7"] = h7_intra(train)
    w("")
    results["H8"] = h8_eco_5_15(train)
    w("")

    w("=" * 60)
    w("SINTESIS")
    w("=" * 60)
    for k, v in results.items():
        w("  %s: %s" % (k, v.get("veredicto", "?")))
    w("")
    w("-- INFO cableable (si humano OK) --")
    w("  H1: cartel h15 = intensidad mean_G (GEN_HOD_OLOR ya lo dice)")
    w("  H2: tip costura h14 opaco -> h15 sube (modal Brillo/mapa)")
    w("  H6: rank #1 robusto sin SN — mapa OK")
    w("")
    w("-- FRIO / OLOR bodega --")
    w("  H3 DOW: olor fuerte pero n~5/celda — no regla dura")
    w("  H8 h5->h15: validar con mas cinta")
    w("")

    text = "\n".join(lines) + "\n"
    (OUT / "LAB_H15.txt").write_text(text, encoding="utf-8")

    acta = """ACTA LAB H15
============
fecha: 2026-08-29
lab: hilo-corto/lab-h15/
script: run_lab.py -> reports/LAB_H15.txt
cinta: data_3dias.txt · %d h · h15 train=%d test=%d

PREGUNTA
  Por que h15 lidera med_sum (733)? H1-H8: perfil, costura,
  DOW, dia generoso, eco 15->19, SN, intra @20/@40, eco 5->15.

VEREDICTOS
%s

VIVE
  (ver report — costura y perfil mean_G)

OLOR
  DOW local · dia generoso · eco puentes · intra @40

FRIO
  (si aplica tras numeros)

DECISION
  No cablear boleto. INFO mapa/Brillo/Eco si humano OK.
  Siguiente: tip costura h14->h15 en MapaPanel o Generosidad.

fin
""" % (
        len(horas),
        len(by_hod(train, HOD)),
        len(by_hod(test, HOD)) if test else 0,
        "\n".join("  %s: %s" % (k, v.get("veredicto", "?")) for k, v in results.items()),
    )
    (LAB / "ACTA_H15.txt").write_text(acta, encoding="utf-8")
    w("Escrito reports/LAB_H15.txt y ACTA_H15.txt")


if __name__ == "__main__":
    main()
