# -*- coding: utf-8 -*-
"""
LOOK: ¿los gestos van de la mano o salen sueltos?
No puntúa 6–7 / 12 / 2G. No saco «de N horas, M%».
Tres ataduras posibles: (1) el TIPO elige la BOLSA
(2) una letra ATA la siguiente (orden ≠ barajar la misma bolsa)
(3) otra cosa (E, lumen, costura, tinta).
Cuerpo = train histórico. Cero tip. Cero cable.
"""
from __future__ import annotations

import random
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
from look_hora_secuencia import (
    ORDEN,
    cab,
    frase,
    frase_hora,
    parse_dia,
    tok,
)

OUT = LAB / "reports" / "LOOK_HORA_ENLACE.txt"
RNG = random.Random(11)
NSH = 400


def w(s: str = "") -> None:
    buf.append(s)


def bolsa(atoms: list[str]) -> str:
    return "".join(a * atoms.count(a) for a in ORDEN) or "∅"


def max_run(atoms: list[str]) -> int:
    if not atoms:
        return 0
    best = run = 1
    for a, b in zip(atoms, atoms[1:]):
        if a == b:
            run += 1
            best = max(best, run)
        else:
            run = 1
    return best


def nulo_run(atoms: list[str]) -> tuple[int, int]:
    """Mediana y p90 de max-run si se baraja ESTA bolsa."""
    if len(atoms) < 2:
        return 1, 1
    xs = []
    base = list(atoms)
    for i in range(NSH):
        RNG.shuffle(base)
        xs.append(max_run(base))
    xs.sort()
    return xs[len(xs) // 2], xs[int(len(xs) * 0.90)]


def corr_huecos(rs: list[int]) -> float | None:
    if len(rs) < 4:
        return None
    xs = rs[:-1]
    ys = rs[1:]
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    if dx < 1e-9 or dy < 1e-9:
        return None
    return num / (dx * dy)


buf: list[str] = []


def main() -> None:
    horas, _ = load_horas_y_cinta()
    train, _ = split_holdout(horas, HOLDOUT)
    docs = []
    for h in train:
        d = frase_hora(h)
        if d and d["atoms"]:
            docs.append(d)
    docs.sort(key=lambda d: (parse_dia(d["day"]), d["hod"] if d["hod"] is not None else 99))

    for d in docs:
        d["bolsa"] = bolsa(d["atoms"])
        d["run"] = max_run(d["atoms"])
        med, p90 = nulo_run(d["atoms"])
        d["run_med"] = med
        d["run_p90"] = p90
        d["pegajosa"] = d["run"] > p90 and d["run"] >= 3
        d["revuelta"] = d["run"] <= med and len(d["atoms"]) >= 5
        rs = [p["r"] for p in d["pasos"]]
        d["corr"] = corr_huecos(rs)

    w("LOOK · ¿los gestos van enlazados?")
    w("No es tip. No es «% de horas». No es el relato 6–7 / 12 / 2G.")
    w("Tres preguntas distintas. Si se mezclan, parece azar o parece ley.")
    w()
    w(f"DATA  train histórico {len(docs)} h con hueco. Hold no se mezcla.")
    w()

    # —— 1. El TIPO elige la BOLSA, no el orden ——
    w("════════════════════════════════ 1. EL TIPO ELIGE LA BOLSA ════════════════════════════════")
    w("Bolsa = letras que ESA hora tiene, sin importar el orden.")
    w("Se muestran horas reales, no un promedio de tono.")
    w()
    ya = defaultdict(int)
    for d in docs:
        clave = (d["tono"], d["clima"])
        if ya[clave] >= 2:
            continue
        if d["nG"] < 5:
            continue
        ya[clave] += 1
        w(f"  {cab(d)}  bolsa {d['bolsa']}")
        w(f"      {frase(d)}")
    w()
    w("Lectura de esas bolsas (sin saco):")
    w("  floja/apagada: la palabra es corta y aparecen L o S.")
    w("  cupo+/rica: la palabra es larga y caben varias T y C.")
    w("  Eso NO es que los gestos «vayan de la mano» entre sí.")
    w("  Es que el cupo/tono elige CUÁNTAS letras y de qué grosor.")
    w("  Bitácora: el clima dice cuántas luces, no el tiro.")
    w()

    # —— 2. ¿Una letra ata la siguiente? barajar la MISMA bolsa ——
    w("════════════════════════════════ 2. ORDEN vs BARAJAR LA MISMA BOLSA ════════════════════════════════")
    w("Si el gesto anterior ATARA al siguiente, el orden real")
    w("se distinguiría de barajar las mismas letras de ESA hora.")
    w("Pegajosa = racha real > p90 del barajado de SU bolsa.")
    w("Revuelta  = racha real ≤ mediana del barajado (sopa de su bolsa).")
    w()
    pega = [d for d in docs if d["pegajosa"]]
    revu = [d for d in docs if d["revuelta"]]
    w("— horas PEGAJOSAS (el orden se pega más que su propia bolsa) —")
    for d in pega[:8]:
        w(
            f"  {cab(d)}  run {d['run']}  nulo {d['run_med']}/{d['run_p90']}  "
            f"bolsa {d['bolsa']}"
        )
        w(f"      {frase(d)}")
    if not pega:
        w("  (no hubo)")
    w()
    w("— horas REVUELTAS (el orden = su bolsa en cualquier orden) —")
    for d in revu[:8]:
        w(
            f"  {cab(d)}  run {d['run']}  nulo {d['run_med']}/{d['run_p90']}  "
            f"bolsa {d['bolsa']}"
        )
        w(f"      {frase(d)}")
    w()
    # hueco numérico: |corr| alta vs ~0
    altos = [d for d in docs if d["corr"] is not None and abs(d["corr"]) >= 0.55]
    bajos = [d for d in docs if d["corr"] is not None and abs(d["corr"]) < 0.15]
    w("— ¿el LARGO del hueco ata el largo del siguiente? (misma hora) —")
    w("  |corr|≥0.55 entre huecos seguidos (una película, no un %):")
    for d in altos[:6]:
        rs = " ".join(str(p["r"]) for p in d["pasos"])
        w(f"  {cab(d)}  corr={d['corr']:+.2f}  R: {rs}")
    if not altos:
        w("  no hay hora con |corr|≥0.55")
    w("  |corr|<0.15 (el siguiente hueco no copia al anterior):")
    for d in bajos[:6]:
        rs = " ".join(str(p["r"]) for p in d["pasos"])
        w(f"  {cab(d)}  corr={d['corr']:+.2f}  R: {rs}")
    w()

    # —— 3. Otras ataduras (no el relato vivo) ——
    w("════════════════════════════════ 3. OTRAS ATADURAS (no tus ejemplos) ════════════════════════════════")
    w()

    # 3a Estirada abre el hueco → qué sale
    w("— A. La G que ABRE ¿ata el hueco? (E vs no-E) —")
    w("  Siguientes 10 huecos abiertos por E, y 10 abiertos por G corta.")
    w("  Se mira el hueco que ELLA abre, no un saco de horas.")
    nE = nC = 0
    w("  abre E:")
    for d in docs:
        for p in d["pasos"]:
            if p["E0"] and nE < 10:
                w(f"    {d['tag']} @{p['m0']:02d} E→{p['atom']}{p['r']}  tinta {p['tinta0']} lm {p['lm0']}")
                nE += 1
        if nE >= 10:
            break
    w("  abre G corta:")
    for d in docs:
        for p in d["pasos"]:
            if (not p["E0"]) and nC < 10:
                w(f"    {d['tag']} @{p['m0']:02d} ·→{p['atom']}{p['r']}  tinta {p['tinta0']} lm {p['lm0']}")
                nC += 1
        if nC >= 10:
            break
    w()

    # 3b lumen gordo vs hueco que abre
    w("— B. Lumen de la G que abre (no es E; es brillo) —")
    w("  G con lm≥80 y el hueco que abre; después G con lm≤20.")
    nH = nL = 0
    w("  lm≥80:")
    for d in docs:
        for p in d["pasos"]:
            if p["lm0"] >= 80 and nH < 8:
                w(f"    {d['tag']} @{p['m0']:02d} lm{p['lm0']} → {p['atom']}{p['r']}")
                nH += 1
        if nH >= 8:
            break
    w("  lm≤20:")
    for d in docs:
        for p in d["pasos"]:
            if 0 < p["lm0"] <= 20 and nL < 8:
                w(f"    {d['tag']} @{p['m0']:02d} lm{p['lm0']} → {p['atom']}{p['r']}")
                nL += 1
        if nL >= 8:
            break
    w()

    # 3c tinta que CIERRA un hueco largo (pulso: L→ tinta)
    w("— C. Tinta que CIERRA un hueco ≥16 (pulso de bitácora, no el vivo) —")
    nT = 0
    for d in docs:
        for p in d["pasos"]:
            if p["atom"] == "S" and nT < 10:
                w(f"    {d['tag']} S{p['r']} cierra en {p['tinta1']} @{p['m1']:02d}  {cab(d)}")
                nT += 1
        if nT >= 10:
            break
    w()

    # 3d costura: último átomo de H vs primero de H+1
    w("— D. Costura H → H+1 (gesto, no cupo) —")
    w("  Bitácora: las horas se juntan por el PULSO cortado, no por el cupo.")
    w("  Aquí: última letra de H y primera de la siguiente mesa.")
    pares = []
    for a, b in zip(docs, docs[1:]):
        if a["day"] != b["day"]:
            continue
        if a["hod"] is None or b["hod"] is None:
            continue
        if b["hod"] != (a["hod"] + 1) % 24 and not (a["hod"] == 23 and b["hod"] == 0):
            continue
        if not a["atoms"] or not b["atoms"]:
            continue
        pares.append((a, b, a["atoms"][-1], b["atoms"][0]))
    w("  doce costuras seguidas del arranque del corpus:")
    for a, b, u, p in pares[:12]:
        mismo = "misma letra" if u == p else "cambia"
        w(f"    {a['tag']} …{u}  →  {p}… {b['tag']}   {mismo}   bolsas {a['bolsa']}|{b['bolsa']}")
    # ¿la primera de H+1 está en su propia bolsa? siempre. ¿copia a H?
    copia = sum(1 for _, _, u, p in pares if u == p)
    w(f"  de {len(pares)} costuras del mismo día, la letra se copia {copia} veces.")
    w("  Eso no corona enlace: dos bolsas ricas copian T por crowding, no por memoria.")
    w()

    # 3e primer hueco de la hora vs el resto (¿el arranque ata?)
    w("— E. ¿El PRIMER hueco de la hora ata el resto? —")
    w("  Se muestra el primero y la bolsa del RESTO (sin el primero).")
    n = 0
    for d in docs:
        if len(d["atoms"]) < 5:
            continue
        resto = d["atoms"][1:]
        w(f"  {cab(d)}  abre {d['atoms'][0]}  resto {bolsa(resto)}")
        n += 1
        if n >= 10:
            break
    w()

    w("════════════════════════════════ LECTURA ════════════════════════════════")
    w("1. Van de la mano con el TIPO de hora en la BOLSA, no en el baile.")
    w("   Apagada/floja: palabra corta, caben L/S. Rica: palabra larga, caben T/C.")
    w("   Eso ya era cupo. No es que k «llame» a L.")
    w("2. El ORDEN, dado esa bolsa, casi no ata. Hay horas pegajosas")
    w("   (una letra se pega: kkkkkk, TTTTT) y horas revueltas.")
    w("   La pegajosa es crowding / isla que se rompe, no un coreógrafo.")
    w("   El largo de un hueco no copia al siguiente (|corr| chica en la")
    w("   mayoría de las películas de abajo-de-0.15).")
    w("3. Otras ataduras: la G que abre (E o lumen) NO elige un hueco fijo")
    w("   en las tiras. La tinta que CIERRA una sequía sí habla el pulso")
    w("   (L largo → luz; a veces G4). Eso es el interruptor, no el gesto.")
    w("4. Costura: a veces se copia la letra, a veces no. La bolsa de H+1")
    w("   es otra mesa. El pulso cruza el :00; el gesto no es un hilo.")
    w("5. Azar acá no significa «dado». Significa: dado el cupo de ESTA")
    w("   hora, el siguiente gesto no está amarrado al anterior.")
    w("   Los átomos no se sueltan del cuerpo; el orden sí se baraja.")
    w()
    w("NO SENTAR: tip · «apagada implica S» · cadena gesto→gesto · dashboard.")
    w("Cero cable. Cero Jaccard.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(buf) + "\n", encoding="utf-8")
    print(f"OK {OUT} ({len(buf)} líneas) pegajosas={len(pega)} revueltas={len(revu)} costuras={len(pares)}")


if __name__ == "__main__":
    main()
