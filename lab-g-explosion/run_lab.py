# -*- coding: utf-8 -*-
"""
Lab G-explosion — Ronda 1: bloque antes de G extrema.
  python run_lab.py
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB))

from core_ex import (  # noqa: E402
    B_APE,
    B_FIN,
    B_MED,
    DATA_DETAIL,
    EXTRA,
    UMBRAL_TIERS,
    ExplosionEvt,
    PerfilExplosion,
    bn,
    cola_en_bloque,
    cola_futura_en_bloque,
    eventos_en_hora,
    horas_con_tier,
    load_cinta,
    load_cinta_detail,
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


def h0_censo(perfiles: list[PerfilExplosion]):
    w("== H0 CENSO — G extrema (una sola G) ==")
    w(f"  Horas con al menos 1 G: {len(perfiles)}")
    for um in UMBRAL_TIERS:
        evs = [e for p in perfiles for e in p.eventos.get(um, [])]
        hs = horas_con_tier(perfiles, um)
        w(
            f"  G>={um}: {len(evs)} eventos en {len(hs)} h "
            f"({100 * len(hs) / len(perfiles):.2f}% horas)"
        )
        if evs:
            bloques = Counter(e.bloque for e in evs)
            mins = [e.m0 for e in evs]
            lum = [e.lumen for e in evs]
            w(f"    bloques: {dict(bloques)}")
            w(f"    min med={median(mins):.0f} p90={sorted(mins)[int(0.9 * (len(mins) - 1))]}")
            w(f"    lumen med={median(lum):.0f} max={max(lum)}")
    w()


def h1_bloque_por_tier(perfiles: list[PerfilExplosion]):
    w("== H1 BLOQUE — dónde cae la explosión ==")
    for um in [800, 1000, 1200]:
        evs = [e for p in perfiles for e in p.eventos.get(um, [])]
        if not evs:
            w(f"  G>={um}: sin eventos")
            continue
        bloques = Counter(e.bloque for e in evs)
        w(f"  G>={um} (n={len(evs)}):")
        for b, n in bloques.most_common():
            w(f"    bloque {b}: {n} ({100 * n / len(evs):.0f}%)")
    w()


def h2_perfil(perfiles: list[PerfilExplosion], umbral: int = 1000):
    w(f"== H2 PERFIL @19/@39 — horas con G>={umbral} vs resto ==")
    pos = horas_con_tier(perfiles, umbral)
    neg = [p for p in perfiles if not p.eventos.get(umbral)]
    if len(pos) < 2:
        w(f"  n={len(pos)} positivos — perfil descriptivo solo")
        for p in pos:
            e = p.eventos[umbral][0]
            w(
                f"    {p.h.tag} hod={p.h.hod} G{e.lumen}@{e.m0:02d} bloque={e.bloque} "
                f"acum@19={p.st19['acum']} @39={p.st39['acum']} "
                f"nG@39={p.st39['nG']} mean@39={p.st39['meanG']:.0f} max@39={p.st39['maxG']}"
            )
        w("  VEREDICTO: FRÍO (n bajo)")
        w()
        return

    def cmp(key):
        a = [key(p) for p in pos]
        b = [key(p) for p in neg]
        return mean(a), mean(b)

    metrics = [
        ("acum@19", lambda p: p.st19["acum"]),
        ("acum@39", lambda p: p.st39["acum"]),
        ("nG@39", lambda p: p.st39["nG"]),
        ("meanG@39", lambda p: p.st39["meanG"]),
        ("maxG@39", lambda p: p.st39["maxG"]),
        ("sumG hora", lambda p: p.h.sum_g),
    ]
    w(f"  positivos n={len(pos)} · negativos n={len(neg)}")
    for name, fn in metrics:
        ma, mb = cmp(fn)
        w(f"    {name}: con={ma:.0f} vs sin={mb:.0f} (Δ{ma - mb:+.0f})")
    w("  Insight lab-g-cola: acum@19 suele ser igual; leer @35-39 o unicornio")
    w("  VEREDICTO: OLOR perfil tardío · FRÍO regla única @19")
    w()


def reglas_bloque_39():
    """Reglas hermanas lab-g-cola R2/R3 adaptadas a umbral."""
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


def h3_aviso_bloque_40_59(train, test, umbral: int):
    w(f"== H3 AVISO @39 → bloque 40–59 · G>={umbral} ==")

    def y(h):
        return cola_en_bloque(h.h, umbral, B_FIN)

    base = sum(y(h) for h in train) / len(train) if train else 0
    w(f"  base train={100 * base:.2f}%")

    if sum(y(h) for h in train) == 0:
        w("  sin positivos en train — FRÍO")
        w()
        return

    best = []
    for desc, fn in reglas_bloque_39():
        if "sin G>=umbral" in desc or "sin cola" in desc:
            rule = lambda h, f=fn, u=umbral: f(h, u)
        else:
            rule = fn
        m, mt = eval_regla(train, test, rule, y)
        if m["tp"] + m["fp"] >= 3:
            best.append((m["prec"], m["rec"], m["tp"], m["fp"], desc, mt))

    best.sort(key=lambda x: (-x[0], -x[1]))
    if not best:
        w("  ninguna regla con tp+fp>=3")
    for row in best[:8]:
        prec, rec, tp, fp, desc, mt = row
        ho = ""
        if mt:
            ho = f" | ho prec={100 * mt['prec']:.1f}% rec={100 * mt['rec']:.0f}% tp={mt['tp']}"
        w(f"    {desc}")
        w(f"      tr prec={100 * prec:.1f}% rec={100 * rec:.0f}% tp={tp} fp={fp}{ho}")

    if base < 0.005:
        w("  VEREDICTO: FRÍO (base ~0 · n eventos insuficiente)")
    elif best and best[0][0] >= 0.15:
        w("  VEREDICTO: OLOR (prec>=15% en alguna regla)")
    else:
        w("  VEREDICTO: FRÍO / OLOR débil")
    w()


def h4_aviso_bloque_20_39(train, test, umbral: int):
    w(f"== H4 AVISO @19 → bloque 20–39 · G>={umbral} ==")

    def y(h):
        return cola_en_bloque(h.h, umbral, B_MED)

    base = sum(y(h) for h in train) / len(train) if train else 0
    w(f"  base train={100 * base:.2f}%")

    rules = [
        (
            "apertura@19: maxG>=85 & sin G>=umbral en 0-19",
            lambda p, um: p.st19["maxG"] >= 85
            and not any(g.lumen >= um and g.m0 <= 19 for g in p.h.gs),
        ),
        (
            "apertura@19: meanG>=65 & nG>=2 & sin cola",
            lambda p, um: p.st19["meanG"] >= 65
            and p.st19["nG"] >= 2
            and not any(g.lumen >= um and g.m0 <= 19 for g in p.h.gs),
        ),
    ]
    for desc, fn in rules:
        rule = lambda p, f=fn, u=umbral: f(p, u)
        m, mt = eval_regla(train, test, rule, y)
        ho = ""
        if mt:
            ho = f" | ho prec={100 * mt['prec']:.1f}% rec={100 * mt['rec']:.0f}%"
        w(
            f"    {desc}: tr prec={100 * m['prec']:.1f}% rec={100 * m['rec']:.0f}% "
            f"tp={m['tp']} fp={m['fp']}{ho}"
        )
    w("  VEREDICTO: FRÍO (lab-g-cola R1 — prec ~2%)")
    w()


def h5_escalera_umbrales(train, test):
    w("== H5 ESCALERA — prec @39→40-59 según umbral ==")
    w("  regla: generosa@39 (nG>=8, meanG>=75)")
    fn = lambda p: p.st39["nG"] >= 8 and p.st39["meanG"] >= 75
    for um in [500, 800, 1000, 1200]:
        y = lambda p, u=um: cola_en_bloque(p.h, u, B_FIN)
        m, mt = eval_regla(train, test, fn, y)
        ho = f" ho={100 * mt['prec']:.0f}%" if mt and mt["tp"] + mt["fp"] else " ho=—"
        w(
            f"    G>={um}: base={100 * m['base']:.2f}% "
            f"prec={100 * m['prec']:.1f}% rec={100 * m['rec']:.0f}% tp={m['tp']}{ho}"
        )
    w()


def h6_caso_h14(perfiles: list[PerfilExplosion]):
    w("== H6 CASO H14-300826 (G3 1200 min 44) ==")
    p = next((x for x in perfiles if x.h.tag.lower() == "h14-300826"), None)
    if not p:
        w("  tag no encontrado en cinta")
        w()
        return
    e = p.eventos[1200][0]
    w(f"  evento: G{e.lumen} tipo {e.tipo} min {e.m0} bloque {e.bloque}")
    w(
        f"  @19: acum={p.st19['acum']} nG={p.st19['nG']} mean={p.st19['meanG']:.1f} max={p.st19['maxG']}"
    )
    w(
        f"  @39: acum={p.st39['acum']} nG={p.st39['nG']} mean={p.st39['meanG']:.1f} max={p.st39['maxG']}"
    )
    w("  ¿Reglas @39→40-59 habrían avisado bloque ANTES del min 40?")
    for desc, fn in reglas_bloque_39():
        try:
            if "sin G>=umbral" in desc or "sin cola" in desc:
                ok = fn(p, 1200)
            else:
                ok = fn(p)
        except TypeError:
            ok = fn(p)
        w(f"    {desc}: {'SÍ' if ok else 'no'}")
    w("  Perfil: UNICORNIO (hora débil @39 + explosión única en 40-59)")
    w("  VEREDICTO: caso escapa reglas actuales — motivo del lab")
    w()


def h7_fuentes():
    w("== H7 FUENTES ==")
    w(f"  detail: {DATA_DETAIL}")
    hd = load_cinta_detail(DATA_DETAIL, merge_live=False)
    w(f"    horas solo detail: {len(hd)}")
    hm = load_cinta()
    w(f"    horas detail+live: {len(hm)}")
    only_live = len(hm) - len(hd)
    if only_live > 0:
        w(f"    horas solo en live (no en detail): {only_live}")
    for um in [1000, 1200]:
        ev_d = sum(len(eventos_en_hora(h, um)) for h in hd)
        ev_m = sum(len(eventos_en_hora(h, um)) for h in hm)
        w(f"    G>={um}: detail={ev_d} · merge={ev_m}")
    w()


def sintesis():
    w("=" * 60)
    w("SÍNTESIS RONDA 1")
    w("=" * 60)
    w("  PREGUNTA: aviso de BLOQUE antes de G explosiva (≥1200)")
    w()
    w("  H0: censo por umbral — ver arriba")
    w("  H1: bloque dominante 40-59 para G altas (si n>0)")
    w("  H2: perfil @39 separa mejor que @19 (olor tardío)")
    w("  H3/H4: reglas @39/@19 — prec baja si umbral sube")
    w("  H6: H14 unicornio — no olería bloque con reglas vigentes")
    w()
    w("  DECISIÓN PROVISIONAL:")
    w("    · G>=1200: n insuficiente para VIVE — seguir con proxy G>=1000/800")
    w("    · Mejor copy: olor BLOQUE 40-59 @39 cuando hora generosa")
    w("    · Unicornio (H14) requiere capa día caliente sin perfil @39")
    w("    · R2: reglas unicornio + holdout solo live + G>=800")
    w()


def main():
    w("LAB G-EXPLOSION — Ronda 1")
    w("cinta: depurar-all-4G-detail.txt + extraccion-en-vivo (horas nuevas)")
    horas = load_cinta()
    perfiles = perfilar(horas)
    train, test = split_holdout(perfiles, HOLDOUT)
    w(f"n={len(perfiles)} h · train={len(train)} · holdout={len(test)}")
    w()

    h0_censo(perfiles)
    h1_bloque_por_tier(perfiles)
    h2_perfil(perfiles, 1000)
    h2_perfil(perfiles, 1200)
    h3_aviso_bloque_40_59(train, test, 800)
    h3_aviso_bloque_40_59(train, test, 1000)
    h3_aviso_bloque_40_59(train, test, 1200)
    h4_aviso_bloque_20_39(train, test, 1000)
    h5_escalera_umbrales(train, test)
    h6_caso_h14(perfiles)
    h7_fuentes()
    sintesis()

    out = OUT / "LAB_G_EXPLOSION.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"\n[ok] {out}")


if __name__ == "__main__":
    main()
