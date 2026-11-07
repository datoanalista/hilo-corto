# -*- coding: utf-8 -*-
"""Barrido fino precisión-recall — cola G por bloque."""
from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))
from core_gc import (  # noqa: E402
    UMBRAL_ALTO,
    UMBRAL_COLA,
    estado_a_min,
    load_horas,
    metrics_binary,
    split_holdout,
)

EXTRA = Path(__file__).resolve().parents[1] / "dashboard" / "extraccion" / "extraccion-en-vivo.txt"
B_MED = (20, 39)
B_FIN = (40, 59)


def cola_futura_en_bloque(h, T, umbral, bloque):
    lo, hi = bloque
    for g in h.gs:
        if g.m0 <= T:
            continue
        if lo <= g.m0 <= hi and g.lumen > umbral:
            return True
    return False


def tiene_g34_fuerte(h, T, min_lumen=70):
    for g in h.gs:
        if g.m0 > T:
            continue
        if g.lumen >= min_lumen and g.tipo in (3, 4):
            return True
    return False


def pareto(train, test, T, bloque, umbral, grid):
    y_tr = [cola_futura_en_bloque(h, T, umbral, bloque) for h in train]
    y_te = [cola_futura_en_bloque(h, T, umbral, bloque) for h in test]
    base = sum(y_tr) / len(y_tr)
    rows = []
    for name, fn in grid:
        m = metrics_binary(y_tr, [fn(h) for h in train])
        if m["tp"] == 0:
            continue
        mt = metrics_binary(y_te, [fn(h) for h in test])
        rows.append((m["prec"], m["rec"], m["tp"], m["fp"], mt["prec"], mt["rec"], mt["tp"], name))
    rows.sort(key=lambda x: (-x[0], -x[1]))
    return base, rows


def main():
    horas = load_horas(EXTRA)
    train, test = split_holdout(horas, 72)
    print(f"train={len(train)} test={len(test)}\n")

    escenarios = [
        ("20-39 @19 G>500", 19, B_MED, UMBRAL_COLA),
        ("20-39 @19 G>400", 19, B_MED, UMBRAL_ALTO),
        ("40-59 @39 G>500", 39, B_FIN, UMBRAL_COLA),
        ("40-59 @39 G>400", 39, B_FIN, UMBRAL_ALTO),
    ]

    for label, T, bloque, um in escenarios:
        grid = []
        for maxg in (110, 130, 150, 200, 250):
            for acum in (0, 200, 300, 400, 500, 600):
                for mg in (0, 70, 80, 90):
                    for g34 in (False, True):
                        parts = [f"maxG>={maxg}"]
                        if acum:
                            parts.append(f"acum>={acum}")
                        if mg:
                            parts.append(f"meanG>={mg}")
                        if g34:
                            parts.append("G34")
                        parts.append(f"sin>{um}")
                        name = " & ".join(parts)

                        def fn(h, t=T, u=um, mgx=maxg, ac=acum, mng=mg, g3=g34):
                            st = estado_a_min(h, t)
                            if st["maxG"] < mgx:
                                return False
                            if ac and st["acum"] < ac:
                                return False
                            if mng and st["meanG"] < mng:
                                return False
                            if g3 and not tiene_g34_fuerte(h, t, 70):
                                return False
                            return not any(g.lumen > u for g in st["gs"])

                        grid.append((name, fn))

        base, rows = pareto(train, test, T, bloque, um, grid)
        print(f"=== {label} base={100*base:.1f}% ===")
        print("top prec (train) con tp>=2:")
        shown = 0
        for r in rows:
            if r[2] < 2:
                continue
            print(
                f"  prec={100*r[0]:.1f}% rec={100*r[1]:.0f}% tp={r[2]} fp={r[3]} "
                f"| hold {100*r[4]:.0f}%/{100*r[5]:.0f}% tp={r[6]} | {r[7]}"
            )
            shown += 1
            if shown >= 10:
                break
        if not shown:
            print("  (ninguna con tp>=2)")
        print()

    # En curso: ¿cola en RESTO de hora tras señal?
    print("=== RESTO DE HORA (cualquier bloque futuro) ===")
    for T in (19, 29, 39):
        for um, nm in ((UMBRAL_COLA, ">500"), (UMBRAL_ALTO, ">400")):
            y_tr = [
                any(g.lumen > um and g.m0 > T for g in h.gs) for h in train
            ]
            base = sum(y_tr) / len(y_tr)
            best = []
            for maxg in (130, 150, 200):
                for acum in (300, 400, 500):
                    def fn(h, t=T, u=um, mg=maxg, ac=acum):
                        st = estado_a_min(h, t)
                        if st["maxG"] < mg or st["acum"] < ac:
                            return False
                        return not any(g.lumen > u for g in st["gs"])

                    m = metrics_binary(y_tr, [fn(h) for h in train])
                    if m["tp"] >= 3:
                        best.append((m["prec"], m["rec"], m["tp"], m["fp"], maxg, acum))
            best.sort(reverse=True)
            if best:
                p, rec, tp, fp, mg, ac = best[0]
                print(
                    f"  @{T} cola {nm} resto: base={100*base:.1f}% "
                    f"mejor maxG>={mg} acum>={ac} prec={100*p:.1f}% rec={100*rec:.0f}% tp={tp} fp={fp}"
                )


if __name__ == "__main__":
    main()
