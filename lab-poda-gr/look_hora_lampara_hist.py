# -*- coding: utf-8 -*-
"""
LOOK: lámpara sobre cinta larga (load_horas_y_cinta).
Camina como la mesa: LC-01 + puerta de poda, luego callar.
Cero cable. Hold = últimas 72 h de esa cinta.
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

from core_ae import HOLDOUT, hit_banda, load_horas_y_cinta, p30, split_holdout
from look_hora_secuencia import atom_r, dur_de, es_nucleo

OUT = LAB / "reports" / "LOOK_HORA_LAMPARA_HIST.txt"


def tip_y_p30(luces: list[int]):
    xs = sorted({int(m) % 60 for m in luces})
    if not xs:
        return None, 5
    T = xs[-1]
    if T >= 59:
        return None, 5
    gaps = [xs[i] - xs[i - 1] for i in range(1, len(xs))]
    gap = max(1, int(round(p30(gaps, 5.0))))
    return min(59, T + gap), gap


def tren_hasta(tiros, idx):
    n = 0
    for i in range(idx, -1, -1):
        if es_nucleo(tiros[i]):
            n += 1
        else:
            break
    return n >= 2


def puerta(gap_tiros: int, tren: bool, estirada: bool) -> bool:
    """gap_tiros = idx_g2 - idx_g1 (1 = pegado)."""
    if gap_tiros >= 5:
        return False
    if gap_tiros == 1:
        return tren or estirada
    return 2 <= gap_tiros <= 4


def walk(horas):
    rows = []
    for h in horas:
        tiros = list(h.tiros or [])
        idxs = [i for i, t in enumerate(tiros) if es_nucleo(t)]
        if len(idxs) < 2:
            continue
        mins = [int(tiros[i].m0) % 60 for i in idxs]
        for k in range(len(idxs) - 1):
            luces = mins[: k + 1]
            tip, p = tip_y_p30(luces)
            if tip is None:
                continue
            real = mins[k + 1]
            g1, g2 = idxs[k], idxs[k + 1]
            r_entre = g2 - g1 - 1
            gap_t = g2 - g1
            prev_atom = atom_r(r_entre) if k >= 1 else None
            if k >= 1:
                prev_atom = atom_r(idxs[k] - idxs[k - 1] - 1)
            tren = tren_hasta(tiros, g1)
            d0 = dur_de(tiros[g1])
            est = d0 is not None and d0 >= 100
            sit_poda = puerta(gap_t, tren, est)
            rows.append(
                {
                    "tag": str(h.tag),
                    "tip": tip,
                    "real": real,
                    "p30": p,
                    "hit": hit_banda(tip, real),
                    "exacto": tip == real,
                    "prev": prev_atom,
                    "atom_este": atom_r(r_entre),
                    "r": r_entre,
                    "sit_poda": sit_poda,
                    "tren": tren,
                    "est": est,
                    "m0": mins[k],
                }
            )
    return rows


def lamp_fns():
    return (
        ("nada", lambda r: False),
        ("p30≥9", lambda r: r["p30"] >= 9),
        ("p30≥10", lambda r: r["p30"] >= 10),
        ("p30≥12", lambda r: r["p30"] >= 12),
        ("largo+p30≥9", lambda r: r["prev"] in ("L", "S") and r["p30"] >= 9),
    )


def resumen(rows, calla, solo_poda: bool):
    base = [r for r in rows if (r["sit_poda"] if solo_poda else True)]
    juega = [r for r in base if not calla(r)]
    callados = [r for r in base if calla(r)]
    n = len(juega)
    h = sum(1 for r in juega if r["hit"])
    ex = sum(1 for r in juega if r["exacto"])
    pnl = sum(1 if r["hit"] else -1 for r in juega)
    c_hit = sum(1 for r in callados if r["hit"])
    c_pas = sum(1 for r in callados if r["tip"] - r["real"] > 1)
    por = defaultdict(list)
    for r in juega:
        por[r["tag"]].append(r)
    horas = len({r["tag"] for r in base})
    horas_ok = 0
    horas_pnl = []
    for tag, xs in por.items():
        if any(x["hit"] for x in xs):
            horas_ok += 1
        horas_pnl.append(sum(1 if x["hit"] else -1 for x in xs))
    med = sorted(horas_pnl)[len(horas_pnl) // 2] if horas_pnl else 0
    return {
        "base": len(base),
        "n": n,
        "calla": len(callados),
        "hit": h,
        "ex": ex,
        "pnl": pnl,
        "c_hit": c_hit,
        "c_pas": c_pas,
        "horas": horas,
        "horas_ok": horas_ok,
        "med_hora": med,
    }


def linea(nom, s):
    if s["n"] <= 0:
        return f"  {nom:<14} n=0"
    return (
        f"  {nom:<14} sit {s['n']:5}/{s['base']:<5}  "
        f"calla {s['calla']:4}  "
        f"banda {s['hit']}/{s['n']}  "
        f"exacto {s['ex']}/{s['n']}  "
        f"pnl {s['pnl']:+d}  "
        f"horas+ {s['horas_ok']}/{s['horas']}  "
        f"callado: pasaba {s['c_pas']}/{s['calla']} caía {s['c_hit']}/{s['calla']}"
    )


def bloque(titulo, rows, w):
    w(f"════ {titulo} · {len(rows)} eventos · {len({r['tag'] for r in rows})} h ════")
    w("— todos los tips (sin puerta) —")
    for nom, fn in lamp_fns():
        w(linea(nom, resumen(rows, fn, solo_poda=False)))
    w("— solo puerta de poda (como la mesa) —")
    for nom, fn in lamp_fns():
        w(linea(nom, resumen(rows, fn, solo_poda=True)))
    w("")


def main() -> None:
    horas, _ = load_horas_y_cinta()
    train, hold = split_holdout(horas, HOLDOUT)
    mid = len(train) // 2
    a, b = train[:mid], train[mid:]
    rt, rh, ra, rb = walk(train), walk(hold), walk(a), walk(b)

    tags = [str(h.tag) for h in horas]
    buf = []
    w = buf.append
    w("LOOK · lámpara en histórico largo (cinta 4G, hold = últimas 72 h)")
    w(f"Horas: {len(horas)}  primera {tags[0] if tags else '—'}  última {tags[-1] if tags else '—'}")
    w(f"Train {len(train)} h · hold {len(hold)} h · dos mitades del train {len(a)}/{len(b)}")
    w("Tip = LC-01 (no se mueve). Lámpara = no me siento.")
    w("Puerta = poda +1 salvo tren/estirada · +2..+4 · no sequía.")
    w("")
    bloque("TRAIN histórico", rt, w)
    bloque("1ª mitad train", ra, w)
    bloque("2ª mitad train", rb, w)
    bloque("HOLD 72 h (cola de la cinta)", rh, w)

    w("════ películas históricas: p30≥9 sobre la PUERTA ════")
    n = 0
    for r in rt:
        if r["p30"] < 9 or not r["sit_poda"]:
            continue
        w(
            f"  {r['tag']:<12} @{r['m0']:02d} prev={r['prev'] or '—'} "
            f"p30={r['p30']} tip {r['tip']:02d} G {r['real']:02d} "
            f"{'cae' if r['hit'] else 'no'}  este={r['atom_este']}{r['r']}"
        )
        n += 1
        if n >= 20:
            break
    w("")
    w("════ un día histórico (primera fecha del train con ≥8 eventos) ════")
    por = defaultdict(list)
    for r in rt:
        por[r["tag"].split("-", 1)[-1] if "-" in r["tag"] else r["tag"]].append(r)
    dia = None
    for d, xs in por.items():
        if len(xs) >= 8:
            dia = d
            break
    if dia:
        w(f"  día {dia}")
        for r in por[dia][:36]:
            lamp = r["p30"] >= 9
            sit = r["sit_poda"] and not lamp
            w(
                f"    {r['tag']:<12} @{r['m0']:02d} p30={r['p30']:<2} "
                f"tip {r['tip']:02d} G {r['real']:02d}  "
                f"{'SIT' if sit else '—  '} "
                f"{'LÁMPARA' if lamp else '      '} "
                f"{'poda' if r['sit_poda'] else 'fuera'}  "
                f"{'ok' if r['hit'] else 'miss'}"
            )
    w("")
    w("Lectura:")
    w("  Histórico puro, dos mitades: si la lámpara limpia en ambas, no es cola.")
    w("  Sobre la PUERTA importa más: es como se juega.")
    w("  Cero cable. No cortar Pool 7.")
    OUT.write_text("\n".join(buf) + "\n", encoding="utf-8")
    print(OUT, len(horas), "h")


if __name__ == "__main__":
    main()
