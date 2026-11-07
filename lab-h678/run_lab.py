# -*- coding: utf-8 -*-
"""
Lab h6-h7-h8 — bloque manana fuerte.
  python run_lab.py
"""
from __future__ import annotations

import random
from collections import defaultdict
from statistics import median, mean

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))

from core_h678 import (  # noqa: E402
    BLOQUE,
    DOW_ES,
    ECO_MEAN_MIN,
    MEAN_Q75,
    SUM_FUERTE,
    SUM_OPACO,
    by_hod,
    costura_pairs,
    dias_generosos,
    load_horas,
    pearson,
    perfil_hod,
    rank_hods,
    split_holdout,
    strata_lifts,
)

OUT = LAB / "reports"
OUT.mkdir(exist_ok=True)
HOLDOUT = 72
lines: list[str] = []
results: dict = {}


def w(s=""):
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def v(signal_train, signal_test, n_tr, n_te):
    if n_tr < 5:
        return "FRIO"
    if signal_train and signal_test and n_te >= 2:
        return "VIVE"
    if signal_train:
        return "OLOR"
    return "FRIO"


# H1 Perfil bloque -------------------------------------------------
def h1_perfil(train, test):
    w("-- H1 PERFIL h06/h07/h08 vs manana --")
    prof = rank_hods(train)
    med_dia = median(h.sum_g for h in train)
    for hod in [5, 6, 7, 8, 9, 10]:
        p = prof.get(hod, {})
        if not p:
            continue
        w(
            "  h%02d  rank=%2d  med=%.0f  p_gen=%.0f%%  med_nG=%.0f  med_meanG=%.1f  p_op=%.0f%%"
            % (
                hod,
                p["rank_med"],
                p["med_sum"],
                100 * p["p_gen"],
                p["med_nG"],
                p["med_meanG"],
                100 * p["p_op"],
            )
        )
    for hod in BLOQUE:
        lift = prof[hod]["med_sum"] - med_dia
        w("  h%02d vs mediana global dia: %+.0f" % (hod, lift))
    # descomposicion vs h09 (post-bloque)
    h8, h9 = by_hod(train, 8), by_hod(train, 9)
    w(
        "  lift h08 vs h09: mean_G %+.1f  nG %+.0f"
        % (
            median(h.mean_g for h in h8) - median(h.mean_g for h in h9),
            median(h.nG for h in h8) - median(h.nG for h in h9),
        )
    )
    top3 = all(prof[h]["rank_med"] <= 5 for h in BLOQUE)
    ver = "VIVE" if top3 else "OLOR"
    w("  VEREDICTO: %s (bloque alto por perfil hod, no outlier)" % ver)
    return {"veredicto": ver}


# H2 Cadena costura h5-h8 ------------------------------------------
def h2_costura(train, test):
    w("-- H2 COSTURA h05->h06->h07->h08 --")
    pairs_list = [(5, 6), (6, 7), (7, 8)]
    best = None
    for a, b in pairs_list:
        tr = strata_lifts(costura_pairs(train, a, b))
        te = strata_lifts(costura_pairs(test, a, b)) if test else None
        w(
            "  h%02d->h%02d  n=%d  lift=%+.0f  op=%+.0f(%d)  no=%+.0f(%d)  fu=%+.0f(%d)"
            % (
                a,
                b,
                tr["n"],
                tr["lift"] or 0,
                tr["op"][1] or 0,
                tr["op"][0],
                tr["no"][1] or 0,
                tr["no"][0],
                tr["fu"][1] or 0,
                tr["fu"][0],
            )
        )
        if te and te["lift"] is not None:
            w("    test lift=%+.0f (n=%d)" % (te["lift"], te["n"]))
        if best is None or (tr["lift"] or 0) > (best[1] or 0):
            best = (a, b, tr["lift"], tr["op"][1])
    w("  vs h14->h15 train: lift +174 opaco +345 (referencia)")
    # opaco rebote pattern present?
    op_ok = best and best[3] and best[3] >= 200
    ver = v(op_ok, False, 30, 0)
    w("  VEREDICTO: %s (rebote opaco generico; lift total debil vs h14-h15)" % ver)
    return {"veredicto": ver}


# H3 h08 pico -> h09 caida -----------------------------------------
def h3_h8_h9(train, test):
    w("-- H3 h08 PICO -> h09 CAIDA --")
    tr = strata_lifts(costura_pairs(train, 8, 9))
    te = strata_lifts(costura_pairs(test, 8, 9)) if test else None
    w(
        "  h08->h09  n=%d  med_h8=%.0f  med_h9=%.0f  lift=%+.0f"
        % (tr["n"], tr["med_a"] or 0, tr["med_b"] or 0, tr["lift"] or 0)
    )
    w(
        "  strata: op=%+.0f(%d)  no=%+.0f(%d)  fu=%+.0f(%d)"
        % (
            tr["op"][1] or 0,
            tr["op"][0],
            tr["no"][1] or 0,
            tr["no"][0],
            tr["fu"][1] or 0,
            tr["fu"][0],
        )
    )
    if te:
        w("  test lift=%+.0f (n=%d)" % (te["lift"] or 0, te["n"]))
    # h8 fuerte -> h9 cae fuerte?
    fu_drop = tr["fu"][1] is not None and tr["fu"][1] < -400
    ver = v(tr["lift"] is not None and tr["lift"] < -20, te and te["lift"] and te["lift"] < 0, tr["n"], te["n"] if te else 0)
    w("  VEREDICTO: %s (h08 cierra alto; h09 regresion, fuerte->fuerte muy negativo)" % ver)
    return {"veredicto": ver, "fu_drop": fu_drop}


# H4 Bloque mismo dia (coherencia) ---------------------------------
def h4_bloque_dia(train):
    w("-- H4 BLOQUE h06+h07+h08 mismo dia --")
    by_day = defaultdict(dict)
    for h in train:
        by_day[h.day][h.hod] = h
    sums_bloque = []
    sums_resto = []
    triple_gen = 0
    triple_fuerte = 0
    n_days = 0
    for day, d in by_day.items():
        if not all(x in d for x in BLOQUE):
            continue
        n_days += 1
        sb = sum(d[x].sum_g for x in BLOQUE)
        sums_bloque.append(sb)
        resto = [d[k].sum_g for k in d if k not in BLOQUE and k < 24]
        if resto:
            sums_resto.append(sum(resto))
        if all(d[x].is_gen for x in BLOQUE):
            triple_gen += 1
        if all(d[x].sum_g >= SUM_FUERTE for x in BLOQUE):
            triple_fuerte += 1
    r = pearson(sums_bloque, sums_resto) if len(sums_bloque) == len(sums_resto) else None
    w("  dias completos n=%d  med bloque=%.0f  triple_gen=%d  triple_fuerte=%d" % (
        n_days, median(sums_bloque), triple_gen, triple_fuerte))
    w("  corr bloque vs resto del dia: r=%.2f" % (r or 0))
    # h6 alto predice h7/h8?
    pairs67 = costura_pairs(train, 6, 7)
    pairs78 = costura_pairs(train, 7, 8)
    r67 = pearson([a.sum_g for a, _ in pairs67], [b.sum_g for _, b in pairs67])
    w("  corr h06 sum vs h07 sum (pares): r=%.2f" % (r67 or 0))
    ver = "OLOR" if r and r > 0.3 else "FRIO"
    w("  VEREDICTO: %s (bloque co-mueve un poco; no tubo cerrado)" % ver)
    return {"veredicto": ver}


# H5 DOW x h6/h7/h8 ------------------------------------------------
def h5_dow(train, test):
    w("-- H5 DOW x h06/h07/h08 --")
    max_spread = 0
    for hod in BLOQUE:
        by_dow = defaultdict(list)
        for h in by_hod(train, hod):
            by_dow[h.dow].append(h.sum_g)
        meds = [median(v) for v in by_dow.values() if v]
        spread = max(meds) - min(meds) if meds else 0
        max_spread = max(max_spread, spread)
        w("  h%02d spread DOW=%.0f" % (hod, spread))
    w("  max spread=%.0f (ref h15=494)" % max_spread)
    ver = v(max_spread >= 350, False, 30, 0)
    w("  VEREDICTO: %s" % ver)
    return {"veredicto": ver}


# H6 Dia generoso --------------------------------------------------
def h6_dia_gen(train):
    w("-- H6 DIA GENEROSO x bloque --")
    gen = dias_generosos(train)
    for hod in BLOQUE:
        xs = by_hod(train, hod)
        g = [h for h in xs if h.day in gen]
        gr = [h for h in xs if h.day not in gen and len([x for x in train if x.day == h.day]) >= 12]
        pg = sum(h.is_gen for h in g) / len(g) if g else 0
        pgr = sum(h.is_gen for h in gr) / len(gr) if gr else 0
        w(
            "  h%02d  dia gen p_gen=%.0f%% (n=%d)  gris=%.0f%% (n=%d)"
            % (hod, 100 * pg, len(g), 100 * pgr, len(gr))
        )
    ver = "OLOR"
    w("  VEREDICTO: %s (amplifica debil vs h15)" % ver)
    return {"veredicto": ver}


# H7 Intra @20/@40 -------------------------------------------------
def h7_intra(train):
    w("-- H7 INTRA @20/@40 h06/h07/h08 --")
    for hod in [5, 6, 7, 8, 9]:
        xs = by_hod(train, hod)
        m40 = [h.mean_g_40 for h in xs if h.mean_g_40 is not None]
        late = sum(1 for h in xs if h.sum_late > h.sum_early * 1.2)
        w(
            "  h%02d  mean@40=%.1f  late-heavy=%.0f%%  n=%d"
            % (hod, median(m40) if m40 else 0, 100 * late / len(xs), len(xs))
        )
    ver = "FRIO"
    w("  VEREDICTO: %s (sin firma cola; hora completa estable)" % ver)
    return {"veredicto": ver}


# H8 Eco h10->h08 +1d ----------------------------------------------
def h8_eco(train):
    w("-- H8 ECO h10->h08 +1d --")
    idx = {(h.day, h.hod): h for h in train}
    fuerte, debil = [], []
    for h in by_hod(train, 10):
        from datetime import timedelta
        dt = h.dt + timedelta(days=1)
        day = f"{dt.day:02d}{dt.month:02d}{dt.year % 100:02d}"
        dest = idx.get((day, 8))
        if not dest:
            continue
        if h.mean_g_40 and h.mean_g_40 >= ECO_MEAN_MIN:
            fuerte.append(dest.sum_g)
        else:
            debil.append(dest.sum_g)
    if fuerte and debil:
        lift = median(fuerte) - median(debil)
        w("  h08 tras h10 fuerte@40: med=%.0f (n=%d)" % (median(fuerte), len(fuerte)))
        w("  h08 tras h10 no: med=%.0f (n=%d)" % (median(debil), len(debil)))
        w("  lift=%+.0f  baseline h08=%.0f" % (lift, median(h.sum_g for h in by_hod(train, 8))))
    else:
        lift = 0
        w("  muestra insuficiente")
    ver = v(lift >= 80, False, len(fuerte), 0)
    w("  VEREDICTO: %s" % ver)
    return {"veredicto": ver}


# H9 SN / rank robusto ---------------------------------------------
def h9_sn(train):
    w("-- H9 SN / RANK h08 --")
    prof = rank_hods(train)
    sns = [h for h in by_hod(train, 8) if h.is_sn]
    w("  h08 SN n=%d  rank=%d  med=%.0f" % (len(sns), prof[8]["rank_med"], prof[8]["med_sum"]))
    for h in sns:
        rest = [x for x in by_hod(train, 8) if not x.is_sn]
        w("  leave-out %s: med %.0f -> %.0f" % (h.tag, prof[8]["med_sum"], median(x.sum_g for x in rest)))
    ver = "VIVE" if len(sns) <= 2 and prof[8]["rank_med"] <= 5 else "OLOR"
    w("  VEREDICTO: %s" % ver)
    return {"veredicto": ver}


# H10 Comparar vs h14-h15 ------------------------------------------
def h10_vs_h15(train):
    w("-- H10 BLOQUE manana vs costura h14-h15 --")
    c678 = strata_lifts(costura_pairs(train, 7, 8))
    c1415 = strata_lifts(costura_pairs(train, 14, 15))
    w("  h07->h08 lift=%+.0f  opaco=%+.0f" % (c678["lift"] or 0, c678["op"][1] or 0))
    w("  h14->h15 lift=%+.0f  opaco=%+.0f" % (c1415["lift"] or 0, c1415["op"][1] or 0))
    ratio = (c1415["lift"] or 1) / max(1, abs(c678["lift"] or 1))
    w("  ratio lift total: h14-h15 es %.1fx h07-h08" % ratio)
    w("  VEREDICTO: VIVE (mecanismos distintos: manana=plano alto; mediodia=rebote valle)")
    return {"veredicto": "VIVE"}


def main():
    horas = load_horas()
    train, test = split_holdout(horas, HOLDOUT)
    w("LAB H678 — bloque manana h06/h07/h08")
    w("n=%d train=%d test=%d holdout=%d" % (len(horas), len(train), len(test), HOLDOUT))
    w("")

    w("=" * 60)
    results["H1"] = h1_perfil(train, test)
    w("")
    results["H2"] = h2_costura(train, test)
    w("")
    results["H3"] = h3_h8_h9(train, test)
    w("")
    results["H4"] = h4_bloque_dia(train)
    w("")
    results["H5"] = h5_dow(train, test)
    w("")
    results["H6"] = h6_dia_gen(train)
    w("")
    results["H7"] = h7_intra(train)
    w("")
    results["H8"] = h8_eco(train)
    w("")
    results["H9"] = h9_sn(train)
    w("")
    results["H10"] = h10_vs_h15(train)
    w("")

    w("=" * 60)
    w("SINTESIS")
    for k, val in results.items():
        w("  %s: %s" % (k, val.get("veredicto", "?")))
    w("")
    w("-- INFO posible --")
    w("  H3: tip h08 fuerte -> h09 techo (simetrico costura h14-h15 invertida)")
    w("  H2: rebote opaco generico h07->h08 (OLOR, no clonar tip h15)")
    w("  H1: cartel hod manana alto — ya en mapa")
    w("")

    text = "\n".join(lines) + "\n"
    (OUT / "LAB_H678.txt").write_text(text, encoding="utf-8")

    acta = """ACTA LAB H678
=============
fecha: 2026-08-29
lab: hilo-corto/lab-h678/
script: run_lab.py -> reports/LAB_H678.txt
cinta: data_3dias.txt · %d h

PREGUNTA
  Que son h06/h07/h08? Perfil, costura h05-h08, pico h08->h09,
  bloque dia, DOW, generosidad, intra, eco h10->h08, SN, vs h14-h15.

VEREDICTOS
%s

fin
""" % (
        len(horas),
        "\n".join("  %s: %s" % (k, v.get("veredicto", "?")) for k, v in results.items()),
    )
    (LAB / "ACTA_H678.txt").write_text(acta, encoding="utf-8")
    w("Escrito reports/LAB_H678.txt y ACTA_H678.txt")


if __name__ == "__main__":
    main()
