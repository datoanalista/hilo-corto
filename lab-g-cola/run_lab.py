# -*- coding: utf-8 -*-
"""
Lab G-cola — ¿se detecta G>400/500 en bloque 20-40 antes o en curso?
  python run_lab.py
"""
from __future__ import annotations

import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
EXTRA = ROOT / "dashboard" / "extraccion" / "extraccion-en-vivo.txt"
sys.path.insert(0, str(LAB))

from core_gc import (  # noqa: E402
    BLOQUES,
    UMBRAL_ALTO,
    UMBRAL_COLA,
    HoraGC,
    estado_a_min,
    load_horas,
    metrics_binary,
    split_holdout,
)

OUT = LAB / "reports"
OUT.mkdir(exist_ok=True)
HOLDOUT = 72
BLOQUE_MED = (20, 39)
lines: list[str] = []


def w(s=""):
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def bloque_nombre(b):
    return f"{b[0]}-{b[1]}"


# ── H0 base ───────────────────────────────────────────────────
def h0_base(horas):
    w("== H0 BASE — frecuencia G alta ==")
    w(f"  horas con G+lumen: {len(horas)}")
    for um, name in [(UMBRAL_ALTO, ">400"), (UMBRAL_COLA, ">500")]:
        con = [h for h in horas if h.tiene_gt(um)]
        w(f"  horas con al menos 1 G{name}: {len(con)} ({100*len(con)/len(horas):.1f}%)")
        for b in BLOQUES:
            hb = [h for h in horas if h.tiene_gt(um, b)]
            w(f"    bloque {bloque_nombre(b)}: {len(hb)} ({100*len(hb)/len(horas):.1f}%)")
        # 1er G>um minuto
        mins = []
        for h in con:
            for g in sorted(h.gs, key=lambda x: x.m0):
                if g.lumen > um:
                    mins.append(g.m0)
                    break
        if mins:
            w(f"  1er G{name}: med min={median(mins):.0f} p75={sorted(mins)[int(0.75*len(mins))-1]:.0f}")
    w("")


# ── H1 pre-hora (antes de comenzar) ───────────────────────────
def h1_prehora(train, test):
    w("== H1 PRE-HORA — señales antes del min 0 ==")
    bloque = BLOQUE_MED
    targets = {
        "gt400_20-39": lambda h: h.tiene_gt(UMBRAL_ALTO, bloque),
        "gt500_20-39": lambda h: h.tiene_gt(UMBRAL_COLA, bloque),
        "gt400_any": lambda h: h.tiene_gt(UMBRAL_ALTO),
        "gt500_any": lambda h: h.tiene_gt(UMBRAL_COLA),
    }

    def eval_reglas(split, label):
        w(f"  -- {label} n={len(split)} --")
        idx = {h.tag: i for i, h in enumerate(split)}
        for tname, tgt_fn in targets.items():
            y = [tgt_fn(h) for h in split]
            base = sum(y) / len(y) if y else 0
            w(f"  target {tname}: base={100*base:.1f}%")

            reglas = []

            # R1: hod tiene alta P en train
            by_hod = defaultdict(list)
            for h in train:
                by_hod[h.hod].append(tgt_fn(h))
            hod_p = {hod: statistics.mean(v) for hod, v in by_hod.items() if len(v) >= 5}
            top_hods = sorted(hod_p, key=hod_p.get, reverse=True)[:4]
            if top_hods:
                thr = statistics.mean(hod_p.values()) + 0.5 * statistics.pstdev(hod_p.values() or [0])
                reglas.append(
                    (
                        f"hod en top caliente ({','.join(f'h{h:02d}' for h in top_hods[:3])})",
                        lambda h, th=thr: hod_p.get(h.hod, 0) >= th,
                    )
                )

            # R2: hora previa max_g alto
            for thr_prev in (85, 110, 150):
                reglas.append(
                    (
                        f"H-1 maxG>={thr_prev}",
                        lambda h, t=thr_prev, s=split, ix=idx: (
                            ix.get(h.tag, 0) > 0
                            and s[ix[h.tag] - 1].max_g >= t
                        ),
                    )
                )

            # R3: H-1 tuvo G>500
            reglas.append(
                (
                    "H-1 tuvo G>500",
                    lambda h, s=split, ix=idx: (
                        ix.get(h.tag, 0) > 0 and s[ix[h.tag] - 1].tiene_gt(UMBRAL_COLA)
                    ),
                )
            )

            # R4: H-1 sum_g generosa
            for thr_sum in (600, 800, 1000):
                reglas.append(
                    (
                        f"H-1 sumG>={thr_sum}",
                        lambda h, t=thr_sum, s=split, ix=idx: (
                            ix.get(h.tag, 0) > 0 and s[ix[h.tag] - 1].sum_g >= t
                        ),
                    )
                )

            # R5: hod perfil — horas con mean_g hist alto en ese hod
            hod_mean = defaultdict(list)
            for h in train:
                hod_mean[h.hod].append(h.mean_g)
            hod_med = {hod: median(v) for hod, v in hod_mean.items() if len(v) >= 8}
            if hod_med:
                reglas.append(
                    (
                        "hod meanG hist >= p75 global",
                        lambda h, hm=hod_med: h.hod in hm
                        and hm[h.hod] >= sorted(hm.values())[int(0.75 * len(hm)) - 1],
                    )
                )

            best = None
            for rname, fn in reglas:
                pred = [fn(h) for h in split]
                m = metrics_binary(y, pred)
                if m["tp"] + m["fp"] == 0:
                    continue
                w(
                    f"    {rname}: prec={100*m['prec']:.0f}% rec={100*m['rec']:.0f}% "
                    f"lift={m['lift']:.1f} (fp={m['fp']} tp={m['tp']})"
                )
                if best is None or m["lift"] > best[1]["lift"]:
                    best = (rname, m)
            if best:
                w(f"  >> mejor pre-hora {tname}: {best[0]} lift={best[1]['lift']:.1f}")
        w("")

    eval_reglas(train, "train")
    if test:
        eval_reglas(test, "holdout")


# ── H2 en curso — antes del bloque 20-40 ─────────────────────
def h2_antes_bloque(train, test):
    w("== H2 EN CURSO — aviso ANTES del bloque 20-40 ==")
    bloque = BLOQUE_MED
    for T in (0, 10, 19):
        w(f"  -- corte @min {T} (antes de 20-39) --")
        for um, name in [(UMBRAL_ALTO, ">400"), (UMBRAL_COLA, ">500")]:
            y_train = [h.tiene_gt(um, bloque) for h in train]
            base = sum(y_train) / len(y_train)

            reglas = [
                (
                    f"maxG@{T}>=110",
                    lambda h, t=T: estado_a_min(h, t)["maxG"] >= 110,
                ),
                (
                    f"maxG@{T}>=85",
                    lambda h, t=T: estado_a_min(h, t)["maxG"] >= 85,
                ),
                (
                    f"meanG@{T}>=70",
                    lambda h, t=T: estado_a_min(h, t)["meanG"] >= 70,
                ),
                (
                    f"acum@{T}>=150",
                    lambda h, t=T: estado_a_min(h, t)["acum"] >= 150,
                ),
                (
                    f"nG@{T}>=3 y meanG>=60",
                    lambda h, t=T: (
                        estado_a_min(h, t)["nG"] >= 3 and estado_a_min(h, t)["meanG"] >= 60
                    ),
                ),
                (
                    f"ya hay G>{name} antes de {T}",
                    lambda h, t=T, u=um: any(g.lumen > u for g in estado_a_min(h, t)["gs"]),
                ),
            ]

            w(f"  target G{name} en 20-39 · base train={100*base:.1f}%")
            for rname, fn in reglas:
                pred = [fn(h) for h in train]
                m = metrics_binary(y_train, pred)
                if m["tp"] + m["fp"] == 0:
                    continue
                w(
                    f"    {rname}: prec={100*m['prec']:.0f}% rec={100*m['rec']:.0f}% "
                    f"lift={m['lift']:.1f}"
                )
            if test:
                y_test = [h.tiene_gt(um, bloque) for h in test]
                fn_best = lambda h, t=T: estado_a_min(h, t)["maxG"] >= 85
                pred_t = [fn_best(h) for h in test]
                m = metrics_binary(y_test, pred_t)
                w(
                    f"  holdout maxG@{T}>=85: prec={100*m['prec']:.0f}% rec={100*m['rec']:.0f}%"
                )
        w("")


# ── H3 en bloque 20-40 — olor temprano ──────────────────────
def h3_dentro_bloque(horas):
    w("== H3 DENTRO 20-39 — cuándo cae la cola ==")
    for um, name in [(UMBRAL_ALTO, ">400"), (UMBRAL_COLA, ">500")]:
        mins = []
        tipos = Counter()
        for h in horas:
            for g in h.gs_gt_en_bloque(um, BLOQUE_MED):
                mins.append(g.m0)
                if g.tipo:
                    tipos[g.tipo] += 1
        if not mins:
            w(f"  G{name} en 20-39: sin casos")
            continue
        w(
            f"  G{name} en 20-39: n={len(mins)} horas-evento "
            f"med min={median(mins):.0f} tipos={dict(tipos)}"
        )
    w("")

    w("  -- regla compuesta INFO (train) --")
    train, test = split_holdout(horas, HOLDOUT)
    bloque = BLOQUE_MED

    def alerta_pre20(h):
        st19 = estado_a_min(h, 19)
        # olor: apertura fuerte pero sin cola aún
        if st19["maxG"] >= 85 and st19["n500"] == 0:
            return True
        if st19["meanG"] >= 65 and st19["nG"] >= 2:
            return True
        return False

    for um, name in [(UMBRAL_ALTO, ">400"), (UMBRAL_COLA, ">500")]:
        y = [h.tiene_gt(um, bloque) for h in train]
        pred = [alerta_pre20(h) for h in train]
        m = metrics_binary(y, pred)
        w(
            f"  @min19 olor cola {name} en 20-39: prec={100*m['prec']:.0f}% "
            f"rec={100*m['rec']:.0f}% lift={m['lift']:.1f} base={100*m['base']:.1f}%"
        )
        if test:
            y2 = [h.tiene_gt(um, bloque) for h in test]
            p2 = [alerta_pre20(h) for h in test]
            m2 = metrics_binary(y2, p2)
            w(
                f"  holdout: prec={100*m2['prec']:.0f}% rec={100*m2['rec']:.0f}% "
                f"lift={m2['lift']:.1f}"
            )
    w("")


# ── H4 hod mapa cola ──────────────────────────────────────────
def h4_hod_mapa(horas):
    w("== H4 MAPA HOD — P(G>500 en 20-39) ==")
    by_h = defaultdict(list)
    for h in horas:
        by_h[h.hod].append(h.tiene_gt(UMBRAL_COLA, BLOQUE_MED))
    rows = []
    for hod in range(24):
        xs = by_h.get(hod, [])
        if len(xs) < 5:
            continue
        p = 100 * sum(xs) / len(xs)
        rows.append((p, hod, len(xs)))
    rows.sort(reverse=True)
    for p, hod, n in rows[:8]:
        w(f"  h{hod:02d}: {p:.0f}% (n={n})")
    w(f"  global: {100*sum(h.tiene_gt(UMBRAL_COLA,BLOQUE_MED) for h in horas)/len(horas):.1f}%")
    w("")


# ── H5 copy propuesto ─────────────────────────────────────────
def h5_sintesis(horas, train, test):
    w("== H5 SINTESIS — aviso cableable ==")
    bloque = BLOQUE_MED
    base400 = sum(h.tiene_gt(UMBRAL_ALTO, bloque) for h in horas) / len(horas)
    base500 = sum(h.tiene_gt(UMBRAL_COLA, bloque) for h in horas) / len(horas)
    w(f"  base G>400 en 20-39: {100*base400:.1f}%")
    w(f"  base G>500 en 20-39: {100*base500:.1f}%")

    # mejor combo pre-hora + @19
    def aviso(h):
        parts = []
        st19 = estado_a_min(h, 19)
        if st19["maxG"] >= 85 and st19["n500"] == 0:
            parts.append("apertura fuerte sin cola aún")
        if st19["meanG"] >= 65 and st19["nG"] >= 2:
            parts.append("meanG alto en 0-19")
        ix = {x.tag: i for i, x in enumerate(horas)}
        i = ix.get(h.tag, -1)
        if i > 0 and horas[i - 1].max_g >= 110:
            parts.append("H-1 trajo G muy fuerte")
        if parts:
            return True, parts
        return False, []

    hits = []
    for h in horas:
        ok, parts = aviso(h)
        if ok and h.tiene_gt(UMBRAL_ALTO, bloque):
            hits.append((h.tag, parts, h.gs_gt_en_bloque(UMBRAL_ALTO, bloque)))
    w(f"  aviso compuesto @19 + H-1: {len(hits)} hits en horas con G>400 en 20-39")
    for tag, parts, gs in hits[:5]:
        w(f"    {tag}: {' · '.join(parts)} -> {[g.lumen for g in gs]}")

    w("")
    w("VEREDICTO PRELIMINAR:")
    w("  PRE-HORA solo: OLOR (lift bajo, muchas FP) salvo hod extremo")
    w("  @min19 antes de 20-39: OLOR-VIVE si maxG>=85 sin G>500 aún")
    w("  G>500 en 20-39: raro (~base baja); 1er >500 suele min~35 (lab-SN)")
    w("  COPY INFO sugerido:")
    w('    "Olor de cola: apertura fuerte — posible G>400-500 en bloque 20-40"')
    w('    Solo @min>=15-19 o tras 1er G>=85 sin cola; no boleto.')
    w("")


def main():
    w("LAB G-COLA — G>400/500 · bloque 20-40")
    w(f"lab: {LAB}")
    horas = load_horas(EXTRA)
    w(f"cinta: data_3dias + extraccion-en-vivo · {len(horas)} h")
    w("")

    train, test = split_holdout(horas, HOLDOUT)
    w(f"train={len(train)} holdout={len(test)}")
    w("")

    h0_base(horas)
    h1_prehora(train, test)
    h2_antes_bloque(train, test)
    h3_dentro_bloque(horas)
    h4_hod_mapa(horas)
    h5_sintesis(horas, train, test)

    out = OUT / "LAB_G_COLA.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"-> {out}")


if __name__ == "__main__":
    main()
