# -*- coding: utf-8 -*-
"""
CIERRE: los dos olores de SUMA-R, película por película.
¿Aguantan una explicación, o eran cifra común / n chico?
Cero cable.
"""
from __future__ import annotations

import random
import sys
from collections import Counter
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))

from look_suma_r import (  # noqa: E402
    HOLD,
    NULA,
    SEED,
    DATA_DEFAULT,
    armar_horas,
    armar_vecinos,
    med,
    pct,
    permutar_firmas,
    vecinos,
    walk_total,
)

OUT = LAB / "reports" / "LOOK_SUMA_R_CIERRE.txt"


def corr(xs, ys):
    n = len(xs)
    if n < 3:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    return num / (dx * dy) if dx and dy else 0.0


def p_nula(xs, real):
    if not xs:
        return "—"
    ge = sum(1 for x in xs if x >= real - 1e-12)
    return f"p_nula={ge}/{len(xs)}"


def p_nula_le(xs, real):
    """cola izquierda: real tan chico como…"""
    if not xs:
        return "—"
    le = sum(1 for x in xs if x <= real + 1e-12)
    return f"p_izq={le}/{len(xs)}"


def main() -> None:
    horas = armar_horas(DATA_DEFAULT)
    armar_vecinos(horas)
    rng = random.Random(SEED)
    train, hold = horas[:-HOLD], horas[-HOLD:]
    mid = len(train) // 2
    a, b = train[:mid], train[mid:]

    buf = []
    w = buf.append
    w("CIERRE · SUMA-R  (primer hueco + total ±2)")
    w(f"cinta {DATA_DEFAULT.name}  {len(horas)} h  {horas[0].tag} → {horas[-1].tag}")
    w("Nula = barajar firmas; el reloj no se mueve.")
    w("")

    # ── 1. primer hueco ──────────────────────────────────────────
    w("════ 1 · primer hueco de horas pegadas ════")
    pares = []
    for i in range(len(horas) - 1):
        if not horas[i].huecos or not horas[i + 1].huecos:
            continue
        if (horas[i + 1].dt - horas[i].dt).total_seconds() > 3660:
            continue
        s0 = horas[i].huecos[0].suma
        s1 = horas[i + 1].huecos[0].suma
        n0 = horas[i].huecos[0].n_r
        n1 = horas[i + 1].huecos[0].n_r
        m0 = horas[i].huecos[0].m1  # minuto de la 1ª G que cierra el hueco
        m1 = horas[i + 1].huecos[0].m1
        pares.append((horas[i], horas[i + 1], s0, s1, n0, n1, m0, m1))

    eq = [(p, q, s0, s1) for p, q, s0, s1, *_ in pares if s0 == s1]
    eq0 = [x for x in eq if x[2] == 0]
    eqp = [x for x in eq if x[2] > 0]
    w(f"  pares civiles pegados: {len(pares)}")
    w(f"  Σ0==Σ1: {len(eq)}/{len(pares)}  {pct(len(eq), len(pares))}  "
      f"(ambos 0: {len(eq0)} · ambos >0: {len(eqp)})")

    eq_nr = sum(1 for row in pares if row[4] == row[5])
    w(f"  n_R0==n_R1: {eq_nr}/{len(pares)}  {pct(eq_nr, len(pares))}")

    # minuto de la 1ª G
    eq_m = sum(1 for row in pares if row[6] == row[7])
    w(f"  1ª G al mismo minuto: {eq_m}/{len(pares)}  {pct(eq_m, len(pares))}")
    w(f"  corr(Σ primer, minuto 1ª G) = "
      f"{corr([h.huecos[0].suma for h in horas if h.huecos], [h.huecos[0].m1 for h in horas if h.huecos]):+.3f}")
    w(f"  corr(Σ primer, n_R primer) = "
      f"{corr([h.huecos[0].suma for h in horas if h.huecos], [h.huecos[0].n_r for h in horas if h.huecos]):+.3f}")

    # nulas
    nula_eq, nula_eq0, nula_eqp, nula_nr = [], [], [], []
    for _ in range(NULA):
        sh = permutar_firmas(horas, rng)
        ps = []
        for i in range(len(sh) - 1):
            if not sh[i].huecos or not sh[i + 1].huecos:
                continue
            if (sh[i + 1].dt - sh[i].dt).total_seconds() > 3660:
                continue
            ps.append((sh[i].huecos[0].suma, sh[i + 1].huecos[0].suma,
                       sh[i].huecos[0].n_r, sh[i + 1].huecos[0].n_r))
        n = len(ps) or 1
        nula_eq.append(sum(1 for a, b, *_ in ps if a == b) / n)
        nula_eq0.append(sum(1 for a, b, *_ in ps if a == b == 0) / n)
        nula_eqp.append(sum(1 for a, b, *_ in ps if a == b > 0) / n)
        nula_nr.append(sum(1 for a, b, c, d in ps if c == d) / n)

    real_eq = len(eq) / max(1, len(pares))
    real_0 = len(eq0) / max(1, len(pares))
    real_p = len(eqp) / max(1, len(pares))
    real_nr = eq_nr / max(1, len(pares))
    w(f"  nula Σ==     med {100*med(nula_eq):.1f}%  {p_nula_le(nula_eq, real_eq)}")
    w(f"  nula ambos 0 med {100*med(nula_eq0):.1f}%  {p_nula_le(nula_eq0, real_0)}")
    w(f"  nula ambos>0 med {100*med(nula_eqp):.1f}%  {p_nula_le(nula_eqp, real_p)}")
    w(f"  nula n_R==   med {100*med(nula_nr):.1f}%  {p_nula_le(nula_nr, real_nr)}")
    w("")

    w("  cortes")
    for nom, xs in (("1ª mitad", a), ("2ª mitad", b), ("hold", hold)):
        ps = []
        for i in range(len(xs) - 1):
            if not xs[i].huecos or not xs[i + 1].huecos:
                continue
            if (xs[i + 1].dt - xs[i].dt).total_seconds() > 3660:
                continue
            ps.append((xs[i].huecos[0].suma, xs[i + 1].huecos[0].suma))
        e = sum(1 for x, y in ps if x == y)
        e0 = sum(1 for x, y in ps if x == y == 0)
        ep = sum(1 for x, y in ps if x == y > 0)
        w(f"    {nom:<10} == {e}/{len(ps)}  {pct(e, len(ps))}  "
          f"(0=0: {e0} · >0: {ep})")
    w("")

    w("  las 10 películas donde Σ0==Σ1")
    for p, q, s0, s1 in eq:
        w(
            f"    {p.tag} Σ={s0:<3} nR={p.huecos[0].n_r} @{p.huecos[0].m0:02d}→{p.huecos[0].m1:02d}"
            f"   {q.tag} Σ={s1:<3} nR={q.huecos[0].n_r} @{q.huecos[0].m0:02d}→{q.huecos[0].m1:02d}"
            f"   {'TREN' if s0 == 0 else 'masa'}"
        )
    w("")

    # ¿complemento? suma de los dos primeros
    sums = [row[2] + row[3] for row in pares]
    diffs = [abs(row[2] - row[3]) for row in pares]
    w(f"  Σ0+Σ1  p50={med([float(s) for s in sums]):.0f}  "
      f"min={min(sums)} max={max(sums)}  (no es cupo fijo)")
    w(f"  |Σ0-Σ1| p50={med([float(d) for d in diffs]):.0f}")
    # cubetas de diferencia
    cub = Counter()
    for d in diffs:
        if d == 0:
            cub["0"] += 1
        elif d <= 2:
            cub["1-2"] += 1
        elif d <= 5:
            cub["3-5"] += 1
        elif d <= 10:
            cub["6-10"] += 1
        else:
            cub[">10"] += 1
    w("  |Σ0-Σ1| cubetas: " + "  ".join(f"{k}={cub[k]}" for k in ("0", "1-2", "3-5", "6-10", ">10")))
    w("")

    # ── 2. total ±2 ──────────────────────────────────────────────
    w("════ 2 · total R de la hora a ±2 h ════")
    # pares no dirigidos únicos
    vistos = set()
    pares2 = []
    for i, h in enumerate(horas):
        for j, lag in vecinos(horas, i):
            if lag != 2:
                continue
            key = tuple(sorted((h.tag, horas[j].tag)))
            if key in vistos:
                continue
            vistos.add(key)
            if h.total == horas[j].total:
                pares2.append((h, horas[j]))
    w(f"  pares únicos H / H+2 con mismo total: {len(pares2)}")

    bag_tot = Counter(h.total for h in horas)
    w("  totales más frecuentes de la cinta: " +
      ", ".join(f"{t}×{c}" for t, c in bag_tot.most_common(8)))
    w("")

    w("  películas (todas)")
    for h, g in pares2:
        w(
            f"    {h.tag} tot={h.total} nR={h.n_r} nG={h.n_g}  "
            f"huecos[{' '.join(str(x.suma) for x in h.huecos)}]"
        )
        w(
            f"    {g.tag} tot={g.total} nR={g.n_r} nG={g.n_g}  "
            f"huecos[{' '.join(str(x.suma) for x in g.huecos)}]"
        )
        w(f"      bag de ese total en 288 h: {bag_tot[h.total]} veces"
          f"  · nR {'igual' if h.n_r == g.n_r else 'distinto'}"
          f"  · nG {'igual' if h.n_g == g.n_g else 'distinto'}"
          f"  · 1er hueco {h.huecos[0].suma if h.huecos else '—'} vs "
          f"{g.huecos[0].suma if g.huecos else '—'}")
        w("")

    # ¿el total es n_R con otro nombre?
    w(f"  corr(total, n_R hora) = {corr([h.total for h in horas], [h.n_r for h in horas]):+.3f}")
    w(f"  corr(total, n_G hora) = {corr([h.total for h in horas], [h.n_g for h in horas]):+.3f}")
    eq_nr2 = sum(1 for h, g in pares2 if h.n_r == g.n_r)
    eq_ng2 = sum(1 for h, g in pares2 if h.n_g == g.n_g)
    w(f"  de esos pares: n_R igual {eq_nr2}/{len(pares2)}  n_G igual {eq_ng2}/{len(pares2)}")
    w("")

    # ¿+2 es especial vs +1 +3 +4 +5 en PARES ÚNICOS?
    w("  mismos totales, pares únicos, por lag (vs nula)")
    for lag in (1, 2, 3, 4, 5):
        seen = set()
        hit = n = 0
        for i, h in enumerate(horas):
            for j, k in vecinos(horas, i):
                if k != lag:
                    continue
                key = tuple(sorted((h.tag, horas[j].tag)))
                if key in seen:
                    continue
                seen.add(key)
                n += 1
                if h.total == horas[j].total:
                    hit += 1
        nula = []
        for _ in range(NULA):
            sh = permutar_firmas(horas, rng)
            se = set()
            hi = nn = 0
            for i, h in enumerate(sh):
                for j, k in vecinos(sh, i):
                    if k != lag:
                        continue
                    key = (min(i, j), max(i, j))
                    if key in se:
                        continue
                    se.add(key)
                    nn += 1
                    if h.total == sh[j].total:
                        hi += 1
            nula.append(hi / nn if nn else 0)
        real = hit / n if n else 0
        w(
            f"    +{lag}h  {hit}/{n}  {pct(hit, n)}  "
            f"nula {100*med(nula):.1f}%  {p_nula(nula, real)}"
        )
    w("")

    # cortes del +2
    w("  +2 en cortes (dirigido, como el look previo)")
    for nom, xs in (("todas", horas), ("1ª", a), ("2ª", b), ("hold", hold)):
        ht, nt = walk_total(xs)
        p2 = ht.get(2, 0) + ht.get(-2, 0)
        n2 = nt.get(2, 0) + nt.get(-2, 0)
        w(f"    {nom:<6} {p2}/{n2}  {pct(p2, n2)}")
    w("")

    # hod de los pares +2
    hods = Counter()
    dias = Counter()
    for h, g in pares2:
        hods[h.dt.hour] += 1
        dias[h.tag.split("-", 1)[-1]] += 1
    w("  hod del primero del par: " + " ".join(f"h{h}={c}" for h, c in sorted(hods.items())))
    w("  días: " + " ".join(f"{d}={c}" for d, c in sorted(dias.items())))
    w("")

    w("════ cierre ════")
    w("  Cifra suelta de hueco vs ±5 h: no. Queda cerrado.")
    w("  Primer hueco pegado: el ‘anti’ vive casi todo en 0=0.")
    w("  Si el 0=0 no levanta vs nula, no hay oficio.")
    w("  Total ±2: pocos pares; si +1/+3/+4/+5 quedan igual, no es lag 2.")
    w("  Cero cable.")

    OUT.write_text("\n".join(buf) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
