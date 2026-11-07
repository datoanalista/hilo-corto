# -*- coding: utf-8 -*-
"""
LOOK: tipo de hora × R entre G × corrimiento.
Juez: banda d<=1 del minuto (tip vs mG), hora a hora.
No Jaccard. No P(el tiro es G) global. No cadenas de color en la cinta.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
AE = ROOT / "lab-apostador-experto"
sys.path.insert(0, str(AE))
sys.path.insert(0, str(ROOT))

from core_ae import HOLDOUT, dist_anillo, load_horas_y_cinta, p30, split_holdout, tip_lc01

lines: list[str] = []


def w(s: str = "") -> None:
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def es_g(t) -> bool:
    return str(getattr(t, "color", "")).upper().startswith("G")


def clima_nG(n: int) -> str:
    if n <= 7:
        return "floja"
    if n >= 13:
        return "rica"
    return "normal"


def cubeta_r(n: int) -> str:
    if n <= 3:
        return "0-3"
    if n <= 6:
        return "4-6"
    if n <= 9:
        return "7-9"
    if n <= 12:
        return "10-12"
    return "13+"


def pct(a, b) -> str:
    if not b:
        return "—"
    return f"{a / b * 100:.1f}%"


def gaps_de_hora(tiros) -> dict:
    idxs = [i for i, t in enumerate(tiros) if es_g(t)]
    if len(idxs) < 2:
        return None
    r_entre = []
    min_entre = []
    for a, b in zip(idxs, idxs[1:]):
        r_entre.append(b - a - 1)
        ma = int(tiros[a].m0) % 60
        mb = int(tiros[b].m0) % 60
        dmin = (mb - ma) % 60
        if dmin == 0:
            dmin = 60
        min_entre.append(dmin)
    nG = len(idxs)
    return {
        "nG": nG,
        "n_tiros": len(tiros),
        "clima": clima_nG(nG),
        "r_entre": r_entre,
        "min_entre": min_entre,
        "med_r": int(round(median(r_entre))),
        "med_min": int(round(median(min_entre))),
        "idxs": idxs,
        "tiros": tiros,
    }


def tip_paso_r(luces_m: list[int], rs: list[int]) -> int | None:
    """Última G + mediana de R-entre ya vistos en ESTA hora (1 R corta ≈ 1 min)."""
    if not luces_m:
        return None
    T = luces_m[-1] % 60
    if T >= 59:
        return None
    paso = int(round(median(rs))) if rs else 5
    paso = max(1, min(20, paso))
    return min(59, T + paso)


def walk_tips(doc) -> list[dict]:
    """Causal dentro de la hora. Cada G después de la 1ª: 3 tips vs mG real."""
    tiros = doc["tiros"]
    idxs = doc["idxs"]
    out = []
    luces = []
    for k, gi in enumerate(idxs):
        m0 = int(tiros[gi].m0) % 60
        if k == 0:
            luces.append(m0)
            continue
        # Huecos ya cerrados ANTES de esta G (nada del hueco que está por caer).
        rs_vistos = doc["r_entre"][: k - 1]
        real = m0
        t_lc = tip_lc01(luces)
        t_r = tip_paso_r(luces, rs_vistos)
        if rs_vistos and median(rs_vistos) >= 9:
            paso_clima = 11
        elif rs_vistos and median(rs_vistos) <= 6:
            paso_clima = 5
        else:
            paso_clima = 7
        t_cli = min(59, luces[-1] + paso_clima) if luces[-1] < 59 else None

        def cob(tip):
            if tip is None:
                return None
            d = dist_anillo(tip, real)
            return {"d": d, "banda": d <= 1, "exacto": d == 0}

        out.append(
            {
                "lc": cob(t_lc),
                "paso_r": cob(t_r),
                "ritmo": cob(t_cli),
                "clima_final": doc["clima"],
            }
        )
        luces.append(m0)
    return out


def main() -> None:
    w("LOOK · tipo de hora × R entre G × corrimiento")
    w("Juez: banda d≤1 tip vs minuto de ESA G. Unidad: la hora.")
    w("No se unionan cadenas de color. No se cobra P(tiro=G).\n")

    horas, _ = load_horas_y_cinta()
    train, hold = split_holdout(horas, HOLDOUT)
    w(f"Cinta {len(horas)} h · train {len(train)} · holdout {len(hold)}")

    for nombre, lote in (("TRAIN", train), ("HOLDOUT", hold)):
        docs = []
        for h in lote:
            d = gaps_de_hora(getattr(h, "tiros", None) or [])
            if d:
                d["tag"] = h.tag
                docs.append(d)
        w(f"\n════════ {nombre}  {len(docs)} horas con ≥2 G ════════")

        # 1) Cada hora tiene UN paso (mediana de R-entre de ESA hora)
        w("\n1. PASO DE LA HORA (mediana de R entre G, una cifra por hora)")
        w("   Esto es lo que pediste: no se mezclan los tiros de todas las horas.")
        w(f"{'Clima (nG)':<14} | {'Horas':>5} | {'mediana del paso':>16} | "
          f"{'4-6 R':>6} | {'10-12 R':>7} | {'13+ R':>6}")
        w(f"{'-'*14}-+-{'-'*5}-+-{'-'*16}-+-{'-'*6}-+-{'-'*7}-+-{'-'*6}")
        by_cli = defaultdict(list)
        for d in docs:
            by_cli[d["clima"]].append(d)
        for cli in ("floja", "normal", "rica"):
            xs = by_cli[cli]
            if not xs:
                continue
            pasos = [x["med_r"] for x in xs]
            n46 = sum(1 for p in pasos if 4 <= p <= 6)
            n1012 = sum(1 for p in pasos if 10 <= p <= 12)
            n13 = sum(1 for p in pasos if p >= 13)
            w(
                f"{cli:<14} | {len(xs):>5} | {median(pasos):>10.0f} R     | "
                f"{pct(n46, len(xs)):>6} | {pct(n1012, len(xs)):>7} | {pct(n13, len(xs)):>6}"
            )

        # cubetas de paso: cuántas horas viven en cada ritmo
        w("\n   Horas según su propio paso (todas):")
        cub = Counter(cubeta_r(d["med_r"]) for d in docs)
        for k in ("0-3", "4-6", "7-9", "10-12", "13+"):
            w(f"     paso {k:>5} R/G : {cub[k]:>4} horas  {pct(cub[k], len(docs))}")

        # 2) ¿El paso se sostiene DENTRO de la hora?
        w("\n2. ¿EL PASO AGARRA EN LA MISMA HORA? (primer gap vs el resto)")
        hold_ok = hold_n = 0
        corto_sigue = corto_n = 0
        largo_sigue = largo_n = 0
        for d in docs:
            rs = d["r_entre"]
            if len(rs) < 2:
                continue
            primero = rs[0]
            resto_med = median(rs[1:])
            hold_n += 1
            # mismo cubo
            if cubeta_r(primero) == cubeta_r(int(round(resto_med))):
                hold_ok += 1
            if 4 <= primero <= 6:
                corto_n += 1
                if 4 <= resto_med <= 7:
                    corto_sigue += 1
            if primero >= 10:
                largo_n += 1
                if resto_med >= 8:
                    largo_sigue += 1
        w(f"   Primer hueco y el resto caen en el mismo cubo: {pct(hold_ok, hold_n)}  ({hold_ok}/{hold_n} h)")
        w(f"   Si el 1º fue 4-6 R, el resto se queda corto (≤7): {pct(corto_sigue, corto_n)}  ({corto_sigue}/{corto_n} h)")
        w(f"   Si el 1º fue ≥10 R, el resto se queda largo (≥8): {pct(largo_sigue, largo_n)}  ({largo_sigue}/{largo_n} h)")

        # 3) Corrimiento: LC-01 vs paso-R de ESTA hora (causal)
        w("\n3. CORRIMIENTO (cuando llega la G: ¿el minuto era el tip?)")
        cob = {"lc": [], "paso_r": [], "ritmo": []}
        exa = {"lc": [], "paso_r": [], "ritmo": []}
        cob_por_clima = defaultdict(lambda: defaultdict(list))
        for d in docs:
            for ev in walk_tips(d):
                for k in cob:
                    if ev[k]:
                        cob[k].append(ev[k]["banda"])
                        exa[k].append(ev[k]["exacto"])
                        cob_por_clima[d["clima"]][k].append(ev[k]["banda"])
        w(f"{'Tip':<22} | {'N G':>6} | {'Banda d≤1':>10} | {'Exacto':>8}")
        w(f"{'-'*22}-+-{'-'*6}-+-{'-'*10}-+-{'-'*8}")
        for k, lab in (
            ("lc", "LC-01 p30 minutos"),
            ("paso_r", "Paso R de ESTA hora"),
            ("ritmo", "Ritmo corto/largo visto"),
        ):
            xs = cob[k]
            n = len(xs)
            w(f"{lab:<22} | {n:>6} | {pct(sum(xs), n):>10} | {pct(sum(exa[k]), n):>8}")
        w("\n   Banda d≤1 por clima de esa hora (no se mezcla floja con rica):")
        w(f"   {'Clima':<10} | {'LC-01':>8} | {'Paso R':>8} | {'Ritmo':>8} | {'N':>5}")
        for cli in ("floja", "normal", "rica"):
            if cli not in cob_por_clima:
                continue
            def pb(k):
                xs = cob_por_clima[cli][k]
                return pct(sum(xs), len(xs)) if xs else "—"
            n = len(cob_por_clima[cli]["lc"])
            w(f"   {cli:<10} | {pb('lc'):>8} | {pb('paso_r'):>8} | {pb('ritmo'):>8} | {n:>5}")

        # 4) Física: 1 R corta ≈ 1 min
        w("\n4. FÍSICA DEL PALO (dentro de la hora: R-entre vs minutos-entre)")
        diffs = []
        for d in docs:
            for r, m in zip(d["r_entre"], d["min_entre"]):
                diffs.append(m - (r + 1))  # +1 por la G previa que ya comió minutos
        if diffs:
            w(
                f"   minuto_gap − (R_entre+1): mediana {median(diffs):+.0f} · "
                f"eso es la sombra de la G previa (bonus), no un ledger de 100x."
            )
        w("   Identidad de cupo (no se promedian tiros; se cuentan HORAS):")
        w("   nG≈10 (normal) ⇒ ~50 R / ~9 huecos ⇒ ~5–6 R por G.")
        w("   nG≤7  (floja)  ⇒ menos huecos ⇒ el paso de ESA hora se va a 9–12 R.")

    w("\n════════════════════════════════ LECTURA ════════════════════════════════")
    w("El 5–6 R/G en hora normal y 10–12 R/G en hora floja/opaca de CUPOS")
    w("no es un saco de 100x que se equilibra. Es el palo de 60 tiros:")
    w("menos G en ESA hora ⇒ más R entre cada G de ESA hora.")
    w("Eso ya está en bitácora: la espera G→G es sombra de los L; la p es de la hora.")
    w("LC-01 (p30 de minutos ya vistos en la hora) ya lee ese paso.")
    w("Forzar el tip con el conteo de R no gana banda al p30 de minutos.")
    w("El primer hueco NO fija el resto de la hora (mismo cubo ~35–44%).")
    w("Un arranque de ≥10 R no obliga a que el resto siga largo.")
    w("10–12 R/G es la cola de horas flojas, no el día opaco típico.")

    out = LAB / "reports" / "LOOK_PASO_HORA.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    w(f"\nGuardado: {out}")


if __name__ == "__main__":
    main()
