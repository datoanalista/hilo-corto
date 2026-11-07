# -*- coding: utf-8 -*-
"""Barrido costuras hN->hN+1 mismo dia — buscar rebotes/techo."""
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.lectores import cargar_ingesta

SUM_OP, SUM_FUERTE = 450, 850
HOLDOUT = 72


def main():
    cinta, _, _ = cargar_ingesta("")
    rows = []
    for tag in cinta.orden:
        h = cinta.get(tag)
        gs = [t for t in (h.tiros_nucleo or []) if t.color == "G" and t.lumen]
        if not gs:
            continue
        sg = sum(t.lumen for t in gs)
        hod = int(tag.split("-")[0][1:])
        day = tag.split("-")[1]
        rows.append({"hod": hod, "day": day, "sum": sg})

    by_day = defaultdict(dict)
    for r in rows:
        by_day[r["day"]][r["hod"]] = r["sum"]

    def analyze_pair(a, b):
        pairs = [(v[a], v[b]) for v in by_day.values() if a in v and b in v]
        if len(pairs) < 8:
            return None
        lifts = [bv - av for av, bv in pairs]
        op = [bv - av for av, bv in pairs if av < SUM_OP]
        no = [bv - av for av, bv in pairs if SUM_OP <= av < SUM_FUERTE]
        fu = [bv - av for av, bv in pairs if av >= SUM_FUERTE]
        return {
            "a": a,
            "b": b,
            "n": len(pairs),
            "lift": median(lifts),
            "med_a": median([p[0] for p in pairs]),
            "med_b": median([p[1] for p in pairs]),
            "op_n": len(op),
            "op_lift": median(op) if op else None,
            "no_n": len(no),
            "no_lift": median(no) if no else None,
            "fu_n": len(fu),
            "fu_lift": median(fu) if fu else None,
        }

    all_pairs = []
    for a in range(24):
        b = (a + 1) % 24
        if b == 0:
            continue  # skip h23->h0 cross-midnight same tag day issue
        r = analyze_pair(a, b)
        if r:
            all_pairs.append(r)

    # Also h23->h0 next hour same calendar? skip - different day logic messy

    print("=== BARRIDO hN->h(N+1) mismo dia ===")
    print(f"cinta {len(rows)} h · dias {len(by_day)}\n")

    # Rank by opaco lift (rebote signal)
    rebotes = sorted(
        [p for p in all_pairs if p["op_lift"] is not None and p["op_n"] >= 5],
        key=lambda x: -x["op_lift"],
    )
    print("--- TOP rebote opaco -> (op_lift, n opaco) ---")
    for p in rebotes[:12]:
        flag = " ***" if p["op_lift"] >= 250 and p["op_n"] >= 8 else ""
        print(
            f"  h{p['a']:02d}->h{p['b']:02d}  op_lift={p['op_lift']:+.0f} (n={p['op_n']})  "
            f"total_lift={p['lift']:+.0f}  med_a={p['med_a']:.0f} med_b={p['med_b']:.0f}{flag}"
        )

    techos = sorted(
        [p for p in all_pairs if p["fu_lift"] is not None and p["fu_n"] >= 4],
        key=lambda x: x["fu_lift"],
    )
    print("\n--- TOP techo fuerte -> (fu_lift, n fuerte) ---")
    for p in techos[:12]:
        flag = " ***" if p["fu_lift"] <= -400 and p["fu_n"] >= 5 else ""
        print(
            f"  h{p['a']:02d}->h{p['b']:02d}  fu_lift={p['fu_lift']:+.0f} (n={p['fu_n']})  "
            f"total_lift={p['lift']:+.0f}{flag}"
        )

    # Strong total lift (valley->peak structure)
    print("\n--- TOP lift total (estructura valle->pico) ---")
    for p in sorted(all_pairs, key=lambda x: -x["lift"])[:10]:
        print(
            f"  h{p['a']:02d}->h{p['b']:02d}  lift={p['lift']:+.0f}  "
            f"med_a={p['med_a']:.0f}->med_b={p['med_b']:.0f}  n={p['n']}"
        )

    # Pairs where med_a is valley (bottom quartile of all hod medians)
    by_hod = defaultdict(list)
    for r in rows:
        by_hod[r["hod"]].append(r["sum"])
    hod_med = {hod: median(v) for hod, v in by_hod.items()}
    q25 = sorted(hod_med.values())[6]

    print(f"\n--- Rebotes desde VALLE hod (med_a < {q25:.0f}) ---")
    valles = [p for p in all_pairs if p["med_a"] < q25]
    for p in sorted(valles, key=lambda x: -x["lift"])[:8]:
        print(
            f"  h{p['a']:02d}->h{p['b']:02d}  lift={p['lift']:+.0f}  op={p['op_lift']:+.0f}({p['op_n']})  "
            f"med_a={p['med_a']:.0f}"
        )

    # Non-consecutive same-day (hod gap 2-3) - sample
    print("\n--- Pares NO consecutivos (gap 2) mismo dia ---")
    gap2 = []
    for a in range(24):
        b = a + 2
        if b > 23:
            continue
        pairs = [(v[a], v[b]) for v in by_day.values() if a in v and b in v]
        if len(pairs) < 8:
            continue
        op = [bv - av for av, bv in pairs if av < SUM_OP]
        if len(op) >= 5:
            gap2.append(
                {
                    "a": a,
                    "b": b,
                    "op_lift": median(op),
                    "op_n": len(op),
                    "lift": median([bv - av for av, bv in pairs]),
                }
            )
    for p in sorted(gap2, key=lambda x: -x["op_lift"])[:8]:
        print(
            f"  h{p['a']:02d}->h{p['b']:02d}  op_lift={p['op_lift']:+.0f} (n={p['op_n']})  lift={p['lift']:+.0f}"
        )

    # Holdout stability top candidates
    days_sorted = sorted(by_day.keys())
    if len(days_sorted) > HOLDOUT // 24:
        cut_day = days_sorted[-(HOLDOUT // 24 + 1)]
        train_days = {d for d in days_sorted if d < cut_day}
        test_days = {d for d in days_sorted if d >= cut_day}

        def split_lift(a, b, days):
            pairs = [(by_day[d][a], by_day[d][b]) for d in days if a in by_day[d] and b in by_day[d]]
            if not pairs:
                return None, 0
            op = [bv - av for av, bv in pairs if av < SUM_OP]
            return (median(op) if op else None, len(op))

        print("\n--- HOLDOUT opaco lift train vs test (candidatos ***) ---")
        cands = [
            (p["a"], p["b"])
            for p in all_pairs
            if p["op_lift"] and p["op_lift"] >= 200 and p["op_n"] >= 8
        ]
        for a, b in cands:
            tr, ntr = split_lift(a, b, train_days)
            te, nte = split_lift(a, b, test_days)
            te_val = te if te is not None else 0
            print(f"  h{a:02d}->h{b:02d}  train op={tr:+.0f}({ntr})  test op={te_val:+.0f}({nte})")

    # Score: rebote fuerte = op_lift high + op_n + total lift positive
    scored = []
    for p in all_pairs:
        if p["op_lift"] is None or p["op_n"] < 5:
            continue
        score = p["op_lift"] * min(1, p["op_n"] / 10) + max(0, p["lift"]) * 0.3
        if p["fu_lift"] is not None and p["fu_lift"] < -300:
            score_techo = abs(p["fu_lift"]) * min(1, p["fu_n"] / 8)
        else:
            score_techo = 0
        scored.append({**p, "score_rebote": score, "score_techo": score_techo})

    print("\n--- CANDIDATOS CABLEAR (score compuesto) ---")
    for p in sorted(scored, key=lambda x: -x["score_rebote"])[:8]:
        vive = p["op_lift"] >= 250 and p["op_n"] >= 8
        print(
            f"  REBOTE h{p['a']:02d}->h{p['b']:02d}  score={p['score_rebote']:.0f}  "
            f"op={p['op_lift']:+.0f}({p['op_n']})  {'VIVE?' if vive else 'OLOR'}"
        )
    for p in sorted(scored, key=lambda x: -x["score_techo"])[:8]:
        if p["score_techo"] < 200:
            continue
        vive = p["fu_lift"] <= -400 and p["fu_n"] >= 5
        print(
            f"  TECHO  h{p['a']:02d}->h{p['b']:02d}  score={p['score_techo']:.0f}  "
            f"fu={p['fu_lift']:+.0f}({p['fu_n']})  {'VIVE?' if vive else 'OLOR'}"
        )


if __name__ == "__main__":
    main()
