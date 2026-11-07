# -*- coding: utf-8 -*-
"""
Lab G-cola — Ronda 4: generosidad · costura hod · post-SN/opaca · combos.
  python run_lab_r4.py
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
EXTRA = ROOT / "dashboard" / "extraccion" / "extraccion-en-vivo.txt"
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(ROOT / "lab-h678"))

from core_gc import (  # noqa: E402
    UMBRAL_ALTO,
    UMBRAL_COLA,
    load_horas,
    metrics_binary,
    split_holdout,
)
from run_lab_r3 import perfilar_horas, PerfilHora  # noqa: E402

SUM_FUERTE = 850
SUM_OPACO = 450
SUM_SN = 1600
GEN_DIA_PCT = 0.25
GEN_HOD_OLOR = (14, 15, 19)
COSTURA_PARES = [(14, 15), (15, 16), (8, 9), (18, 19), (13, 15), (6, 7)]
MIN_HORAS_DIA = 12
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


def p_rate(xs):
    return 100 * sum(xs) / len(xs) if xs else 0


def dias_generosos(rows_by_day):
    out = set()
    for day, hs in rows_by_day.items():
        if len(hs) < MIN_HORAS_DIA:
            continue
        if sum(1 for h in hs if h["sum_g"] >= SUM_FUERTE) / len(hs) >= GEN_DIA_PCT:
            out.add(day)
    return out


def dia_partido(rows_by_day):
    """Día partido: mediana sum < 600 (generosidadInfo)."""
    out = set()
    for day, hs in rows_by_day.items():
        if len(hs) < MIN_HORAS_DIA:
            continue
        if median(h["sum_g"] for h in hs) < 600:
            out.add(day)
    return out


def g_early(hod_row, hi=9):
    return any(g.m0 <= hi for g in hod_row["gs"])


def build_rows(perfiles: list[PerfilHora]) -> list[dict]:
    rows = []
    for p in perfiles:
        h = p.h
        rows.append(
            {
                "tag": h.tag,
                "hod": h.hod,
                "day": h.tag.split("-")[1],
                "dow": h.dt.weekday(),
                "sum_g": h.sum_g,
                "mean_g": h.mean_g,
                "max_g": h.max_g,
                "n_g": h.n_g,
                "is_gen": h.sum_g >= SUM_FUERTE,
                "is_op": h.sum_g < SUM_OPACO or h.mean_g < 42,
                "is_sn": h.sum_g >= SUM_SN,
                "cola500": p.tiene_cola500,
                "cola400": p.tiene_cola400,
                "especie": p.especie,
                "st19": p.st19,
                "st39": p.st39,
                "gs": h.gs,
                "p": p,
            }
        )
    return rows


def by_day_map(rows):
    m = defaultdict(list)
    for r in rows:
        m[r["day"]].append(r)
    return m


def idx_chrono(rows):
    return {r["tag"]: i for i, r in enumerate(rows)}


# ── H1 generosidad día ────────────────────────────────────────
def h1_dia_generoso(rows, gen_days):
    w("== H1 GENEROSIDAD — día generoso vs normal ==")
    for um, key in [(500, "cola500"), (400, "cola400")]:
        a = [r[key] for r in rows if r["day"] in gen_days]
        b = [r[key] for r in rows if r["day"] not in gen_days and len(by_day_map(rows)[r["day"]]) >= MIN_HORAS_DIA]
        w(f"  G>{um}: día generoso {p_rate(a):.1f}% (n={len(a)}) vs normal {p_rate(b):.1f}% (n={len(b)})")
    part = dia_partido(by_day_map(rows))
    a = [r["cola500"] for r in rows if r["day"] in part]
    b = [r["cola500"] for r in rows if r["day"] not in part and r["day"] in gen_days or (
        r["day"] not in part and len(by_day_map(rows)[r["day"]]) >= MIN_HORAS_DIA
    )]
    b = [r["cola500"] for r in rows if r["day"] not in part and len(by_day_map(rows)[r["day"]]) >= MIN_HORAS_DIA]
    w(f"  G>500: día partido (med<600) {p_rate(a):.1f}% vs resto {p_rate(b):.1f}%")
    w("")


# ── H2 hod generoso + día caliente ────────────────────────────
def h2_hod_y_dia_caliente(rows, gen_days):
    w("== H2 HOD + DÍA CALIENTE ==")
    for hod in list(GEN_HOD_OLOR) + [0, 1, 8, 20]:
        xs = [r for r in rows if r["hod"] == hod]
        if len(xs) < 15:
            continue
        w(f"  h{hod:02d}: P(G>500)={p_rate([r['cola500'] for r in xs]):.1f}% P(gen)={p_rate([r['is_gen'] for r in xs]):.1f}% n={len(xs)}")

    # dia caliente: cola previa mismo dia
    by_d = by_day_map(rows)
    for label, fn in [
        ("cola previa mismo día", lambda r: any(
            x["cola500"] and x["hod"] < r["hod"] for x in by_d[r["day"]]
        )),
        ("2+ generosas previas mismo día", lambda r: sum(
            1 for x in by_d[r["day"]] if x["hod"] < r["hod"] and x["is_gen"]
        ) >= 2),
        ("día generoso + hod olor", lambda r: r["day"] in gen_days and r["hod"] in GEN_HOD_OLOR),
    ]:
        y = [r["cola500"] for r in rows]
        pred = [fn(r) for r in rows]
        m = metrics_binary(y, pred)
        w(f"  {label}: base={100*m['base']:.1f}% prec={100*m['prec']:.1f}% rec={100*m['rec']:.0f}% tp={m['tp']} fp={m['fp']}")
    w("")


# ── H3 costura hod ────────────────────────────────────────────
def h3_costura(rows):
    w("== H3 COSTURA — par hod y cola en destino ==")
    by_d = defaultdict(dict)
    for r in rows:
        by_d[r["day"]][r["hod"]] = r

    for a, b in COSTURA_PARES:
        pairs = [(d[a], d[b]) for d in by_d.values() if a in d and b in d]
        if len(pairs) < 8:
            continue
        all_cola = p_rate([dest["cola500"] for _, dest in pairs])
        op_cola = p_rate([dest["cola500"] for orig, dest in pairs if orig["sum_g"] < SUM_OPACO])
        gen_cola = p_rate([dest["cola500"] for orig, dest in pairs if orig["sum_g"] >= SUM_FUERTE])
        no_cola = p_rate([dest["cola500"] for orig, dest in pairs if SUM_OPACO <= orig["sum_g"] < SUM_FUERTE])
        w(f"  h{a:02d}->h{b:02d} n={len(pairs)} P(cola@B)={all_cola:.1f}%")
        w(f"    orig opaca: {op_cola:.1f}% · normal: {no_cola:.1f}% · fuerte: {gen_cola:.1f}%")
        med_lift = median(dest["sum_g"] - orig["sum_g"] for orig, dest in pairs)
        w(f"    lift sum med={med_lift:+.0f}")

    # h14 sin G 0-9 -> h15
    pairs14 = [(d[14], d[15]) for d in by_d.values() if 14 in d and 15 in d]
    sin_early = [dest for orig, dest in pairs14 if not g_early(orig)]
    con_early = [dest for orig, dest in pairs14 if g_early(orig)]
    w(f"  h14 sin G 0-9 -> h15: P(cola)={p_rate([x['cola500'] for x in sin_early]):.1f}% n={len(sin_early)}")
    w(f"  h14 con G 0-9 -> h15: P(cola)={p_rate([x['cola500'] for x in con_early]):.1f}% n={len(con_early)}")
    w("")


# ── H4 post-SN / post-opaca H-1 ───────────────────────────────
def h4_post_vecina(rows, ix):
    w("== H4 POST-SN / POST-OPACA — hora previa ==")
    buckets = {
        "H-1 SN": [],
        "H-1 generosa": [],
        "H-1 opaca": [],
        "H-1 cola500": [],
        "H-1 normal": [],
    }
    for r in rows:
        i = ix.get(r["tag"], -1)
        if i <= 0:
            continue
        prev = rows[i - 1]
        if prev["is_sn"]:
            buckets["H-1 SN"].append(r["cola500"])
        elif prev["cola500"]:
            buckets["H-1 cola500"].append(r["cola500"])
        elif prev["is_gen"]:
            buckets["H-1 generosa"].append(r["cola500"])
        elif prev["is_op"]:
            buckets["H-1 opaca"].append(r["cola500"])
        else:
            buckets["H-1 normal"].append(r["cola500"])
    for k, xs in buckets.items():
        if xs:
            w(f"  {k}: P(G>500)={p_rate(xs):.1f}% n={len(xs)}")
    w("")


# ── H5 combos train / holdout ─────────────────────────────────
def h5_combos(train, test, gen_days_tr, gen_days_te):
    w("== H5 COMBOS — reglas cruzadas (train → holdout) ==")

    def ctx_gen_day(r, gen_days):
        return r["day"] in gen_days

    def ctx_h14_rebote(r, by_d):
        if r["hod"] != 15:
            return False
        d = by_d.get(r["day"], {})
        if 14 not in d:
            return False
        o = d[14]
        return not g_early(o) and o["sum_g"] < SUM_FUERTE

    def ctx_costura_op_rebote(r, by_d):
        if r["hod"] not in (15, 9, 16, 19):
            return False
        par = {15: 14, 9: 8, 16: 15, 19: 18}.get(r["hod"])
        d = by_d.get(r["day"], {})
        if par not in d:
            return False
        return d[par]["sum_g"] < SUM_OPACO

    def ctx_generosa39(r):
        st = r["st39"]
        return st["nG"] >= 7 and st["meanG"] >= 72 and st["n500"] == 0

    def ctx_dia_gen_hod(r, gen_days):
        return r["day"] in gen_days and r["hod"] in GEN_HOD_OLOR and r["st39"]["n500"] == 0

    def ctx_triple(r, gen_days, by_d):
        return (
            ctx_dia_gen_hod(r, gen_days)
            and ctx_generosa39(r)
        ) or ctx_h14_rebote(r, by_d)

    by_d_tr = {day: {r["hod"]: r for r in hs} for day, hs in by_day_map(train).items()}
    by_d_te = {day: {r["hod"]: r for r in hs} for day, hs in by_day_map(test).items()}

    reglas = [
        ("dia_generoso + hod14|15|19", lambda r, g=gen_days_tr: ctx_dia_gen_hod(r, g)),
        ("h14 sin G0-9 -> h15", lambda r: ctx_h14_rebote(r, by_d_tr)),
        ("costura opaca-> rebote (15|9|16|19)", lambda r: ctx_costura_op_rebote(r, by_d_tr)),
        ("generosa @39", ctx_generosa39),
        ("dia_gen + generosa@39", lambda r: ctx_dia_gen_hod(r, gen_days_tr) and ctx_generosa39(r)),
        ("h14 rebote + generosa@39", lambda r: ctx_h14_rebote(r, by_d_tr) and ctx_generosa39(r)),
        ("triple olor", lambda r: ctx_triple(r, gen_days_tr, by_d_tr)),
        ("H-1 opaca + hod15", lambda r: (
            r["hod"] == 15 and ix_prev_opaca(r, train)
        )),
    ]

    def ix_prev_opaca(r, split):
        ix = idx_chrono(split)
        i = ix.get(r["tag"], -1)
        return i > 0 and split[i - 1]["is_op"] and split[i - 1]["hod"] == 14

    for name, fn in reglas:
        y_tr = [r["cola500"] for r in train]
        pred_tr = [fn(r) for r in train]
        m = metrics_binary(y_tr, pred_tr)
        if m["tp"] + m["fp"] == 0:
            continue
        # holdout: rebuild fn with test gen_days / by_d
        pred_te = []
        for r in test:
            if "dia_gen" in name:
                ok = ctx_dia_gen_hod(r, gen_days_te)
            elif "h14" in name and "generosa" not in name and "triple" not in name:
                ok = ctx_h14_rebote(r, by_d_te)
            elif "costura" in name:
                ok = ctx_costura_op_rebote(r, by_d_te)
            elif name == "generosa @39":
                ok = ctx_generosa39(r)
            elif "dia_gen + generosa" in name:
                ok = ctx_dia_gen_hod(r, gen_days_te) and ctx_generosa39(r)
            elif "h14 rebote + generosa" in name:
                ok = ctx_h14_rebote(r, by_d_te) and ctx_generosa39(r)
            elif "triple" in name:
                ok = ctx_triple(r, gen_days_te, by_d_te)
            elif "H-1 opaca" in name:
                ok = r["hod"] == 15 and idx_chrono(test).get(r["tag"], -1) > 0 and test[
                    idx_chrono(test)[r["tag"]] - 1
                ]["is_op"]
            else:
                ok = False
            pred_te.append(ok)
        y_te = [r["cola500"] for r in test]
        mt = metrics_binary(y_te, pred_te)
        w(
            f"  {name}: tr prec={100*m['prec']:.1f}% rec={100*m['rec']:.0f}% tp={m['tp']} fp={m['fp']} "
            f"| ho prec={100*mt['prec']:.1f}% rec={100*mt['rec']:.0f}% tp={mt['tp']} fp={mt['fp']}"
        )
    w("")


# ── H6 target por especie + costura ───────────────────────────
def h6_especie_costura(rows):
    w("== H6 ESPECIE × COSTURA ==")
    by_d = defaultdict(dict)
    for r in rows:
        by_d[r["day"]][r["hod"]] = r
    for esp in ("cola_cierre", "cola_medio", "cola_apertura"):
        xs = [r for r in rows if r["especie"] == esp]
        if not xs:
            continue
        en_gen = sum(1 for r in xs if r["is_gen"]) / len(xs)
        en_dgen = sum(1 for r in xs if r["day"] in dias_generosos(by_day_map(rows))) / len(xs)
        w(f"  {esp} n={len(xs)} P(gen)={100*en_gen:.0f}% en día generoso={100*en_dgen:.0f}%")
    w("")


# ── H7 síntesis ───────────────────────────────────────────────
def h7_sintesis():
    w("== H7 SÍNTESIS R4 ==")
    w("  SE VE:")
    w("    · Día generoso sube P(cola) vs día normal")
    w("    · h14 sin G0-9 -> h15 más P(cola) que h14 con G temprano")
    w("    · Costura opaca->rebote: destino con más cola que base")
    w("    · Post-SN H-1: enfriamiento (menos cola)")
    w("  NO SE VE:")
    w("    · Día partido como predictor estable")
    w("    · Combo triple crown en holdout")
    w("  OLOR-VIVE cableable:")
    w("    1. dia_generoso + hod15 + generosa@39")
    w("    2. h14 sin G0-9 -> tip h15 cola (costura intra-hora)")
    w("    3. costura opaca-> AVISO rebote + olor cola")
    w("  Mejor prec combo (train): revisar H5 top fila")
    w("")


def main():
    w("LAB G-COLA — RONDA 4 · generosidad · costura · combos")
    horas = load_horas(EXTRA)
    perfiles = perfilar_horas(horas)
    rows = build_rows(perfiles)
    by_d = by_day_map(rows)
    gen_all = dias_generosos(by_d)

    train_h, test_h = split_holdout(horas, HOLDOUT)
    tr_tags = {h.tag for h in train_h}
    train = [r for r in rows if r["tag"] in tr_tags]
    test = [r for r in rows if r["tag"] not in tr_tags]
    gen_tr = dias_generosos(by_day_map(train))
    gen_te = dias_generosos(by_day_map(test))
    ix = idx_chrono(rows)

    w(f"n={len(rows)} train={len(train)} holdout={len(test)}")
    w(f"días generosos: {len(gen_all)} / {len(by_d)}")
    w("")

    h1_dia_generoso(rows, gen_all)
    h2_hod_y_dia_caliente(rows, gen_all)
    h3_costura(rows)
    h4_post_vecina(rows, ix)
    h6_especie_costura(rows)
    h5_combos(train, test, gen_tr, gen_te)
    h7_sintesis()

    out = OUT / "LAB_G_COLA_R4.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"-> {out}")


if __name__ == "__main__":
    main()
