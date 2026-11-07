# -*- coding: utf-8 -*-
"""
LOOK: ¿el miss del tip/pools es el gesto (elástico)?
LC-01 = lo que ve Next / zona Pool 7.
Cero tip nuevo. Cero cable. No coronar 12+9.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
AE = ROOT / "lab-apostador-experto"
GEXP = ROOT / "lab-g-explosion"
sys.path.insert(0, str(GEXP))
sys.path.insert(0, str(AE))
sys.path.insert(0, str(ROOT))

from core_ae import HOLDOUT, dist_anillo, load_horas_y_cinta, p30, split_holdout
from look_hora_secuencia import ORDEN, atom_r, es_nucleo, frase_hora, tok

OUT = LAB / "reports" / "LOOK_HORA_POOLGESTO.txt"
NOMBRE = {
    "T": "tren",
    "C": "casi",
    "k": "corto",
    "m": "medio",
    "L": "cola",
    "S": "sequía",
}


def tip_lc(luces: list[int]) -> tuple[int | None, int]:
    xs = sorted({int(m) % 60 for m in luces})
    if not xs:
        return None, 5
    T = xs[-1]
    if T >= 59:
        return None, 5
    gaps = [xs[i] - xs[i - 1] for i in range(1, len(xs))]
    gap = max(1, int(round(p30(gaps, 5.0))))
    return min(59, T + gap), gap


def clase(tip: int, real: int) -> str:
    d = tip - real
    if abs(d) <= 1:
        return "cae"
    if d > 1:
        return "largo"  # se pasó: tip después de la G
    return "corto"  # se quedó corto: tip antes de la G


def main() -> None:
    horas, _ = load_horas_y_cinta()
    train, _ = split_holdout(horas, HOLDOUT)
    rows = []
    for h in train:
        d = frase_hora(h)
        if not d or len(d["pasos"]) < 1:
            continue
        gs = [t for t in (h.tiros or []) if es_nucleo(t)]
        mins = [int(t.m0) % 60 for t in gs]
        for i, p in enumerate(d["pasos"]):
            # p cierra en la G i+1; tip se arma con luces hasta ESA G
            luces = mins[: i + 2]
            if i + 2 >= len(mins):
                continue
            real = mins[i + 2] if i + 1 < len(d["pasos"]) else None
            # el siguiente gesto es pasos[i+1]; real = G que cierra ese gesto
            if i + 1 >= len(d["pasos"]):
                continue
            nxt = d["pasos"][i + 1]
            real = int(nxt["m1"]) % 60
            tip, gap = tip_lc(luces)
            if tip is None:
                continue
            rows.append(
                {
                    "tag": d["tag"],
                    "prev": p["atom"],
                    "nxt": nxt["atom"],
                    "tip": tip,
                    "real": real,
                    "gap": gap,
                    "cls": clase(tip, real),
                    "p30_largo": gap >= 9,
                    "prev_largo": p["atom"] in ("L", "S"),
                    "tok": tok(p),
                    "tok2": tok(nxt),
                    "d": d,
                }
            )

    buf = []
    w = buf.append
    w("LOOK · tip/pools × gesto")
    w("LC-01 = Next / zona Pool 7: última G + p30 de los huecos YA vistos.")
    w("cae = tip a ≤1 min de la G. largo = el tip se pasó (G antes). corto = G después.")
    w(f"train {len(rows)} tips con gesto previo y G siguiente. Hold no se mezcla.")
    w("")

    def bloque(titulo, xs):
        n = len(xs)
        if n < 8:
            return
        c = Counter(x["cls"] for x in xs)
        w(
            f"  {titulo:<28} n={n:4}  "
            f"cae {c['cae']}/{n}  "
            f"se pasó {c['largo']}/{n}  "
            f"se quedó {c['corto']}/{n}"
        )

    w("════ 1. Tras CADA gesto, qué hizo LC-01 ════")
    for a in ORDEN:
        bloque(f"tras {NOMBRE[a]}", [x for x in rows if x["prev"] == a])
    w("")
    w("════ 2. El cruce (no es el 12+9) ════")
    bloque("previo largo (cola/sequía)", [x for x in rows if x["prev_largo"]])
    bloque("previo no largo", [x for x in rows if not x["prev_largo"]])
    bloque("p30 todavía ≥9", [x for x in rows if x["p30_largo"]])
    bloque("p30 ya corto (<9)", [x for x in rows if not x["p30_largo"]])
    bloque("largo Y p30≥9", [x for x in rows if x["prev_largo"] and x["p30_largo"]])
    bloque("largo pero p30<9", [x for x in rows if x["prev_largo"] and not x["p30_largo"]])
    w("")
    w("════ 3. Películas: tras cola, tip vs G ════")
    n = 0
    for x in rows:
        if x["prev"] != "L":
            continue
        w(
            f"  {x['tag']:<12} {x['tok']} → {x['tok2']}   "
            f"p30={x['gap']} tip {x['tip']:02d}  G {x['real']:02d}  {x['cls']}"
        )
        n += 1
        if n >= 16:
            break
    w("")
    w("════ 4. Películas: dos colas (forma 12+9) y el tip ════")
    n = 0
    hay = 0
    for h in train:
        d = frase_hora(h)
        if not d or len(d["pasos"]) < 3:
            continue
        gs = [t for t in (h.tiros or []) if es_nucleo(t)]
        mins = [int(t.m0) % 60 for t in gs]
        ats = d["atoms"]
        for i in range(len(ats) - 2):
            if ats[i] != "L" or ats[i + 1] != "L":
                continue
            hay += 1
            luces = mins[: i + 3]
            nxt = d["pasos"][i + 2]
            tip, gap = tip_lc(luces)
            if tip is None:
                continue
            real = int(nxt["m1"]) % 60
            w(
                f"  {d['tag']:<12} {tok(d['pasos'][i])} {tok(d['pasos'][i+1])} → {tok(nxt)}  "
                f"p30={gap} tip {tip:02d} G {real:02d}  {clase(tip, real)}"
            )
            n += 1
            if n >= 10:
                break
        if n >= 10:
            break
    w(f"  (L+L con siguiente: {hay} en train)")
    w("")
    w("Lectura:")
    w("  LC-01 recuerda el LARGO de los huecos ya vistos (p30).")
    w("  El próximo gesto no copia ese largo: suele ser corto.")
    w("  Ahí el tip se PASA: apunta lejos y la G ya cayó.")
    w("  Si el p30 ya era corto (la hora traía muchos k), no se pasa:")
    w("  el tip y la G corta coinciden.")
    w("  Los chips de pool son menú de la hora, no leen el gesto:")
    w("  la G corta cae ENTRE fichas → también se pasan de largo.")
    w("  Cruzar = no es un tip nuevo; es leer CUÁNDO el menú miente.")
    OUT.write_text("\n".join(buf) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
