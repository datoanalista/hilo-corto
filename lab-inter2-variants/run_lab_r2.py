# -*- coding: utf-8 -*-
"""
Lab INTER2 variantes R2 — ge2 + filtros INFO (@19 · @20 · H-1).
  python run_lab_r2.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from statistics import mean

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
RZ = ROOT / "lab-ruleta-zero"
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(RZ))
sys.path.insert(0, str(ROOT))

import importlib.util

_spec = importlib.util.spec_from_file_location("run_lab_r1", LAB / "run_lab.py")
_run_r1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_run_r1)
build_rows = _run_r1.build_rows
load_cinta = _run_r1.load_cinta
metrics = _run_r1.metrics

from core_info import load_horas_detail, prev_tag  # noqa: E402
from core_rz import DETAIL, HOLDOUT, split_tags, tag_key  # noqa: E402
from motors_info_filter import build_info_filters  # noqa: E402

OUT = LAB / "reports"
OUT.mkdir(exist_ok=True)
lines: list[str] = []


def w(s=""):
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def agg(rows, name):
    bs = [r[f"{name}_banda"] for r in rows if r.get(f"{name}_banda") is not None]
    if not bs:
        return None
    ks = [r[f"{name}_k"] for r in rows]
    hs = [r[f"{name}_hit"] for r in rows]
    ex = [r[f"{name}_exact"] for r in rows if r.get(f"{name}_exact") is not None]
    trimmed = [r.get(f"{name}_trim_pct", 0) for r in rows]
    return {
        "banda": mean(bs),
        "k": mean(ks),
        "hit": mean(hs),
        "exact": mean(ex) if ex else None,
        "trim_pct": mean(trimmed) if trimmed else 0,
        "k0": sum(1 for r in rows if r.get(f"{name}_k", 0) == 0),
        "n": len(bs),
    }


def walk_info(rows, test_tags, horas_info, strategies):
    tr, te = [], []
    ref = "REF-INTER2-ge2"
    for row in rows:
        tag = row["tag"].lower()
        hi = horas_info.get(tag)
        if not hi:
            continue
        prev = prev_tag(tag, horas_info)
        ctx = {
            "tag": tag,
            "chips_map": row["chips_map"],
            "prev": prev,
            "st19": hi.estado(19),
            "st20": hi.estado(20),
            "oficiales": row["oficiales"],
        }
        bucket = te if tag in test_tags else tr
        base_ch = strategies[ref](ctx)
        base_k = len(base_ch)
        out = {"tag": tag, "nG": row["nG"]}
        for nm, fn in strategies.items():
            ch = fn(ctx)
            m = metrics(ch, row["oficiales"])
            out[f"{nm}_banda"] = m["banda"]
            out[f"{nm}_k"] = m["k"]
            out[f"{nm}_hit"] = m["hit"]
            out[f"{nm}_exact"] = m["exact"]
            out[f"{nm}_trim_pct"] = (
                100 * (1 - len(ch) / base_k) if base_k else 0.0
            )
        bucket.append(out)
    return tr, te


def pareto(ref_te, candidates):
    out = []
    for nm, te in candidates:
        if te["banda"] >= ref_te["banda"] - 0.003 and te["k"] < ref_te["k"] - 0.3:
            out.append((nm, te))
        elif te["banda"] > ref_te["banda"] + 0.003 and te["k"] <= ref_te["k"]:
            out.append((nm, te))
    out.sort(key=lambda x: (-x[1]["banda"], x[1]["k"]))
    return out


def main():
    w("LAB INTER2 VARIANTES R2 — ge2 + filtros INFO")
    w(f"detail: {DETAIL} · holdout={HOLDOUT}h · juez banda d≤1")
    w("  ge2 intacto (≥2 P0–P5); INFO recorta bloques @19/@20 o H-1")
    w()

    horas_info = load_horas_detail(DETAIL)
    cinta = load_cinta()
    rows = build_rows(cinta)
    tags = sorted({r["tag"] for r in rows}, key=tag_key)
    _, test_tags = split_tags(tags)
    test_set = set(t.lower() for t in test_tags)
    strategies = build_info_filters()

    tr, te = walk_info(rows, test_set, horas_info, strategies)
    ref = "REF-INTER2-ge2"
    ref_te = agg(te, ref)
    ref_tr = agg(tr, ref)
    if not ref_te:
        w("sin holdout")
        return

    w(f"horas eval={len(te)+len(tr)} · holdout={len(te)}")
    w(f"REF train {100*ref_tr['banda']:.1f}% k={ref_tr['k']:.1f} · "
      f"holdout {100*ref_te['banda']:.1f}% k={ref_te['k']:.1f}")
    w()

    w("== RANKING holdout ==")
    w(f"  {'motor':26s}  banda   k   exact  hit  trim%  k=0   Δpp")
    ranking = []
    for nm in strategies:
        te_a = agg(te, nm)
        if not te_a:
            continue
        d = te_a["banda"] - ref_te["banda"]
        ranking.append((te_a["banda"], nm, te_a, d))
        w(
            f"  {nm:26s}  {100*te_a['banda']:5.1f}%  {te_a['k']:5.1f}  "
            f"{100*(te_a['exact'] or 0):5.1f}%  {100*te_a['hit']:5.0f}%  "
            f"{te_a['trim_pct']:5.1f}  {te_a['k0']:3d}  {100*d:+5.1f}pp"
        )
    ranking.sort(reverse=True)
    w()

    w("== H-1 pre-hora ==")
    for nm in strategies:
        if not nm.startswith("F-H1"):
            continue
        te_a = agg(te, nm)
        if te_a:
            w(
                f"  {nm:26s}  {100*te_a['banda']:.1f}%  k={te_a['k']:.1f}  "
                f"trim={te_a['trim_pct']:.0f}%  Δ={100*(te_a['banda']-ref_te['banda']):+.1f}pp"
            )
    w()

    w("== @19 cola ==")
    for nm in strategies:
        if "@19" not in nm:
            continue
        te_a = agg(te, nm)
        if te_a:
            w(
                f"  {nm:26s}  {100*te_a['banda']:.1f}%  k={te_a['k']:.1f}  "
                f"trim={te_a['trim_pct']:.0f}%  Δ={100*(te_a['banda']-ref_te['banda']):+.1f}pp"
            )
    w()

    w("== @20 intra ==")
    for nm in strategies:
        if "@20" not in nm:
            continue
        te_a = agg(te, nm)
        if te_a:
            w(
                f"  {nm:26s}  {100*te_a['banda']:.1f}%  k={te_a['k']:.1f}  "
                f"trim={te_a['trim_pct']:.0f}%  Δ={100*(te_a['banda']-ref_te['banda']):+.1f}pp"
            )
    w()

    w("== COMBOS ==")
    for nm in ("F-19cola+20opaca", "F-H1wrap+19cola"):
        te_a = agg(te, nm)
        if te_a:
            w(
                f"  {nm:26s}  {100*te_a['banda']:.1f}%  k={te_a['k']:.1f}  "
                f"Δ={100*(te_a['banda']-ref_te['banda']):+.1f}pp"
            )
    w()

    w("== PARETO banda/k vs REF ==")
    cands = [(n, agg(te, n)) for n in strategies if n != ref and agg(te, n)]
    pf = pareto(ref_te, cands)
    if pf:
        for nm, te_a in pf[:6]:
            w(
                f"  {nm:26s}  banda={100*te_a['banda']:.1f}%  k={te_a['k']:.1f}  "
                f"Δb={100*(te_a['banda']-ref_te['banda']):+.1f}pp  "
                f"Δk={te_a['k']-ref_te['k']:+.1f}"
            )
    else:
        w("  (ninguno domina REF)")
    w()

    w("== TOP 5 holdout ==")
    for i, (b, nm, te_a, d) in enumerate(ranking[:5], 1):
        w(f"  {i}. {nm}  {100*b:.1f}%  k={te_a['k']:.1f}  ΔREF={100*d:+.1f}pp")
    w()

    out = OUT / "LAB_INTER2_VARIANTS_R2.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"Reporte: {out}")


if __name__ == "__main__":
    main()
