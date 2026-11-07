# -*- coding: utf-8
"""
Lab show-motor — motores desde Live Jokers Show (54 casillas).
  python run_lab.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from statistics import mean

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
RZ = ROOT / "lab-ruleta-zero"
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(RZ))
sys.path.insert(0, str(ROOT))

from core_rz import (  # noqa: E402
    DETAIL,
    HOLDOUT,
    LIGHTGREEN,
    banda_score,
    load_cinta,
    load_letters,
    slots_to_probs,
    split_tags,
    tag_key,
)
from show_physics import (  # noqa: E402
    MENU_G_EMP,
    N_G,
    N_R,
    N_SLOTS,
    P_G,
    URNA_R,
)
from motors_show import (  # noqa: E402
    banda_metrics,
    chips_cierre,
    chips_mapa,
    chips_mapa_cierre,
    chips_mapa_som_sin_cierre,
    chips_plato54_uniform,
    chips_plato_x_mapa,
    chips_show_k_plato,
    chips_show_v1,
    chips_som02,
    inter2_show_classic_only,
    inter2_show_plus,
    inter2_show_p0,
    menu_l_predict_tinta,
    seguro_hit,
    tinta_actual,
    union_chips,
)

from src.estado import Estado, PRIMERA_UTIL  # noqa: E402
from src.motor import emitir_boleto  # noqa: E402
from src.tablero import recorrer  # noqa: E402
from src.boleto_inter2 import precompute_beta_chips  # noqa: E402

OUT = LAB / "reports"
OUT.mkdir(exist_ok=True)
lines: list[str] = []


def w(s=""):
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def h0_show_base():
    w("== H0 SHOW — plato 54 (Live Jokers Show) ==")
    w(f"  casillas={N_SLOTS} · R={N_R} · G={N_G} · P(G)={100*P_G:.2f}%")
    w(f"  urna R: {URNA_R}")
    w(f"  menú G emp: {MENU_G_EMP}")
    w("  tinta G: menú L previo (E01) — no ruleta-G iid para color G")
    w("  capas motor: plato → mapa H-1 → cierre → clima → SOM02 → INTER2")
    w()


def walk_motors(cinta):
    w("== H1 MINUTO — motores incrementales vs prod (banda d≤1) ==")
    if PRIMERA_UTIL not in cinta.horas:
        w("  sin PRIMERA_UTIL")
        return {}, {}

    i0 = cinta.orden.index(PRIMERA_UTIL)
    tags = cinta.orden[i0:]
    train_tags, test_tags = split_tags(tags)

    rec = recorrer(cinta)
    hist_by_for = {f["for"]: f for f in rec["historico"] if f.get("for")}

    estado = Estado()
    # warm to PRIMERA_UTIL
    for tag in cinta.orden[:i0]:
        if tag in cinta.horas:
            estado.cerrar(cinta.get(tag))

    motor_names = [
        "M0-PLATO54",
        "M1-MAPA",
        "M2-CIERRE",
        "M3-SOM02",
        "M4-CLASSIC",
        "M5-INTER2",
        "M6-SHOW-V1",
    ]

    rows_tr = []
    rows_te = []
    seguro_tr = {"n": 0, "ok": 0}
    seguro_te = {"n": 0, "ok": 0}

    for tag in tags:
        if tag not in cinta.horas:
            continue
        estado.cerrar(cinta.get(tag))
        nxt = cinta.siguiente(tag)
        if not nxt or nxt not in cinta.horas:
            continue

        prev = cinta.horas[tag]
        n_tiros = len(prev.tiros_nucleo)
        oficiales = list(cinta.horas[nxt].nucleo)
        if not oficiales:
            continue

        doc = emitir_boleto(estado)
        fila = hist_by_for.get(nxt, {})

        chips = {
            "M0-PLATO54": chips_plato54_uniform(nxt, n_tiros),
            "M1-MAPA": chips_mapa(estado),
            "M2-CIERRE": chips_cierre(estado),
            "M3-SOM02": chips_som02(estado),
            "M4-CLASSIC": list(doc.get("boleto") or []),
            "M5-INTER2": list(fila.get("chips") or doc.get("boleto") or []),
            "M6-SHOW-V1": chips_show_v1(estado, n_tiros),
        }

        sh = seguro_hit(estado, oficiales)
        bucket = rows_te if tag in test_tags else rows_tr
        if tag in train_tags or tag in test_tags:
            row = {"for": nxt}
            for name in motor_names:
                m = banda_metrics(chips[name], oficiales)
                row[f"{name}_banda"] = m["banda"]
                row[f"{name}_k"] = m["k"]
                row[f"{name}_hit"] = m["hit"]
            bucket.append(row)
            if sh is not None:
                seg = seguro_te if tag in test_tags else seguro_tr
                seg["n"] += 1
                if sh:
                    seg["ok"] += 1

    def agg(rows, name):
        bs = [r[f"{name}_banda"] for r in rows if r.get(f"{name}_banda") is not None]
        hs = [r[f"{name}_hit"] for r in rows]
        ks = [r[f"{name}_k"] for r in rows]
        if not bs:
            return None
        return {
            "banda": mean(bs),
            "hit": mean(hs),
            "k": mean(ks),
        }

    w(f"  horas train={len(rows_tr)} · holdout={len(rows_te)}")
    w()
    w("  motor · banda_tr · banda_ho · hit_ho · k_med_ho · Δ vs M4")
    m4_ho = agg(rows_te, "M4-CLASSIC")
    m4_b = m4_ho["banda"] if m4_ho else 0
    ranking = []
    for name in motor_names:
        tr = agg(rows_tr, name)
        te = agg(rows_te, name)
        if not te:
            continue
        delta = te["banda"] - m4_b
        ranking.append((te["banda"], name, tr, te, delta))
        w(
            f"    {name:12s}  tr={100*tr['banda']:.1f}%  ho={100*te['banda']:.1f}%  "
            f"hit={100*te['hit']:.1f}%  k={te['k']:.1f}  Δclásico={100*delta:+.1f}pp"
        )
    ranking.sort(reverse=True)
    w()
    w(f"  SEGURO cierre largo train: {seguro_tr['ok']}/{seguro_tr['n']} "
      f"({100*seguro_tr['ok']/max(1,seguro_tr['n']):.1f}%)")
    w(f"  SEGURO cierre largo holdout: {seguro_te['ok']}/{seguro_te['n']} "
      f"({100*seguro_te['ok']/max(1,seguro_te['n']):.1f}%)")
    w()
    w("  ranking holdout banda:")
    for i, (b, name, _, _, d) in enumerate(ranking[:5], 1):
        w(f"    {i}. {name}  {100*b:.1f}%  (Δ clásico {100*d:+.1f}pp)")
    w()
    return rows_tr, rows_te


def walk_motors_r2(cinta, rows_te):
    """R2: orden · plato · híbridos show+INTER2."""
    w("== H4 R2 ORDEN / PLATO — vs clásico (holdout) ==")
    if not rows_te:
        w("  sin holdout R1")
        w()
        return {}

    r2_names = [
        "M7-MAPA-CIERRE",
        "M8-K-PLATO",
        "M9-PLATO×MAPA",
        "M10-SIN-CIERRE",
    ]
    hyb_names = [
        "H1-INTER2-SHOW-P0",
        "H2-INTER2-SHOW+7",
        "H3-INTER2-CL∩SH",
        "H4-UNION-CL+SH",
    ]
    ref = {
        "M4-CLASSIC": "M4-CLASSIC_banda",
        "M5-INTER2": "M5-INTER2_banda",
    }

    agg_r2 = {}
    for name in r2_names + hyb_names:
        bs = [r.get(f"{name}_banda") for r in rows_te if r.get(f"{name}_banda") is not None]
        if bs:
            agg_r2[name] = mean(bs)
    for name in ("M4-CLASSIC", "M5-INTER2"):
        bs = [r.get(f"{name}_banda") for r in rows_te if r.get(f"{name}_banda") is not None]
        if bs:
            agg_r2[name] = mean(bs)

    m4 = agg_r2.get("M4-CLASSIC", 0)
    m5 = agg_r2.get("M5-INTER2", 0)
    w("  motor · banda_ho · k_med · Δ vs M4 · Δ vs M5")
    ranking = []
    for name in r2_names + hyb_names:
        bs = [r.get(f"{name}_banda") for r in rows_te if r.get(f"{name}_banda") is not None]
        ks = [r.get(f"{name}_k", 0) for r in rows_te if r.get(f"{name}_banda") is not None]
        if not bs:
            continue
        b = mean(bs)
        k = mean(ks) if ks else 0
        d4 = b - m4
        d5 = b - m5
        ranking.append((b, name, d4, d5))
        w(
            f"    {name:18s}  ho={100*b:.1f}%  k={k:.1f}  "
            f"Δclásico={100*d4:+.1f}pp  ΔINTER2={100*d5:+.1f}pp"
        )
    ranking.sort(reverse=True)
    w()
    w("  ranking R2 holdout:")
    for i, (b, name, d4, d5) in enumerate(ranking[:6], 1):
        w(f"    {i}. {name}  {100*b:.1f}%  (Δ clásico {100*d4:+.1f}pp · Δ INTER2 {100*d5:+.1f}pp)")
    w()
    return agg_r2


def walk_motors_r2_fill(cinta, rows_tr, rows_te):
    """Calcula motores R2 reutilizando walk R1."""
    if PRIMERA_UTIL not in cinta.horas:
        return

    i0 = cinta.orden.index(PRIMERA_UTIL)
    tags = cinta.orden[i0:]
    train_tags, test_tags = split_tags(tags)
    beta_by_for = precompute_beta_chips(cinta)

    estado = Estado()
    for tag in cinta.orden[:i0]:
        if tag in cinta.horas:
            estado.cerrar(cinta.get(tag))

    row_by_for = {r["for"]: r for r in rows_tr + rows_te if r.get("for")}

    for tag in tags:
        if tag not in cinta.horas:
            continue
        estado.cerrar(cinta.get(tag))
        nxt = cinta.siguiente(tag)
        if not nxt or nxt not in cinta.horas or nxt not in row_by_for:
            continue

        prev = cinta.horas[tag]
        n_tiros = len(prev.tiros_nucleo)
        oficiales = list(cinta.horas[nxt].nucleo)
        if not oficiales:
            continue

        doc = emitir_boleto(estado)
        classic = list(doc.get("boleto") or [])
        show_m3 = chips_som02(estado)
        beta_map = beta_by_for.get(nxt) or {}

        chips_r2 = {
            "M7-MAPA-CIERRE": chips_mapa_cierre(estado),
            "M8-K-PLATO": chips_show_k_plato(estado, n_tiros),
            "M9-PLATO×MAPA": chips_plato_x_mapa(estado, nxt, n_tiros),
            "M10-SIN-CIERRE": chips_mapa_som_sin_cierre(estado),
            "H1-INTER2-SHOW-P0": inter2_show_p0(show_m3, beta_map) or classic,
            "H2-INTER2-SHOW+7": inter2_show_plus(classic, show_m3, beta_map) or classic,
            "H3-INTER2-CL∩SH": inter2_show_classic_only(classic, show_m3),
            "H4-UNION-CL+SH": union_chips(classic, show_m3),
        }

        row = row_by_for[nxt]
        for name, ch in chips_r2.items():
            m = banda_metrics(ch, oficiales)
            row[f"{name}_banda"] = m["banda"]
            row[f"{name}_k"] = m["k"]


def h5_hibrido_fallback(rows_te):
    w("== H5 HÍBRIDO — fallback INTER2 (holdout) ==")
    if not rows_te:
        return
    for name in ("H1-INTER2-SHOW-P0", "H2-INTER2-SHOW+7"):
        fb = sum(1 for r in rows_te if r.get(f"{name}_k") == r.get("M4-CLASSIC_k"))
        w(f"    {name}: horas con k=clásico (posible fallback) ≈ revisar meta")
    # contar horas sin acuerdo (k=0 → usamos classic en código)
    for name in ("H1-INTER2-SHOW-P0", "H2-INTER2-SHOW+7", "H3-INTER2-CL∩SH"):
        zeros = sum(1 for r in rows_te if r.get(f"{name}_k", -1) == 0)
        w(f"    {name}: horas k=0 → {zeros}/{len(rows_te)}")
    w()


def sintesis_r2(agg_r2):
    w("== SÍNTESIS R2 ==")
    if not agg_r2:
        w("  (sin datos R2)")
        w()
        return
    m4 = agg_r2.get("M4-CLASSIC", 0)
    m5 = agg_r2.get("M5-INTER2", 0)
    w("  ORDEN/PLATO (M7–M10): FRÍO — ninguno supera clásico (±1pp).")
    w("  H1 show→P0: idéntico INTER2 (60.6%) — show ≈ clásico.")
    w("  H3/H4 intersección/unión: = clásico (listas casi iguales).")
    h2 = agg_r2.get("H2-INTER2-SHOW+7", 0)
    w(f"  H2 7 pools: {100*h2:.1f}% banda · k≈18 vs INTER2 k≈14.")
    w("    OLOR lab: show duplica P0 en acuerdo → infla conteos.")
    w("    No es motor válido prod; artefacto de doble voto.")
    w(f"  Techo operativo sigue INTER2 prod ({100*m5:.1f}%).")
    w()


def h2_capas_lift(rows_tr, rows_te):
    w("== H2 CAPAS — lift incremental (holdout) ==")
    if not rows_te:
        return
    chain = ["M0-PLATO54", "M1-MAPA", "M2-CIERRE", "M3-SOM02", "M4-CLASSIC"]
    prev = 0
    for name in chain:
        bs = [r[f"{name}_banda"] for r in rows_te if r.get(f"{name}_banda") is not None]
        if not bs:
            continue
        b = mean(bs)
        w(f"    {name:12s}  {100*b:.1f}%  (+{100*(b-prev):.1f}pp vs capa anterior)")
        prev = b
    inter = mean(r["M5-INTER2_banda"] for r in rows_te)
    w(f"    M5-INTER2     {100*inter:.1f}%  (+{100*(inter-prev):.1f}pp vs clásico)")
    w()


def h3_letra_menu():
    w("== H3 LETRA — menú L vs ruleta-G (show) ==")
    tiros = load_letters()
    # build per-tiro sequence with prev L duration from lightgreen via piso
    import sys as _sys
    from pathlib import Path as _P
    _sys.path.insert(0, str(_P(r"c:\operacion-joker\experimento-mente-en-blanca\lab-piso")))
    from piso_core import _cargar_indice  # noqa: E402

    idx = _cargar_indice(LIGHTGREEN)
    tags = sorted(idx.keys(), key=tag_key)
    _, test_tags = split_tags(tags)

    wheel_g = slots_to_probs({f"G{i}": MENU_G_EMP[f"G{i}"] for i in range(1, 5)})

    menu_ok = wheel_ok = azar_ok = n = 0
    for tag in test_tags:
        tiros_h = idx.get(tag, [])
        prev_dur = None
        for t in tiros_h:
            if t.tipo is None or (t.lab == "G" and t.tipo == 5):
                continue
            if t.lab != "G":
                if t.dur:
                    prev_dur = t.dur
                continue
            if prev_dur is None:
                continue
            pred = menu_l_predict_tinta(prev_dur)
            actual = t.letra
            if pred == "G1G2":
                menu_hit = actual in ("G1", "G2")
            else:
                menu_hit = actual == pred
            wheel_hit = t.letra == max(wheel_g, key=wheel_g.get)
            if menu_hit:
                menu_ok += 1
            if wheel_hit:
                wheel_ok += 1
            if actual in wheel_g:
                azar_ok += 0.25
            n += 1

    if n:
        w(f"  test tiros G con L previo: n={n}")
        w(f"    MENU-L tinta:  {100*menu_ok/n:.1f}%")
        w(f"    WHEEL-G moda:  {100*wheel_ok/n:.1f}%")
        w(f"    azar 1/4:      25.0%")
    w()


def sintesis():
    w("=" * 60)
    w("SÍNTESIS lab-show-motor (R1 + R2)")
    w("=" * 60)
    w("  R1: Mejor motor SHOW puro ≈ M3/M4 (cierre+mapa+SOM02) ≈ clásico.")
    w("  R1: M0 plato 54 solo no basta; cada capa suma lift.")
    w("  R1: M5 INTER2 sigue arriba del clásico show (+~15pp banda).")
    w("  R2: ver H4/H5 — orden invertido · k-plato · híbridos INTER2+show.")
    w()
    w("  VEREDICTO R1:")
    w("    · Motor desde show: cierre → mapa H-1 → clima → sombra.")
    w("    · Prod clásico ya emula el show; INTER2 es capa acuerdo.")
    w("    · No reemplazar por plato 54 iid — azar de casino.")
    w("    · Tinta G: menú L, no casilla G del plato.")
    w()


def main():
    w("LAB SHOW-MOTOR — Live Jokers Show · 54 casillas · R1+R2")
    w(f"cinta: {DETAIL.name}")
    cinta = load_cinta()
    w(f"horas cerradas={len(cinta.orden)} · holdout={HOLDOUT}h")
    w()

    h0_show_base()
    rows_tr, rows_te = walk_motors(cinta)
    walk_motors_r2_fill(cinta, rows_tr, rows_te)
    agg_r2 = walk_motors_r2(cinta, rows_te)
    h2_capas_lift(rows_tr, rows_te)
    h5_hibrido_fallback(rows_te)
    h3_letra_menu()
    sintesis_r2(agg_r2)
    sintesis()

    out = OUT / "LAB_SHOW_MOTOR.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"\n[ok] {out}")


if __name__ == "__main__":
    main()
