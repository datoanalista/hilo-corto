# -*- coding: utf-8 -*-
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.lectores import cargar_ingesta

SUM_OP, SUM_FUERTE = 450, 850
PAIRS = [(5, 6), (6, 7), (7, 8), (8, 9), (12, 13), (13, 14), (14, 15), (15, 16), (17, 18), (18, 19)]


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

    def strata_lift(a, b):
        pairs = [(v[a], v[b]) for v in by_day.values() if a in v and b in v]
        if not pairs:
            return None
        lifts = [bv - av for av, bv in pairs]
        op = [bv - av for av, bv in pairs if av < SUM_OP]
        no = [bv - av for av, bv in pairs if SUM_OP <= av < SUM_FUERTE]
        fu = [bv - av for av, bv in pairs if av >= SUM_FUERTE]
        return {
            "n": len(pairs),
            "med_a": median([p[0] for p in pairs]),
            "med_b": median([p[1] for p in pairs]),
            "lift": median(lifts),
            "op": (len(op), median(op) if op else None),
            "no": (len(no), median(no) if no else None),
            "fu": (len(fu), median(fu) if fu else None),
        }

    print("=== COSTURAS mismo dia ===\n")
    for a, b in PAIRS:
        s = strata_lift(a, b)
        if not s:
            continue
        print(
            f"h{a:02d}->h{b:02d}  n={s['n']:2d}  med_a={s['med_a']:.0f}  med_b={s['med_b']:.0f}  lift={s['lift']:+.0f}"
        )
        print(
            f"         opaco->{s['op'][1]:+.0f} (n={s['op'][0]})  "
            f"normal->{s['no'][1]:+.0f} (n={s['no'][0]})  "
            f"fuerte->{s['fu'][1]:+.0f} (n={s['fu'][0]})"
        )

    by_hod = defaultdict(list)
    for r in rows:
        by_hod[r["hod"]].append(r["sum"])
    print("\n=== med_sum manana + h15 ===")
    for hod in [5, 6, 7, 8, 9, 14, 15, 16]:
        xs = by_hod[hod]
        print(f"  h{hod:02d}  med={median(xs):.0f}  n={len(xs)}")


if __name__ == "__main__":
    main()
