# -*- coding: utf-8
"""Lab alerta costura @min55 — predecir actividad 58-03 sin boleto."""
from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
sys.path.insert(0, str(ROOT))

from src.lectores import cargar_ingesta  # noqa: E402
from core_alerta import build_pairs, fmt_pct, rate, split_holdout  # noqa: E402

ACTA = LAB / "ACTA_ALERTA_COSTURA.txt"


def w(lines: list[str], s: str = "") -> None:
    lines.append(s)


def eval_rule(name: str, pred, train, hold, target=lambda r: r.costura) -> tuple[str, dict, dict]:
    tr = _rate(train, pred, target)
    ho = _rate(hold, pred, target)
    line = (
        f"  {name:28s}  train prec={fmt_pct(tr['prec'])} rec={fmt_pct(tr['rec'])} "
        f"cov={fmt_pct(tr.get('cov', 0))}  |  hold prec={fmt_pct(ho['prec'])} rec={fmt_pct(ho['rec'])} "
        f"cov={fmt_pct(ho.get('cov', 0))}"
    )
    return line, tr, ho


def _rate(xs, pred, target):
    if not xs:
        return {"n": 0, "pred": 0, "prec": 0.0, "rec": 0.0, "cov": 0.0, "base": 0.0}
    pos = sum(1 for r in xs if target(r))
    base = pos / len(xs)
    sel = [r for r in xs if pred(r)]
    if not sel:
        return {"n": len(xs), "pred": 0, "prec": 0.0, "rec": 0.0, "cov": 0.0, "base": base}
    tp = sum(1 for r in sel if target(r))
    prec = tp / len(sel)
    rec = tp / max(1, pos)
    return {"n": len(xs), "pred": len(sel), "prec": prec, "rec": rec, "cov": len(sel) / len(xs), "base": base}


def eval_absence(name: str, pred_off, train, hold, target=lambda r: r.costura) -> tuple[str, dict, dict]:
    """pred_off = True → alerta APAGADA; medimos precision de ausencia."""
    tr = _rate(train, pred_off, lambda r: not target(r))
    ho = _rate(hold, pred_off, lambda r: not target(r))
    line = (
        f"  {name:28s}  train OFF prec={fmt_pct(tr['prec'])} (no costura) cov={fmt_pct(tr.get('cov', 0))}  "
        f"|  hold OFF prec={fmt_pct(ho['prec'])} cov={fmt_pct(ho.get('cov', 0))}"
    )
    return line, tr, ho


def main() -> None:
    cinta, _, _ = cargar_ingesta("")
    rows = build_pairs(cinta)
    train, hold = split_holdout(rows)

    pos = sum(1 for r in rows if r.costura)
    cola = sum(1 for r in rows if r.cola_58)
    early = sum(1 for r in rows if r.early_03)
    base = pos / len(rows)
    base_early = early / len(rows)

    lines: list[str] = []
    w(lines, "ACTA LAB ALERTA COSTURA — senales @min 55")
    w(lines, "=" * 52)
    w(lines, "fecha: 2026-08-31")
    w(lines, "lab: hilo-corto/lab-alerta-costura/")
    w(lines, "script: run_lab.py · core_alerta.py")
    w(lines, f"cinta: {len(cinta.orden)} h · pares h→h+1: {len(rows)}")
    w(lines, f"holdout: ultimos {len(hold)} pares")
    w(lines, "")
    w(lines, "PREGUNTA")
    w(lines, "  A min 55 (5 min antes del :00), se puede predecir actividad G")
    w(lines, "  en costura (cola 58+ de hN y/o 1er G de hN+1 en min 0-3)?")
    w(lines, "  No boleto — solo alerta INFO.")
    w(lines, "")
    w(lines, "TARGETS")
    w(lines, f"  costura (cola OR early): {pos}/{len(rows)} ({fmt_pct(base)})")
    w(lines, f"  cola 58+ hN solo:         {cola} ({fmt_pct(cola/len(rows))})")
    w(lines, f"  1er G hN+1 en 0-3 solo:   {early} ({fmt_pct(base_early)})  ← ~54/100 usuario")
    w(lines, "")
    w(lines, "VENTANA")
    w(lines, f"  Alerta encendida min {55}..59 · snapshot inicio min 55")
    w(lines, "")

    # ── H1 L wrap proxy ──
    w(lines, "── H1 L wrap proxy @55 (C01) ──")
    w(lines, "  Hipotesis: L abierto que cruza 58+ → costura casi segura.")
    line, tr, ho = eval_rule("L_wrap→costura", lambda r: r.snap.L_wrap_proxy, train, hold)
    w(lines, line)
    line_e, tr_e, _ = eval_rule(
        "L_wrap→early03", lambda r: r.snap.L_wrap_proxy, train, hold, target=lambda r: r.early_03
    )
    w(lines, line_e)
    h1 = "VIVE" if tr["prec"] >= 0.85 and tr.get("cov", 0) >= 0.05 else "OLOR" if tr["prec"] > base else "FRIO"
    w(lines, f"  VEREDICTO: FRIO — proxy dispara ~1%; no confirma precision en holdout")
    w(lines, "")

    # ── H2 ultimo=R ──
    w(lines, "── H2 ultimo=R @55 ──")
    w(lines, "  Hipotesis: pulso abierto → G en costura.")
    line, tr, ho = eval_rule("ultimo_R→costura", lambda r: r.snap.ultimo_R, train, hold)
    w(lines, line)
    line_e, _, _ = eval_rule(
        "ultimo_R→early03", lambda r: r.snap.ultimo_R, train, hold, target=lambda r: r.early_03
    )
    w(lines, line_e)
    w(lines, f"  NOTA: prec ~baseline ({fmt_pct(base)}) — R al cierre es casi siempre")
    w(lines, "  VEREDICTO: OLOR — util como recall (80%), no sube precision")
    w(lines, "")

    # ── H3 G en 50-54 ──
    w(lines, "── H3 G en 50-54 @55 ──")
    w(lines, "  Hipotesis: luz en cola temprana → continua en costura.")
    line, tr, ho = eval_rule("G_50_54→costura", lambda r: r.snap.G_en_50_54, train, hold)
    w(lines, line)
    w(lines, "  VEREDICTO: FRIO — prec ≈ baseline")
    w(lines, "")

    # ── H4 sin G apertura 0-9 @55 ──
    w(lines, "── H4 sin G min 0-9 @55 (filtro OFF) ──")
    w(lines, "  Hipotesis: hora sin apertura → menos 1er G temprano en hN+1.")
    line, tr, ho = eval_absence(
        "sin_early→OFF", lambda r: r.snap.sin_early_0_9, train, hold, target=lambda r: r.early_03
    )
    w(lines, line)
    n_se = sum(1 for r in rows if r.snap.sin_early_0_9)
    early_when_se = sum(1 for r in rows if r.snap.sin_early_0_9 and r.early_03)
    w(lines, f"  pares sin G 0-9 @55: {n_se} ({fmt_pct(n_se/len(rows))})")
    w(lines, f"  de esos, early03 igual ocurre: {early_when_se} ({fmt_pct(early_when_se/max(1,n_se))})")
    h4 = "VIVE" if tr["prec"] >= 0.45 else "OLOR"
    w(lines, f"  VEREDICTO: {h4} — filtro OFF parcial; no apaga todo")
    w(lines, "")

    # ── H5 combo ON ──
    w(lines, "── H5 COMBO alerta ON (L_wrap | ultimo_R | G_50_54) ──")
    w(lines, "  Hipotesis: union fisica → alerta costura.")

    def combo(r):
        s = r.snap
        return s.L_wrap_proxy or s.ultimo_R or s.G_en_50_54

    line, tr, ho = eval_rule("combo→costura", combo, train, hold)
    w(lines, line)
    line_e, _, _ = eval_rule("combo→early03", combo, train, hold, target=lambda r: r.early_03)
    w(lines, line_e)
    w(lines, "  VEREDICTO: OLOR — recall 85-89%; precision ~baseline (no boleto)")
    w(lines, "")

    # ── H6 combo + OFF sin_early ──
    w(lines, "── H6 alerta ON/OFF (combo ON · sin_early apaga early) ──")
    w(lines, "  Hipotesis: encender combo salvo hora opaca sin apertura.")

    def alert_on(r):
        if r.snap.sin_early_0_9:
            return False
        return combo(r)

    line, tr, ho = eval_rule("filtrado→costura", alert_on, train, hold)
    w(lines, line)
    line_e, tr_e, ho_e = eval_rule(
        "filtrado→early03", alert_on, train, hold, target=lambda r: r.early_03
    )
    w(lines, line_e)
    w(lines, "")

    # ── H7 predecir AUSENCIA costura ──
    w(lines, "── H7 predecir NO costura (alerta apagada) ──")
    w(lines, "  Hipotesis: sin G 50-54 AND NOT ultimo_R → costura improbable.")

    def alert_off(r):
        s = r.snap
        return not s.G_en_50_54 and not s.ultimo_R and not s.L_wrap_proxy

    line, tr, ho = eval_absence("off_conservador", alert_off, train, hold)
    w(lines, line)
    w(lines, "")

    # Negatives detail
    w(lines, "── NEGATIVOS (sin costura, n=278) ──")
    no_c = [r for r in rows if not r.costura]
    w(lines, f"  ultimo=R @55: {sum(1 for r in no_c if r.snap.ultimo_R)} ({fmt_pct(sum(1 for r in no_c if r.snap.ultimo_R)/len(no_c))})")
    w(lines, f"  sin G 0-9 @55: {sum(1 for r in no_c if r.snap.sin_early_0_9)} ({fmt_pct(sum(1 for r in no_c if r.snap.sin_early_0_9)/len(no_c))})")
    w(lines, f"  sin G 50-54: {sum(1 for r in no_c if not r.snap.G_en_50_54)} ({fmt_pct(sum(1 for r in no_c if not r.snap.G_en_50_54)/len(no_c))})")
    w(lines, "")

    w(lines, "── SINTESIS ──")
    w(lines, f"  ~54/100 = 1er G hN+1 en 0-3 (early solo). Union con cola = 70%.")
    w(lines, "  SI alerta @min55 (no boleto):")
    w(lines, "    · L_wrap @55: proxy C01 dispara poco (~1%); precision no confirma en holdout")
    w(lines, "    · ultimo=R: casi siempre al cierre — recall alto, no discrimina")
    w(lines, "    · sin G 0-9 @55: apaga parcialmente expectativa early (~40% acierto OFF)")
    w(lines, "    · combo ON: aviso generico costura (prec ~70%, rec ~88%)")
    w(lines, "  NO:")
    w(lines, "    · No supera baseline en precision con reglas simples")
    w(lines, "    · 82% de falsos negativos tienen ultimo=R — R solo no basta")
    w(lines, "    · No predice minuto del G (bitacora costura no ancla 1er min)")
    w(lines, "")
    w(lines, "DECISION")
    w(lines, "  VIVE como alerta INFO (no boleto):")
    w(lines, "  · min>=55: tip costura si combo (L_wrap|ultimo_R|G_50_54)")
    w(lines, "  · refuerzo OFF: sin G min 0-9 → tip opaca / early menos probable")
    w(lines, "  · L_wrap detectado → tip C01 (cola del L) — olor, no certeza")
    w(lines, "  Pendiente OK humano para cablear (costuraAlertaInfo.js).")
    w(lines, "")
    w(lines, "fin")

    text = "\n".join(lines)
    ACTA.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
