# -*- coding: utf-8 -*-
"""Perfil h15 vs vecinos — borrador lab."""
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median, mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.lectores import cargar_ingesta

SUM_FUERTE = 850
SUM_SN = 1600
DOW = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"]


def perfil_hora(hod, rows):
    xs = [r for r in rows if r["hod"] == hod]
    if not xs:
        return None
    sums = sorted(r["sum"] for r in xs)
    means = [r["mean"] for r in xs]
    nG = [r["nG"] for r in xs]
    return {
        "n": len(xs),
        "med_sum": median(sums),
        "mean_sum": mean(sums),
        "p25_sum": sums[len(sums) // 4],
        "p75_sum": sums[3 * len(sums) // 4],
        "p_gen": sum(1 for r in xs if r["gen"]) / len(xs),
        "p_fuerte": sum(1 for r in xs if r["sum"] >= SUM_FUERTE) / len(xs),
        "p_sn": sum(1 for r in xs if r["sum"] >= SUM_SN) / len(xs),
        "med_nG": median(nG),
        "med_meanG": median(means),
        "p_op": sum(1 for r in xs if r["op"]) / len(xs),
    }


def main():
    cinta, _, _ = cargar_ingesta("")
    rows = []
    for tag in cinta.orden:
        h = cinta.get(tag)
        tiros = [t for t in (h.tiros_nucleo or []) if t.color == "G" and t.lumen]
        if not tiros:
            continue
        lum = [t.lumen for t in tiros]
        sg = sum(lum)
        mg = sg / len(lum)
        hod = int(tag.split("-")[0][1:])
        day = tag.split("-")[1]
        dd, mm, yy = int(day[:2]), int(day[2:4]), 2000 + int(day[4:6])
        from datetime import date

        dt = date(yy, mm, dd)
        rows.append({
            "tag": tag,
            "hod": hod,
            "sum": sg,
            "mean": mg,
            "nG": len(lum),
            "gen": sg >= SUM_FUERTE,
            "op": sg < 450 or mg < 42,
            "dow": dt.weekday(),
            "day": day,
        })

    print(f"=== CINTA: {len(rows)} horas ===\n")

    # ranking med_sum
    by_hod = {}
    for hod in range(24):
        p = perfil_hora(hod, rows)
        if p:
            by_hod[hod] = p
    ranked = sorted(by_hod.items(), key=lambda x: -x[1]["med_sum"])
    print("--- TOP 5 med_sum ---")
    for hod, p in ranked[:5]:
        print(f"  h{hod:02d}  med={p['med_sum']:.0f}  p_gen={p['p_gen']*100:.0f}%  p_sn={p['p_sn']*100:.0f}%  n={p['n']}")

    print("\n--- h15 vs h08 vs h14 vs h16 ---")
    for hod in [14, 15, 16, 8, 19]:
        p = by_hod.get(hod)
        if p:
            print(
                f"  h{hod:02d}  med={p['med_sum']:.0f}  p25={p['p25_sum']:.0f}  p75={p['p75_sum']:.0f}  "
                f"p_gen={p['p_gen']*100:.0f}%  med_nG={p['med_nG']:.0f}  med_meanG={p['med_meanG']:.1f}  n={p['n']}"
            )

    h15 = [r for r in rows if r["hod"] == 15]
    print(f"\n--- h15 distribución sum (n={len(h15)}) ---")
    bands = [(0, 450), (450, 600), (600, 850), (850, 1100), (1100, 1600), (1600, 99999)]
    for lo, hi in bands:
        c = sum(1 for r in h15 if lo <= r["sum"] < hi)
        print(f"  {lo}-{hi if hi < 90000 else '+'}: {c} ({100*c/len(h15):.0f}%)")

    print("\n--- h15 por DOW ---")
    by_dow = defaultdict(list)
    for r in h15:
        by_dow[r["dow"]].append(r["sum"])
    for d in range(7):
        xs = by_dow[d]
        if xs:
            print(f"  {DOW[d]}  n={len(xs)}  med={median(xs):.0f}  p_gen={100*sum(1 for x in xs if x>=850)/len(xs):.0f}%")

    # h14 -> h15 mismo día
    print("\n--- Par h14->h15 mismo dia ---")
    by_day = defaultdict(dict)
    for r in rows:
        if r["hod"] in (14, 15):
            by_day[r["day"]][r["hod"]] = r["sum"]
    pairs = [(v[14], v[15]) for v in by_day.values() if 14 in v and 15 in v]
    if pairs:
        lifts = [b - a for a, b in pairs]
        print(f"  n={len(pairs)}  med h14={median([p[0] for p in pairs]):.0f}  med h15={median([p[1] for p in pairs]):.0f}  med lift={median(lifts):+.0f}")

    # cluster ago 17-19
    print("\n--- h15 fechas sum>=850 ---")
    gen_days = sorted(set(r["day"] for r in h15 if r["gen"]))
    print(f"  días generosos h15: {len(gen_days)} / {len(set(r['day'] for r in h15))} días")
    for r in sorted(h15, key=lambda x: -x["sum"])[:8]:
        print(f"    {r['tag']}  sum={r['sum']}  mean={r['mean']:.1f}  nG={r['nG']}")

    # bloque 40-59 vs 0-39
    print("\n--- h15 curva intra-hora (aprox por min último G) ---")
    late_high = 0
    for tag in cinta.orden:
        if not tag.lower().startswith("h15-"):
            continue
        h = cinta.get(tag)
        tiros = [t for t in (h.tiros_nucleo or []) if t.color == "G" and t.lumen]
        if len(tiros) < 3:
            continue
        sg = sum(t.lumen for t in tiros)
        early = sum(t.lumen for t in tiros if t.m0 <= 29)
        late = sg - early
        if late > early * 1.2:
            late_high += 1
    print(f"  horas con más luz en 30-59: {late_high}/{len(h15)} ({100*late_high/max(1,len(h15)):.0f}%)")


if __name__ == "__main__":
    main()
