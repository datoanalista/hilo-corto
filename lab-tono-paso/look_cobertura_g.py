# -*- coding: utf-8 -*-
"""
LOOK: cobertura de G con la estrategia cableada (gatillo + poda + ventana).
Juez de ESTA ficha = G cuyo tiro está en casilla apostable / todas las G de ESA hora.
NO es el juez de corrimiento (banda). LC-01 ±1 = oficio hermano, nota al final.
Cero Jaccard. Cero prod. Cero LIVE. Cero cable.
"""
from __future__ import annotations

import sys
from pathlib import Path
from statistics import median

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
AE = ROOT / "lab-apostador-experto"
sys.path.insert(0, str(AE))
sys.path.insert(0, str(ROOT))

from core_ae import (  # noqa: E402
    HOLDOUT,
    dist_anillo,
    load_horas_y_cinta,
    split_holdout,
    tip_lc01,
)

lines: list[str] = []


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


def qtile(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    ys = sorted(xs)
    i = min(len(ys) - 1, max(0, int(round((len(ys) - 1) * q))))
    return float(ys[i])


def es_g(t) -> bool:
    return str(getattr(t, "color", "")).upper().startswith("G")


def minuto(t) -> int:
    return int(getattr(t, "m0", 0)) % 60


def dur_de(t) -> int | None:
    d = getattr(t, "dur_s", None)
    if d is None:
        d = getattr(t, "dur", None)
    if d is None:
        return None
    try:
        return int(d)
    except (TypeError, ValueError):
        return None


def g_consecutivas_hasta(tiros: list, last_g_idx: int) -> int:
    n = 0
    for i in range(last_g_idx, -1, -1):
        if es_g(tiros[i]):
            n += 1
        else:
            break
    return n


def apostable(
    gap: int | None,
    *,
    plus1: str,
    gaps_win: frozenset[int],
    drought_from: int,
    tren: bool,
    estirada: bool,
) -> tuple[bool, str]:
    """
    plus1: never | tren_estirada | always
    gaps_win: gaps que se apuestan (p.ej. {2,3,4})
    drought_from: gap >= esto = sequía (5 = 4 R tras la G)
    """
    if gap is None:
        return False, "espera_primera"
    if gap >= drought_from:
        return False, "sequia"
    if gap == 1:
        if plus1 == "always":
            return True, "mas1"
        if plus1 == "tren_estirada":
            if tren:
                return True, "tren"
            if estirada:
                return True, "estirada"
            return False, "poda"
        return False, "poda"
    if gap in gaps_win:
        return True, f"gap{gap}"
    return False, "fuera"


def walk_hora(
    h,
    *,
    plus1: str,
    gaps_win: frozenset[int],
    drought_from: int,
    all_shots: bool = False,
) -> dict:
    """
    Una hora = una mesa. No se une la cinta al :00.
    Tras cada G, last G = ancla (como Go! cableado). La G que cae
    no se apuesta a sí misma: se decide el tiro ANTES de ver el color.
    """
    tiros = list(getattr(h, "tiros", None) or [])
    n = len(tiros)
    last_g_idx: int | None = None
    luces: list[int] = []
    bets: list[dict] = []
    gs: list[dict] = []
    rafaga_bets = 0
    rafaga_lens: list[int] = []
    en_rafaga = False

    for i, t in enumerate(tiros):
        gap = None if last_g_idx is None else (i - last_g_idx)
        tren = False
        estirada = False
        if last_g_idx is not None:
            tren = g_consecutivas_hasta(tiros, last_g_idx) >= 2
            dprev = dur_de(tiros[last_g_idx])
            estirada = dprev is not None and dprev >= 100

        if all_shots:
            es_bet, motivo = True, "all"
        else:
            es_bet, motivo = apostable(
                gap,
                plus1=plus1,
                gaps_win=gaps_win,
                drought_from=drought_from,
                tren=tren,
                estirada=estirada,
            )

        if es_bet:
            bets.append({"i": i, "gap": gap, "motivo": motivo, "hit": es_g(t)})
            if en_rafaga or (gap is not None and gap < drought_from):
                rafaga_bets += 1
                en_rafaga = True

        if es_g(t):
            if last_g_idx is None:
                rol = "gatillo_hora"
            elif gap is not None and gap >= drought_from:
                rol = "gatillo_sequia"
            elif gap == 1:
                rol = "seguidora_pegada"
            elif gap is not None and gap in gaps_win:
                rol = "seguidora_ventana"
            else:
                rol = "seguidora_otra"

            tip = tip_lc01(luces) if luces else None
            m = minuto(t)
            banda = bool(tip is not None and dist_anillo(tip, m) <= 1)
            gs.append(
                {
                    "i": i,
                    "gap": gap,
                    "rol": rol,
                    "caught": es_bet,
                    "motivo_bet": motivo,
                    "tren_prev": tren,
                    "estirada_prev": estirada,
                    "dur": dur_de(t),
                    "m0": m,
                    "banda": banda,
                    "tiene_tip": tip is not None,
                }
            )
            luces.append(m)
            last_g_idx = i
            # ráfaga sigue (nueva ancla); no se cierra
            en_rafaga = True
        else:
            if (
                last_g_idx is not None
                and gap is not None
                and gap + 1 >= drought_from
                and en_rafaga
            ):
                if rafaga_bets:
                    rafaga_lens.append(rafaga_bets)
                rafaga_bets = 0
                en_rafaga = False

    if rafaga_bets:
        rafaga_lens.append(rafaga_bets)

    nG = len(gs)
    caught = sum(1 for g in gs if g["caught"])
    return {
        "tag": getattr(h, "tag", "?"),
        "n_tiros": n,
        "nG": nG,
        "caught": caught,
        "cov": (caught / nG) if nG else 0.0,
        "n_bets": len(bets),
        "bets": bets,
        "gs": gs,
        "rafaga_lens": rafaga_lens,
    }


# Oficio: nombre, kwargs de walk
OFICIOS = {
    "ALL": dict(plus1="never", gaps_win=frozenset(), drought_from=10**9, all_shots=True),
    "N3_A": dict(plus1="never", gaps_win=frozenset({2, 3, 4}), drought_from=5),
    "N3_B": dict(plus1="tren_estirada", gaps_win=frozenset({2, 3, 4}), drought_from=5),
    "N4_A": dict(plus1="never", gaps_win=frozenset({2, 3, 4, 5}), drought_from=6),
    "N4_B": dict(plus1="tren_estirada", gaps_win=frozenset({2, 3, 4, 5}), drought_from=6),
    "SOLO1": dict(plus1="always", gaps_win=frozenset(), drought_from=2),
}


def tren_eventos(docs: list[dict]) -> dict:
    """Corridas de 2+ G pegadas (índices consecutivos)."""
    n_ev = 0
    n_h = 0
    n_g_en_tren = 0
    n_seg = 0  # G 2ª+ de cada corrida
    catch_a = 0
    catch_b = 0
    catch_b_2da_estirada = 0
    catch_b_3plus_tren = 0
    miss_b_2da = 0
    horas_a = 0
    horas_b = 0
    for d in docs:
        gs = d["gs"]
        if not gs:
            continue
        runs: list[list[dict]] = []
        cur = [gs[0]]
        for g in gs[1:]:
            if g["gap"] == 1:
                cur.append(g)
            else:
                if len(cur) >= 2:
                    runs.append(cur)
                cur = [g]
        if len(cur) >= 2:
            runs.append(cur)
        if not runs:
            continue
        n_h += 1
        got_a = got_b = False
        for run in runs:
            n_ev += 1
            n_g_en_tren += len(run)
            for k, g in enumerate(run):
                if k == 0:
                    continue
                n_seg += 1
                # (A) nunca apuesta +1
                a_ok = False
                # (B) 2ª de corrida: solo si G previa Estirada
                #     3ª+: Tren (ya hay 2+ G)
                prev = run[k - 1]
                if k == 1:
                    b_ok = bool(prev["dur"] is not None and prev["dur"] >= 100)
                    if b_ok:
                        catch_b_2da_estirada += 1
                    else:
                        miss_b_2da += 1
                else:
                    b_ok = True
                    catch_b_3plus_tren += 1
                if a_ok:
                    catch_a += 1
                    got_a = True
                if b_ok:
                    catch_b += 1
                    got_b = True
        if got_a:
            horas_a += 1
        if got_b:
            horas_b += 1
    return {
        "n_ev": n_ev,
        "n_h": n_h,
        "n_g_en_tren": n_g_en_tren,
        "n_seg": n_seg,
        "catch_a": catch_a,
        "catch_b": catch_b,
        "catch_b_2da_estirada": catch_b_2da_estirada,
        "catch_b_3plus_tren": catch_b_3plus_tren,
        "miss_b_2da": miss_b_2da,
        "horas_a": horas_a,
        "horas_b": horas_b,
    }


def resumir(docs: list[dict]) -> dict:
    gs = [g for d in docs for g in d["gs"]]
    bets = [b for d in docs for b in d["bets"]]
    bets_h = [d["n_bets"] for d in docs]
    cov_h = [d["cov"] for d in docs if d["nG"]]
    raf = [x for d in docs for x in d["rafaga_lens"]]
    gat_h = [g for g in gs if g["rol"] == "gatillo_hora"]
    gat_s = [g for g in gs if g["rol"] == "gatillo_sequia"]
    gat = gat_h + gat_s
    seg = [g for g in gs if g["rol"].startswith("seguidora")]
    peg = [g for g in gs if g["rol"] == "seguidora_pegada"]
    ven = [g for g in gs if g["rol"] == "seguidora_ventana"]
    caught = [g for g in gs if g["caught"]]
    caught_gat = [g for g in gat if g["caught"]]
    caught_seg = [g for g in seg if g["caught"]]
    by_gap: dict[str, list] = {}
    for g in gs:
        key = "hora" if g["gap"] is None else (str(g["gap"]) if g["gap"] <= 8 else "9+")
        by_gap.setdefault(key, []).append(g)
    g_tip = [g for g in caught if g["tiene_tip"]]
    g_banda = [g for g in g_tip if g["banda"]]
    # destino seguidoras: gap 1..4 vs gap≥5 (esas son gatillo_sequia)
    g_prev = [g for g in gs if g["gap"] is not None]
    dest = {
        "g1": [g for g in g_prev if g["gap"] == 1],
        "g24": [g for g in g_prev if g["gap"] in (2, 3, 4)],
        "g5p": [g for g in g_prev if g["gap"] >= 5],
    }
    return {
        "horas": len(docs),
        "nG": len(gs),
        "n_tiros": sum(d["n_tiros"] for d in docs),
        "caught": len(caught),
        "apuestas": len(bets),
        "g_por_ap": (len(caught) / len(bets)) if bets else 0.0,
        "med_bets_h": median(bets_h) if bets_h else 0,
        "p90_bets_h": qtile(bets_h, 0.90),
        "max_bets_h": max(bets_h) if bets_h else 0,
        "med_cov_h": median(cov_h) if cov_h else 0.0,
        "p10_cov_h": qtile(cov_h, 0.10) if cov_h else 0.0,
        "p90_cov_h": qtile(cov_h, 0.90) if cov_h else 0.0,
        "n_gat": len(gat),
        "n_gat_hora": len(gat_h),
        "n_gat_seq": len(gat_s),
        "n_seg": len(seg),
        "caught_gat": len(caught_gat),
        "caught_seg": len(caught_seg),
        "n_peg": len(peg),
        "caught_peg": sum(1 for g in peg if g["caught"]),
        "n_ven": len(ven),
        "caught_ven": sum(1 for g in ven if g["caught"]),
        "dest": dest,
        "by_gap": by_gap,
        "g_tip": len(g_tip),
        "g_banda": len(g_banda),
        "med_raf": median(raf) if raf else 0,
        "p90_raf": qtile(raf, 0.90) if raf else 0.0,
        "max_raf": max(raf) if raf else 0,
        "n_raf": len(raf),
        "bets_h": bets_h,
        "docs": docs,
        "tren": tren_eventos(docs),
    }


def foto_oficio(nombre: str, r: dict) -> None:
    w(f"  {nombre:<7} | {r['apuestas']:>6} | {pct(r['caught'], r['nG']):>8} |"
      f" {r['g_por_ap']*100:>6.1f}% | {r['horas']:>5} |"
      f" med {r['med_bets_h']:.0f}  p90 {r['p90_bets_h']:.0f}  max {r['max_bets_h']:.0f}")


def bloque_split(nombre: str, horas) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for key, kw in OFICIOS.items():
        docs = [walk_hora(h, **kw) for h in horas]
        out[key] = resumir(docs)
    return out


def foto_destino(r: dict, etiqueta: str) -> None:
    d = r["dest"]
    g1, g24, g5 = d["g1"], d["g24"], d["g5p"]
    n_prev = len(g1) + len(g24) + len(g5)
    w(f"  {etiqueta}")
    w(f"    G con previa (no 1ª de hora): {n_prev}")
    w(
        f"    gap=1 pegada:     {len(g1):>5}  {pct(len(g1), n_prev)}"
        f"   · atrapadas {sum(1 for g in g1 if g['caught'])}/{len(g1)}"
        f"  {pct(sum(1 for g in g1 if g['caught']), len(g1))}"
    )
    w(
        f"    gap 2..4 ventana: {len(g24):>5}  {pct(len(g24), n_prev)}"
        f"   · atrapadas {sum(1 for g in g24 if g['caught'])}/{len(g24)}"
        f"  {pct(sum(1 for g in g24 if g['caught']), len(g24))}"
    )
    w(
        f"    gap≥5 sequía:     {len(g5):>5}  {pct(len(g5), n_prev)}"
        f"   · atrapadas {sum(1 for g in g5 if g['caught'])}/{len(g5)}"
        f"  {pct(sum(1 for g in g5 if g['caught']), len(g5))}"
        f"   (son gatillo que rompe sequía; no se apuestan)"
    )


def foto_roles(r: dict) -> None:
    w(
        f"    G-gatillo: {r['n_gat']}  {pct(r['n_gat'], r['nG'])}"
        f"  · 1ª de hora {r['n_gat_hora']}  · rompe sequía {r['n_gat_seq']}"
        f"  · atrapadas {r['caught_gat']}  {pct(r['caught_gat'], r['n_gat'])}"
    )
    w(
        f"    G-seguidoras (ventana o pegada):    {r['n_seg']}"
        f"  atrapadas {r['caught_seg']}  {pct(r['caught_seg'], r['n_seg'])}"
    )
    w(
        f"      de ellas pegadas gap=1: {r['n_peg']}"
        f"  atrapadas {r['caught_peg']}  {pct(r['caught_peg'], r['n_peg'])}"
    )
    w(
        f"      de ellas ventana:       {r['n_ven']}"
        f"  atrapadas {r['caught_ven']}  {pct(r['caught_ven'], r['n_ven'])}"
    )


def foto_tren(tr: dict, etiqueta: str) -> None:
    w(f"  {etiqueta}")
    w(
        f"    horas con ≥1 tren (2+ G pegadas): {tr['n_h']}"
        f"  · eventos tren: {tr['n_ev']}"
        f"  · G en tren: {tr['n_g_en_tren']}"
        f"  · G-seguidoras del tren (2ª+): {tr['n_seg']}"
    )
    w(
        f"    (A) poda siempre: coge {tr['catch_a']}/{tr['n_seg']}"
        f"  {pct(tr['catch_a'], tr['n_seg'])}"
        f"  · horas donde coge alguna: {tr['horas_a']}/{tr['n_h']}"
    )
    w(
        f"    (B) Tren/Estirada: coge {tr['catch_b']}/{tr['n_seg']}"
        f"  {pct(tr['catch_b'], tr['n_seg'])}"
        f"  · horas donde coge alguna: {tr['horas_b']}/{tr['n_h']}"
    )
    w(
        f"      2ª del tren vía Estirada (prev ≥100s): {tr['catch_b_2da_estirada']}"
        f"  · 2ª perdida (prev no larga): {tr['miss_b_2da']}"
    )
    w(
        f"      3ª+ vía Tren (ya hay 2+ G): {tr['catch_b_3plus_tren']}"
    )


def main() -> None:
    w("LOOK · Cobertura de G · estrategia cableada (gatillo + poda + ventana)")
    w("Fecha: 2026-09-06")
    w("Gatillo = FORMA: no se apuesta la G que abre. No corona «perder la primera».")
    w("JUEZ = cobertura hora a hora: G de ESA hora cuyo tiro está en casilla apostable")
    w("/ todas las G de ESA hora. NO es banda. NO es PnL color.")
    w("")
    w("Política causal (como Go! cableado; last G = ancla; no se une al :00):")
    w("  1. La G que abre (1ª de hora / 1ª que rompe sequía) se ESPERA. No se apuesta.")
    w("  2. Tras esa G: NO apostar +1, salvo variante.")
    w("     (A) poda siempre = look de apuesta N.")
    w("     (B) poda salvo Tren (2+ G ya pegadas) o Estirada (dur≥100s) = lo cableado.")
    w("  3. Apostar +2,+3,+4. Si 4 R tras la G (gap≥5) → sequía, silencio hasta la")
    w("     próxima G (otra vez gatillo, no se apuesta).")
    w("  4. Cada G nueva ancla de nuevo (como diagnosticarGo). La G no se apuesta a")
    w("     sí misma: la casilla se decide antes de ver el color.")
    w("Cero Jaccard. Cero cable al dashboard.")
    w("")

    horas, _cinta = load_horas_y_cinta()
    train, hold = split_holdout(horas, HOLDOUT)
    w(f"Cinta load_horas_y_cinta: {len(horas)} h · train {len(train)} · holdout {len(hold)}")
    w(f"HOLDOUT={HOLDOUT} (core_ae). Horas = las de load_cinta (≥1 G).")

    def base_g(hs) -> tuple[int, int]:
        n = g = 0
        for h in hs:
            for t in getattr(h, "tiros", None) or []:
                n += 1
                if es_g(t):
                    g += 1
        return g, n

    g_tr, n_tr = base_g(train)
    g_ho, n_ho = base_g(hold)
    w(
        f"Base P(tiro=G) — train {g_tr}/{n_tr} {pct(g_tr, n_tr)}"
        f" · holdout {g_ho}/{n_ho} {pct(g_ho, n_ho)}"
    )
    w(f"G/hora mediana train: {g_tr/len(train):.1f}  hold: {g_ho/len(hold):.1f}"
      if train and hold else "")

    splits = {
        "TRAIN": bloque_split("TRAIN", train),
        "HOLDOUT 72 h": bloque_split("HOLDOUT", hold),
    }

    for split_name, off in splits.items():
        a, b = off["N3_A"], off["N3_B"]
        w(f"\n════════ {split_name}  {a['horas']} h · {a['nG']} G ════════")
        w("── Cobertura (juez) · N=3 ──")
        w(
            f"  (A) poda siempre:     {pct(a['caught'], a['nG'])}"
            f"   {a['caught']}/{a['nG']}"
            f"   · apuestas {a['apuestas']}"
            f"   · G/apuesta {a['g_por_ap']*100:.1f}%"
        )
        w(
            f"  (B) Tren/Estirada:    {pct(b['caught'], b['nG'])}"
            f"   {b['caught']}/{b['nG']}"
            f"   · apuestas {b['apuestas']}"
            f"   · G/apuesta {b['g_por_ap']*100:.1f}%"
        )
        w(
            f"  cobertura hora a hora (B): mediana {b['med_cov_h']*100:.1f}%"
            f"  · p10 {b['p10_cov_h']*100:.1f}%"
            f"  · p90 {b['p90_cov_h']*100:.1f}%"
        )
        w("  Apuestas/hora (B): "
          f"mediana {b['med_bets_h']:.0f}  p90 {b['p90_bets_h']:.0f}  max {b['max_bets_h']:.0f}"
          f"   · no es 40")
        w("  Apuestas/hora (A): "
          f"mediana {a['med_bets_h']:.0f}  p90 {a['p90_bets_h']:.0f}  max {a['max_bets_h']:.0f}")
        w(
            f"  Apuestas hasta sequía (B, ventanas apiladas si cae G): n={b['n_raf']}"
            f"  mediana {b['med_raf']:.0f}  p90 {b['p90_raf']:.0f}  max {b['max_raf']:.0f}"
        )
        w("    Techo por ancla = 3 casillas (+2,+3,+4), +1 si Tren/Estirada.")
        w("    Si cae G, ancla de nuevo: no son 40 tiros ciegos, es racimo sobre racimo.")
        w("  Roles (B):")
        foto_roles(b)
        w("  Roles (A):")
        foto_roles(a)
        foto_destino(b, "Destino de G-con-previa · (B)")
        foto_destino(a, "Destino de G-con-previa · (A)")

        w("\n── Oficio comparado (apuestas | %G atrapadas | G/apuesta | horas | ap/hora) ──")
        w("  oficio  |    ap. |  G atrap |  G/ap  | horas | apuestas/hora")
        w("  " + "-" * 68)
        for key, label in (
            ("ALL", "ALL"),
            ("N3_A", "N3_A"),
            ("N3_B", "N3_B"),
            ("N4_A", "N4_A"),
            ("N4_B", "N4_B"),
            ("SOLO1", "SOLO+1"),
        ):
            foto_oficio(label, off[key])

        w("\n── Tren (2+ G pegadas) ──")
        foto_tren(b["tren"], f"{split_name} · conteo de eventos (misma cinta)")

        w(
            f"  Oficio hermano · de las G atrapadas (B) con tip LC-01:"
            f"  {b['g_banda']}/{b['g_tip']} minuto en LC-01 ±1"
            f"  {pct(b['g_banda'], b['g_tip'])}"
            f"   (NO es el score de cobertura)"
        )

    tr_a, tr_b = splits["TRAIN"]["N3_A"], splits["TRAIN"]["N3_B"]
    ho_a, ho_b = splits["HOLDOUT 72 h"]["N3_A"], splits["HOLDOUT 72 h"]["N3_B"]
    tr_all, ho_all = splits["TRAIN"]["ALL"], splits["HOLDOUT 72 h"]["ALL"]
    tr_s1, ho_s1 = splits["TRAIN"]["SOLO1"], splits["HOLDOUT 72 h"]["SOLO1"]
    tr_n4, ho_n4 = splits["TRAIN"]["N4_B"], splits["HOLDOUT 72 h"]["N4_B"]

    w("\n════════════════════════════════ LEAD ════════════════════════════════")
    w(
        f"  % G atrapadas (B, cableado N=3):"
        f"  train {pct(tr_b['caught'], tr_b['nG'])}"
        f"   holdout {pct(ho_b['caught'], ho_b['nG'])}"
    )
    w(
        f"  % G atrapadas (A, poda siempre):"
        f"  train {pct(tr_a['caught'], tr_a['nG'])}"
        f"   holdout {pct(ho_a['caught'], ho_a['nG'])}"
    )
    w(
        f"  Apuestas/hora (B): train med {tr_b['med_bets_h']:.0f}"
        f" p90 {tr_b['p90_bets_h']:.0f} max {tr_b['max_bets_h']:.0f}"
        f"  · hold med {ho_b['med_bets_h']:.0f}"
        f" p90 {ho_b['p90_bets_h']:.0f} max {ho_b['max_bets_h']:.0f}"
    )
    def foto_perdida(lab: str, r: dict) -> None:
        miss_peg = r["n_peg"] - r["caught_peg"]
        w(f"  Qué se pierde ({lab}, suma 100%):")
        w(
            f"    atrapadas           {r['caught']:>5}/{r['nG']}  {pct(r['caught'], r['nG'])}"
        )
        w(
            f"    gatillo 1ª de hora  {r['n_gat_hora']:>5}/{r['nG']}  {pct(r['n_gat_hora'], r['nG'])}"
        )
        w(
            f"    gatillo rompe-seq   {r['n_gat_seq']:>5}/{r['nG']}  {pct(r['n_gat_seq'], r['nG'])}"
            f"   (gap≥5; nueva isla)"
        )
        w(
            f"    pegada no except.   {miss_peg:>5}/{r['nG']}  {pct(miss_peg, r['nG'])}"
            f"   (2ª de GG, 1ª no larga)"
        )

    foto_perdida("B train", tr_b)
    foto_perdida("B hold", ho_b)

    w("\n════════════════════════════════ ¿EL TRADE ES RAZONABLE? ════════════════════════════════")
    w("  Comparar oficios (no coronar N=3 por un racimo):")
    w(
        f"  ALL   train {pct(tr_all['caught'], tr_all['nG'])} G con {tr_all['med_bets_h']:.0f} ap/h"
        f"  G/ap {tr_all['g_por_ap']*100:.1f}%   · hold {pct(ho_all['caught'], ho_all['nG'])}"
        f"  {ho_all['med_bets_h']:.0f} ap/h"
    )
    w(
        f"  N3_B  train {pct(tr_b['caught'], tr_b['nG'])} G con {tr_b['med_bets_h']:.0f} ap/h"
        f"  G/ap {tr_b['g_por_ap']*100:.1f}%   · hold {pct(ho_b['caught'], ho_b['nG'])}"
        f"  {ho_b['med_bets_h']:.0f} ap/h"
    )
    w(
        f"  N4_B  train {pct(tr_n4['caught'], tr_n4['nG'])} G con {tr_n4['med_bets_h']:.0f} ap/h"
        f"  G/ap {tr_n4['g_por_ap']*100:.1f}%   · hold {pct(ho_n4['caught'], ho_n4['nG'])}"
        f"  {ho_n4['med_bets_h']:.0f} ap/h"
    )
    w(
        f"  SOLO+1 train {pct(tr_s1['caught'], tr_s1['nG'])} G con {tr_s1['med_bets_h']:.0f} ap/h"
        f"  G/ap {tr_s1['g_por_ap']*100:.1f}%   · hold {pct(ho_s1['caught'], ho_s1['nG'])}"
        f"  {ho_s1['med_bets_h']:.0f} ap/h"
    )

    # números para razones
    seg_tr = tr_b["n_seg"]
    w("")
    w("  Razones (la G inicial es FORMA de gatillo; el número decide si el trade cabe):")
    w(
        f"  1. Impuesto del gatillo: train {pct(tr_b['n_gat'], tr_b['nG'])} de las G"
        f" no tienen casilla previa ({pct(tr_b['n_gat_hora'], tr_b['nG'])} 1ª de hora +"
        f" {pct(tr_b['n_gat_seq'], tr_b['nG'])} rompe-sequía). Apostarlas = ALL"
        f" (~{tr_all['med_bets_h']:.0f} ap/h), no 3 por ancla."
    )
    w(
        f"  2. Cosecha de seguidoras (B): train {pct(tr_b['caught_seg'], tr_b['n_seg'])}"
        f" de las {seg_tr} G-seguidoras caen en casilla apostable."
        f" Hold {pct(ho_b['caught_seg'], ho_b['n_seg'])}."
        f" Eso es el racimo corto (gap 2..4), no la densidad ciega."
    )
    w(
        f"  3. La pegada (+1) no es el racimo: train {tr_b['n_peg']} G en gap=1"
        f" ({pct(tr_b['n_peg'], tr_b['nG'])} de todas)."
        f" SOLO+1 las cobra todas y deja el resto."
        f" (A) pierde las {tr_a['n_peg']}. (B) recupera"
        f" {tr_b['caught_peg']}/{tr_b['n_peg']} {pct(tr_b['caught_peg'], tr_b['n_peg'])}"
        f" (Tren 3ª+ o Estirada)."
    )
    w(
        f"  4. Sequía gap≥5: train {len(tr_b['dest']['g5p'])} G"
        f" {pct(len(tr_b['dest']['g5p']), tr_b['nG'])}."
        f" No son seguidoras perdidas de ESTA ráfaga: son el próximo gatillo."
        f" N=4 alarga un tiro y sube cobertura"
        f" {pct(tr_n4['caught'], tr_n4['nG'])} vs {pct(tr_b['caught'], tr_b['nG'])}"
        f" a costa de más apuestas ({tr_n4['med_bets_h']:.0f} vs {tr_b['med_bets_h']:.0f}/h)."
    )
    w(
        f"  5. Volumen: B no es 40 ni 59 ap/h. Train mediana {tr_b['med_bets_h']:.0f}"
        f" · p90 {tr_b['p90_bets_h']:.0f} · max {tr_b['max_bets_h']:.0f}."
        f" Techo por ancla = 3 (+1 si inercia). Si el racimo sigue, se apila otra terna."
        f" ALL gasta {tr_all['med_bets_h']:.0f}/h para el 100% de las G."
        f" G/apuesta de B ({tr_b['g_por_ap']*100:.1f}%) vs p de la hora"
        f" ({g_tr/n_tr*100:.1f}%): el extra es inercia (pegada tras larga/Tren),"
        f" no un filo de color en +2..+4 (ahí G/ap ≈ p)."
    )
    trt = tr_b["tren"]
    hot = ho_b["tren"]
    w(
        f"  6. Tren: (A) coge 0/{trt['n_seg']} pegadas de tren (poda siempre)."
        f" (B) coge {trt['catch_b']}/{trt['n_seg']} {pct(trt['catch_b'], trt['n_seg'])}"
        f" train · hold {hot['catch_b']}/{hot['n_seg']} {pct(hot['catch_b'], hot['n_seg'])}."
        f" Matiz: la 2ª de un GG no es Tren todavía (hace falta 2 G ya cerradas)."
        f" (B) salva la 2ª solo si la 1ª fue Estirada ({trt['catch_b_2da_estirada']} train);"
        f" la 3ª+ sí entra por Tren ({trt['catch_b_3plus_tren']} train)."
        f" (A) pierde el tren entero de pegadas."
    )

    w("")
    w("  Lectura (no cablear):")
    w("  · 3 casillas por ancla bastan para el racimo gap 2..4 (100% de esas).")
    w("  · La G inicial se pierde por oficio: no hay casilla antes. Es cara")
    w("    (~10% 1ª de hora + ~40% rompe-sequía = ~mitad de las G; isla, no mancha).")
    w("    El 100% exige ~50–60 ap/h (ALL).")
    w("  · (B) vs (A) no es un puñado: +9 pp train / +10 pp hold, todas en la pegada.")
    w("    (A) pierde el tren entero de pegadas. (B) no coge el tren entero:")
    w("    2ª solo si Estirada; 3ª+ sí por Tren. Tras G≥100s, el +1 ya es G ~89%")
    w("    (tras largo ≈95, salvo fuga): Estirada no es adorno.")
    w("  · N=3 es el oficio del racimo corto. N=4 compra G en gap=5 (el primer")
    w("    tiro de lo que N=3 llama sequía) a ~+4 ap/h. ALL compra todas.")
    w("    SOLO+1 es la sombra: solo la pegada, no la ventana.")
    w("  · Oficio hermano: de las G que sí cayeron en casilla, LC-01 ±1 se anota")
    w("    en cada split. No es este juez.")

    outp = LAB / "reports" / "LOOK_COBERTURA_G.txt"
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"\nGuardado: {outp}")


if __name__ == "__main__":
    main()
