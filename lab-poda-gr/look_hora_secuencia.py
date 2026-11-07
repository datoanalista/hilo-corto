# -*- coding: utf-8 -*-
"""
LOOK: la hora como frase que camina.
No pool de horas. No % de «cuántas horas hacen X».
Cuerpo = train histórico. Hold = no se usa como saco.
Cero tip. Cero cable. Cero Jaccard.
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

OUT = LAB / "reports" / "LOOK_HORA_SECUENCIA.txt"

ATOM = {
    "T": "tren  (0 R · 2G pegadas)",
    "C": "casi  (1 R · G-R-G)",
    "k": "corto (2–4 R · paso / G-RR-G)",
    "m": "medio (5–8 R · el 6–7 del vivo)",
    "L": "cola  (9–15 R · el 12–15 del vivo)",
    "S": "sequía (≥16 R · 20 y más)",
}
ORDEN = ("T", "C", "k", "m", "L", "S")


def w(s: str = "") -> None:
    buf.append(s)


def es_g(t) -> bool:
    return str(getattr(t, "color", "")).upper().startswith("G")


def es_nucleo(t) -> bool:
    return es_g(t) and getattr(t, "tipo", None) != 5


def dur_de(t) -> int | None:
    d = getattr(t, "dur_s", None)
    if d is None:
        d = getattr(t, "dur", None)
    try:
        return int(d) if d is not None else None
    except (TypeError, ValueError):
        return None


def lumen_de(t) -> int:
    lm = getattr(t, "lumen", None)
    if lm is None:
        lm = getattr(t, "vecino", None)
    try:
        return int(lm or 0)
    except (TypeError, ValueError):
        return 0


def tono_suma(suma: int) -> str:
    if suma < 450:
        return "apag"
    if suma < 600:
        return "opac"
    if suma < 850:
        return "norm"
    if suma < 1100:
        return "fuer"
    return "rica"


def clima_nG(n: int) -> str:
    if n <= 7:
        return "floja"
    if n >= 13:
        return "cupo+"
    return "mesa"


def atom_r(k: int) -> str:
    if k <= 0:
        return "T"
    if k == 1:
        return "C"
    if k <= 4:
        return "k"
    if k <= 8:
        return "m"
    if k <= 15:
        return "L"
    return "S"


def day_key(tag: str) -> str:
    cuerpo = str(tag).strip().lower()
    if cuerpo.startswith("h") and "-" in cuerpo:
        return cuerpo.split("-", 1)[1]
    return cuerpo


def hod_de(tag: str) -> int | None:
    cuerpo = str(tag).strip().lower()
    if cuerpo.startswith("h") and "-" in cuerpo:
        raw = cuerpo.split("-", 1)[0][1:]
        try:
            return int(raw)
        except ValueError:
            return None
    return None


def tipo_g(t) -> str:
    tp = getattr(t, "tipo", None)
    if tp in (1, 2, 3, 4):
        return f"G{tp}"
    return "G?"


def frase_hora(h) -> dict | None:
    tiros = list(getattr(h, "tiros", None) or [])
    idxs = [i for i, t in enumerate(tiros) if es_nucleo(t)]
    if not idxs:
        return None
    nucleos = [tiros[i] for i in idxs]
    tag = str(getattr(h, "tag", "?"))
    pasos = []
    for a, b in zip(idxs, idxs[1:]):
        r = b - a - 1
        ga = tiros[a]
        gb = tiros[b]
        dur_a = dur_de(ga)
        dur_b = dur_de(gb)
        pasos.append(
            {
                "m0": int(ga.m0) % 60,
                "m1": int(gb.m0) % 60,
                "r": r,
                "atom": atom_r(r),
                "E0": dur_a is not None and dur_a >= 100,
                "E1": dur_b is not None and dur_b >= 100,
                "tinta0": tipo_g(ga),
                "tinta1": tipo_g(gb),
                "lm0": lumen_de(ga),
                "dur0": dur_a,
            }
        )
    nG = len(nucleos)
    suma = sum(lumen_de(t) for t in nucleos)
    nE = sum(1 for t in nucleos if (dur_de(t) or 0) >= 100)
    nT = sum(1 for p in pasos if p["atom"] == "T")
    ultima = nucleos[-1]
    return {
        "tag": tag,
        "day": day_key(tag),
        "hod": hod_de(tag),
        "nG": nG,
        "tono": tono_suma(suma),
        "clima": clima_nG(nG),
        "pasos": pasos,
        "nE": nE,
        "nT": nT,
        "cierre_E": (dur_de(ultima) or 0) >= 100,
        "cierre_m": int(ultima.m0) % 60,
        "cierre_tinta": tipo_g(ultima),
        "atoms": [p["atom"] for p in pasos],
    }


def tok(p: dict) -> str:
    e = "E" if p["E0"] else "·"
    return f"{p['m0']:02d}{e}{p['atom']}{p['r']}"


def frase(d: dict) -> str:
    if not d["pasos"]:
        return f"{d['cierre_m']:02d} (una G, sin hueco)"
    cuerpo = "  ".join(tok(p) for p in d["pasos"])
    fin = f"  →{d['cierre_m']:02d}"
    if d["cierre_E"]:
        fin += "E"
    return cuerpo + fin


def cab(d: dict) -> str:
    return (
        f"{d['tag']:<12} {d['tono']:<4} {d['clima']:<5} "
        f"nG={d['nG']:<2} E={d['nE']} T={d['nT']}"
    )


def parse_dia(day: str) -> tuple[int, int, int]:
    # ddmmyy
    if len(day) == 6 and day.isdigit():
        return int(day[4:6]), int(day[2:4]), int(day[0:2])
    return (99, 99, 99)


buf: list[str] = []


def main() -> None:
    horas, _ = load_horas_y_cinta()
    train, hold = split_holdout(horas, HOLDOUT)
    docs = []
    for h in train:
        d = frase_hora(h)
        if d:
            docs.append(d)
    docs.sort(key=lambda d: (parse_dia(d["day"]), d["hod"] if d["hod"] is not None else 99, d["tag"]))

    w("LOOK · hora en secuencia (frase, no promedio)")
    w("Unidad = esta hora caminando, y la hora de al lado.")
    w("Átomo = un hueco G→G de ESA hora + si la G que abre es estirada (≥100 s).")
    w("No se saca «de N horas, M hacen X». Eso ya se sabe que aplasta.")
    w("Cero tip. Cero cable. Extra (tipo 5) no sienta.")
    w()
    w("DATA")
    w(f"  train histórico: {len(docs)} horas con G núcleo")
    w(f"  hold {HOLDOUT} h: no se mezcla en las películas")
    w("  fuente: depurar-all-4G-detail.txt (mismo loader que FORMAS / ELÁSTICO)")
    w("  NO es la cola de ~900 anclas G+7.")
    w()
    w("ÁTOMOS (vocabulario de la cinta, no de un relato)")
    for k in ORDEN:
        w(f"  {k}  {ATOM[k]}")
    w("  E  marca la G que ABRE el hueco si duró ≥100 s (estirada).")
    w("  ·  G corta.  El número pegado es cuántas R hubo.")
    w("  Ejemplo de token: 21E m6 = G estirada en :21, luego 6 R, luego otra G.")
    w()

    # —— I. Películas de días enteros (primera mitad del train) ——
    by_day: dict[str, list[dict]] = defaultdict(list)
    for d in docs:
        by_day[d["day"]].append(d)
    dias_orden = sorted(by_day, key=parse_dia)
    # primera mitad cronológica del corpus
    corte = max(1, len(dias_orden) // 2)
    candidatos = []
    for day in dias_orden[:corte]:
        hs = sorted(by_day[day], key=lambda x: x["hod"] if x["hod"] is not None else 99)
        if len(hs) >= 20:
            candidatos.append((day, hs))
    w("════════════════════════════════ PELÍCULAS DE DÍAS ════════════════════════════════")
    w("Cada renglón es UNA hora, de :00 a :59, en el orden en que se tiró.")
    w("Se lee de izquierda a derecha. No se promedia con la de al lado.")
    w("E=estiradas de esa hora. T=trenes (hueco 0) de esa hora.")
    w()
    n_dias = min(3, len(candidatos))
    for day, hs in candidatos[:n_dias]:
        w(f"── día {day}  ·  {len(hs)} horas (histórico, no la cola) ──")
        prev = None
        for d in hs:
            puente = ""
            if prev is not None and prev["hod"] is not None and d["hod"] is not None:
                if d["hod"] == (prev["hod"] + 1) % 24 or (
                    prev["hod"] == 23 and d["hod"] == 0 and d["day"] == prev["day"]
                ):
                    # costura: último hueco no existe; se marca si cerró E y si abrió T/E
                    abre = d["pasos"][0]["atom"] if d["pasos"] else "-"
                    puente = f"   └ costura {prev['tag']}→{d['tag']}: cerró {'E' if prev['cierre_E'] else '·'} @{prev['cierre_m']:02d} · abre {abre}"
            if puente:
                w(puente)
            w(f"  {cab(d)}")
            w(f"      {frase(d)}")
            prev = d
        w()

    # —— II. Cómo VA: después del primer tren de ESA hora ——
    w("════════════════════════════════ DESPUÉS DEL PRIMER TREN ════════════════════════════════")
    w("Oficio que pediste: si pasó un tren al inicio, ¿se espera otro?")
    w("No es un %. Son películas. El corte es el PRIMER T de esa hora;")
    w("a la derecha queda el resto de LA MISMA hora.")
    w()

    def idx_primer(atoms: list[str], letra: str) -> int | None:
        for i, a in enumerate(atoms):
            if a == letra:
                return i
        return None

    con_tren = [d for d in docs if "T" in d["atoms"]]
    # primeras del corpus (histórico), no la cola
    mues_ini = [d for d in con_tren if d["atoms"] and idx_primer(d["atoms"], "T") is not None and idx_primer(d["atoms"], "T") <= 2]
    w("— tren en los primeros 3 huecos (arranque de hora) —")
    for d in mues_ini[:12]:
        i = idx_primer(d["atoms"], "T")
        iz = "  ".join(tok(p) for p in d["pasos"][: i + 1])
        de = "  ".join(tok(p) for p in d["pasos"][i + 1 :]) or "(se acabó la hora)"
        otro = "T" in d["atoms"][i + 1 :]
        w(f"  {cab(d)}  {'volvió T' if otro else 'no volvió T'}")
        w(f"      {iz}  |  {de}")
    w()
    w("— tren más tarde (no es el arranque); el resto de ESA hora —")
    tarde = [d for d in con_tren if (idx_primer(d["atoms"], "T") or 0) >= 3]
    for d in tarde[:8]:
        i = idx_primer(d["atoms"], "T")
        iz = "  ".join(tok(p) for p in d["pasos"][: i + 1])
        de = "  ".join(tok(p) for p in d["pasos"][i + 1 :]) or "(se acabó la hora)"
        otro = "T" in d["atoms"][i + 1 :]
        w(f"  {cab(d)}  {'volvió T' if otro else 'no volvió T'}")
        w(f"      {iz}  |  {de}")
    w()

    # —— III. Estirada vs tren: cómo se LEE mientras camina ——
    w("════════════════════════════════ ESTIRADA vs TREN (mientras camina) ════════════════════════════════")
    w("A cada hueco se anota el marcador E/T ACUMULADO de ESA hora.")
    w("Así se ve si «vienen más estiradas que trenes» SIN promediar mesas.")
    w("Doce horas del arranque del corpus, distintas tintas de tono.")
    w()
    vistos_tono = {t: 0 for t in ("apag", "opac", "norm", "fuer", "rica")}
    n_muestra = 0
    for d in docs:
        if d["nG"] < 6:
            continue
        if vistos_tono.get(d["tono"], 99) >= 3:
            continue
        vistos_tono[d["tono"]] = vistos_tono.get(d["tono"], 0) + 1
        e = t = 0
        bits = []
        for p in d["pasos"]:
            if p["E0"]:
                e += 1
            if p["atom"] == "T":
                t += 1
            bits.append(f"{tok(p)}[{e}/{t}]")
        w(f"  {cab(d)}")
        w(f"      " + "  ".join(bits))
        n_muestra += 1
        if n_muestra >= 12:
            break
    w("  [E/T] = estiradas / trenes VISTOS hasta ese hueco (incluye ese).")
    w()

    # —— IV. Sílabas que NO estaban en el relato ——
    w("════════════════════════════════ SÍLABAS (pares que la cinta habla) ════════════════════════════════")
    w("Se camina hueco→hueco DENTRO de la hora. Un par = dos átomos seguidos.")
    w("Esto no es «% de horas». Es el idioma: qué par EXISTE, con UNA película.")
    w("Tus ejemplos (T, C, m, L) son átomos. Las sílabas de abajo son otras.")
    w()
    par_ej: dict[tuple[str, str], dict] = {}
    for d in docs:
        ats = d["atoms"]
        for i in range(len(ats) - 1):
            key = (ats[i], ats[i + 1])
            if key not in par_ej:
                par_ej[key] = d
    # pares que el vivo ya nombró vs el resto
    nombrados = {("m", "L"), ("L", "m"), ("T", "m"), ("T", "L"), ("m", "T"), ("L", "T"), ("T", "T"), ("C", "T"), ("T", "C")}
    w("— pares que NO son la coreografía G-6 / G-12 / 2G —")
    otros = [(a, b) for (a, b) in par_ej if (a, b) not in nombrados]
    otros.sort(key=lambda ab: (ORDEN.index(ab[0]), ORDEN.index(ab[1])))
    for a, b in otros:
        d = par_ej[(a, b)]
        w(f"  {a}→{b}   {ATOM[a].split('(')[0].strip():<6} luego {ATOM[b].split('(')[0].strip()}")
        w(f"      {cab(d)}")
        w(f"      {frase(d)}")
    w()
    w("— pares que SÍ coinciden con lo que notaste (una película cada uno) —")
    for a, b in sorted(nombrados, key=lambda ab: (ORDEN.index(ab[0]), ORDEN.index(ab[1]))):
        if (a, b) not in par_ej:
            w(f"  {a}→{b}   no aparece como huecos seguidos en el train")
            continue
        d = par_ej[(a, b)]
        w(f"  {a}→{b}   {cab(d)}")
        w(f"      {frase(d)}")
    w()

    # snap S→T y E abre S
    w("— tres gestos que no estaban en tu lista (oficio, no ejemplo) —")
    snap = next((d for d in docs if any(d["atoms"][i] == "S" and d["atoms"][i + 1] == "T" for i in range(len(d["atoms"]) - 1))), None)
    if snap:
        w("  1. SEQUÍA y después TREN (elástico que suelta de golpe)")
        w(f"      {cab(snap)}")
        w(f"      {frase(snap)}")
    ee = next((d for d in docs if any(p["E0"] and p["atom"] == "S" for p in d["pasos"])), None)
    if ee:
        w("  2. ESTIRADA que abre SEQUÍA (G gorda y después silencio largo)")
        w(f"      {cab(ee)}")
        w(f"      {frase(ee)}")
    tinta = None
    for d in docs:
        for p in d["pasos"]:
            if p["atom"] == "S" and p["tinta1"] == "G4":
                tinta = d
                break
        if tinta:
            break
    if tinta:
        w("  3. SEQUÍA que cierra en G4 (pulso: L largo → tinta gorda; bitácora)")
        w(f"      {cab(tinta)}")
        w(f"      {frase(tinta)}")
    # tren al cierre
    tren_cierre = next((d for d in docs if d["atoms"] and d["atoms"][-1] == "T"), None)
    if tren_cierre:
        w("  4. TREN al CIERRE (no al inicio): la hora se va pegada")
        w(f"      {cab(tren_cierre)}")
        w(f"      {frase(tren_cierre)}")
    w()

    # —— V. Límites del cuerpo (la masa no se va a las nubes) ——
    w("════════════════════════════════ LÍMITES (el cuerpo no se ensancha) ════════════════════════════════")
    w("Esto NO es un promedio. Es el BORDE: lo más que hizo UNA hora,")
    w("y lo que no vi nunca en el train. Así se reconoce «sigue adentro».")
    w()
    max_T = max((d["nT"] for d in docs), default=0)
    max_E = max((d["nE"] for d in docs), default=0)
    max_S = max((d["atoms"].count("S") for d in docs), default=0)
    max_nG = max((d["nG"] for d in docs), default=0)
    min_nG = min((d["nG"] for d in docs), default=0)
    hT = max(docs, key=lambda d: d["nT"])
    hE = max(docs, key=lambda d: d["nE"])
    hS = max(docs, key=lambda d: d["atoms"].count("S"))
    w(f"  más trenes en UNA hora:     {max_T}   {cab(hT)}")
    w(f"      {frase(hT)}")
    w(f"  más estiradas en UNA hora:  {max_E}   {cab(hE)}")
    w(f"      {frase(hE)}")
    w(f"  más sequías en UNA hora:    {max_S}   {cab(hS)}")
    w(f"      {frase(hS)}")
    w(f"  nG del cuerpo: {min_nG} … {max_nG}  (cupo; bitácora: salta hora a hora)")
    w()
    # racha máxima de un átomo
    def max_run(atom: str) -> tuple[int, dict | None]:
        best = 0
        who = None
        for d in docs:
            run = mx = 0
            for a in d["atoms"]:
                if a == atom:
                    run += 1
                    if run > mx:
                        mx = run
                else:
                    run = 0
            if mx > best:
                best = mx
                who = d
        return best, who

    w("  racha más larga del MISMO átomo (no se apila hasta el cielo):")
    for a in ORDEN:
        n, who = max_run(a)
        if who:
            w(f"    {a} ×{n}   {who['tag']}  {frase(who)}")
    w()
    # nunca
    nunca_par = [(a, b) for a in ORDEN for b in ORDEN if (a, b) not in par_ej]
    w("  pares que NO vi nunca (hueco→hueco, misma hora):")
    if nunca_par:
        w("    " + "  ".join(f"{a}→{b}" for a, b in nunca_par))
    else:
        w("    todos los pares de 6 átomos aparecen al menos una vez.")
    w()

    # —— VI. Lectura ——
    w("════════════════════════════════ CÓMO SE LEE (sin saco) ════════════════════════════════")
    w("Bitácora ya decía: cómo VA esta hora, no cómo se viene; isla;")
    w("no hay álbum de mapas de minutos. Esto no reabre H-1→H de cupo.")
    w("La ficha es la FRASE de huecos+estirada, de izquierda a derecha.")
    w()
    w("1. La hora es una palabra de átomos T C k m L S, con E rayado")
    w("   en las G gordas. Tus 6–7 / 12–15 / 2G son tres letras, no la lengua.")
    w("2. Se mueve: el renglón de un día no se parece al siguiente renglón.")
    w("   Los átomos son los mismos. Eso es «sin ensancharse ni irse al cielo».")
    w("3. Después de un tren al arranque: mira el lado derecho de las")
    w("   películas de arriba. A veces se acabó la hora. A veces vuelve T.")
    w("   No es ley «nunca otro tren». Es: ya se gastó un T; el resto se LEE,")
    w("   no se espera el mismo gesto por promedio.")
    w("4. Estirada vs tren se lee en el marcador [E/T] mientras camina.")
    w("   Si a media hora va 3/0, esa hora viene estirada, no en trenes.")
    w("5. Gestos que no nombraste y sí están: S→T (suelta), E abre S,")
    w("   S cierra en G4, tren al cierre. Están en las películas, no en un %.")
    w()
    w("NO SENTAR: tip · d≤1 · taxonomía al dashboard · «si tren, no tren»")
    w("como regla. COVER/SPAN. Jaccard. Cubetas de día.")
    w("NO es predicción. Es reconocer la frase que ya está en la mesa.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(buf) + "\n", encoding="utf-8")
    print(f"OK {OUT}  ({len(buf)} líneas)")


if __name__ == "__main__":
    main()
