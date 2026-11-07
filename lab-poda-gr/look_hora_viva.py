# -*- coding: utf-8 -*-
"""
LOOK: ¿el tipo VIVO (lo ya caído) nombra lo que queda de ESTA hora?
Cortes varios, no solo 20/30. Cero tip. Cero cable.
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

from core_ae import HOLDOUT, load_horas_y_cinta, split_holdout
from look_hora_secuencia import atom_r, es_nucleo, frase, frase_hora

OUT = LAB / "reports" / "LOOK_HORA_VIVA.txt"
CORTES = (12, 15, 20, 25, 30, 40)


def clima_nG(n: int) -> str:
    if n <= 7:
        return "flaca"
    if n >= 13:
        return "llena"
    return "mesa"


def tipo_vivo(nG_ya: int, T: int) -> str:
    """Proyecta el cupo de 60 min con el ritmo visto hasta T."""
    if T < 8:
        return "temprano"
    implied = nG_ya * 60.0 / (T + 1)
    return clima_nG(int(round(implied)))


def nucleos_hora(h):
    return [t for t in (h.tiros or []) if es_nucleo(t)]


def huecos(gs):
    out = []
    for a, b in zip(gs, gs[1:]):
        # R entre G = diferencia de índice en la cinta de la hora
        # usamos minutos de reloj + atom por tiros si hay idx
        out.append(int(b.m0) - int(a.m0))
    return out


def huecos_tiros(h, gs):
    tiros = list(h.tiros or [])
    idxs = [i for i, t in enumerate(tiros) if es_nucleo(t)]
    pos = {id(tiros[i]): i for i in idxs}
    out = []
    for a, b in zip(gs, gs[1:]):
        ia, ib = pos.get(id(a)), pos.get(id(b))
        if ia is None or ib is None:
            out.append(max(0, int(b.m0) - int(a.m0) - 1))
        else:
            out.append(max(0, ib - ia - 1))
    return out


def med(xs):
    if not xs:
        return None
    ys = sorted(xs)
    return ys[len(ys) // 2]


def p10(xs):
    if not xs:
        return None
    ys = sorted(xs)
    return ys[max(0, int(len(ys) * 0.10))]


def p90(xs):
    if not xs:
        return None
    ys = sorted(xs)
    return ys[min(len(ys) - 1, int(len(ys) * 0.90))]


def main() -> None:
    horas, _ = load_horas_y_cinta()
    train, _ = split_holdout(horas, HOLDOUT)
    docs = []
    for h in train:
        gs = nucleos_hora(h)
        if len(gs) < 1:
            continue
        d = frase_hora(h)
        if not d:
            continue
        docs.append((h, gs, d))

    buf = []
    w = buf.append
    w("LOOK · tipo vivo → lo que queda de ESTA hora")
    w("No es tip del próximo hueco. Es: ¿el ritmo ya visto se sostiene?")
    w(f"train {len(docs)} h. Hold no se mezcla.")
    w("")

    for T in CORTES:
        buckets = defaultdict(list)
        for h, gs, d in docs:
            ya = [g for g in gs if int(g.m0) % 60 <= T]
            rest = [g for g in gs if int(g.m0) % 60 > T]
            tip = tipo_vivo(len(ya), T)
            r_tiros = huecos_tiros(h, rest) if len(rest) >= 2 else []
            # hueco abierto: de última G ya vista (o :00) hasta primera del resto
            abierto = None
            if ya and rest:
                abierto = huecos_tiros(h, [ya[-1], rest[0]])[0]
            elif not ya and rest:
                abierto = int(rest[0].m0)
            max_r = max(r_tiros) if r_tiros else (abierto if abierto is not None else 0)
            atoms_r = [atom_r(x) for x in r_tiros]
            if abierto is not None:
                atoms_r = [atom_r(abierto)] + atoms_r
            buckets[tip].append(
                {
                    "tag": d["tag"],
                    "n_ya": len(ya),
                    "n_rest": len(rest),
                    "n_tot": len(gs),
                    "clima_fin": clima_nG(len(gs)),
                    "max_r": max_r,
                    "hay_S": any(a == "S" for a in atoms_r),
                    "hay_T": any(a == "T" for a in atoms_r),
                    "hay_L": any(a == "L" for a in atoms_r),
                    "d": d,
                    "ya": ya,
                    "rest": rest,
                }
            )

        w(f"════ al minuto {T}  (quedan {59 - T} min) ════")
        for tip in ("flaca", "mesa", "llena"):
            xs = buckets[tip]
            n = len(xs)
            if n < 8:
                continue
            nrest = [x["n_rest"] for x in xs]
            ntot = [x["n_tot"] for x in xs]
            mx = [x["max_r"] for x in xs]
            same = sum(1 for x in xs if x["clima_fin"] == tip)
            flip_up = sum(1 for x in xs if tip == "flaca" and x["clima_fin"] == "llena")
            flip_dn = sum(1 for x in xs if tip == "llena" and x["clima_fin"] == "flaca")
            w(
                f"  {tip:5}  {n} h   G ya~{med([x['n_ya'] for x in xs])}   "
                f"quedan G {p10(nrest)}…{med(nrest)}…{p90(nrest)}   "
                f"cierra {med(ntot)} G   "
                f"hueco máx resto med {med(mx)}   "
                f"S en resto {sum(x['hay_S'] for x in xs)}/{n}   "
                f"tren en resto {sum(x['hay_T'] for x in xs)}/{n}   "
                f"sigue {tip} al cierre {same}/{n}"
                + (f"   vuelco flaca→llena {flip_up}" if tip == "flaca" else "")
                + (f"   vuelco llena→flaca {flip_dn}" if tip == "llena" else "")
            )
        w("")

    # Películas: al :20 qué dirías, qué quedó
    w("════ películas  (lectura @20 → lo que quedó) ════")
    w("Se lee: G ya / tipo vivo → resto de la frase. No un %.")
    shown = 0
    for h, gs, d in docs:
        ya = [g for g in gs if int(g.m0) % 60 <= 20]
        tip = tipo_vivo(len(ya), 20)
        if tip not in ("flaca", "llena"):
            continue
        rest_txt = []
        for p in d["pasos"]:
            if p["m0"] > 20:
                rest_txt.append(f"{p['m0']:02d}{('E' if p['E0'] else '·')}{p['atom']}{p['r']}")
        w(
            f"  {d['tag']:<12} @20 {tip} G={len(ya):2}  "
            f"cierra {clima_nG(d['nG'])} nG={d['nG']}  "
            f"ya {[int(g.m0)%60 for g in ya]}  "
            f"luego {'  '.join(rest_txt) or '∅'}"
        )
        shown += 1
        if shown >= 24:
            break

    w("")
    w("Lectura (sin saco):")
    w("  El resto NO copia el arranque.")
    w("  En todos los cortes, las G que QUEDAN son las mismas")
    w("  (al :20: 4…6…9 tanto si iba flaca como si iba llena).")
    w("  “Sigue flaca/llena” baja porque el resto es ritmo de mesa.")
    w("  Sequía en el resto: sesgo leve. Tren en el resto: igual.")
    w("  Tipo vivo = marcador de lo ya caído, no pronóstico del resto.")
    w("  Antes de ~:12 el recuento no decide nada.")
    OUT.write_text("\n".join(buf) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
