# -*- coding: utf-8 -*-
"""
Lab costura — barrido rebotes/techo hN->h(N+1).
  python run_lab.py
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
sys.path.insert(0, str(ROOT))

from src.lectores import cargar_ingesta  # noqa: E402

SUM_OP, SUM_FUERTE = 450, 850
HOLDOUT_H = 72
lines = []


def w(s=""):
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def load_rows():
    cinta, _, _ = cargar_ingesta("")
    rows = []
    for tag in cinta.orden:
        h = cinta.get(tag)
        gs = [t for t in (h.tiros_nucleo or []) if t.color == "G" and t.lumen]
        if not gs:
            continue
        rows.append({
            "hod": int(tag.split("-")[0][1:]),
            "day": tag.split("-")[1],
            "sum": sum(t.lumen for t in gs),
        })
    return rows


def pair_stats(by_day, a, b):
    pairs = [(v[a], v[b]) for v in by_day.values() if a in v and b in v]
    if len(pairs) < 8:
        return None
    lifts = [bv - av for av, bv in pairs]
    op = [bv - av for av, bv in pairs if av < SUM_OP]
    no = [bv - av for av, bv in pairs if SUM_OP <= av < SUM_FUERTE]
    fu = [bv - av for av, bv in pairs if av >= SUM_FUERTE]
    return {
        "a": a, "b": b, "n": len(pairs),
        "lift": median(lifts),
        "med_a": median([p[0] for p in pairs]),
        "med_b": median([p[1] for p in pairs]),
        "op_n": len(op), "op_lift": median(op) if op else None,
        "no_n": len(no), "no_lift": median(no) if no else None,
        "fu_n": len(fu), "fu_lift": median(fu) if fu else None,
    }


def split_train_test(rows):
    n = len(rows)
    cut = max(0, n - HOLDOUT_H)
    train_days = {r["day"] for r in rows[:cut]}
    test_days = {r["day"] for r in rows[cut:]}
    return train_days, test_days


def main():
    rows = load_rows()
    by_day = defaultdict(dict)
    for r in rows:
        by_day[r["day"]][r["hod"]] = r["sum"]

    all_pairs = []
    for a in range(23):
        r = pair_stats(by_day, a, a + 1)
        if r:
            all_pairs.append(r)

    train_d, test_d = split_train_test(rows)

    w("LAB COSTURA — BARRIDO REBOTES")
    w("cinta %d h · %d pares consecutivos" % (len(rows), len(all_pairs)))
    w("")

    w("=== YA CABLEADO ===")
    w("  h14->h15 rebote (VIVE lab-h15) · h08->h09 techo AVISO (lab-h678)")
    w("  Generico: opacidadInfo castigo ~1h + post-opaca")
    w("")

    w("=== TOP REBOTE opaco-> (n>=8, op>=250) ===")
    reb = [p for p in all_pairs if p["op_n"] >= 8 and p["op_lift"] and p["op_lift"] >= 250]
    reb.sort(key=lambda x: -x["op_lift"])
    for p in reb:
        w("  h%02d->h%02d  op=%+.0f(n=%d)  total=%+.0f  med_a=%.0f" % (
            p["a"], p["b"], p["op_lift"], p["op_n"], p["lift"], p["med_a"]))
    w("")

    w("=== TOP TECHO fuerte-> (n>=5, fu<=-400) ===")
    tec = [p for p in all_pairs if p["fu_n"] >= 5 and p["fu_lift"] and p["fu_lift"] <= -400]
    tec.sort(key=lambda x: x["fu_lift"])
    for p in tec:
        w("  h%02d->h%02d  fu=%+.0f(n=%d)  total=%+.0f" % (
            p["a"], p["b"], p["fu_lift"], p["fu_n"], p["lift"]))
    w("")

    w("=== VALLE->PICO (lift total >=80) ===")
    for p in sorted(all_pairs, key=lambda x: -x["lift"]):
        if p["lift"] < 80:
            break
        w("  h%02d->h%02d  lift=%+.0f  med %.0f->%.0f" % (
            p["a"], p["b"], p["lift"], p["med_a"], p["med_b"]))
    w("")

    w("=== GAP 2 (no consecutivo) op>=300 n>=8 ===")
    gap2 = []
    for a in range(22):
        b = a + 2
        pairs = [(v[a], v[b]) for v in by_day.values() if a in v and b in v]
        op = [bv - av for av, bv in pairs if av < SUM_OP]
        if len(op) >= 8:
            gap2.append((a, b, median(op), len(op), median([bv - av for av, bv in pairs])))
    for a, b, op, n, tot in sorted(gap2, key=lambda x: -x[2])[:6]:
        w("  h%02d->h%02d  op=%+.0f(n=%d)  total=%+.0f" % (a, b, op, n, tot))
    w("")

    w("=== HOLDOUT opaco (train vs test) — candidatos nuevos ===")
    nuevos = [(1, 2), (18, 19), (15, 16), (11, 12), (22, 23), (19, 20)]
    for a, b in nuevos:
        tr = pair_stats({d: {k: v[k] for k in v if d in train_d} for d, v in by_day.items()}, a, b)
        te = pair_stats({d: v for d, v in by_day.items() if d in test_d}, a, b)
        if not tr:
            continue
        te_op = te["op_lift"] if te and te["op_lift"] is not None else None
        te_fu = te["fu_lift"] if te and te["fu_lift"] is not None else None
        w("  h%02d->h%02d  train op=%+.0f(%d) fu=%+.0f(%d) | test op=%s fu=%s" % (
            a, b,
            tr["op_lift"] or 0, tr["op_n"],
            tr["fu_lift"] or 0, tr["fu_n"],
            ("%.0f" % te_op) if te_op is not None else "-",
            ("%.0f" % te_fu) if te_fu is not None else "-",
        ))
    w("")

    w("=== VEREDICTOS PROPUESTOS ===")
    verdictos = [
        ("h14->h15", "VIVE rebote", "cableado"),
        ("h08->h09", "VIVE techo", "cableado AVISO"),
        ("h15->h16", "VIVE techo", "complemento h14-h15 · prioridad cable"),
        ("h01->h02", "OLOR rebote", "op max +434 · total +38 · madrugada"),
        ("h18->h19", "OLOR rebote", "cluster tarde · op +313 · total plano"),
        ("h11->h12", "OLOR rebote", "valle h11 · lift +52"),
        ("h13->h15", "OLOR gap2", "salta h14 · investigar"),
        ("h07->h08", "OLOR rebote", "generico manana"),
        ("h22->h23", "FRIO", "op alto pero total/fu contradictorios"),
        ("generico H+1", "VIVE", "opacidadInfo ya cubre"),
    ]
    for par, v, nota in verdictos:
        w("  %s: %s — %s" % (par, v, nota))

    out = LAB / "reports" / "LAB_COSTURA_BARRIDO.txt"
    out.parent.mkdir(exist_ok=True)
    text = "\n".join(lines) + "\n"
    out.write_text(text, encoding="utf-8")

    acta = """ACTA LAB COSTURA — BARRIDO REBOTES
====================================
fecha: 2026-08-29
lab: hilo-corto/lab-costura/
script: run_lab.py -> reports/LAB_COSTURA_BARRIDO.txt

PREGUNTA
  Hay mas rebotes/techo ademas de h14-h15 y h08-h09?

HALLAZGO CLAVE
  Fisica GENERICA: casi todo par opaco-> rebote positivo (castigo ~1h).
  Eso ya vive en opacidadInfo. No duplicar 23 tips.

  Pares con VALOR DECISION extra (mas alla del generico):

VIVE / PRIORIDAD CABLE
  h15->h16 techo fu=-780 (n=11) — espejo natural post-h15
  (complemento obligatorio del tip h14->h15)

OLOR — siguiente ola INFO
  h01->h02 rebote op=+434 (madrugada)
  h18->h19 rebote op=+313 (tarde / olor h19)
  h11->h12 valle->sube lift=+52
  h13->h15 gap2 op=+383 (salta h14 — raro)

FRIO / ya cubierto
  h07->h08, h04->h05, etc: olor generico sin lift total
  h22->h23 contradictorio
  eco +1d: no sustituye costura mismo dia (H5 h15 lab FRIO)

DECISION
  No cablear los 23 pares. Mantener generico + pares VIVE.
  Siguiente tip recomendado: h15->h16 techo (cerrar ciclo mediodia).

fin
"""
    (LAB / "ACTA_COSTURA_BARRIDO.txt").write_text(acta, encoding="utf-8")
    w("Escrito reports/LAB_COSTURA_BARRIDO.txt y ACTA_COSTURA_BARRIDO.txt")


if __name__ == "__main__":
    main()
