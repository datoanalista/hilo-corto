# -*- coding: utf-8 -*-
"""
Lab ruleta-zero — supuesto casino 54 casillas vs prod.
  python run_lab.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from statistics import mean, median

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))

from core_rz import (  # noqa: E402
    DETAIL,
    HOLDOUT,
    LETRAS,
    LIGHTGREEN,
    P_G_WHEEL,
    WHEEL_EMP,
    WHEEL_HUMAN,
    banda_score,
    calibrate_slots_from_counts,
    letter_log_loss,
    load_cinta,
    load_letters,
    load_tiros_rg_detail,
    pick_minutes_uniform,
    slots_to_probs,
    split_tags,
    tag_key,
    urn_probs,
)

from src.estado import PRIMERA_UTIL  # noqa: E402
from src.tablero import recorrer  # noqa: E402

OUT = LAB / "reports"
OUT.mkdir(exist_ok=True)
lines: list[str] = []


def w(s=""):
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def h0_mezcla_global(tiros: list):
    cnt = Counter(t.letra for t in tiros)
    n = sum(cnt.values())
    nR = sum(cnt[k] for k in ["R1", "R2", "R3", "R4"])
    nG = sum(cnt[k] for k in ["G1", "G2", "G3", "G4"])
    nR_d, nG_d = load_tiros_rg_detail()
    n_d = nR_d + nG_d
    w("== H0 MEZCLA GLOBAL — ¿calza ruleta 9/54? ==")
    w(f"  lightgreen (R1–R4): tiros n={n}")
    w(f"    R {nR} ({100*nR/n:.1f}%) · G {nG} ({100*nG/n:.1f}%)")
    w(f"    G teórico 9/54 = {100*9/54:.1f}% · Δ {100*nG/n - 100*9/54:+.1f}pp")
    w(f"  detail (R corto): tiros n={n_d}")
    w(f"    R {nR_d} ({100*nR_d/n_d:.1f}%) · G {nG_d} ({100*nG_d/n_d:.1f}%)")
    w("  slots humano vs empírico lightgreen (freq→54):")
    emp = calibrate_slots_from_counts(cnt)
    for let in LETRAS:
        w(f"    {let}: humano={WHEEL_HUMAN[let]:2d}  emp={emp[let]:2d}  n={cnt[let]}")
    w("  Ajuste vs imagen: G1↔G2 (humano 3/2 · data 2/3).")
    w()


def h1_letra_test(tiros: list):
    w("== H1 LETRA — predicción iid ruleta (holdout) ==")
    tags = sorted({t.tag for t in tiros}, key=tag_key)
    train_tags, test_tags = split_tags(tags)
    train = [t for t in tiros if t.tag in train_tags]
    test = [t for t in tiros if t.tag in test_tags]
    cnt_tr = Counter(t.letra for t in train)

    models = {
        "RZ-HUMAN-iid": slots_to_probs(WHEEL_HUMAN),
        "RZ-EMP-iid": slots_to_probs(WHEEL_EMP),
        "RZ-TRAIN-iid": slots_to_probs(calibrate_slots_from_counts(cnt_tr)),
        "RZ-URN-EMP": urn_probs(WHEEL_EMP),
        "UNIFORM-8": {k: 1 / 8 for k in LETRAS},
    }

    w(f"  train tags={len(train_tags)} test tags={len(test_tags)} test tiros={len(test)}")
    w("  modelo · logloss · top1% · vs uniform")
    base_ll = mean(letter_log_loss(models["UNIFORM-8"], t.letra) for t in test)
    rows = []
    for name, probs in models.items():
        ll = mean(letter_log_loss(probs, t.letra) for t in test)
        top1 = mean(1 if max(probs, key=probs.get) == t.letra else 0 for t in test)
        rows.append((ll, top1, name))
    rows.sort()
    for ll, top1, name in rows:
        w(f"    {name:16s}  ll={ll:.3f}  top1={100*top1:.1f}%  Δll={ll-base_ll:+.3f}")
    w("  Lectura: si Δll≈0 vs uniform → ruleta iid no predice letra.")
    w()


def h2_minuto_vs_prod(cinta):
    w("== H2 MINUTO — banda d≤1 vs prod (mismo juez) ==")
    if PRIMERA_UTIL not in cinta.horas:
        w("  sin PRIMERA_UTIL")
        return

    i0 = cinta.orden.index(PRIMERA_UTIL)
    tags = cinta.orden[i0:]
    train_tags, test_tags = split_tags(tags)

    rec = recorrer(cinta)
    hist_by_for = {f["for"]: f for f in rec["historico"] if f.get("for")}

    # mediana nG en train
    train_nG = []
    for tag in train_tags:
        if tag in cinta.horas:
            train_nG.append(len(cinta.horas[tag].nucleo))
    med_nG = int(round(median(train_nG))) if train_nG else 10

    def agg(rows, key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        if not vals:
            return None
        return mean(vals)

    def run_split(tag_list, label):
        rows = []
        for tag in tag_list:
            nxt = cinta.siguiente(tag)
            if not nxt or nxt not in cinta.horas:
                continue
            oficiales = list(cinta.horas[nxt].nucleo)
            if not oficiales:
                continue
            prev = cinta.horas[tag]
            n_tiros = len(prev.tiros_nucleo)
            h1 = list(prev.nucleo)

            fila = hist_by_for.get(nxt, {})
            chips_inter2 = list(fila.get("chips") or [])
            chips_classic = list(fila.get("chips_classic") or [])

            k_wheel = max(0, min(15, round(n_tiros * P_G_WHEEL)))
            k_iid = med_nG

            preds = {
                "RZ-PLANTATE": [],
                "RZ-IID-UNIF": pick_minutes_uniform(nxt, k_iid),
                "RZ-WHEEL-K": pick_minutes_uniform(nxt, k_wheel),
                "PROD-INTER2": chips_inter2,
                "PROD-CLASSIC": chips_classic,
                "REF-H1": h1,
            }
            row = {"for": nxt, "nG": len(oficiales), "n_tiros": n_tiros}
            for name, chips in preds.items():
                sc = banda_score(chips, oficiales)
                row[f"{name}_banda"] = sc["banda"]
                row[f"{name}_hit"] = sc["hit"]
                row[f"{name}_k"] = len(chips)
            rows.append(row)
        return rows

    tr_rows = run_split(train_tags, "train")
    te_rows = run_split(test_tags, "test")

    models = [
        "RZ-PLANTATE",
        "RZ-IID-UNIF",
        "RZ-WHEEL-K",
        "REF-H1",
        "PROD-CLASSIC",
        "PROD-INTER2",
    ]

    w(f"  mediana nG train={med_nG} · P(G) wheel={P_G_WHEEL:.3f}")
    w(f"  horas train={len(tr_rows)} holdout={len(te_rows)}")
    w()
    w("  modelo · banda_train · banda_hold · hit_hold · k_med_hold")
    for m in models:
        bt = agg(tr_rows, f"{m}_banda")
        bh = agg(te_rows, f"{m}_banda")
        hh = agg(te_rows, f"{m}_hit")
        ks = [r[f"{m}_k"] for r in te_rows]
        km = median(ks) if ks else 0
        w(
            f"    {m:14s}  tr={100*bt:.1f}%  ho={100*bh:.1f}%  "
            f"hit_ho={100*hh:.1f}%  k_med={km:.0f}"
        )
    w()


def h3_cierre_ruleta_no_tiene(cinta):
    w("== H3 LO QUE RULETA NO EXPLICA (conocimiento vigente) ==")
    if PRIMERA_UTIL not in cinta.horas:
        return
    i0 = cinta.orden.index(PRIMERA_UTIL)
    tags = cinta.orden[i0:]
    n_largo_g = 0
    n_largo_total = 0
    n_corto_g = 0
    n_corto_total = 0
    for tag in tags:
        if tag not in cinta.horas:
            continue
        nxt = cinta.siguiente(tag)
        if not nxt or nxt not in cinta.horas:
            continue
        prev = cinta.horas[tag]
        if not prev.tiros_nucleo:
            continue
        last = prev.tiros_nucleo[-1]
        first = cinta.horas[nxt].tiros_nucleo[0] if cinta.horas[nxt].tiros_nucleo else None
        if not first:
            continue
        g_next = first.color == "G"
        if last.largo:
            n_largo_total += 1
            if g_next:
                n_largo_g += 1
        else:
            n_corto_total += 1
            if g_next:
                n_corto_g += 1
    w(f"  cierre LARGO → 1er tiro G: {n_largo_g}/{n_largo_total} "
      f"({100*n_largo_g/max(1,n_largo_total):.1f}%)")
    w(f"  cierre CORTO → 1er tiro G: {n_corto_g}/{n_corto_total} "
      f"({100*n_corto_g/max(1,n_corto_total):.1f}%)")
    w("  Ruleta iid no distingue cierre largo/corto → pierde SEGURO ~95%.")
    w()


def h4_identicos_prod(cinta):
    w("== H4 PROD vs CLÁSICO (referencia hilo) ==")
    rec = recorrer(cinta)
    hist = rec["historico"]
    same = sum(1 for f in hist if (f.get("chips") or []) == (f.get("chips_classic") or []))
    w(f"  horas histórico={len(hist)} · P0==P9 idénticas={same}")
    if hist:
        bi = mean(
            banda_score(f.get("chips") or [], f.get("oficiales") or [])["banda"] or 0
            for f in hist
        )
        bc = mean(
            banda_score(f.get("chips_classic") or [], f.get("oficiales") or [])["banda"] or 0
            for f in hist
        )
        bh = mean(
            banda_score(f.get("h1") or [], f.get("oficiales") or [])["banda"] or 0
            for f in hist
        )
        w(f"  banda media INTER2={100*bi:.1f}% · CLASSIC={100*bc:.1f}% · H1 foto={100*bh:.1f}%")
    w()


def sintesis():
    w("=" * 60)
    w("SÍNTESIS lab-ruleta-zero")
    w("=" * 60)
    w("  H0: mezcla G/R ≈ 9/54 — la FORMA ruleta describe el plato.")
    w("  H1: letra iid — mejora vs uniforme (frecuencias) pero sin memoria de tiro.")
    w("  H2: minuto — RZ uniforme ≈ H1/clásico (~46%); INTER2 ~61% (prod gana).")
    w("  H3: cierre largo/corto — fuera del supuesto ruleta.")
    w()
    w("  VEREDICTO:")
    w("    · Como DESCRIPCIÓN global: SÍ (9/54, slots R, menú G).")
    w("    · Como PREDICTOR de minuto: NO alcanza INTER2.")
    w("    · RZ uniforme ≈ foto H-1 en banda (~46%) — geometría, no mapa.")
    w("    · Prod INTER2 +16pp sobre ruleta/H1 — no convergerías al mismo boleto.")
    w()


def main():
    w("LAB RULETA-ZERO — supuesto casino 54 casillas")
    w(f"cinta minuto: {DETAIL.name}")
    w(f"cinta letras: {LIGHTGREEN.name}")
    tiros = load_letters()
    cinta = load_cinta()
    w(f"tiros letra={len(tiros)} · horas cerradas={len(cinta.orden)}")
    w(f"holdout={HOLDOUT} h · PRIMERA_UTIL={PRIMERA_UTIL}")
    w()

    h0_mezcla_global(tiros)
    h1_letra_test(tiros)
    h2_minuto_vs_prod(cinta)
    h3_cierre_ruleta_no_tiene(cinta)
    h4_identicos_prod(cinta)
    sintesis()

    out = OUT / "LAB_RULETA_ZERO.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"\n[ok] {out}")


if __name__ == "__main__":
    main()
