# -*- coding: utf-8 -*-
"""Preview R2: multi-bloque + unicornio — sin cablear dashboard."""
from __future__ import annotations

from pathlib import Path

LAB = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(LAB))

from core_ex import (
    B_FIN,
    B_MED,
    cola_en_bloque,
    load_cinta,
    metrics_binary,
    perfilar,
    split_holdout,
)

HOLDOUT = 72


def eval_regla(train, test, fn, y_fn):
    y_tr = [y_fn(h) for h in train]
    y_te = [y_fn(h) for h in test] if test else []
    m = metrics_binary(y_tr, [fn(h) for h in train])
    mt = metrics_binary(y_te, [fn(h) for h in test]) if test else None
    return m, mt


def reglas_bloque_39():
    return [
        (
            "generosa@39: nG>=8 & meanG>=75",
            lambda p: p.st39["nG"] >= 8 and p.st39["meanG"] >= 75,
        ),
        (
            "cierre@39: acum>=550 & maxG>=200 & sin G>=umbral ya",
            lambda p, um: p.st39["acum"] >= 550
            and p.st39["maxG"] >= 200
            and not any(g.lumen >= um and g.m0 <= 39 for g in p.h.gs),
        ),
        (
            "estricta@39: maxG>=250 & meanG>=70 & G34 fuerte & sin cola",
            lambda p, um: p.st39["maxG"] >= 250
            and p.st39["meanG"] >= 70
            and any(g.tipo in (3, 4) and g.lumen >= 70 and g.m0 <= 39 for g in p.h.gs)
            and not any(g.lumen >= um and g.m0 <= 39 for g in p.h.gs),
        ),
        (
            "dia_caliente_proxy: hod14|15 & acum@39>=400",
            lambda p: p.h.hod in (14, 15) and p.st39["acum"] >= 400,
        ),
    ]


def cola_med_fin(h, um: int) -> bool:
    return cola_en_bloque(h, um, B_MED) or cola_en_bloque(h, um, B_FIN)


def main():
    horas = load_cinta()
    perfiles = perfilar(horas)
    train, test = split_holdout(perfiles, HOLDOUT)

    print("=== R2 PREVIEW lab-g-explosion ===")
    print(f"n={len(perfiles)} train={len(train)} holdout={len(test)}")
    print()

    for um in [800, 1000, 1200]:
        print(f"--- TARGET: G>={um} en 20-39 OR 40-59 (multi-bloque) ---")
        y = lambda p, u=um: cola_med_fin(p.h, u)
        base = sum(y(p) for p in train) / len(train)
        npos = sum(y(p) for p in train)
        print(f"  base train={100 * base:.2f}% ({npos} pos / {len(train)})")
        best = []
        for desc, fn in reglas_bloque_39():
            if "sin G>=umbral" in desc or "sin cola" in desc:
                rule = lambda p, f=fn, u=um: f(p, u)
            else:
                rule = fn
            m, mt = eval_regla(train, test, rule, y)
            if m["tp"] + m["fp"] >= 2:
                best.append(
                    (
                        m["prec"],
                        m["rec"],
                        m["tp"],
                        m["fp"],
                        mt["prec"] if mt else 0,
                        mt["tp"] if mt else 0,
                        desc,
                    )
                )
        extras = [
            (
                "unicornio@39: maxG>=400 & meanG<55 & nG<=6 & acum@39<250",
                lambda p: p.h.max_g >= 400
                and p.h.mean_g < 55
                and p.h.n_g <= 6
                and p.st39["acum"] < 250,
            ),
            (
                "flaca+dia: hod14|15 & acum@39<200 & maxG@39<100",
                lambda p: p.h.hod in (14, 15)
                and p.st39["acum"] < 200
                and p.st39["maxG"] < 100,
            ),
            (
                "flaca+dia: hod14|15 & mean@39<50 & nG@39<=5",
                lambda p: p.h.hod in (14, 15)
                and p.st39["meanG"] < 50
                and p.st39["nG"] <= 5,
            ),
        ]
        for desc, fn in extras:
            m, mt = eval_regla(train, test, fn, y)
            if m["tp"] + m["fp"] >= 1:
                best.append(
                    (
                        m["prec"],
                        m["rec"],
                        m["tp"],
                        m["fp"],
                        mt["prec"] if mt else 0,
                        mt["tp"] if mt else 0,
                        desc,
                    )
                )

        def combo(p, u=um):
            checks = []
            for d, fn in reglas_bloque_39():
                if "sin G>=umbral" in d or "sin cola" in d:
                    checks.append(fn(p, u))
                else:
                    checks.append(fn(p))
            checks.append(
                p.h.hod in (14, 15)
                and p.st39["meanG"] < 50
                and p.st39["nG"] <= 5
            )
            return any(checks)

        m, mt = eval_regla(train, test, combo, y)
        best.append(
            (
                m["prec"],
                m["rec"],
                m["tp"],
                m["fp"],
                mt["prec"] if mt else 0,
                mt["tp"] if mt else 0,
                "COMBO: generosa|cierre|estricta|dia|flaca+dia",
            )
        )
        best.sort(key=lambda x: (-x[0], -x[2]))
        for row in best[:6]:
            print(f"  {row[6]}")
            print(
                f"    tr prec={100 * row[0]:.1f}% rec={100 * row[1]:.0f}% "
                f"tp={row[2]} fp={row[3]} | ho prec={100 * row[4]:.1f}% tp={row[5]}"
            )
        print()

    print("--- CENSO G>=1200: cobertura @39 (snapshot min 39) ---")
    caught = 0
    multi_ok = 0
    for p in perfiles:
        evs = p.eventos.get(1200, [])
        if not evs:
            continue
        e = evs[0]
        if e.bloque != "0-19":
            multi_ok += 1
        hits = []
        for desc, fn in reglas_bloque_39():
            try:
                ok = (
                    fn(p, 1200)
                    if ("sin G>=umbral" in desc or "sin cola" in desc)
                    else fn(p)
                )
            except TypeError:
                ok = fn(p)
            if ok:
                hits.append(desc.split(":")[0])
        flaca = (
            p.h.hod in (14, 15)
            and p.st39["meanG"] < 50
            and p.st39["nG"] <= 5
        )
        if flaca:
            hits.append("flaca+dia")
        if hits:
            caught += 1
        note = e.bloque if e.bloque != "0-19" else "0-19 (fuera multi)"
        print(
            f"  {p.h.tag} G{e.lumen}@{e.m0:02d} bloque={note} "
            f"@39 acum={p.st39['acum']} mean={p.st39['meanG']:.0f} max={p.st39['maxG']} "
            f"-> {' | '.join(hits) if hits else 'NINGUNA'}"
        )
    print(f"  resumen: {caught}/13 con alguna regla @39 · {multi_ok}/13 en bloques 20-59")
    print()

    print("--- COMBO multi-bloque G>=800 (mejor proxy) ---")
    y800 = lambda p: cola_med_fin(p.h, 800)

    def combo800(p):
        return (
            (p.st39["nG"] >= 8 and p.st39["meanG"] >= 75)
            or (p.st39["acum"] >= 550 and p.st39["maxG"] >= 200)
            or (p.h.hod in (14, 15) and p.st39["acum"] >= 400)
            or (
                p.h.hod in (14, 15)
                and p.st39["meanG"] < 50
                and p.st39["nG"] <= 5
            )
        )

    m, mt = eval_regla(train, test, combo800, y800)
    print(
        f"  tr prec={100 * m['prec']:.1f}% rec={100 * m['rec']:.0f}% "
        f"tp={m['tp']} fp={m['fp']} | ho prec={100 * mt['prec']:.1f}% "
        f"tp={mt['tp']} fp={mt['fp']}"
    )


if __name__ == "__main__":
    main()
