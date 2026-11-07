# -*- coding: utf-8 -*-
"""Lab hora flaca — pocas G (nG=1,2,3)."""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
EXTRA = ROOT / "dashboard" / "extraccion" / "extraccion-en-vivo.txt"
OUT = LAB / "reports"
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(LAB))

from core_gc import load_horas  # noqa: E402

SUM_OP = 450
SUM_GEN = 850
SN = 1600


def main():
    horas = load_horas(EXTRA)
    horas_raw = []
    for h in horas:
        lum = [g.lumen for g in h.gs]
        sg = h.sum_g
        horas_raw.append({
            "tag": h.tag,
            "hod": h.hod,
            "day": h.tag.split("-")[1],
            "nG": h.n_g,
            "sum_g": sg,
            "mean_g": h.mean_g,
            "max_g": h.max_g,
            "is_op": sg < SUM_OP,
            "is_gen": sg >= SUM_GEN,
            "is_sn": sg >= SN,
            "n500": sum(1 for l in lum if l > 500),
            "gs": h.gs,
        })

    n = len(horas_raw)
    lines = [f"LAB HORA FLACA — {n} h con G+lumen\n"]

    cnt = Counter(h["nG"] for h in horas_raw)
    lines.append("== DISTRIBUCIÓN nG ==")
    for k in sorted(cnt.keys())[:15]:
        lines.append(f"  nG={k:2d}: {cnt[k]:4d} ({100*cnt[k]/n:.1f}%)")
    lines.append(f"  mediana nG={median(h['nG'] for h in horas_raw):.0f}")

    flaca1 = [h for h in horas_raw if h["nG"] == 1]
    flaca2 = [h for h in horas_raw if h["nG"] <= 2]
    flaca3 = [h for h in horas_raw if h["nG"] <= 3]
    lines.append(f"\n  nG=1: {len(flaca1)} ({100*len(flaca1)/n:.1f}%)")
    lines.append(f"  nG<=2: {len(flaca2)} ({100*len(flaca2)/n:.1f}%)")
    lines.append(f"  nG<=3: {len(flaca3)} ({100*len(flaca3)/n:.1f}%)")

    resto = [h for h in horas_raw if h["nG"] > 1]

    def med(xs, key):
        return median([x[key] for x in xs]) if xs else 0

    lines.append("\n== PERFIL nG=1 vs resto ==")
    lines.append(f"  sumG med: {med(flaca1, 'sum_g'):.0f} vs {med(resto, 'sum_g'):.0f}")
    lines.append(f"  meanG med: {med(flaca1, 'mean_g'):.0f} vs {med(resto, 'mean_g'):.0f}")
    lines.append(f"  maxG med: {med(flaca1, 'max_g'):.0f} vs {med(resto, 'max_g'):.0f}")
    lines.append(
        f"  P(opaca): {100*sum(h['is_op'] for h in flaca1)/len(flaca1):.0f}% "
        f"vs {100*sum(h['is_op'] for h in resto)/len(resto):.0f}%"
    )
    lines.append(
        f"  P(G>500): {100*sum(h['n500']>0 for h in flaca1)/len(flaca1):.0f}% "
        f"vs {100*sum(h['n500']>0 for h in resto)/len(resto):.0f}%"
    )

    lines.append("\n== PERFIL nG<=2 vs nG>=8 ==")
    gorda = [h for h in horas_raw if h["nG"] >= 8]
    lines.append(f"  sumG med: {med(flaca2, 'sum_g'):.0f} vs {med(gorda, 'sum_g'):.0f}")
    lines.append(
        f"  P(opaca): {100*sum(h['is_op'] for h in flaca2)/len(flaca2):.0f}% "
        f"vs {100*sum(h['is_op'] for h in gorda)/len(gorda):.0f}%"
    )

    lines.append("\n== nG=1 — minuto de la única G ==")
    mins1 = [h["gs"][0].m0 for h in flaca1]
    if mins1:
        lines.append(
            f"  med min={median(mins1):.0f} · bloque 0-19: "
            f"{100*sum(m<=19 for m in mins1)/len(mins1):.0f}% · "
            f"bloque 40-59: {100*sum(m>=40 for m in mins1)/len(mins1):.0f}%"
        )

    lines.append("\n== H+1 tras hora flaca ==")
    idx = {h["tag"]: i for i, h in enumerate(horas_raw)}
    for label, subset in [
        ("nG=1", flaca1),
        ("nG<=2", flaca2),
        ("nG<=3", flaca3),
        ("nG>=8", gorda),
    ]:
        lifts_sum = []
        lifts_nG = []
        for h in subset:
            i = idx[h["tag"]]
            if i + 1 >= len(horas_raw):
                continue
            nxt = horas_raw[i + 1]
            lifts_sum.append(nxt["sum_g"] - h["sum_g"])
            lifts_nG.append(nxt["nG"] - h["nG"])
        if lifts_sum:
            lines.append(
                f"  {label} -> H+1 lift sum med={median(lifts_sum):+.0f} · "
                f"lift nG med={median(lifts_nG):+.0f} n={len(lifts_sum)}"
            )

    lines.append("\n== MISMO DÍA ==")
    by_day = defaultdict(list)
    for h in horas_raw:
        by_day[h["day"]].append(h)
    dias_con_1g = sum(1 for hs in by_day.values() if any(x["nG"] == 1 for x in hs))
    lines.append(f"  días con al menos 1 hora nG=1: {dias_con_1g}/{len(by_day)}")
    # cluster: 2+ horas flacas seguidas mismo día
    cluster = 0
    for hs in by_day.values():
        hs.sort(key=lambda x: x["hod"])
        run = 0
        for h in hs:
            if h["nG"] <= 2:
                run += 1
                if run >= 2:
                    cluster += 1
                    break
            else:
                run = 0
    lines.append(f"  días con 2+ horas nG<=2: {cluster}")

    lines.append("\n== HOD P(nG=1) top ==")
    by_h = defaultdict(list)
    for h in horas_raw:
        by_h[h["hod"]].append(h["nG"] == 1)
    rows = [(100 * sum(v) / len(v), hod, len(v)) for hod, v in by_h.items() if len(v) >= 15]
    rows.sort(reverse=True)
    for p, hod, nn in rows[:6]:
        lines.append(f"  h{hod:02d}: {p:.1f}% (n={nn})")
    rows.sort()
    lines.append("  bottom:")
    for p, hod, nn in rows[:3]:
        lines.append(f"  h{hod:02d}: {p:.1f}% (n={nn})")
    base = 100 * len(flaca1) / n
    lines.append(f"  global: {base:.1f}%")

    lines.append("\n== EN VIVO: al min 20 con 0-1 G ==")
    total = 0
    early_sparse_op = 0
    early_sparse_gen = 0
    for h in horas_raw:
        g20 = [g for g in h["gs"] if g.m0 <= 19]
        if len(g20) > 1:
            continue
        total += 1
        if h["is_op"]:
            early_sparse_op += 1
        if h["is_gen"]:
            early_sparse_gen += 1
    if total:
        lines.append(f"  horas con <=1 G en 0-19: {total} ({100*total/n:.1f}%)")
        lines.append(f"  de esas, cierran opacas (sum<450): {100*early_sparse_op/total:.0f}%")
        lines.append(f"  de esas, cierran generosas (sum>=850): {100*early_sparse_gen/total:.0f}%")

    # nG=0 horas (sin G en núcleo pero con cinta)
    lines.append("\n== nG=0 (sin G en hora) ==")
    lines.append("  (load_horas filtra horas sin G — no medible aquí)")

    lines.append("\n== CENSO nG=1 (todas) ==")
    for h in sorted(flaca1, key=lambda x: -x["sum_g"])[:12]:
        m0 = h["gs"][0].m0
        lines.append(
            f"  {h['tag']} h{h['hod']:02d} min={m0} sum={h['sum_g']} "
            f"mean={h['mean_g']:.0f} max={h['max_g']}"
        )
    if len(flaca1) > 12:
        lines.append(f"  ... +{len(flaca1)-12} más")

    # veredicto
    p_op_flaca = 100 * sum(h["is_op"] for h in flaca1) / len(flaca1) if flaca1 else 0
    p_op_resto = 100 * sum(h["is_op"] for h in resto) / len(resto) if resto else 0
    lines.append("\n== VEREDICTO ==")
    lines.append(f"  nG=1 = {100*len(flaca1)/n:.1f}% horas · P(opaca)={p_op_flaca:.0f}% vs resto {p_op_resto:.0f}%")
    if total:
        lines.append(f"  señal temprana: <=1 G al min 20 -> {100*early_sparse_op/total:.0f}% opacas")
    lines.append("  1 sola G puede traer mucho lumen (outlier) — no confundir nG bajo con sumG bajo")
    lines.append("  H+1: ver lift — olor rebote posible tras hora muerta")
    lines.append("  VIVE=0 como cola; OLOR-VIVE para dashboard si se cablea")

    text = "\n".join(lines)
    out_path = OUT / "LAB_HORA_FLACA.txt"
    out_path.write_text(text + "\n", encoding="utf-8")
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))
    print(f"\n-> {out_path}")


if __name__ == "__main__":
    main()
