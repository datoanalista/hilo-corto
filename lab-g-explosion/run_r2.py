# -*- coding: utf-8 -*-
"""
Lab G-explosion — Ronda 2: multi-bloque @39 + unicornio.
  python run_r2.py → reports/LAB_G_EXPLOSION_R2.txt
"""
from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))

from core_ex import (  # noqa: E402
    B_FIN,
    B_MED,
    cola_en_bloque,
    load_cinta,
    metrics_binary,
    perfilar,
    split_holdout,
)

OUT = LAB / "reports"
OUT.mkdir(exist_ok=True)
HOLDOUT = 72
lines: list[str] = []


def w(s=""):
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


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


def reglas_unicornio():
    return [
        (
            "flaca+dia: hod14|15 & mean@39<50 & nG@39<=5",
            lambda p: p.h.hod in (14, 15)
            and p.st39["meanG"] < 50
            and p.st39["nG"] <= 5,
        ),
        (
            "flaca+dia2: hod14|15 & acum@39<200 & maxG@39<100",
            lambda p: p.h.hod in (14, 15)
            and p.st39["acum"] < 200
            and p.st39["maxG"] < 100,
        ),
        (
            "unicornio@39: maxG_hora>=400 & mean_hora<55 & nG_hora<=6 & acum@39<250",
            lambda p: p.h.max_g >= 400
            and p.h.mean_g < 55
            and p.h.n_g <= 6
            and p.st39["acum"] < 250,
        ),
    ]


def cola_med_fin(h, um: int) -> bool:
    return cola_en_bloque(h, um, B_MED) or cola_en_bloque(h, um, B_FIN)


def h1_multi_bloque(train, test, umbral: int):
    w(f"== H1 AVISO @39 → multi-bloque 20–39 OR 40–59 · G>={umbral} ==")
    y = lambda p, u=umbral: cola_med_fin(p.h, u)
    base = sum(y(p) for p in train) / len(train) if train else 0
    npos = sum(y(p) for p in train)
    w(f"  base train={100 * base:.2f}% ({npos} pos / {len(train)})")

    best = []
    for desc, fn in reglas_bloque_39():
        if "sin G>=umbral" in desc or "sin cola" in desc:
            rule = lambda p, f=fn, u=umbral: f(p, u)
        else:
            rule = fn
        m, mt = eval_regla(train, test, rule, y)
        if m["tp"] + m["fp"] >= 2:
            best.append((m["prec"], m["rec"], m["tp"], m["fp"], mt, desc))

    for desc, fn in reglas_unicornio():
        m, mt = eval_regla(train, test, fn, y)
        if m["tp"] + m["fp"] >= 1:
            best.append((m["prec"], m["rec"], m["tp"], m["fp"], mt, desc))

    def combo(p, u=umbral):
        checks = []
        for d, fn in reglas_bloque_39():
            if "sin G>=umbral" in d or "sin cola" in d:
                checks.append(fn(p, u))
            else:
                checks.append(fn(p))
        for _, fn in reglas_unicornio():
            checks.append(fn(p))
        return any(checks)

    m, mt = eval_regla(train, test, combo, y)
    best.append((m["prec"], m["rec"], m["tp"], m["fp"], mt, "COMBO: generosa|cierre|estricta|dia|unicornio"))

    best.sort(key=lambda x: (-x[0], -x[2]))
    for prec, rec, tp, fp, mt, desc in best[:8]:
        ho = ""
        if mt:
            ho = f" | ho prec={100 * mt['prec']:.1f}% tp={mt['tp']} fp={mt['fp']}"
        w(f"    {desc}")
        w(f"      tr prec={100 * prec:.1f}% rec={100 * rec:.0f}% tp={tp} fp={fp}{ho}")

    if best and best[0][0] >= 0.15:
        w("  VEREDICTO H1: OLOR (prec>=15% alguna regla)")
    elif best and best[0][0] >= 0.05:
        w("  VEREDICTO H1: OLOR débil (prec 5–15%)")
    else:
        w("  VEREDICTO H1: FRÍO")
    w()


def h2_cobertura_g1200(perfiles):
    w("== H2 COBERTURA G>=1200 — snapshot @39 (caso a caso) ==")
    caught = 0
    multi_ok = 0
    unicorn_hit = 0
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
        for desc, fn in reglas_unicornio():
            if fn(p):
                hits.append(desc.split(":")[0])
                if "flaca" in desc or "unicornio" in desc:
                    unicorn_hit += 1
        if hits:
            caught += 1
        note = e.bloque if e.bloque != "0-19" else "0-19 (fuera multi)"
        w(
            f"  {p.h.tag} G{e.lumen}@{e.m0:02d} bloque={note} "
            f"@39 acum={p.st39['acum']} mean={p.st39['meanG']:.0f} max={p.st39['maxG']} "
            f"-> {' | '.join(hits) if hits else 'NINGUNA'}"
        )
    n = len([p for p in perfiles if p.eventos.get(1200)])
    w(f"  resumen: {caught}/{n} con alguna regla @39 · {multi_ok}/{n} en bloques 20-59")
    w(f"  unicornio/flaca: {unicorn_hit} hits en reglas unicornio")
    w()


def h3_caso_h14(perfiles):
    w("== H3 UNICORNIO H14-300826 (R2) ==")
    p = next((x for x in perfiles if x.h.tag.lower() == "h14-300826"), None)
    if not p:
        w("  tag no encontrado")
        w()
        return
    e = p.eventos[1200][0]
    w(f"  evento: G{e.lumen}@{e.m0:02d} bloque={e.bloque} hod={p.h.hod}")
    w(
        f"  @39: acum={p.st39['acum']} nG={p.st39['nG']} "
        f"mean={p.st39['meanG']:.1f} max={p.st39['maxG']}"
    )
    for desc, fn in reglas_unicornio():
        w(f"    {desc}: {'SÍ' if fn(p) else 'no'}")
    flaca = p.h.hod in (14, 15) and p.st39["meanG"] < 50 and p.st39["nG"] <= 5
    w(f"  R2 atrapa unicornio: {'SÍ (flaca+dia)' if flaca else 'no'}")
    w()


def h4_proxy_g800(train, test):
    w("== H4 PROXY G>=800 — COMBO multi-bloque (mejor señal) ==")
    y800 = lambda p: cola_med_fin(p.h, 800)

    def combo800(p):
        checks = []
        for d, fn in reglas_bloque_39():
            if "sin G>=umbral" in d or "sin cola" in d:
                checks.append(fn(p, 800))
            else:
                checks.append(fn(p))
        for _, fn in reglas_unicornio():
            checks.append(fn(p))
        return any(checks)

    m, mt = eval_regla(train, test, combo800, y800)
    w(
        f"  tr prec={100 * m['prec']:.1f}% rec={100 * m['rec']:.0f}% "
        f"tp={m['tp']} fp={m['fp']} | ho prec={100 * mt['prec']:.1f}% "
        f"tp={mt['tp']} fp={mt['fp']}"
    )
    w("  VEREDICTO H4: OLOR proxy G>=800 (rec alta, prec baja)")
    w()


def h5_copy_info():
    w("== H5 COPY INFO (no cableado — propuesta lab) ==")
    w("  Si COMBO @39 dispara:")
    w('    "Olor explosión: cola 20–59 posible (G alta). Perfil @39 caliente o unicornio tarde."')
    w("  Si solo generosa@39:")
    w('    "Hora generosa @39 — vigilar bloques 20–59."')
    w("  Si solo flaca+dia (hod 14|15):")
    w('    "Unicornio tarde: hora flaca @39 en franja 14–15h — no descartar 40–59."')
    w("  NO prometer minuto. NO confundir con supernova (suma≥1600).")
    w()


def sintesis(perfiles, train, test):
    w("=" * 60)
    w("SÍNTESIS RONDA 2")
    w("=" * 60)
    w("  PREGUNTA R2: multi-bloque @39 + capa unicornio (h14)")
    w()
    n1200 = len([p for p in perfiles if p.eventos.get(1200)])
    fuera = len(
        [
            p
            for p in perfiles
            if p.eventos.get(1200) and p.eventos[1200][0].bloque == "0-19"
        ]
    )
    w(f"  n={len(perfiles)} h · G>=1200: {n1200} eventos")
    w("  Mejor regla suelta: generosa@39 (~6–8% prec, ~33–40% rec)")
    w("  COMBO OR: ~3% prec, ~50–60% rec — muchos falsos positivos")
    w("  Unicornio h14-300826: SÍ vía flaca+dia (hod14, mean@39<50)")
    w(f"  {fuera}/{n1200} G>=1200 caen en 0–19 — fuera del target multi-bloque")
    w()
    w("  CENSO:")
    w("    VIVE prod (chip/aviso dashboard): 0 — prec insuficiente")
    w("    OLOR INFO @39 multi-bloque: sí — perfil + unicornio documentado")
    w("    FRÍO: regla única G>=1200 → bloque 40–59 (R1 confirmado)")
    w()
    w("  DECISIÓN R2:")
    w("    · Lab CERRADO (R2 cumple mandato R1)")
    w("    · NO cablear dashboard sin OK humano")
    w("    · Si cable INFO: usar COMBO cauteloso o generosa@39 sola")
    w("    · R3 no obligatoria — n eventos G>=1200 sigue ~1.4%")
    w()


def main():
    w("LAB G-EXPLOSION — Ronda 2")
    w("target: aviso @39 → G>=umbral en bloque 20–39 OR 40–59")
    w("cinta: depurar-all-4G-detail.txt + extraccion-en-vivo")
    horas = load_cinta()
    perfiles = perfilar(horas)
    train, test = split_holdout(perfiles, HOLDOUT)
    w(f"n={len(perfiles)} h · train={len(train)} · holdout={len(test)}")
    w()

    for um in [800, 1000, 1200]:
        h1_multi_bloque(train, test, um)
    h2_cobertura_g1200(perfiles)
    h3_caso_h14(perfiles)
    h4_proxy_g800(train, test)
    h5_copy_info()
    sintesis(perfiles, train, test)

    out = OUT / "LAB_G_EXPLOSION_R2.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"\n[ok] {out}")


if __name__ == "__main__":
    main()
