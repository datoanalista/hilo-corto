# -*- coding: utf-8
"""
Lab costura — candidatos post-barrido H1..H6.
  python run_lab_candidatos.py
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))

from core_costura import (  # noqa: E402
    SUM_OPACO,
    costura_pairs,
    load_horas,
    split_holdout,
    strata_lifts,
    veredicto,
)

OUT = LAB / "reports"
OUT.mkdir(exist_ok=True)
lines: list[str] = []
results: dict = {}


def w(s=""):
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def test_pair(train, test, a, b):
    tr = strata_lifts(costura_pairs(train, a, b))
    te = strata_lifts(costura_pairs(test, a, b)) if test else None
    return tr, te


def print_pair(label, tr, te=None):
    w("  %s  n=%d  lift=%+.0f  med_a=%.0f  med_b=%.0f" % (
        label, tr["n"], tr["lift"], tr["med_a"], tr["med_b"]))
    w("    op=%+.0f(%d)  no=%+.0f(%d)  fu=%+.0f(%d)" % (
        tr["op"][1] or 0, tr["op"][0],
        tr["no"][1] or 0, tr["no"][0],
        tr["fu"][1] or 0, tr["fu"][0],
    ))
    if te and te["n"]:
        w("    test lift=%+.0f  op=%+.0f(%d)  fu=%+.0f(%d)" % (
            te["lift"] or 0,
            te["op"][1] or 0, te["op"][0],
            te["fu"][1] or 0, te["fu"][0],
        ))


def h1_15_16(train, test):
    w("-- H1 TECHO h15->h16 (post-pico h15) --")
    tr, te = test_pair(train, test, 15, 16)
    print_pair("h15->h16", tr, te)
    ref, _ = test_pair(train, test, 14, 15)
    w("  ref h14->h15 lift=%+.0f  op=%+.0f  fu=%+.0f" % (
        ref["lift"], ref["op"][1] or 0, ref["fu"][1] or 0))
    fu_tr = tr["fu"][1] is not None and tr["fu"][1] <= -400 and tr["fu"][0] >= 5
    fu_te = te and te["fu"][1] is not None and te["fu"][1] <= -300 and te["fu"][0] >= 2
    v = veredicto(fu_tr, fu_te, tr["fu"][0], te["fu"][0] if te else 0)
    w("  VEREDICTO: %s" % v)
    return {"veredicto": v}


def h2_18_19(train, test):
    w("-- H2 REBOTE h18->h19 (tarde) --")
    tr, te = test_pair(train, test, 18, 19)
    print_pair("h18->h19", tr, te)
    prev, _ = test_pair(train, test, 17, 18)
    w("  ref h17->h18 fu=%+.0f" % (prev["fu"][1] or 0))
    op_tr = tr["op"][1] is not None and tr["op"][1] >= 250 and tr["op"][0] >= 8
    op_te = te and te["op"][1] is not None and te["op"][1] >= 150 and te["op"][0] >= 2
    v = veredicto(op_tr, op_te, tr["op"][0], te["op"][0] if te else 0)
    w("  VEREDICTO: %s (op fuerte; total plano)" % v)
    return {"veredicto": v}


def h3_13_15(train, test):
    w("-- H3 GAP2 h13->h15 (salta h14) --")
    tr, te = test_pair(train, test, 13, 15)
    print_pair("h13->h15", tr, te)
    c14, _ = test_pair(train, test, 14, 15)
    w("  ref h14->h15 lift=%+.0f  op=%+.0f" % (c14["lift"], c14["op"][1] or 0))
    by_day = defaultdict(dict)
    for h in train:
        by_day[h.day][h.hod] = h
    both = [(d[13], d[14], d[15]) for d in by_day.values() if 13 in d and 14 in d and 15 in d]
    if both:
        w("  dias 13+14+15 n=%d  lift13->15=%+.0f  lift14->15=%+.0f" % (
            len(both),
            median([c.sum_g - a.sum_g for a, b, c in both]),
            median([c.sum_g - b.sum_g for a, b, c in both]),
        ))
        when_14_op = [(a, c) for a, b, c in both if b.sum_g < SUM_OPACO]
        if when_14_op:
            w("    si h14 opaca: lift13->15=%+.0f (n=%d)" % (
                median([c.sum_g - a.sum_g for a, c in when_14_op]), len(when_14_op)))
    op_tr = tr["op"][1] is not None and tr["op"][1] >= 300 and tr["op"][0] >= 8
    v = veredicto(op_tr, False, tr["op"][0], 0)
    w("  VEREDICTO: %s" % v)
    return {"veredicto": v}


def h4_01_02(train, test):
    w("-- H4 REBOTE h01->h02 (madrugada) --")
    tr, te = test_pair(train, test, 1, 2)
    print_pair("h01->h02", tr, te)
    op_tr = tr["op"][1] is not None and tr["op"][1] >= 350 and tr["op"][0] >= 8
    v = veredicto(op_tr, te and te["op"][1] and te["op"][1] >= 200, tr["op"][0], te["op"][0] if te else 0)
    w("  VEREDICTO: %s" % v)
    return {"veredicto": v}


def h5_20_21(train, test):
    w("-- H5 VALLE-PICO h20->h21 --")
    tr, te = test_pair(train, test, 20, 21)
    print_pair("h20->h21", tr, te)
    lift_tr = tr["lift"] is not None and tr["lift"] >= 80
    lift_te = te and te["lift"] is not None and te["lift"] >= 50
    v = veredicto(lift_tr, lift_te, tr["n"], te["n"] if te else 0)
    w("  VEREDICTO: %s" % v)
    return {"veredicto": v}


def h6_baseline(train):
    w("-- H6 BASELINE generico opaco->H+1 --")
    all_op = []
    for a in range(23):
        for ha, hb in costura_pairs(train, a, a + 1):
            if ha.sum_g < SUM_OPACO:
                all_op.append(hb.sum_g - ha.sum_g)
    w("  med lift opaco-> =%+.0f  n=%d" % (median(all_op), len(all_op)))
    w("  VEREDICTO: VIVE (opacidadInfo; no 23 tips)")
    return {"veredicto": "VIVE"}


def main():
    horas = load_horas()
    train, test = split_holdout(horas)
    w("LAB COSTURA — CANDIDATOS H1-H6")
    w("n=%d train=%d test=%d" % (len(horas), len(train), len(test)))
    w("")

    results["H1"] = h1_15_16(train, test)
    w("")
    results["H2"] = h2_18_19(train, test)
    w("")
    results["H3"] = h3_13_15(train, test)
    w("")
    results["H4"] = h4_01_02(train, test)
    w("")
    results["H5"] = h5_20_21(train, test)
    w("")
    results["H6"] = h6_baseline(train)
    w("")

    w("=" * 60)
    w("SINTESIS")
    for k, v in results.items():
        w("  %s: %s" % (k, v.get("veredicto", "?")))

    text = "\n".join(lines) + "\n"
    (OUT / "LAB_COSTURA.txt").write_text(text, encoding="utf-8")

    acta_body = "\n".join("  %s: %s" % (k, v.get("veredicto", "?")) for k, v in results.items())
    cable = [k for k, v in results.items() if v.get("veredicto") == "VIVE"]

    acta = f"""ACTA LAB COSTURA — CANDIDATOS
==============================
fecha: 2026-08-29
lab: hilo-corto/lab-costura/
script: run_lab_candidatos.py -> reports/LAB_COSTURA.txt
previo: ACTA_COSTURA_BARRIDO.txt · ya cableado h14-h15 · h08-h09

PREGUNTA
  Validar H1-H6 antes de nuevos tips.

VEREDICTOS
{acta_body}

H1 h15->h16
  Espejo post-pico. Fuerte->fuerte caida fuerte.
H2 h18->h19
  Rebote opaco tarde; total lift no confirma.
H3 h13->h15 gap2
  Opaco fuerte; h14 explica parte del camino.
H4 h01->h02
  Max op rebote; lift total modesto.
H5 h20->h21
  Valle-pico noche.
H6
  Generico ya en opacidadInfo.

CABLEAR (solo VIVE): {", ".join(cable) or "ninguno nuevo sin OK"}

DECISION
  Ver report numerico. OLOR no cablear salvo OK humano.

fin
"""
    (LAB / "ACTA_COSTURA.txt").write_text(acta, encoding="utf-8")
    w("Escrito reports/LAB_COSTURA.txt y ACTA_COSTURA.txt")


if __name__ == "__main__":
    main()
