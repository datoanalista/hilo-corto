# -*- coding: utf-8 -*-
"""Matriz hod x franja x banda para mapa UI."""
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.lectores import cargar_ingesta

SUM_APAG = 450
SUM_NORM = 600
SUM_FUERTE = 850
SUM_MUY = 1100
SUM_SN = 1600
MEAN_APAG = 42

FRANJAS = [
    ("madrugada", range(0, 6)),
    ("manana", range(6, 12)),
    ("mediodia", range(12, 18)),
    ("noche", range(18, 24)),
]

BANDAS = [
    ("muy_apag", lambda s, m: s < SUM_APAG or m < MEAN_APAG),
    ("opaco", lambda s, m: SUM_APAG <= s < SUM_NORM and m >= MEAN_APAG),
    ("normal", lambda s, m: SUM_NORM <= s < SUM_FUERTE),
    ("fuerte", lambda s, m: SUM_FUERTE <= s < SUM_MUY),
    ("muy_fuerte", lambda s, m: SUM_MUY <= s < SUM_SN),
    ("sn", lambda s, m: s >= SUM_SN),
]


def band(s, m):
    for name, fn in BANDAS:
        if fn(s, m):
            return name
    return "?"


def franja(h):
    for name, hrs in FRANJAS:
        if h in hrs:
            return name
    return "?"


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
        rows.append({
            "hod": hod,
            "fr": franja(hod),
            "sum": sg,
            "mean": mg,
            "band": band(sg, mg),
            "gen": sg >= SUM_FUERTE,
            "op": sg < SUM_APAG or mg < MEAN_APAG,
        })

    n = len(rows)
    print("=== MAPA: %d horas ===\n" % n)

    # franja x banda (%)
    print("--- FRANJA x BANDA (% horas) ---")
    hdr = [b[0] for b in BANDAS]
    print("%-10s" % "franja", " ".join("%8s" % x[:4] for x in hdr), " med_sum P_gen")
    for fname, _ in FRANJAS:
        xs = [r for r in rows if r["fr"] == fname]
        if not xs:
            continue
        pcts = []
        for bname, _ in BANDAS:
            pcts.append(100 * sum(1 for x in xs if x["band"] == bname) / len(xs))
        print("%-10s" % fname, " ".join("%7.0f%%" % p for p in pcts),
              "%4.0f" % median(x["sum"] for x in xs),
              "%4.0f%%" % (100 * sum(1 for x in xs if x["gen"]) / len(xs)))

    # hod heat - med sum + banda moda
    print("\n--- HOD (med sum · banda moda · P_gen) ---")
    by_h = defaultdict(list)
    for r in rows:
        by_h[r["hod"]].append(r)
    for hod in range(24):
        xs = by_h.get(hod, [])
        if not xs:
            continue
        bands = defaultdict(int)
        for x in xs:
            bands[x["band"]] += 1
        moda = max(bands.items(), key=lambda z: z[1])[0]
        print(" h%02d %s %3d med=%4.0f P_gen=%2d%% P_op=%2d%% moda=%s" % (
            hod, franja(hod)[:3], len(xs), median(x["sum"] for x in xs),
            round(100 * sum(1 for x in xs if x["gen"]) / len(xs)),
            round(100 * sum(1 for x in xs if x["op"]) / len(xs)),
            moda))

    # matriz compacta hod x franja solo P_gen (for UI grid 6x4 blocks)
    print("\n--- GRILLA P_gen hod dentro de franja (referencia) ---")
    for fname, hrs in FRANJAS:
        line = ["%s:" % fname]
        for hod in hrs:
            xs = by_h.get(hod, [])
            if xs:
                pg = round(100 * sum(1 for x in xs if x["gen"]) / len(xs))
                line.append("h%02d=%d%%" % (hod, pg))
        print(" ", " ".join(line))

    # contraste dia generoso vs resto por franja
    print("\n--- CONTRASTE (sim: top/bottom 25%% tot dia) ---")
    by_day = defaultdict(list)
    for tag in cinta.orden:
        h = cinta.get(tag)
        tiros = [t for t in (h.tiros_nucleo or []) if t.color == "G" and t.lumen]
        if not tiros:
            continue
        lum = [t.lumen for t in tiros]
        sg = sum(lum)
        day = tag.split("-")[1]
        by_day[day].append(sg)
    day_tot = {d: sum(v) for d, v in by_day.items()}
    sorted_days = sorted(day_tot.items(), key=lambda x: -x[1])
    n_d = len(sorted_days)
    bright = set(d for d, _ in sorted_days[: max(1, n_d // 4)])
    dark = set(d for d, _ in sorted_days[-max(1, n_d // 4):])

    def prof(days_set):
        out = {}
        for fname, hrs in FRANJAS:
            xs = []
            for tag in cinta.orden:
                if tag.split("-")[1] not in days_set:
                    continue
                hod = int(tag.split("-")[0][1:])
                if hod not in hrs:
                    continue
                h = cinta.get(tag)
                tiros = [t for t in (h.tiros_nucleo or []) if t.color == "G" and t.lumen]
                if tiros:
                    xs.append(sum(t.lumen for t in tiros))
            out[fname] = median(xs) if xs else 0
        return out

    pb = prof(bright)
    pd = prof(dark)
    print("  franja     brill med  oscuro med  delta")
    for fname, _ in FRANJAS:
        print("  %-10s %6.0f    %6.0f      %+4.0f" % (
            fname, pb[fname], pd[fname], pb[fname] - pd[fname]))

    print("\n=== FIN ===")


if __name__ == "__main__":
    main()
