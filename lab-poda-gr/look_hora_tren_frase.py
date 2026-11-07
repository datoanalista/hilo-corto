# -*- coding: utf-8 -*-
"""
LOOK: cómo se llega a un tren de 3–5 G.
Forma base del humano: sequía larga → huecos que se acortan → tren.
No % sobre totales. No Jaccard. Película por película.
Cero tip. Cero cable.
"""
from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
AE = ROOT / "lab-apostador-experto"
GEXP = ROOT / "lab-g-explosion"
sys.path.insert(0, str(GEXP))
sys.path.insert(0, str(AE))
sys.path.insert(0, str(ROOT))

from core_ae import HOLDOUT, load_horas_y_cinta, split_holdout
from look_hora_secuencia import atom_r, dur_de, es_nucleo

OUT = LAB / "reports" / "LOOK_HORA_TREN_FRASE.txt"


def atom(k: int) -> str:
    return atom_r(k)


def huecos_y_g(tiros):
    """G núcleo en orden + R entre ellas (hueco [i] = R entre G_i y G_{i+1})."""
    gix = [i for i, t in enumerate(tiros) if es_nucleo(t)]
    gs = [tiros[i] for i in gix]
    hues = []
    for a, b in zip(gix, gix[1:]):
        hues.append(b - a - 1)
    return gix, gs, hues


def trenes_en(hues):
    """Trenes de largo 3,4,5: n G pegadas = (n-1) huecos 0 seguidos.
    Devuelve (idx_primer_g_del_tren, n_g, n_ceros).
    idx es índice en la lista de G (no de tiros).
    """
    out = []
    i = 0
    while i < len(hues):
        if hues[i] != 0:
            i += 1
            continue
        j = i
        while j < len(hues) and hues[j] == 0:
            j += 1
        n_ceros = j - i
        n_g = n_ceros + 1
        if 3 <= n_g <= 5:
            out.append((i, n_g, n_ceros))
        i = j
    return out


def prev_hues(hues, start_g_idx, k=5):
    """Huecos CERRADOS justo antes del tren (el de la izquierda del 1er G)."""
    # el tren empieza en G[start_g_idx]; hueco a su izquierda es hues[start_g_idx-1]
    lo = max(0, start_g_idx - k)
    return hues[lo:start_g_idx]


def acorta(xs):
    """¿La cola de xs (tras el primer largo) baja hasta el tren?"""
    if len(xs) < 2:
        return False
    return all(xs[i] >= xs[i + 1] for i in range(len(xs) - 1)) and xs[0] > xs[-1]


def hay_largo(xs, umbral=10):
    return any(x >= umbral for x in xs)


def familia(prev):
    """Nombre de la frase de llegada. Forma base = S/L luego baja."""
    if not prev:
        return "sin_antes · tren al arranque de la hora"
    inm = prev[-1]
    if inm >= 10:
        return "ANTI · sequía pegada al tren (el ejemplo dice que no)"
    if hay_largo(prev, 16) and acorta(prev):
        return "FORMA · S (≥16) y se acorta hasta el tren"
    if hay_largo(prev, 10) and acorta(prev):
        return "FORMA · cola/S (≥10) y se acorta hasta el tren"
    if hay_largo(prev, 10) and not acorta(prev):
        return "hubo largo, pero no bajó en orden"
    if acorta(prev) and prev[0] >= 5:
        return "baja, pero el primero no era sequía"
    if all(x <= 4 for x in prev):
        return "ya era corto · el tren nace en racimo"
    return "otra frase"


def linea_g(g):
    d = dur_de(g)
    m = int(getattr(g, "m0", 0) or 0) % 60
    tp = getattr(g, "tipo", None)
    t = f"G{tp}" if tp in (1, 2, 3, 4) else "G"
    ds = f"{d}s" if d is not None else "?s"
    return f"{t}@{m:02d}/{ds}"


def pinta_frase(tag, gs, hues, start, n_g):
    prev = prev_hues(hues, start, 6)
    # G que cierran esos huecos + las del tren
    g0 = start - len(prev)
    trozo_g = gs[g0 : start + n_g]
    trozo_h = hues[g0 : start + n_g - 1] if start + n_g - 1 <= len(hues) else hues[g0:]
    bits = []
    for i, g in enumerate(trozo_g):
        bits.append(linea_g(g))
        if i < len(trozo_h):
            r = trozo_h[i]
            bits.append(f"—{r}R:{atom(r)}—")
    fam = familia(prev)
    durs = [dur_de(g) for g in gs[max(0, start - 3) : start + 1]]
    durs = [d for d in durs if d is not None]
    dur_txt = ""
    if len(durs) >= 2:
        if all(durs[i] >= durs[i + 1] for i in range(len(durs) - 1)) and durs[0] > durs[-1]:
            dur_txt = f"  durs G↓ {durs}"
        elif all(durs[i] <= durs[i + 1] for i in range(len(durs) - 1)) and durs[0] < durs[-1]:
            dur_txt = f"  durs G↑ {durs}"
        else:
            dur_txt = f"  durs G {durs}"
    prev_txt = " ".join(f"{x}{atom(x)}" for x in prev) if prev else "—"
    return (
        f"  {tag:<12} T{n_g}  antes[{prev_txt}]  "
        f"{fam}  {' '.join(bits)}{dur_txt}"
    ), fam, prev, n_g


def recolectar(horas):
    rows = []
    for h in horas:
        tiros = list(h.tiros or [])
        gix, gs, hues = huecos_y_g(tiros)
        if len(gs) < 3:
            continue
        for start, n_g, _ in trenes_en(hues):
            line, fam, prev, ng = pinta_frase(str(h.tag), gs, hues, start, n_g)
            rows.append(
                {
                    "tag": str(h.tag),
                    "n": ng,
                    "fam": fam,
                    "prev": prev,
                    "inm": prev[-1] if prev else None,
                    "line": line,
                }
            )
    return rows


def bloque(w, titulo, rows):
    w(f"════ {titulo} · {len(rows)} trenes ════")
    if not rows:
        w("  (ninguno)")
        w("")
        return
    por = {}
    for r in rows:
        por.setdefault(r["fam"], []).append(r)
    # primero las formas, después el resto
    orden = sorted(
        por.keys(),
        key=lambda k: (0 if k.startswith("FORMA") else 1 if k.startswith("ANTI") else 2, k),
    )
    for fam in orden:
        xs = por[fam]
        w(f"  — {fam} · {len(xs)} películas —")
        tope = 36 if fam.startswith("FORMA") or fam.startswith("ANTI") else 16
        for r in xs[:tope]:
            w(r["line"])
        if len(xs) > tope:
            w(f"    … +{len(xs) - tope} películas más de esta frase")
        w("")
    # vecinos inmediatos, como lista (no %)
    w("  vecino inmediato (último hueco antes del tren), cifra por cifra:")
    from collections import Counter

    c = Counter(r["inm"] for r in rows if r["inm"] is not None)
    arranque = sum(1 for r in rows if r["inm"] is None)
    bits = [f"{k}R×{c[k]}" for k in sorted(c)]
    w("    " + "  ".join(bits) + (f"  · tren al arranque×{arranque}" if arranque else ""))
    w("")


def main() -> None:
    horas, _ = load_horas_y_cinta()
    train, hold = split_holdout(horas, HOLDOUT)
    rt, rh = recolectar(train), recolectar(hold)

    buf = []
    w = buf.append
    w("LOOK · tren 3–5 G: cómo se llega")
    w("Forma base: sequía larga se acaba → huecos se acortan → G-G-G…")
    w("No el hueco de 10–20 R pegado al tren. No Jaccard. No saco de %.")
    w(f"Cinta {len(horas)} h  {horas[0].tag} → {horas[-1].tag}  hold {HOLDOUT}h")
    w("Tren = 3, 4 o 5 G núcleo pegadas (0 R). Extra tipo 5 no cuenta.")
    w("")
    w("Lectura de una línea:")
    w("  antes[15S 4k 2k] = huecos ya cerrados, de más viejo a más nuevo.")
    w("  —nR:atom— entre las G. T3/T4/T5 = largo del tren.")
    w("  durs G = duración de las G que caminan hacia el tren (¿se achican?).")
    w("")

    bloque(w, "TRAIN · trenes 3–5", rt)
    bloque(w, "HOLD 72 h · trenes 3–5", rh)

    # T4 y T5 solas, todas (pocas)
    w("════ todas las T4 y T5 del train (sin recorte) ════")
    t45 = [r for r in rt if r["n"] >= 4]
    if not t45:
        w("  (ninguna)")
    for r in t45:
        w(r["line"])
    w("")
    w("════ T4 y T5 del hold ════")
    h45 = [r for r in rh if r["n"] >= 4]
    if not h45:
        w("  (ninguna)")
    for r in h45:
        w(r["line"])
    w("")

    w("Lectura:")
    w("  La forma base se confirma o se parte en las películas, no en un %.")
    w("  ANTI = sequía ≥10 R pegada al tren: si aparece, el ejemplo no cubre eso.")
    w("  Cero cable.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(buf) + "\n", encoding="utf-8")
    print(OUT, "train", len(rt), "hold", len(rh), "T4/T5", len(t45) + len(h45))


if __name__ == "__main__":
    main()
