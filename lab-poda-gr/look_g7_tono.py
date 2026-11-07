# -*- coding: utf-8 -*-
"""
LOOK: una G y las 7 casillas siguientes × tono.
Casilla = minuto de pista (Tiro.casilla = m0). Contrastar 7 tiros.
Juez hermano: banda d≤1 tip LC-01 vs minuto de la próxima G.
No Jaccard. No P(tiro=G). No cadenas de toda la cinta. Cero cable.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
AE = ROOT / "lab-apostador-experto"
sys.path.insert(0, str(AE))
sys.path.insert(0, str(ROOT))

from core_ae import HOLDOUT, dist_anillo, load_horas_y_cinta, split_holdout, tip_lc01

lines: list[str] = []

TONOS = ("muy_apagado", "opaco", "normal", "fuerte", "muy_fuerte", "supernova")
TONOS_TAB = ("muy_apagado", "opaco", "normal", "fuerte", "muy_fuerte+")
FORMAS_MIN = (
    "desierto",
    "silla_vecina",
    "silla_ventana",
    "silla_lejos",
    "racimo_pegado",
    "racimo_ventana",
    "racimo_tarde",
)
FORMAS_TIRO = (
    "desierto",
    "pegada",
    "ventana_234",
    "sequia_rompe",
    "tren",
    "estirada_pega",
    "racimo_ventana",
)
GEN_SUM = 850
GEN_DIA_PCT = 0.25
W = 7


def w(s: str = "") -> None:
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def pct(a, b, dec: int = 1) -> str:
    if not b:
        return "—"
    return f"{a / b * 100:.{dec}f}%"


def es_g(t) -> bool:
    return str(getattr(t, "color", "")).upper().startswith("G")


def es_nucleo(t) -> bool:
    if not es_g(t):
        return False
    return getattr(t, "tipo", None) != 5


def lumen_de(t) -> int:
    lm = getattr(t, "lumen", None)
    if lm is None:
        lm = getattr(t, "vecino", None)
    try:
        return int(lm or 0)
    except (TypeError, ValueError):
        return 0


def dur_de(t) -> int | None:
    d = getattr(t, "dur_s", None)
    if d is None:
        d = getattr(t, "dur", None)
    try:
        return int(d) if d is not None else None
    except (TypeError, ValueError):
        return None


def tono_suma(suma: int) -> str:
    if suma < 450:
        return "muy_apagado"
    if suma < 600:
        return "opaco"
    if suma < 850:
        return "normal"
    if suma < 1100:
        return "fuerte"
    if suma < 1600:
        return "muy_fuerte"
    return "supernova"


def tono_tab(tono: str) -> str:
    if tono in ("muy_fuerte", "supernova"):
        return "muy_fuerte+"
    return tono


def clima_nG(n: int) -> str:
    if n <= 7:
        return "floja"
    if n >= 13:
        return "rica"
    return "normal"


def day_key(tag: str) -> str:
    cuerpo = str(tag).strip().lower()
    if cuerpo.startswith("h") and "-" in cuerpo:
        return cuerpo.split("-", 1)[1]
    return cuerpo


def forma_minutos(first: int | None, n_luces: int) -> str:
    if n_luces == 0 or first is None:
        return "desierto"
    if n_luces >= 2:
        if first == 1:
            return "racimo_pegado"
        if first <= 4:
            return "racimo_ventana"
        return "racimo_tarde"
    if first == 1:
        return "silla_vecina"
    if first <= 4:
        return "silla_ventana"
    return "silla_lejos"


def forma_tiros(
    first: int | None,
    nG: int,
    *,
    tren_ancla: bool,
    estirada: bool,
    pegada_doble: bool,
) -> str:
    if nG == 0 or first is None:
        return "desierto"
    if first == 1:
        if tren_ancla or pegada_doble:
            return "tren"
        if estirada:
            return "estirada_pega"
        return "pegada"
    if first <= 4:
        if nG >= 2:
            return "racimo_ventana"
        return "ventana_234"
    return "sequia_rompe"


def doc_hora(h) -> dict | None:
    tiros = list(getattr(h, "tiros", None) or [])
    nucleos = [t for t in tiros if es_nucleo(t)]
    if not nucleos:
        return None
    suma = sum(lumen_de(t) for t in nucleos)
    nG = len(nucleos)
    return {
        "h": h,
        "tag": getattr(h, "tag", "?"),
        "tiros": tiros,
        "nucleos": nucleos,
        "nG": nG,
        "suma": suma,
        "mean": (suma / nG) if nG else 0,
        "tono": tono_suma(suma),
        "clima": clima_nG(nG),
        "day": day_key(getattr(h, "tag", "")),
    }


def eventos_hora(d: dict) -> list[dict]:
    tiros = d["tiros"]
    luces_min: set[int] = set()
    idxs = []
    for i, t in enumerate(tiros):
        if not es_nucleo(t):
            continue
        idxs.append(i)
        luces_min.add(int(t.m0) % 60)

    evs = []
    luces_antes: list[int] = []
    for k, i in enumerate(idxs):
        t = tiros[i]
        m = int(t.m0) % 60
        tren_ancla = False
        if i > 0 and es_g(tiros[i - 1]):
            tren_ancla = True
        dur = dur_de(t)
        estirada = dur is not None and dur >= 100

        # --- 7 casillas = minutos m+1 .. m+7, sin cruzar :00 ---
        rest_m = [mm for mm in range(m + 1, m + 1 + W) if mm <= 59]
        complete_m = m + W <= 59
        offs_lit = [mm - m for mm in rest_m if mm in luces_min]
        n_luces = len(offs_lit)
        first_m = offs_lit[0] if offs_lit else None
        forma_m = forma_minutos(first_m, n_luces) if complete_m else "cola_reloj"

        # --- 7 tiros siguientes, misma hora ---
        rest_t = tiros[i + 1 : i + 1 + W]
        complete_t = len(tiros) >= i + 1 + W
        gpos = [j + 1 for j, x in enumerate(rest_t) if es_nucleo(x)]
        nG_t = len(gpos)
        first_t = gpos[0] if gpos else None
        pegada_doble = bool(rest_t) and es_nucleo(rest_t[0]) and len(rest_t) > 1 and es_nucleo(rest_t[1])
        forma_t = (
            forma_tiros(
                first_t,
                nG_t,
                tren_ancla=tren_ancla,
                estirada=estirada,
                pegada_doble=pegada_doble,
            )
            if complete_t
            else "cola_cinta"
        )

        # tip LC-01 pide huecos (≥2 luces). 1ª G de hora = sin tip.
        tip = tip_lc01(luces_antes + [m]) if luces_antes else None

        prox_m = None
        if k + 1 < len(idxs):
            prox_m = int(tiros[idxs[k + 1]].m0) % 60
        banda = bool(tip is not None and prox_m is not None and dist_anillo(tip, prox_m) <= 1)
        silla_en_7 = bool(
            tip is not None
            and any(dist_anillo(tip, mm) <= 1 for mm in rest_m)
        )
        prox_en_silla = bool(
            tip is not None and prox_m is not None and prox_m in rest_m and dist_anillo(tip, prox_m) <= 1
        )

        evs.append(
            {
                "tono": d["tono"],
                "tono_tab": tono_tab(d["tono"]),
                "clima": d["clima"],
                "day": d["day"],
                "tag": d["tag"],
                "m": m,
                "complete_m": complete_m,
                "forma_m": forma_m,
                "n_luces": n_luces if complete_m else None,
                "first_m": first_m if complete_m else None,
                "complete_t": complete_t,
                "forma_t": forma_t,
                "nG_t": nG_t if complete_t else None,
                "first_t": first_t if complete_t else None,
                "tren_ancla": tren_ancla,
                "estirada": estirada,
                "tip": tip,
                "prox_m": prox_m,
                "banda": banda,
                "silla_en_7": silla_en_7,
                "prox_en_silla": prox_en_silla,
                "lumen": lumen_de(t),
            }
        )
        luces_antes.append(m)
    return evs


def cubrir_dias(docs: list[dict]) -> dict[str, dict]:
    by = defaultdict(list)
    for d in docs:
        by[d["day"]].append(d)
    out = {}
    for day, hs in by.items():
        n = len(hs)
        n_gen = sum(1 for x in hs if x["suma"] >= GEN_SUM)
        generoso = n >= 8 and (n_gen / n) >= GEN_DIA_PCT
        cnt = Counter(x["tono"] for x in hs)
        moda, n_moda = cnt.most_common(1)[0]
        empate = sum(1 for _, c in cnt.items() if c == n_moda) > 1
        out[day] = {
            "n": n,
            "generoso": generoso,
            "p_gen": n_gen / n if n else 0,
            "moda": None if empate else moda,
        }
    return out


def tabla_formas(evs: list[dict], campo: str, formas: tuple[str, ...], titulo: str) -> None:
    w(f"\n{titulo}")
    hdr = f"{'corte':<14} | {'N':>5} | " + " | ".join(f"{f:>14}" for f in formas)
    w(hdr)
    w("-" * len(hdr))

    def fila(nombre: str, xs: list[dict]) -> None:
        n = len(xs)
        if not n:
            return
        w(
            f"{nombre:<14} | {n:>5} | "
            + " | ".join(
                f"{pct(sum(1 for e in xs if e[campo] == f), n):>6} {sum(1 for e in xs if e[campo] == f):>4}"
                for f in formas
            )
        )

    fila("todas", evs)
    by_t = defaultdict(list)
    for e in evs:
        by_t[e["tono_tab"]].append(e)
    for tono in TONOS_TAB:
        fila(tono, by_t[tono])
    by_c = defaultdict(list)
    for e in evs:
        by_c[e["clima"]].append(e)
    w("  -- cupo (nG), no es tono --")
    for clima in ("floja", "normal", "rica"):
        fila(clima, by_c[clima])


def tabla_first(evs: list[dict], campo_first: str, titulo: str) -> None:
    w(f"\n{titulo}")
    cubos = ("+1", "+2..+4", "+5..+7", "ninguna")
    w(f"{'corte':<14} | {'N':>5} | {'+1':>12} | {'+2..+4':>12} | {'+5..+7':>12} | {'ninguna':>12}")
    w("-" * 80)

    def cubo(e) -> str:
        f = e[campo_first]
        if f is None:
            return "ninguna"
        if f == 1:
            return "+1"
        if f <= 4:
            return "+2..+4"
        return "+5..+7"

    def fila(nombre: str, xs: list[dict]) -> None:
        n = len(xs)
        if not n:
            return
        c = Counter(cubo(e) for e in xs)
        w(
            f"{nombre:<14} | {n:>5} | "
            + " | ".join(f"{pct(c[k], n):>6} {c[k]:>4}" for k in cubos)
        )

    fila("todas", evs)
    by_t = defaultdict(list)
    for e in evs:
        by_t[e["tono_tab"]].append(e)
    for tono in TONOS_TAB:
        fila(tono, by_t[tono])


def tabla_dia(evs: list[dict], dias: dict, campo: str, formas: tuple[str, ...], titulo: str) -> None:
    w(f"\n{titulo}")
    w("Día generoso = oficio ya definido (≥25% horas del día con suma≥850; ≥8 h).")
    w("Moda = cubeta de TONO DE HORA más frecuente ese día (sin cubeta nueva).")
    w(f"{'corte':<16} | {'N':>5} | " + " | ".join(f"{f:>12}" for f in formas[:4]) + " | …")
    grupos = defaultdict(list)
    for e in evs:
        info = dias.get(e["day"]) or {}
        grupos["dia_generoso" if info.get("generoso") else "dia_no_gen"].append(e)
        moda = info.get("moda")
        if moda:
            grupos[f"moda_{tono_tab(moda)}"].append(e)
    orden = (
        "dia_generoso",
        "dia_no_gen",
        "moda_muy_apagado",
        "moda_opaco",
        "moda_normal",
        "moda_fuerte",
        "moda_muy_fuerte+",
    )
    for nombre in orden:
        xs = grupos[nombre]
        n = len(xs)
        if n < 20:
            continue
        w(
            f"{nombre:<16} | {n:>5} | "
            + " | ".join(
                f"{pct(sum(1 for e in xs if e[campo] == f), n):>6} {sum(1 for e in xs if e[campo] == f):>4}"
                for f in formas
            )
        )


def tabla_banda(evs: list[dict], titulo: str) -> None:
    w(f"\n{titulo}")
    w("Oficio hermano (no juez de esta ficha): d(tip LC-01, minuto de la PRÓXIMA G) ≤ 1.")
    w("Tip causal = luces ya caídas + esta G. Sin 1ª G de hora no hay p30.")
    xs = [e for e in evs if e["tip"] is not None and e["prox_m"] is not None]
    n = len(xs)
    w(f"  N con tip y próxima G en la hora: {n}")
    if not n:
        return
    hit = sum(1 for e in xs if e["banda"])
    w(f"  banda d≤1 próxima G: {hit}  {pct(hit, n)}")
    en7 = [e for e in xs if e["prox_m"] is not None and e["m"] < e["prox_m"] <= e["m"] + W]
    if en7:
        h7 = sum(1 for e in en7 if e["prox_en_silla"])
        w(f"  de esas, próxima G cae en las 7 casillas: {len(en7)}  · banda {h7}  {pct(h7, len(en7))}")
    w(f"{'corte':<14} | {'N':>5} | {'banda':>10} | {'prox en +2..+4 y banda':>24}")
    by_t = defaultdict(list)
    for e in xs:
        by_t[e["tono_tab"]].append(e)
    for tono in ("todas", *TONOS_TAB):
        ys = xs if tono == "todas" else by_t[tono]
        if not ys:
            continue
        b = sum(1 for e in ys if e["banda"])
        v = [
            e
            for e in ys
            if e["first_m"] is not None and 2 <= e["first_m"] <= 4 and e["prox_en_silla"]
        ]
        w(f"{tono:<14} | {len(ys):>5} | {pct(b, len(ys)):>10} | {len(v):>5}  {pct(len(v), len(ys))}")


def bloque(nombre: str, docs: list[dict], dias: dict) -> None:
    evs = []
    for d in docs:
        evs.extend(eventos_hora(d))
    n_h = len(docs)
    n_ev = len(evs)
    w(f"════════ {nombre}  {n_h} horas con ≥1 G núcleo  ·  {n_ev} anclas G ════════")
    c_tono = Counter(d["tono"] for d in docs)
    w(
        "Horas por tono: "
        + "  ".join(f"{t}={c_tono[t]}" for t in TONOS if c_tono[t])
    )
    n_gen = sum(1 for info in dias.values() if info["generoso"])
    w(f"Días en el lote: {len(dias)}  · generosos (oficio): {n_gen}")

    ev_m = [e for e in evs if e["complete_m"]]
    ev_t = [e for e in evs if e["complete_t"]]
    w(f"Ventanas completas: minutos {len(ev_m)}/{n_ev}  · tiros {len(ev_t)}/{n_ev}")
    w(f"Colas (no caben 7): reloj {sum(1 for e in evs if not e['complete_m'])}  · cinta {sum(1 for e in evs if not e['complete_t'])}")

    tabla_formas(
        ev_m,
        "forma_m",
        FORMAS_MIN,
        "1. FORMAS · 7 CASILLAS = minutos (ficha). Completas. n y %.",
    )
    tabla_first(ev_m, "first_m", "2. PRIMERA LUZ en las 7 casillas (minuto), sin nombrar racimo")
    tabla_formas(
        ev_t,
        "forma_t",
        FORMAS_TIRO,
        "3. CONTRASTE · 7 TIROS de cinta (no es la ficha). Completas.",
    )
    tabla_first(ev_t, "first_t", "4. PRIMERA G núcleo en los 7 tiros")
    tabla_dia(
        ev_m,
        dias,
        "forma_m",
        FORMAS_MIN,
        "5. ¿EL DÍA MUEVE? mismas formas de minutos, corte oficio de día",
    )
    tabla_banda(ev_m, "6. SILLA / BANDA d≤1 (oficio hermano, no color)")

    # flags que no son clase exclusiva
    w("\n7. BANDERAS (no son clase; van encima de la forma)")
    if ev_t:
        w(
            f"  ancla ya en tren (G previa): {sum(1 for e in ev_t if e['tren_ancla'])}  "
            f"{pct(sum(1 for e in ev_t if e['tren_ancla']), len(ev_t))}"
        )
        w(
            f"  ancla estirada (≥100 s): {sum(1 for e in ev_t if e['estirada'])}  "
            f"{pct(sum(1 for e in ev_t if e['estirada']), len(ev_t))}"
        )
    w("  media de luces en las 7 casillas (completas) por tono:")
    by_t = defaultdict(list)
    for e in ev_m:
        if e["n_luces"] is not None:
            by_t[e["tono_tab"]].append(e["n_luces"])
    for tono in TONOS_TAB:
        xs = by_t[tono]
        if not xs:
            continue
        mu = sum(xs) / len(xs)
        w(f"    {tono:<14}  n={len(xs):<5}  media={mu:.2f}  p0={sum(1 for x in xs if x==0)/len(xs)*100:.1f}%  p≥2={sum(1 for x in xs if x>=2)/len(xs)*100:.1f}%")


def main() -> None:
    w("LOOK · G + 7 casillas × tono")
    w("Casilla = minuto de pista (lectores.Tiro.casilla = m0; analogía: silla).")
    w("Ancla = cada G núcleo (tipo ≠ 5). Extra no sienta casilla.")
    w("Ventana = los 7 minutos siguientes EN ESA hora (no se cose :00).")
    w("Tono = TONO DE HORA (suma lumen), cubetas de LOOK_HUECO_TONO.")
    w("'Día opaco / muy opaco / normal' del boleto = esas cubetas de HORA.")
    w("Día (oficio ya definido) = generoso ≥25% horas suma≥850. No se inventan cubetas.")
    w("Juez de corrimiento = banda d≤1 (nota). Unidad = la hora. Cero cable.\n")

    horas, _ = load_horas_y_cinta()
    train, hold = split_holdout(horas, HOLDOUT)
    docs_tr = [d for h in train if (d := doc_hora(h))]
    docs_ho = [d for h in hold if (d := doc_hora(h))]
    dias_tr = cubrir_dias(docs_tr)
    dias_ho = cubrir_dias(docs_ho)

    w(f"Cinta {len(horas)} h · train {len(train)} · holdout {len(hold)}")
    w(f"Con ≥1 G núcleo: train {len(docs_tr)} · hold {len(docs_ho)}\n")

    bloque("TRAIN", docs_tr, dias_tr)
    w("")
    bloque("HOLDOUT", docs_ho, dias_ho)

    w("\n════════════════════════════════ LECTURA ════════════════════════════════")
    w("Ficha = 7 minutos tras la G, misma hora. 7 tiros = contraste, no el boleto.")
    w("")
    w("Hay FORMAS recurrentes, no siete máquinas. Cuatro cubos mayoritarios")
    w("estables train/hold (ventanas completas):")
    w("  desierto        27.6% / 31.1%   (0 luces en las 7)")
    w("  silla_ventana   22.3% / 22.0%   (1 luz, primera en +2..+4)")
    w("  silla_lejos     21.6% / 22.2%   (1 luz, primera en +5..+7)")
    w("  racimo_ventana  21.0% / 19.0%   (2+ luces, primera en +2..+4)")
    w("Las otras tres (silla_vecina, racimo_pegado, racimo_tarde) <4%. No sentar.")
    w("")
    w("TONO DE HORA mueve VOLUMEN, no el gesto:")
    w("  muy_apagado: desierto 39.2%/39.2% · racimo_ventana 12.5%/10.5%")
    w("  normal:      desierto 23.5%/23.2% · racimo_ventana 24.8%/25.4%")
    w("  silla_ventana ~22% en TODOS los tonos (plana). silla_lejos igual ~22%.")
    w("  Cupo (floja/rica) mueve más que el tono: floja desierto ~51/48;")
    w("  rica racimo_ventana ~37/37. Misma física que LOOK_HUECO_TONO / PASO_HORA.")
    w("")
    w("TIPO DE DÍA no corta. Día generoso vs no: mismas % (desierto 26.4 vs 28.0;")
    w("  silla_ventana 22.3=22.3). Moda del tono del día ≈ plana. El objeto del")
    w("  boleto ('opaco, muy opaco, normal') es TONO DE HORA, no un clima de día.")
    w("")
    w("YA ESTABA: apagada estira el paso (4 R vs 2 R); hueco bimodal racimo/sequía;")
    w("  'apagada ⇒ sequía 6–15 luego racimo' era FALSO (más racimo en fuertes);")
    w("  islas (casi no se pegan): +1 minuto 4.8%/3.0% vs iid ~nG/60.")
    w("  desierto ~28% ≈ sombra de ocupación (1−nG/60)^7 en hora normal.")
    w("")
    w("NUEVO (esta ventana): las dos sillas sueltas (+2..+4 y +5..+7) son planas")
    w("  al tono; lo que el tono cambia es desierto ↔ racimo. +1 minuto no es clase.")
    w("  +1 TIRO sí es frecuente (~16%) porque tren/estirada/pegada viven en cinta,")
    w("  no en la silla de al lado.")
    w("")
    w("NO SENTAR / NO CABLEAR: taxonomía G+7 al dashboard · alarma · ventana +5..+7")
    w("  como oficio nuevo (Go! ya calla a 4 R) · cubetas de 'día opaco' ·")
    w("  P(tiro=G) / Jaccard como juez · COVER/SPAN.")

    out = LAB / "reports" / "LOOK_G7_TONO.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"\nGuardado: {out}")


if __name__ == "__main__":
    main()
