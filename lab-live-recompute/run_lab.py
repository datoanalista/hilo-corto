# -*- coding: utf-8
"""
Lab live-recompute — pool intra-hora desde extracción simulada.
  python run_lab.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from statistics import mean

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
RZ = ROOT / "lab-ruleta-zero"
OJ = Path(r"c:\operacion-joker")
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(RZ))
sys.path.insert(0, str(ROOT))

from core_rz import DETAIL, HOLDOUT, banda_score, load_cinta, split_tags, tag_key  # noqa: E402
from motors_live_rc import (  # noqa: E402
    MULTI,
    SINGLE,
    StepCtx,
    chips_lc01_accum,
    eval_multi,
    eval_tip,
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
        cm: dict[str, list[int]] = {"oficial": list(f.get("chips_classic") or f.get("chips") or [])}
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
        rows.append(
            {
                "tag": tag,
                "chips_map": cm,
                "inter2": inter2,
                "oficiales": ofc,
                "nG": len(ofc),
            }
        )
    return rows


def walk_stepwise(rows, test_tags: set[str]):
    names = list(SINGLE) + list(MULTI)
    total = {nm: Counter() for nm in names}
    hold = {nm: Counter() for nm in names}
    gaps_hist: list[int] = []
    nG_prev = 10

    for row in rows:
        tag = row["tag"]
        ofc = row["oficiales"]
        cm = row["chips_map"]
        inter2 = row["inter2"]
        is_hold = tag in test_tags

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
            )
            for nm, fn in SINGLE.items():
                tip = fn(ctx)
                eval_tip(tip, nxt, total[nm])
                if is_hold:
                    eval_tip(tip, nxt, hold[nm])
            for nm, fn in MULTI.items():
                tips = fn(ctx)
                eval_multi(tips, nxt, total[nm])
                if is_hold:
                    eval_multi(tips, nxt, hold[nm])

            Tg = ofc[j - 1] if j > 0 else -1
            gaps_hist.append(nxt - Tg if Tg >= 0 else nxt)
        nG_prev = len(ofc)

    return total, hold, names


def h1_stepwise(total, hold, names, n_hold_hours):
    w("== H1 PASO — predict next G @ cada luz (J1/J4 banda d≤1) ==")
    ref_h = hold.get("REF-INTER2-FIX", Counter())
    ref_b = ref_h["banda"] / ref_h["hablo"] if ref_h.get("hablo") else 0
    w(f"  horas holdout ≈ {n_hold_hours} · pasos = sum(nG-1) por hora")
    w()
    w("  motor · banda_all · banda_ho · hablo_ho · Δ vs INTER2-fix")
    ranking = []
    for nm in names:
        h = hold[nm]
        t = total[nm]
        hb = h["hablo"] or 0
        tb = t["hablo"] or 0
        b_ho = h["banda"] / hb if hb else 0
        b_all = t["banda"] / tb if tb else 0
        delta = b_ho - ref_b
        ranking.append((b_ho, nm, b_all, delta))
        w(
            f"    {nm:18s}  all={pct(t['banda'], tb)}  ho={pct(h['banda'], hb)}  "
            f"hablo={hb}  Δfix={100 * delta:+.1f}pp"
        )
    ranking.sort(reverse=True)
    w()
    w("  ranking holdout paso:")
    for i, (b, nm, _, d) in enumerate(ranking[:8], 1):
        w(f"    {i}. {nm}  {100 * b:.1f}%  (Δ INTER2-fix {100 * d:+.1f}pp)")
    w()
    return ranking


def h2_hora_banda(rows, test_tags):
    w("== H2 HORA — lista acumulada tips vs INTER2 fijo (banda d≤1) ==")
    bs_i2 = []
    bs_lc = []
    bs_m93 = []
    for row in rows:
        if row["tag"] not in test_tags:
            continue
        ofc = row["oficiales"]
        inter2 = row["inter2"]
        lc = chips_lc01_accum(ofc)
        # multi93 chips = union of all step tips in hour
        tips93: set[int] = set()
        gaps_hist: list[int] = []
        for j, nxt in enumerate(ofc):
            prefix = ofc[:j]
            T = prefix[-1] if prefix else -1
            from motors_live_rc import rc04_multi93

            gaps_hora = [prefix[k] - prefix[k - 1] for k in range(1, len(prefix))]
            ctx = StepCtx(
                T=T,
                prefix=prefix,
                chips_map=row["chips_map"],
                inter2=inter2,
                gaps_hist=list(gaps_hist),
                gaps_hora=gaps_hora,
                tag=row["tag"],
            )
            tips93.update(rc04_multi93(ctx))
            Tg = ofc[j - 1] if j > 0 else -1
            gaps_hist.append(nxt - Tg if Tg >= 0 else nxt)
        m_i2 = banda_score(inter2, ofc)
        m_lc = banda_score(lc, ofc)
        m93 = banda_score(sorted(tips93), ofc)
        if m_i2["banda"] is not None:
            bs_i2.append(m_i2["banda"])
        if m_lc["banda"] is not None:
            bs_lc.append(m_lc["banda"])
        if m93["banda"] is not None:
            bs_m93.append(m93["banda"])
    if bs_i2:
        w(f"    INTER2 fijo hora      {pct(sum(bs_i2), len(bs_i2))}  k≈{mean(len(r['inter2']) for r in rows if r['tag'] in test_tags):.1f}")
        w(f"    LC-01 chips acum      {pct(sum(bs_lc), len(bs_lc))}")
        w(f"    RC-MULTI93 union/hora {pct(sum(bs_m93), len(bs_m93))}")
    w()


def sintesis(ranking):
    w("=" * 60)
    w("SÍNTESIS lab-live-recompute R1")
    w("=" * 60)
    if not ranking:
        w("  sin datos")
        w()
        return
    best = ranking[0]
    ref = next((r for r in ranking if r[1] == "REF-INTER2-FIX"), None)
    ref_b = ref[0] if ref else 0
    w(f"  Mejor paso holdout: {best[1]} @ {100 * best[0]:.1f}%")
    w(f"  REF-INTER2-fix paso: {100 * ref_b:.1f}%")
    if best[1].startswith("RC-") and best[0] > ref_b + 0.005:
        w(f"  OLOR: {best[1]} supera INTER2 fijo en paso (+{100 * (best[0] - ref_b):.1f}pp)")
    elif best[1].startswith("RC-"):
        w("  RC no supera INTER2-fix en paso holdout.")
    lc = next((r for r in ranking if r[1] == "REF-LC01"), None)
    if lc:
        w(f"  REF-LC01 paso: {100 * lc[0]:.1f}% (Pool 7 canónico)")
    w()
    w("  VEREDICTO R1:")
    w("    · Pool live-recompute = otro juez (paso next-G), no boleto hora INTER2.")
    w("    · Multi RC-03/04 = candidatos pool sombra adicional.")
    w("    · Cablear solo tras R2 confirmación + OK humano.")
    w()


def main():
    w("LAB LIVE-RECOMPUTE — extracción min a min · pool extra")
    w(f"cinta: {DETAIL.name}")
    cinta = load_cinta()
    rows = build_rows(cinta)
    tags = sorted({r["tag"] for r in rows}, key=tag_key)
    if PRIMERA_UTIL in tags:
        i0 = tags.index(PRIMERA_UTIL)
        tags = tags[i0:]
    _, test_tags = split_tags(tags)
    test_set = set(test_tags)
    n_hold = sum(1 for r in rows if r["tag"] in test_set)

    w(f"horas walk={len(rows)} · holdout tags={len(test_tags)} · horas ho={n_hold}")
    w()

    total, hold, names = walk_stepwise(rows, test_set)
    ranking = h1_stepwise(total, hold, names, n_hold)
    h2_hora_banda(rows, test_set)
    sintesis(ranking)

    out = OUT / "LAB_LIVE_RECOMPUTE.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"\n[ok] {out}")


if __name__ == "__main__":
    main()
