# -*- coding: utf-8 -*-
"""Lab perfil intra-hora — G temprano vs tardio vs cola wrap 58-03."""
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median, mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.lectores import cargar_ingesta, arranque_proxima

EARLY = (0, 9)   # min 0-9
LATE = (50, 59)  # min 50-59
WRAP = "wrap"    # G que cae en cruce hora


def perfil_hora(h):
    gs = [t for t in (h.tiros_nucleo or []) if t.color == "G" and t.lumen]
    if not gs:
        return None
    sg = sum(t.lumen for t in gs)
    mins = [t.m0 for t in gs]
    first_m = min(mins)
    last_m = max(t.m1 for t in gs)
    early = [t for t in gs if t.m0 <= 9]
    late = [t for t in gs if t.m0 >= 50]
    mid = [t for t in gs if 10 <= t.m0 <= 49]
    # G con tramo en 58-59 o arranque muy temprano (m0<=3 con L wrap previo — proxy: m0<=3)
    ultra_early = [t for t in gs if t.m0 <= 3]
    ultra_late = [t for t in gs if t.m0 >= 58 or t.m1 >= 58]
    return {
        "tag": h.tag.lower(),
        "hod": int(h.tag.split("-")[0][1:]),
        "nG": len(gs),
        "sum": sg,
        "mean": sg / len(gs),
        "first_m": first_m,
        "last_m": last_m,
        "pct_early": 100 * len(early) / len(gs),
        "pct_late": 100 * len(late) / len(gs),
        "sum_early": sum(t.lumen for t in early),
        "sum_late": sum(t.lumen for t in late),
        "sum_mid": sum(t.lumen for t in mid),
        "n_ultra_early": len(ultra_early),
        "n_ultra_late": len(ultra_late),
        "sin_early": len(early) == 0,
        "mostly_late": len(late) > len(early) * 1.5 and len(late) >= 2,
        "mostly_early": len(early) > len(late) * 1.5 and len(early) >= 2,
    }


def main():
    cinta, _, _ = cargar_ingesta("")
    perfiles = []
    for tag in cinta.orden:
        p = perfil_hora(cinta.get(tag))
        if p:
            perfiles.append(p)

    print(f"=== PERFIL INTRA-HORA · {len(perfiles)} h ===\n")

    # Global
    sin_early = [p for p in perfiles if p["sin_early"]]
    mostly_late = [p for p in perfiles if p["mostly_late"]]
    mostly_early = [p for p in perfiles if p["mostly_early"]]
    print("--- Global ---")
    print(f"  sin G en min 0-9: {len(sin_early)}/{len(perfiles)} ({100*len(sin_early)/len(perfiles):.0f}%)")
    print(f"  perfil late-heavy (50-59): {len(mostly_late)} ({100*len(mostly_late)/len(perfiles):.0f}%)")
    print(f"  perfil early-heavy (0-9): {len(mostly_early)} ({100*len(mostly_early)/len(perfiles):.0f}%)")
    print(f"  med first G min: {median(p['first_m'] for p in perfiles):.0f}")
    print(f"  med last G min: {median(p['last_m'] for p in perfiles):.0f}")
    print()

    # By hod
    by_hod = defaultdict(list)
    for p in perfiles:
        by_hod[p["hod"]].append(p)

    print("--- Por hod: sin G 0-9 · late-heavy · med first_m ---")
    ranked_sin = sorted(by_hod.items(), key=lambda x: -sum(1 for p in x[1] if p["sin_early"]) / len(x[1]))
    for hod, xs in ranked_sin[:8]:
        n = len(xs)
        se = sum(1 for p in xs if p["sin_early"])
        lh = sum(1 for p in xs if p["mostly_late"])
        fm = median(p["first_m"] for p in xs)
        print(f"  h{hod:02d}  sin_early={100*se/n:.0f}%  late_heavy={100*lh/n:.0f}%  med_first_m={fm:.0f}  n={n}")

    print("\n--- Por hod: early-heavy (mas G al abrir) ---")
    ranked_early = sorted(by_hod.items(), key=lambda x: -sum(1 for p in x[1] if p["mostly_early"]) / len(x[1]))
    for hod, xs in ranked_early[:8]:
        n = len(xs)
        eh = sum(1 for p in xs if p["mostly_early"])
        if eh == 0:
            continue
        print(f"  h{hod:02d}  early_heavy={100*eh/n:.0f}%  med_first_m={median(p['first_m'] for p in xs):.0f}  n={n}")

    # Ultra late 58+ vs ultra early 0-3
    print("\n--- Luz en cola (m0>=58 o m1>=58) vs apertura (m0<=3) ---")
    has_ul = [p for p in perfiles if p["n_ultra_late"] > 0]
    has_ue = [p for p in perfiles if p["n_ultra_early"] > 0]
    print(f"  horas con G en 58+: {len(has_ul)}/{len(perfiles)} ({100*len(has_ul)/len(perfiles):.0f}%)")
    print(f"  horas con G en 0-3: {len(has_ue)}/{len(perfiles)} ({100*len(has_ue)/len(perfiles):.0f}%)")
    both = [p for p in perfiles if p["n_ultra_late"] > 0 and p["n_ultra_early"] > 0]
    neither = [p for p in perfiles if p["n_ultra_late"] == 0 and p["n_ultra_early"] == 0]
    print(f"  ambos (cola Y apertura): {len(both)} ({100*len(both)/len(perfiles):.0f}%)")
    print(f"  ninguno: {len(neither)} ({100*len(neither)/len(perfiles):.0f}%)")

    # Cross-hour wrap: last tiro of hour N and first G of hour N+1
    print("\n--- CRUCE hora: ultimo tiro hN -> primer G h(N+1) ---")
    wrap_g_first = 0
    wrap_g_late_prev = 0
    first_g_mins = []
    gap_cases = []
    n_pairs = 0
    for i, tag in enumerate(cinta.orden):
        if i + 1 >= len(cinta.orden):
            break
        tag2 = cinta.orden[i + 1]
        # same day consecutive hod?
        h1 = cinta.get(tag)
        h2 = cinta.get(tag2)
        hod1 = int(tag.split("-")[0][1:])
        hod2 = int(tag2.split("-")[0][1:])
        day1 = tag.split("-")[1]
        day2 = tag2.split("-")[1]
        if hod2 != (hod1 + 1) % 24:
            continue
        if day1 != day2 and not (hod1 == 23 and hod2 == 0):
            continue
        n_pairs += 1
        tiros1 = h1.tiros_nucleo or []
        gs2 = [t for t in (h2.tiros_nucleo or []) if t.color == "G" and t.lumen]
        if not gs2:
            continue
        first_g = min(gs2, key=lambda t: t.m0)
        first_g_mins.append(first_g.m0)
        if first_g.m0 <= 3:
            wrap_g_first += 1
        if tiros1:
            last = tiros1[-1]
            if last.m1 >= 58 or last.m0 >= 58:
                wrap_g_late_prev += 1
                if first_g.m0 <= 5:
                    gap_cases.append((tag, tag2, last.m0, last.m1, first_g.m0, first_g.lumen))

    print(f"  pares consecutivos mismo dia: {n_pairs}")
    print(f"  1er G h(N+1) en min 0-3: {wrap_g_first} ({100*wrap_g_first/max(1,len(first_g_mins)):.0f}% de horas con G)")
    print(f"  ultimo tiro hN en 58+: {wrap_g_late_prev}")
    print(f"  secuencia cola 58+ -> 1er G <=5: {len(gap_cases)} casos")
    if first_g_mins:
        print(f"  med min 1er G: {median(first_g_mins):.0f}  p25={sorted(first_g_mins)[len(first_g_mins)//4]}")

    # Correlacion sin_early vs sum
    print("\n--- sin G 0-9 vs sum total ---")
    with_e = [p["sum"] for p in perfiles if not p["sin_early"]]
    without_e = [p["sum"] for p in perfiles if p["sin_early"]]
    print(f"  con G 0-9: med sum={median(with_e):.0f}  n={len(with_e)}")
    print(f"  sin G 0-9: med sum={median(without_e):.0f}  n={len(without_e)}")

    # late-heavy vs sum
    print("\n--- late-heavy vs early-heavy (sum) ---")
    lh = [p["sum"] for p in perfiles if p["mostly_late"]]
    eh = [p["sum"] for p in perfiles if p["mostly_early"]]
    if lh:
        print(f"  late-heavy med sum={median(lh):.0f} n={len(lh)}")
    if eh:
        print(f"  early-heavy med sum={median(eh):.0f} n={len(eh)}")

    # Costura link: h14 sin early -> h15 lift?
    print("\n--- COSTURA: h14 sin G 0-9 -> lift h15 ---")
    by_day = defaultdict(dict)
    for p in perfiles:
        by_day[p["tag"].split("-")[1]][p["hod"]] = p
    lifts_se = []
    lifts_con = []
    for day, d in by_day.items():
        if 14 not in d or 15 not in d:
            continue
        lift = d[15]["sum"] - d[14]["sum"]
        if d[14]["sin_early"]:
            lifts_se.append(lift)
        else:
            lifts_con.append(lift)
    if lifts_se:
        print(f"  h14 sin G 0-9 -> lift h15 med={median(lifts_se):+.0f} (n={len(lifts_se)})")
    if lifts_con:
        print(f"  h14 con G 0-9 -> lift h15 med={median(lifts_con):+.0f} (n={len(lifts_con)})")

    # DOW effect on first_m
    print("\n--- med first_m por hod (apertura tardia?) ---")
    for hod in [14, 15, 8, 9, 0, 1, 22, 23]:
        if hod in by_hod:
            xs = by_hod[hod]
            print(f"  h{hod:02d}  first_m med={median(p['first_m'] for p in xs):.0f}  sin_early={100*sum(1 for p in xs if p['sin_early'])/len(xs):.0f}%")


if __name__ == "__main__":
    main()
