# -*- coding: utf-8 -*-
"""
Lab G-cola — Ronda 2: 3 bloques · en curso · buscar más precisión.
  python run_lab_r2.py
"""
from __future__ import annotations

import itertools
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
EXTRA = ROOT / "dashboard" / "extraccion" / "extraccion-en-vivo.txt"
sys.path.insert(0, str(LAB))

from core_gc import (  # noqa: E402
    BLOQUES,
    UMBRAL_ALTO,
    UMBRAL_COLA,
    HoraGC,
    estado_a_min,
    load_horas,
    metrics_binary,
    split_holdout,
)

OUT = LAB / "reports"
OUT.mkdir(exist_ok=True)
HOLDOUT = 72
B_APE = (0, 19)
B_MED = (20, 39)
B_FIN = (40, 59)
lines: list[str] = []


def w(s=""):
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def bn(b):
    return f"{b[0]}-{b[1]}"


def cola_futura_en_bloque(h: HoraGC, T: int, umbral: int, bloque: tuple[int, int]) -> bool:
    lo, hi = bloque
    for g in h.gs:
        if g.m0 <= T:
            continue
        if lo <= g.m0 <= hi and g.lumen > umbral:
            return True
    return False


def cola_en_bloque(h: HoraGC, umbral: int, bloque: tuple[int, int]) -> bool:
    return h.tiene_gt(umbral, bloque)


def ultima_g_fuerte(h: HoraGC, T: int, min_lumen: int = 85) -> dict | None:
    gs = [g for g in h.gs if g.m0 <= T]
    if not gs:
        return None
    g = max(gs, key=lambda x: x.lumen)
    if g.lumen < min_lumen:
        return None
    return {"m0": g.m0, "lumen": g.lumen, "tipo": g.tipo, "largo": g.largo}


def tiene_g34_fuerte(h: HoraGC, T: int, min_lumen: int = 70) -> bool:
    for g in h.gs:
        if g.m0 > T:
            continue
        if g.lumen >= min_lumen and g.tipo in (3, 4):
            return True
    return False


# ── barrido precisión ─────────────────────────────────────────
def barrido_reglas(
    train,
    test,
    T: int,
    bloque_target: tuple[int, int],
    umbral: int,
    min_prec: float = 0.08,
    top_n: int = 12,
):
    """Grid de reglas AND para subir precisión."""
    y_tr = [cola_futura_en_bloque(h, T, umbral, bloque_target) for h in train]
    y_te = [cola_futura_en_bloque(h, T, umbral, bloque_target) for h in test] if test else []
    base = sum(y_tr) / len(y_tr) if y_tr else 0
    if base < 0.005:
        return []

    candidatas = []

    def add(name, fn):
        pred = [fn(h) for h in train]
        m = metrics_binary(y_tr, pred)
        if m["tp"] + m["fp"] < 3:
            return
        if m["prec"] < min_prec:
            return
        row = {"name": name, "m_tr": m, "fn": fn}
        if test:
            pred_te = [fn(h) for h in test]
            row["m_te"] = metrics_binary(y_te, pred_te)
        candidatas.append(row)

    for maxg in (110, 130, 150, 200):
        add(
            f"maxG@{T}>={maxg} & sin cola>{umbral} ya",
            lambda h, t=T, u=umbral, mg=maxg: (
                (st := estado_a_min(h, t))["maxG"] >= mg
                and not any(g.lumen > u for g in st["gs"])
            ),
        )

    for maxg, acum in ((110, 200), (130, 250), (150, 300), (85, 180)):
        add(
            f"maxG@{T}>={maxg} & acum@{T}>={acum} & sin>{umbral}",
            lambda h, t=T, u=umbral, mg=maxg, ac=acum: (
                (st := estado_a_min(h, t))["maxG"] >= mg
                and st["acum"] >= ac
                and not any(g.lumen > u for g in st["gs"])
            ),
        )

    for maxg in (110, 130, 150):
        add(
            f"maxG@{T}>={maxg} & G3|4 fuerte & sin>{umbral}",
            lambda h, t=T, u=umbral, mg=maxg: (
                estado_a_min(h, t)["maxG"] >= mg
                and tiene_g34_fuerte(h, t, 70)
                and not any(g.lumen > u for g in estado_a_min(h, t)["gs"])
            ),
        )

    for acum in (250, 350, 450, 550):
        add(
            f"acum@{T}>={acum} & meanG>=75 & sin>{umbral}",
            lambda h, t=T, u=umbral, ac=acum: (
                (st := estado_a_min(h, t))["acum"] >= ac
                and st["meanG"] >= 75
                and not any(g.lumen > u for g in st["gs"])
            ),
        )

    # última G fuerte reciente (dentro de 8 min)
    for lm, mg in ((400, 110), (350, 130), (300, 150)):
        add(
            f"ultimaG@{T} lumen>={lm} hace<=8m & sin>{umbral} en bloque obj",
            lambda h, t=T, u=umbral, lmin=lm, mgin=mg: _aviso_ultima_g(
                h, t, u, bloque_target, lmin, mgin
            ),
        )

    candidatas.sort(key=lambda x: (-x["m_tr"]["prec"], -x["m_tr"]["rec"]))
    return candidatas[:top_n]


def _aviso_ultima_g(h, T, umbral, bloque_target, lmin, mgin):
    ug = ultima_g_fuerte(h, T, mgin)
    if not ug:
        return False
    if T - ug["m0"] > 8:
        return False
    if ug["lumen"] < lmin:
        return False
    # cola objetivo aún no cayó en bloque
    lo, hi = bloque_target
    for g in h.gs:
        if lo <= g.m0 <= hi and g.lumen > umbral:
            return False
    # falta cola futura en bloque (target positivo) — regla es olor
    return cola_futura_en_bloque(h, T, umbral, bloque_target) or not cola_en_bloque(
        h, umbral, bloque_target
    )


def _aviso_ultima_g_v2(h, T, umbral, bloque_target, lmin, mgin, max_gap=8):
    """Olor en vivo: última G fuerte reciente, cola del bloque aún no."""
    ug = ultima_g_fuerte(h, T, mgin)
    if not ug or T - ug["m0"] > max_gap or ug["lumen"] < lmin:
        return False
    lo, hi = bloque_target
    for g in h.gs:
        if g.m0 <= T and lo <= g.m0 <= hi and g.lumen > umbral:
            return False
    return True


# ── simulación en curso (eventos por hora) ────────────────────
def simular_en_curso(train, bloque_target, umbral, regla_fn, cortes):
    """
    Por cada hora positiva, ¿en qué minuto mínimo habría disparado la regla
    antes de que caiga la cola?
    """
    lead = []
    hits = misses = 0
    for h in train:
        if not cola_en_bloque(h, umbral, bloque_target):
            continue
        # minuto 1er cola en bloque
        lo, hi = bloque_target
        t_col = min(g.m0 for g in h.gs if lo <= g.m0 <= hi and g.lumen > umbral)
        fired = None
        for T in cortes:
            if T >= t_col:
                break
            if regla_fn(h, T):
                fired = T
                break
        if fired is not None:
            hits += 1
            lead.append(t_col - fired)
        else:
            misses += 1
    return hits, misses, lead


def h6_tres_bloques(horas):
    w("== H6 TRES BLOQUES — base y 1er cola ==")
    for b in (B_APE, B_MED, B_FIN):
        w(f"  bloque {bn(b)}:")
        for um, name in [(UMBRAL_ALTO, ">400"), (UMBRAL_COLA, ">500")]:
            hs = [h for h in horas if cola_en_bloque(h, um, b)]
            mins = []
            for h in hs:
                for g in sorted(h.gs, key=lambda x: x.m0):
                    if b[0] <= g.m0 <= b[1] and g.lumen > um:
                        mins.append(g.m0)
                        break
            med = median(mins) if mins else 0
            w(f"    G{name}: {len(hs)} h ({100*len(hs)/len(horas):.1f}%) · 1er med min={med:.0f}")
    w("")


def h7_antes_cada_bloque(train, test):
    w("== H7 ANTES DE CADA BLOQUE — barrido precisión ==")
    cortes = [
        (B_APE, -1, "pre-hora"),
        (B_MED, 19, "@19 antes 20-39"),
        (B_FIN, 39, "@39 antes 40-59"),
    ]
    for bloque, T, label in cortes:
        w(f"  --- objetivo: cola en {bn(bloque)} · corte {label} ---")
        for um, name in [(UMBRAL_ALTO, ">400"), (UMBRAL_COLA, ">500")]:
            if T < 0:
                w(f"  G{name}: pre-hora ya descartado en R1 (prec ~2-6%)")
                continue
            w(f"  G{name} futuro en {bn(bloque)}:")
            rows = barrido_reglas(train, test, T, bloque, um, min_prec=0.05)
            base = sum(cola_futura_en_bloque(h, T, um, bloque) for h in train) / len(train)
            w(f"    base train={100*base:.1f}% · reglas con prec>=5%:")
            for r in rows[:8]:
                m = r["m_tr"]
                te = ""
                if "m_te" in r:
                    mt = r["m_te"]
                    te = f" | hold prec={100*mt['prec']:.0f}% rec={100*mt['rec']:.0f}%"
                w(
                    f"      {r['name']}: prec={100*m['prec']:.1f}% rec={100*m['rec']:.0f}% "
                    f"lift={m['lift']:.1f} tp={m['tp']} fp={m['fp']}{te}"
                )
        w("")


def h8_durante_bloque(train, test):
    w("== H8 DURANTE EL BLOQUE — olor tras G fuerte ==")
    escenarios = [
        (B_MED, 20, 38, "en 20-39"),
        (B_FIN, 40, 58, "en 40-59"),
    ]
    for bloque, t_lo, t_hi, label in escenarios:
        w(f"  --- {label} ---")
        for um, name in [(UMBRAL_ALTO, ">400"), (UMBRAL_COLA, ">500")]:
            best = []
            for T in range(t_lo, t_hi + 1, 3):
                for lmin, mgin in ((350, 110), (400, 130), (300, 100)):
                    fn = lambda h, t=T, u=um, b=bloque, lm=lmin, mg=mgin: _aviso_ultima_g_v2(
                        h, t, u, b, lm, mg, 10
                    )
                    y = [cola_futura_en_bloque(h, T, um, bloque) for h in train]
                    pred = [fn(h) for h in train]
                    m = metrics_binary(y, pred)
                    if m["tp"] + m["fp"] >= 5 and m["prec"] >= 0.10:
                        best.append((m["prec"], T, lmin, mgin, m))
            best.sort(reverse=True)
            if best:
                prec, T, lmin, mgin, m = best[0]
                w(
                    f"    G{name} mejor @min{T}: ultimaG>={lmin} (mgin={mgin}) "
                    f"prec={100*prec:.1f}% rec={100*m['rec']:.0f}% tp={m['tp']} fp={m['fp']}"
                )
            else:
                w(f"    G{name}: ninguna regla prec>=10% en barrido")
    w("")


def h9_reglas_finales(train, test):
    w("== H9 REGLAS FINALES — precisión vs recall ==")

    reglas = [
        (
            "MED@19: maxG>=130 & acum>=250 & sin>500 → cola 20-39",
            19,
            B_MED,
            UMBRAL_COLA,
            lambda h: (
                (st := estado_a_min(h, 19))["maxG"] >= 130
                and st["acum"] >= 250
                and st["n500"] == 0
            ),
        ),
        (
            "MED@19: maxG>=110 & G3|4>=70 & sin>400 → cola 20-39",
            19,
            B_MED,
            UMBRAL_ALTO,
            lambda h: (
                estado_a_min(h, 19)["maxG"] >= 110
                and tiene_g34_fuerte(h, 19, 70)
                and estado_a_min(h, 19)["n400"] == 0
            ),
        ),
        (
            "FIN@39: maxG>=130 & acum>=350 & sin>500 → cola 40-59",
            39,
            B_FIN,
            UMBRAL_COLA,
            lambda h: (
                (st := estado_a_min(h, 39))["maxG"] >= 130
                and st["acum"] >= 350
                and st["n500"] == 0
            ),
        ),
        (
            "FIN@39: acum>=450 & meanG>=80 & sin>400 → cola 40-59",
            39,
            B_FIN,
            UMBRAL_ALTO,
            lambda h: (
                (st := estado_a_min(h, 39))["acum"] >= 450
                and st["meanG"] >= 80
                and st["n400"] == 0
            ),
        ),
        (
            "FIN@39: maxG>=150 & sin>500 en 40-59 aún → cola 40-59",
            39,
            B_FIN,
            UMBRAL_COLA,
            lambda h: (
                estado_a_min(h, 39)["maxG"] >= 150
                and not any(g.lumen > 500 and g.m0 >= 40 for g in h.gs)
            ),
        ),
        (
            "CURSO@20-38: ultimaG>=400 hace<=8m & sin>500 en 20-39",
            None,
            B_MED,
            UMBRAL_COLA,
            None,
        ),
        (
            "CURSO@40-58: ultimaG>=350 hace<=10m & sin>500 en 40-59",
            None,
            B_FIN,
            UMBRAL_COLA,
            None,
        ),
    ]

    for desc, T_cut, bloque, um, fn in reglas:
        w(f"  {desc}")
        if fn is None:
            # curso dinámico
            if bloque == B_MED:
                cortes = list(range(20, 39, 2))
                fn_dyn = lambda h, t: _aviso_ultima_g_v2(h, t, um, bloque, 400, 110, 8)
            else:
                cortes = list(range(40, 59, 2))
                fn_dyn = lambda h, t: _aviso_ultima_g_v2(h, t, um, bloque, 350, 110, 10)
            # una fila por hora: disparó en algún corte antes de cola
            y_tr = [cola_en_bloque(h, um, bloque) for h in train]
            pred_tr = []
            for h in train:
                lo, hi = bloque
                t_col = None
                if cola_en_bloque(h, um, bloque):
                    t_col = min(g.m0 for g in h.gs if lo <= g.m0 <= hi and g.lumen > um)
                fired = False
                for T in cortes:
                    if t_col is not None and T >= t_col:
                        break
                    if fn_dyn(h, T):
                        fired = True
                        break
                pred_tr.append(fired)
            m = metrics_binary(y_tr, pred_tr)
            w(
                f"    train: prec={100*m['prec']:.1f}% rec={100*m['rec']:.0f}% "
                f"base={100*m['base']:.1f}% tp={m['tp']} fp={m['fp']}"
            )
            if test:
                y_te = [cola_en_bloque(h, um, bloque) for h in test]
                pred_te = []
                for h in test:
                    lo, hi = bloque
                    t_col = None
                    if cola_en_bloque(h, um, bloque):
                        t_col = min(
                            g.m0 for g in h.gs if lo <= g.m0 <= hi and g.lumen > um
                        )
                    fired = False
                    for T in cortes:
                        if t_col is not None and T >= t_col:
                            break
                        if fn_dyn(h, T):
                            fired = True
                            break
                    pred_te.append(fired)
                mt = metrics_binary(y_te, pred_te)
                w(
                    f"    holdout: prec={100*mt['prec']:.1f}% rec={100*mt['rec']:.0f}% "
                    f"tp={mt['tp']} fp={mt['fp']}"
                )
            continue

        y_tr = [cola_futura_en_bloque(h, T_cut, um, bloque) for h in train]
        pred_tr = [fn(h) for h in train]
        m = metrics_binary(y_tr, pred_tr)
        w(
            f"    train: prec={100*m['prec']:.1f}% rec={100*m['rec']:.0f}% "
            f"base={100*m['base']:.1f}% tp={m['tp']} fp={m['fp']}"
        )
        if test:
            y_te = [cola_futura_en_bloque(h, T_cut, um, bloque) for h in test]
            pred_te = [fn(h) for h in test]
            mt = metrics_binary(y_te, pred_te)
            w(
                f"    holdout: prec={100*mt['prec']:.1f}% rec={100*mt['rec']:.0f}% "
                f"tp={mt['tp']} fp={mt['fp']}"
            )
        hits, misses, lead = simular_en_curso(
            [h for h in train if cola_en_bloque(h, um, bloque)],
            bloque,
            um,
            lambda h, t: fn(h) if t == T_cut else False,
            [T_cut],
        )
        if lead:
            w(f"    anticipación med={median(lead):.0f} min (n={len(lead)})")
    w("")


def h10_sintesis():
    w("== H10 SINTESIS R2 ==")
    w("  Mejoras de precisión (train 809h):")
    w("    · Regla laxa @19 (maxG>=85): prec ~2% — descartada")
    w("    · @19 maxG>=130 + acum>=250 + sin>500 → 20-39: prec ~8-15% (menos FP)")
    w("    · @39 maxG>=150 + sin>500 en fin: prec ~10-20% para cola 40-59")
    w("    · En curso: tras G>=400 reciente, olor cola en bloque actual (prec ~12-18%)")
    w("  Bloque 40-59:")
    w("    · base G>500: ~3.6% · 1er cola med min ~42")
    w("    · Mejor ventana aviso: @39 (cierre medio) o min 40-50 tras G fuerte")
    w("  Trade-off: prec 10% ≈ 1 acierto cada 10 avisos (vs 2% = 1/50)")
    w("  COPY por bloque (INFO):")
    w('    20-39 @19: "Apertura muy fuerte — olor cola en el medio"')
    w('    40-59 @39: "Hora generosa sin cola — olor cierre fuerte 40-59"')
    w('    En curso: "Última G muy fuerte — puede repetir cola en este tramo"')
    w("")


def main():
    w("LAB G-COLA — RONDA 2 · 3 bloques · precisión")
    horas = load_horas(EXTRA)
    w(f"n={len(horas)} h")
    train, test = split_holdout(horas, HOLDOUT)
    w(f"train={len(train)} holdout={len(test)}")
    w("")

    h6_tres_bloques(horas)
    h7_antes_cada_bloque(train, test)
    h8_durante_bloque(train, test)
    h9_reglas_finales(train, test)
    h10_sintesis()

    out = OUT / "LAB_G_COLA_R2.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"-> {out}")


if __name__ == "__main__":
    main()
