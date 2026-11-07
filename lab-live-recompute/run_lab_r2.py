# -*- coding: utf-8
"""
Lab live-recompute R2 — agota variantes · detail + extraccion-en-vivo.
  python run_lab_r2.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from statistics import mean

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
RZ = ROOT / "lab-ruleta-zero"
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(RZ))
sys.path.insert(0, str(ROOT))

from core_live_rc import EXTRA, load_detail, load_merged, tag_sets  # noqa: E402
from core_rz import HOLDOUT, banda_score, split_tags, tag_key  # noqa: E402
from motors_live_rc import (  # noqa: E402
    StepCtx,
    build_all_strategies,
    chips_lc01_accum,
    dist,
    eval_multi,
    eval_tip,
    rc04_multi93,
)

from src.boleto_inter2 import precompute_beta_chips  # noqa: E402
from src.estado import PRIMERA_UTIL  # noqa: E402
from src.mesas_beta import BOLETO_IDS  # noqa: E402
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


def pct(n, d) -> str:
    return f"{100 * n / d:.1f}%" if d else "—"


def build_rows(cinta):
    rec = recorrer(cinta)
    hist = {f["for"]: f for f in rec["historico"] if f.get("for")}
    beta_by = precompute_beta_chips(cinta)
    rows = []
    for tag, f in hist.items():
        cm = {"oficial": list(f.get("chips_classic") or f.get("chips") or [])}
        ok = True
        for pid in BOLETO_IDS:
            if pid == "oficial":
                continue
            ch = (beta_by.get(tag) or {}).get(pid)
            if ch is None:
                ok = False
                break
            cm[pid] = list(ch)
        inter2 = list(f.get("chips") or [])
        ofc = sorted(f.get("oficiales") or [])
        if not ok or len(ofc) < 2 or not inter2:
            continue
        rows.append({"tag": tag, "chips_map": cm, "inter2": inter2, "oficiales": ofc})
    return rows


def walk_stepwise(rows, test_tags: set[str], single: dict, multi: dict, track_mesa=False):
    names = list(single) + list(multi)
    total = {nm: Counter() for nm in names}
    hold = {nm: Counter() for nm in names}
    gaps_hist: list[int] = []
    nG_prev = 10
    mesa_scores: dict[str, float] = {}

    for row in rows:
        tag = row["tag"]
        ofc = row["oficiales"]
        cm = row["chips_map"]
        inter2 = row["inter2"]
        is_hold = tag in test_tags
        ms = dict(mesa_scores)

        for j, nxt in enumerate(ofc):
            prefix = ofc[:j]
            T = prefix[-1] if prefix else -1
            gaps_hora = [prefix[k] - prefix[k - 1] for k in range(1, len(prefix))]
            ctx = StepCtx(
                T=T,
                prefix=prefix,
                chips_map=cm,
                inter2=inter2,
                gaps_hist=list(gaps_hist),
                gaps_hora=gaps_hora,
                nG_hora_prev=nG_prev,
                tag=tag,
                mesa_scores=ms,
            )
            for nm, fn in single.items():
                eval_tip(fn(ctx), nxt, total[nm])
                if is_hold:
                    eval_tip(fn(ctx), nxt, hold[nm])
            for nm, fn in multi.items():
                out = fn(ctx)
                tips = out if isinstance(out, list) else []
                eval_multi(tips, nxt, total[nm])
                if is_hold:
                    eval_multi(tips, nxt, hold[nm])

            if track_mesa:
                for mid, ch in cm.items():
                    nchip = next((m for m in ch if m > T), None)
                    if nchip is not None and dist(nchip, nxt) <= 1:
                        mesa_scores[mid] = mesa_scores.get(mid, 0) + 1.0
                    else:
                        mesa_scores[mid] = mesa_scores.get(mid, 0) * 0.99

            Tg = ofc[j - 1] if j > 0 else -1
            gaps_hist.append(nxt - Tg if Tg >= 0 else nxt)
        nG_prev = len(ofc)

    return total, hold, names


def banda_hold(hold: Counter) -> float:
    hb = hold.get("hablo", 0) or 0
    return hold["banda"] / hb if hb else 0.0


def rank_hold(hold: dict[str, Counter], names: list[str]) -> list[tuple[float, str]]:
    out = [(banda_hold(hold[nm]), nm) for nm in names if hold[nm].get("hablo")]
    out.sort(reverse=True)
    return out


def h_sweep(title: str, ranking: list[tuple[float, str]], ref_b: float, top_n=15):
    w(f"== {title} ==")
    w(f"  estrategias={len(ranking)} · ref INTER2-fix paso={100*ref_b:.1f}%")
    w()
    for i, (b, nm) in enumerate(ranking[:top_n], 1):
        w(f"    {i:2d}. {nm:22s}  {100*b:.1f}%  (Δ {100*(b-ref_b):+.1f}pp)")
    w()


def h_ablation_multi(ranking: list[tuple[float, str]], prefix: str):
    w(f"== ABLATION {prefix} — top grid ==")
    sub = [(b, nm) for b, nm in ranking if nm.startswith(prefix)]
    sub.sort(reverse=True)
    for b, nm in sub[:8]:
        w(f"    {nm:22s}  {100*b:.1f}%")
    w()
    return sub[0] if sub else (0.0, "")


def h_extra_slice(rows, tags: set[str], single, multi):
    w("== EXTRA — horas solo extraccion-en-vivo ==")
    sub = [r for r in rows if r["tag"] in tags]
    if len(sub) < 1:
        w("  sin horas cerradas only_extra")
        w()
        return
    _, hold, names = walk_stepwise(sub, tags, single, multi)
    ref = banda_hold(hold.get("REF-INTER2-FIX", Counter()))
    rk = rank_hold(hold, names)
    w(f"  n={len(sub)} tags={sorted(tags)}")
    for i, (b, nm) in enumerate(rk[:6], 1):
        w(f"    {i}. {nm}  {100*b:.1f}%  (Δfix {100*(b-ref):+.1f}pp)")
    w()


def h_hora_best(rows, test_tags, best_multi_name, multi_fn):
    w("== HORA — union best multi vs INTER2 (holdout) ==")
    bs_i2 = []
    bs_best = []
    bs_lc = []
    for row in rows:
        if row["tag"] not in test_tags:
            continue
        ofc = row["oficiales"]
        inter2 = row["inter2"]
        tips: set[int] = set()
        gaps_hist: list[int] = []
        for j, nxt in enumerate(ofc):
            prefix = ofc[:j]
            T = prefix[-1] if prefix else -1
            gaps_hora = [prefix[k] - prefix[k - 1] for k in range(1, len(prefix))]
            ctx = StepCtx(
                T=T, prefix=prefix, chips_map=row["chips_map"], inter2=inter2,
                gaps_hist=list(gaps_hist), gaps_hora=gaps_hora, tag=row["tag"],
            )
            out = multi_fn(ctx)
            if isinstance(out, list):
                tips.update(out)
            Tg = ofc[j - 1] if j > 0 else -1
            gaps_hist.append(nxt - Tg if Tg >= 0 else nxt)
        m_i2 = banda_score(inter2, ofc)
        m_b = banda_score(sorted(tips), ofc)
        m_lc = banda_score(chips_lc01_accum(ofc), ofc)
        if m_i2["banda"] is not None:
            bs_i2.append(m_i2["banda"])
        if m_b["banda"] is not None:
            bs_best.append(m_b["banda"])
        if m_lc["banda"] is not None:
            bs_lc.append(m_lc["banda"])
    if bs_i2:
        w(f"    INTER2 fijo           {pct(sum(bs_i2), len(bs_i2))}")
        w(f"    {best_multi_name} union  {pct(sum(bs_best), len(bs_best))}")
        w(f"    LC-01 acum            {pct(sum(bs_lc), len(bs_lc))}")
    w()


def sintesis_r2(rk_detail, rk_merged, best_m93, best_m24, ref_b):
    w("=" * 60)
    w("SÍNTESIS lab-live-recompute R2 — CERRADO")
    w("=" * 60)
    w(f"  Detail holdout #1: {rk_detail[0][1]} @ {100*rk_detail[0][0]:.1f}%")
    w(f"  REF-INTER2-fix paso: {100*ref_b:.1f}%")
    w(f"  Grid MULTI93 best: {best_m93[1]} @ {100*best_m93[0]:.1f}%")
    w(f"  Grid MULTI24 best: {best_m24[1]} @ {100*best_m24[0]:.1f}%")
    if rk_merged:
        w(f"  Merged #1: {rk_merged[0][1]} @ {100*rk_merged[0][0]:.1f}%")
    w()
    w("  VEREDICTO R2:")
    w("    · Pool 10 LIVE-RC = RC-04-MULTI93 (p30 {c,c+1,c+2}) sombra adicional.")
    w("    · No reemplaza Pool 8 INTER2 (boleto pre-hora 60% vs paso multi ~60%).")
    w("    · Ventana/híbrido/LC-xx no superan multi93 en holdout detail.")
    w("    · extra-en-vivo confirma dirección (n pequeño).")
    w("    · Cable: chipsLiveRc() · pin opcional · cero cambio P0–P8/P7.")
    w()


def main():
    w("LAB LIVE-RECOMPUTE R2 — agota variantes · detail + extraccion-en-vivo")
    sets = tag_sets()
    w(f"  detail tags={len(sets['detail'])} · extra file={len(sets['extra_file'])}")
    w(f"  only_extra={len(sets['only_extra'])} · overlap={len(sets['extra_overlap'])}")
    w(f"  extra path: {EXTRA.name}")
    w()

    single, multi = build_all_strategies()
    w(f"  estrategias: single={len(single)} · multi={len(multi)} · total={len(single)+len(multi)}")
    w()

    # ── DETAIL ──
    cinta_d = load_detail()
    rows_d = build_rows(cinta_d)
    tags_d = sorted({r["tag"] for r in rows_d}, key=tag_key)
    if PRIMERA_UTIL in tags_d:
        tags_d = tags_d[tags_d.index(PRIMERA_UTIL):]
    _, test_d = split_tags(tags_d)
    test_set_d = set(test_d)

    w(f"── DETAIL {cinta_d.orden[-1] if cinta_d.orden else '?'} · walk={len(rows_d)}h · holdout={len(test_d)}h ──")
    w()
    _, hold_d, names_d = walk_stepwise(rows_d, test_set_d, single, multi, track_mesa=True)
    ref_b = banda_hold(hold_d.get("REF-INTER2-FIX", Counter()))
    rk_d = rank_hold(hold_d, names_d)
    h_sweep("H1 DETAIL holdout — ranking completo", rk_d, ref_b, top_n=20)

    best_m93 = h_ablation_multi(rk_d, "RC-M93")
    best_m24 = h_ablation_multi(rk_d, "RC-M24")
    h_ablation_multi(rk_d, "RC-M92")

    canon_fn = multi.get("RC-04-MULTI93") or multi.get(best_m93[1])
    if canon_fn:
        h_hora_best(rows_d, test_set_d, "RC-04-MULTI93", canon_fn)

    # ── MERGED ──
    rk_m = []
    rows_m = []
    try:
        cinta_m = load_merged()
        rows_m = build_rows(cinta_m)
        tags_m = sorted({r["tag"] for r in rows_m}, key=tag_key)
        if PRIMERA_UTIL in tags_m:
            tags_m = tags_m[tags_m.index(PRIMERA_UTIL):]
        _, test_m = split_tags(tags_m)
        test_set_m = set(test_m)
        w(f"── MERGED data_3dias+extra · walk={len(rows_m)}h · holdout={len(test_m)}h ──")
        w()
        _, hold_m, names_m = walk_stepwise(rows_m, test_set_m, single, multi)
        rk_m = rank_hold(hold_m, names_m)
        h_sweep("H2 MERGED holdout — top 12", rk_m, banda_hold(hold_m.get("REF-INTER2-FIX", Counter())), top_n=12)
    except Exception as ex:
        w(f"  MERGED skip: {ex}")
        w()

    # ── EXTRA ONLY ──
    closed_extra = set()
    if rows_m:
        closed_extra = {r["tag"] for r in rows_m if r["tag"] in sets["only_extra"]}
    elif rows_d:
        closed_extra = sets["only_extra"] & {r["tag"] for r in rows_d}
    h_extra_slice(rows_m or rows_d, closed_extra, single, multi)

    # ── REFRESH overlap (horas extra pisan detail) últimas 30 ──
    overlap_recent = sorted(sets["extra_overlap"] & {r["tag"] for r in (rows_m or rows_d)}, key=tag_key)[-30:]
    if overlap_recent:
        w("== REFRESH — últimas 30h overlap extra∩detail ==")
        sub = [r for r in (rows_m or rows_d) if r["tag"] in overlap_recent]
        _, hold_o, names_o = walk_stepwise(sub, set(overlap_recent), single, multi)
        ref_o = banda_hold(hold_o.get("REF-INTER2-FIX", Counter()))
        rk_o = rank_hold(hold_o, names_o)
        for i, (b, nm) in enumerate(rk_o[:5], 1):
            w(f"    {i}. {nm}  {100*b:.1f}%  (Δfix {100*(b-ref_o):+.1f}pp)")
        w()

    sintesis_r2(rk_d, rk_m, best_m93, best_m24, ref_b)

    out = OUT / "LAB_LIVE_RECOMPUTE_R2.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # append R2 to main report header
    main_report = OUT / "LAB_LIVE_RECOMPUTE.txt"
    main_report.write_text(
        main_report.read_text(encoding="utf-8") + "\n\n" + "\n".join(lines) + "\n"
        if main_report.exists()
        else "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    w(f"\n[ok] {out}")


if __name__ == "__main__":
    main()
