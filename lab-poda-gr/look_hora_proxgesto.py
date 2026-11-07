# -*- coding: utf-8 -*-
"""
LOOK: ¿el gesto ya visto mueve el ESPERADO del siguiente?
No tip. No 12+9 como ficha. Cero cable.
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

from core_ae import HOLDOUT, load_horas_y_cinta, split_holdout
from look_hora_secuencia import ORDEN, cab, frase_hora, tok

OUT = LAB / "reports" / "LOOK_HORA_PROXGESTO.txt"
NOMBRE = {
    "T": "tren",
    "C": "casi",
    "k": "corto",
    "m": "medio",
    "L": "cola",
    "S": "sequía",
}


def top3(c: Counter, n: int) -> str:
    if n <= 0:
        return "—"
    parts = []
    for a, k in c.most_common(3):
        parts.append(f"{NOMBRE[a]} {k}/{n}")
    return "  ".join(parts)


def main() -> None:
    horas, _ = load_horas_y_cinta()
    train, _ = split_holdout(horas, HOLDOUT)
    docs = []
    for h in train:
        d = frase_hora(h)
        if d and len(d["pasos"]) >= 2:
            docs.append(d)

    pares = []
    trigramas = []
    rs_after = defaultdict(list)
    for d in docs:
        ats = d["atoms"]
        rs = [p["r"] for p in d["pasos"]]
        for i in range(len(ats) - 1):
            pares.append((ats[i], ats[i + 1], rs[i + 1], d, i))
            rs_after[ats[i]].append(rs[i + 1])
        for i in range(len(ats) - 2):
            trigramas.append((ats[i], ats[i + 1], ats[i + 2], rs[i + 2], d, i))

    base = Counter(b for _, b, _, _, _ in pares)
    n_par = len(pares)
    buf = []
    w = buf.append
    w("LOOK · ¿se puede estimar el próximo gesto?")
    w("Esperado ≠ preciso. No se corona el 12-luego-9.")
    w(f"train {len(docs)} h · {n_par} pares gesto→siguiente. Hold no se mezcla.")
    w("")
    w("Menú general (siguiente, sin mirar el anterior):")
    w(f"  {top3(base, n_par)}")
    w("  (si el anterior no aporta, el ‘esperado’ es siempre ese menú)")
    w("")

    w("════ 1. Un gesto → el siguiente ════")
    trans = {a: Counter() for a in ORDEN}
    for a, b, _, _, _ in pares:
        trans[a][b] += 1
    for a in ORDEN:
        n = sum(trans[a].values())
        if n < 20:
            continue
        ys = sorted(rs_after[a])
        med = ys[len(ys) // 2]
        gana = trans[a].most_common(1)[0][0]
        mismo = gana == base.most_common(1)[0][0]
        w(
            f"  tras {NOMBRE[a]:6}  n={n:4}  esperado {top3(trans[a], n)}  "
            f"R med del siguiente {med}  "
            f"{'mismo menú' if mismo else 'SE MUEVE: gana ' + NOMBRE[gana]}"
        )
    w("")

    w("════ 2. Dos gestos → el siguiente ════")
    w("Solo pares con ≥25 casos. ¿El segundo cambia lo que ya decía el último?")
    bi = defaultdict(Counter)
    bi_n = Counter()
    for a, b, c, _, _, _ in trigramas:
        bi[(a, b)][c] += 1
        bi_n[(a, b)] += 1
    filas = sorted(bi_n.items(), key=lambda kv: -kv[1])
    for (a, b), n in filas:
        if n < 25:
            continue
        gana_bi = bi[(a, b)].most_common(1)[0][0]
        gana_uno = trans[b].most_common(1)[0][0]
        w(
            f"  {NOMBRE[a]}+{NOMBRE[b]:6}  n={n:4}  esperado {top3(bi[(a, b)], n)}  "
            f"{'igual que tras el último' if gana_bi == gana_uno else 'cambia vs solo ' + NOMBRE[b] + ' → ' + NOMBRE[gana_bi]}"
        )
    w("")

    w("════ 3. Películas: tras cola, qué salió ════")
    w("No es el 12. Es ‘después de un hueco largo (9–15 R)’.")
    n = 0
    for d in docs:
        for i, p in enumerate(d["pasos"][:-1]):
            if p["atom"] != "L":
                continue
            nxt = d["pasos"][i + 1]
            w(
                f"  {d['tag']:<12} {tok(p)}  →  {tok(nxt)}   "
                f"{NOMBRE[p['atom']]} luego {NOMBRE[nxt['atom']]}"
            )
            n += 1
            if n >= 16:
                break
        if n >= 16:
            break
    w("")

    w("════ 4. Películas: dos colas seguidas (la forma del 12+9) ════")
    n = 0
    hay = sum(
        1
        for d in docs
        for i in range(len(d["atoms"]) - 2)
        if d["atoms"][i] == "L" and d["atoms"][i + 1] == "L"
    )
    for d in docs:
        ats = d["atoms"]
        for i in range(len(ats) - 2):
            if ats[i] == "L" and ats[i + 1] == "L":
                nxt = d["pasos"][i + 2]
                w(
                    f"  {d['tag']:<12} {tok(d['pasos'][i])}  {tok(d['pasos'][i+1])}  →  {tok(nxt)}"
                )
                n += 1
                if n >= 12:
                    break
        if n >= 12:
            break
    w(f"  (en el train hay {hay} veces L+L con un gesto después; arriba van las primeras tiras)")
    w("")

    w("════ 5. Películas: tras sequía ════")
    n = 0
    for d in docs:
        for i, p in enumerate(d["pasos"][:-1]):
            if p["atom"] != "S":
                continue
            nxt = d["pasos"][i + 1]
            w(
                f"  {d['tag']:<12} {tok(p)}  →  {tok(nxt)}   "
                f"luego {NOMBRE[nxt['atom']]}"
            )
            n += 1
            if n >= 12:
                break
        if n >= 12:
            break
    w("")

    w("════ 6. Hueco ABIERTO (vas 9 R y todavía no cerró) ════")
    w("Eso ya ES el gesto de ahora, no el próximo.")
    w("Si el anterior cerró cola/sequía y este ya lleva 9+ R,")
    w("la pregunta es si ESTE se queda cola o se va a sequía.")
    # dado anterior L/S/k/m y abierto ≥9 (el siguiente r ≥ 9)
    ab = defaultdict(Counter)
    for a, b, r, d, i in pares:
        if r >= 9:
            grosor = "S" if r >= 16 else "L"
            ab[a][grosor] += 1
    w("  Cuando el siguiente YA midió ≥9 R, ¿cerró cola o sequía?")
    for a in ORDEN:
        n = sum(ab[a].values())
        if n < 15:
            continue
        w(f"  anterior {NOMBRE[a]:6}  n={n:4}  {top3(ab[a], n)}")
    w("")
    w("Lectura:")
    w("  El menú del siguiente casi no se mueve: gana corto, luego medio.")
    w("  Tras cola/sequía el siguiente NO copia el largo (elástico).")
    w("  Dos colas seguidas no mandan una tercera.")
    w("  Un tren no prohíbe otro; tampoco lo promete.")
    w("  Esperado = ‘lo más frecuente del menú’, no un minuto.")
    OUT.write_text("\n".join(buf) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
