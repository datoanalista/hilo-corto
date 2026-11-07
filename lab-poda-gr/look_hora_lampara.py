# -*- coding: utf-8 -*-
"""
LOOK: lámpara sobre LC-01 (callar, no mover el tip).
Mismo número Next / Pool 7. Solo: ¿me siento o no?
Cero cable. Hold aparte. No 12+9 como ficha.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
AE = ROOT / "lab-apostador-experto"
GEXP = ROOT / "lab-g-explosion"
sys.path.insert(0, str(GEXP))
sys.path.insert(0, str(AE))
sys.path.insert(0, str(ROOT))

from core_ae import HOLDOUT, hit_banda, load_horas_y_cinta, split_holdout
from look_hora_poolgesto import clase, tip_lc
from look_hora_secuencia import es_nucleo, frase_hora, tok

OUT = LAB / "reports" / "LOOK_HORA_LAMPARA.txt"
NOMBRE = {
    "T": "tren",
    "C": "casi",
    "k": "corto",
    "m": "medio",
    "L": "cola",
    "S": "sequía",
}


def filas(horas):
    rows = []
    for h in horas:
        d = frase_hora(h)
        if not d or len(d["pasos"]) < 2:
            continue
        gs = [t for t in (h.tiros or []) if es_nucleo(t)]
        mins = [int(t.m0) % 60 for t in gs]
        for i, p in enumerate(d["pasos"][:-1]):
            nxt = d["pasos"][i + 1]
            luces = mins[: i + 2]
            tip, gap = tip_lc(luces)
            if tip is None:
                continue
            real = int(nxt["m1"]) % 60
            rows.append(
                {
                    "tag": d["tag"],
                    "prev": p["atom"],
                    "nxt": nxt["atom"],
                    "tip": tip,
                    "real": real,
                    "p30": gap,
                    "cls": clase(tip, real),
                    "hit": hit_banda(tip, real),
                    "tok": tok(p),
                    "tok2": tok(nxt),
                }
            )
    return rows


def lamp_p30(r, umbral=9):
    return r["p30"] >= umbral


def lamp_largo_y_p30(r, umbral=9):
    return r["prev"] in ("L", "S") and r["p30"] >= umbral


def lamp_prev_largo(r, _umbral=9):
    return r["prev"] in ("L", "S")


POLS = (
    ("siempre", "Siempre me siento (Pool 7 hoy)", lambda r: False),
    ("p30≥9", "Callo si p30≥9", lamp_p30),
    ("p30≥7", "Callo si p30≥7 (otro corte)", lambda r: lamp_p30(r, 7)),
    ("largo+p30≥9", "Callo si cola/sequía Y p30≥9", lamp_largo_y_p30),
    ("solo-largo", "Callo tras cola/sequía (sin mirar p30)", lamp_prev_largo),
)


def score(rows, calla):
    juega = [r for r in rows if not calla(r)]
    callados = [r for r in rows if calla(r)]
    n = len(juega)
    h = sum(1 for r in juega if r["hit"])
    ex = sum(1 for r in juega if r["tip"] == r["real"])
    # lo que se calló: ¿eran pases o aciertos?
    c_hit = sum(1 for r in callados if r["hit"])
    c_pas = sum(1 for r in callados if r["cls"] == "largo")
    por_h = defaultdict(list)
    for r in juega:
        por_h[r["tag"]].append(r["hit"])
    horas_ok = sum(1 for xs in por_h.values() if any(xs))
    return {
        "n": n,
        "calla": len(callados),
        "hit": h,
        "ex": ex,
        "c_hit": c_hit,
        "c_pas": c_pas,
        "horas": len(por_h),
        "horas_ok": horas_ok,
    }


def linea(nombre, s, n0):
    if s["n"] <= 0:
        return f"  {nombre:<16} n=0"
    return (
        f"  {nombre:<16} juega {s['n']:4}/{n0}  "
        f"calla {s['calla']:4}  "
        f"banda {s['hit']}/{s['n']}  "
        f"exacto {s['ex']}/{s['n']}  "
        f"horas con cobro {s['horas_ok']}/{s['horas']}  "
        f"de lo callado: se pasaba {s['c_pas']}/{s['calla']} · caía {s['c_hit']}/{s['calla']}"
    )


def bloque(titulo, rows, w):
    n0 = len(rows)
    w(f"════ {titulo}  ·  {n0} tips ════")
    for clave, _txt, fn in POLS:
        w(linea(clave, score(rows, fn), n0))
    w("")


def main() -> None:
    horas, _ = load_horas_y_cinta()
    train, hold = split_holdout(horas, HOLDOUT)
    rt = filas(train)
    rh = filas(hold)
    buf = []
    w = buf.append
    w("LOOK · lámpara: mismo tip LC-01, ¿me siento?")
    w("No se cambia el número. Callar ≠ tip nuevo.")
    w("Juez: banda d≤1 tip vs minuto de ESA G.")
    w("")
    bloque("TRAIN", rt, w)
    bloque("HOLD 72 h", rh, w)

    w("════ películas: lo que callaría p30≥9 (train, primeras tiras) ════")
    n = 0
    for r in rt:
        if r["p30"] < 9:
            continue
        w(
            f"  {r['tag']:<12} {r['tok']} → {r['tok2']}  "
            f"p30={r['p30']} tip {r['tip']:02d} G {r['real']:02d}  {r['cls']}"
        )
        n += 1
        if n >= 16:
            break
    w("")
    w("════ películas: p30≥9 y AUN ASÍ caía (la lámpara habría callado un cobro) ════")
    n = 0
    hay = 0
    for r in rt:
        if r["p30"] < 9 or not r["hit"]:
            continue
        hay += 1
        if n < 10:
            w(
                f"  {r['tag']:<12} {r['tok']} → {r['tok2']}  "
                f"p30={r['p30']} tip {r['tip']:02d} G {r['real']:02d}"
            )
            n += 1
    w(f"  (en train hay {hay} cobros que p30≥9 habría apagado)")
    w("")
    w("Lectura:")
    w("  Si lo callado es casi todo ‘se pasó’, la lámpara limpia.")
    w("  Si apaga muchos ‘cae’, está cortando cobros: no coronar.")
    w("  Hold manda para no sentar. Cero cable.")
    OUT.write_text("\n".join(buf) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
