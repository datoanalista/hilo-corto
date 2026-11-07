# -*- coding: utf-8 -*-
"""
R1 senior-poda: barrido fino de la PUERTA (no ML).
  python eval_r1.py → reports/LAB_SENIOR_PODA_R1.txt
Cero prod. Cero LIVE. Cero ML/fuzzy. Cero Jaccard.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
AE = ROOT / "lab-apostador-experto"
sys.path.insert(0, str(AE))
sys.path.insert(0, str(ROOT))

OUT = LAB / "reports"
OUT.mkdir(exist_ok=True)

from core_ae import (  # noqa: E402
    HOLDOUT,
    STAKE_WEAK,
    Decision,
    MesaChips,
    acuerdo_tip,
    dist_anillo,
    hit_banda,
    indices_g_en_tiros,
    load_horas_y_cinta,
    precompute_mesas,
    split_holdout,
    tip_lc01,
)

# 7 puertas pedidas + 1 forma del catálogo (PODA G-R: ancla tras R, no pegada)
PUERTAS = (
    "PODA_R0",
    "PODA_SIEMPRE",
    "VENTANA_23",
    "VENTANA_2345",
    "SOLO_ZONA",
    "GATILLO_HORA",
    "ESTIRADA_ONLY",
    "ENTRADA_GR",
)
CONTROL = "CONTROL_AYUDA_P8"
POLS = PUERTAS + (CONTROL,)

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


def es_g(t) -> bool:
    return str(getattr(t, "color", "")).upper().startswith("G")


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


def puerta_base(
    gap: int,
    tren: bool,
    estirada: bool,
    *,
    gaps_win: frozenset[int],
    drought_from: int,
    plus1: str,
) -> tuple[bool, str]:
    """plus1: never | tren_estirada | estirada."""
    if gap >= drought_from:
        return False, "sequia"
    if gap == 1:
        if plus1 == "never":
            return False, "poda_mas1"
        if plus1 == "estirada":
            if estirada:
                return True, "estirada"
            return False, "poda_mas1"
        if tren:
            return True, "tren"
        if estirada:
            return True, "estirada"
        return False, "poda_mas1"
    if gap in gaps_win:
        return True, f"gap{gap}"
    return False, "fuera"


def decidir(
    pol: str,
    *,
    gap: int,
    tren: bool,
    estirada: bool,
    i_ancla: int,
    gap_prev: int | None,
    tip: int,
    m_est: int,
    acuerdo_p8: bool,
) -> tuple[str, int, list[str]]:
    win234 = frozenset({2, 3, 4})
    if pol in ("PODA_R0", "SOLO_ZONA", "GATILLO_HORA", "ENTRADA_GR", CONTROL):
        go, mot = puerta_base(
            gap, tren, estirada,
            gaps_win=win234, drought_from=5, plus1="tren_estirada",
        )
    elif pol == "PODA_SIEMPRE":
        go, mot = puerta_base(
            gap, tren, estirada,
            gaps_win=win234, drought_from=5, plus1="never",
        )
    elif pol == "VENTANA_23":
        go, mot = puerta_base(
            gap, tren, estirada,
            gaps_win=frozenset({2, 3}), drought_from=5, plus1="tren_estirada",
        )
    elif pol == "VENTANA_2345":
        go, mot = puerta_base(
            gap, tren, estirada,
            gaps_win=frozenset({2, 3, 4, 5}), drought_from=6, plus1="tren_estirada",
        )
    elif pol == "ESTIRADA_ONLY":
        go, mot = puerta_base(
            gap, tren, estirada,
            gaps_win=win234, drought_from=5, plus1="estirada",
        )
    else:
        return "NO_GO", 0, ["desconocida"]

    if pol == "GATILLO_HORA" and i_ancla == 0:
        return "NO_GO", 0, ["lead"]
    if pol == "ENTRADA_GR" and gap_prev is not None and gap_prev == 1:
        return "NO_GO", 0, ["ancla_pegada"]
    if pol == "SOLO_ZONA":
        if not go:
            return "NO_GO", 0, [mot]
        if not hit_banda(tip, m_est):
            return "NO_GO", 0, ["fuera_zona"]
        return "GO_WEAK", STAKE_WEAK, [mot, "zona"]
    if not go:
        return "NO_GO", 0, [mot]
    if pol == CONTROL:
        if acuerdo_p8:
            return "GO_WEAK", STAKE_WEAK, [mot, "ayuda_p8"]
        return "NO_GO", 0, [mot, "sin_ayuda_p8"]
    return "GO_WEAK", STAKE_WEAK, [mot]


@dataclass
class WalkOut:
    decs: dict[str, list[Decision]] = field(
        default_factory=lambda: {p: [] for p in POLS}
    )
    por_hora: dict[str, dict[str, list[Decision]]] = field(
        default_factory=lambda: {p: defaultdict(list) for p in POLS}
    )
    motivos_go: dict[str, dict[str, int]] = field(
        default_factory=lambda: {p: defaultdict(int) for p in POLS}
    )
    zona_diag: dict[str, int] = field(
        default_factory=lambda: {
            "n_poda": 0,
            "m_est_en_banda": 0,
            "real_en_banda": 0,
            "ambos": 0,
            "solo_est": 0,
            "solo_real": 0,
            "ninguno": 0,
            "d0": 0,
            "d1": 0,
            "d2": 0,
            "d3p": 0,
        }
    )


def walk(horas, mesas: dict[str, MesaChips]) -> WalkOut:
    out = WalkOut()
    for h in horas:
        gs = sorted(h.gs, key=lambda g: g.m0)
        if len(gs) < 2:
            continue
        tiros = list(getattr(h, "tiros", None) or [])
        idxs = indices_g_en_tiros(h)
        mesa = mesas.get(h.tag) or MesaChips([], [])
        chips_p8 = mesa.inter2 or mesa.classic
        luces: list[int] = []
        for i in range(len(gs) - 1):
            luces.append(gs[i].m0)
            tip = tip_lc01(luces)
            if tip is None:
                continue
            real = gs[i + 1].m0
            hit = hit_banda(tip, real)
            if len(idxs) >= i + 2:
                gap = idxs[i + 1] - idxs[i]
                ancla = idxs[i]
            else:
                gap = 1
                ancla = idxs[i] if i < len(idxs) else 0
            tren = g_consecutivas_hasta(tiros, ancla) >= 2 if tiros else False
            dprev = dur_de(tiros[ancla]) if tiros and ancla < len(tiros) else None
            estirada = dprev is not None and dprev >= 100
            gap_prev = None
            if i >= 1 and len(idxs) >= i + 1:
                gap_prev = idxs[i] - idxs[i - 1]
            m_est = (int(gs[i].m0) + int(gap)) % 60
            ac_p8 = acuerdo_tip(tip, chips_p8)
            go_r0, _ = puerta_base(
                gap, tren, estirada,
                gaps_win=frozenset({2, 3, 4}), drought_from=5, plus1="tren_estirada",
            )
            if go_r0:
                out.zona_diag["n_poda"] += 1
                est_ok = hit_banda(tip, m_est)
                d_er = dist_anillo(m_est, real)
                if d_er == 0:
                    out.zona_diag["d0"] += 1
                elif d_er == 1:
                    out.zona_diag["d1"] += 1
                elif d_er == 2:
                    out.zona_diag["d2"] += 1
                else:
                    out.zona_diag["d3p"] += 1
                if est_ok:
                    out.zona_diag["m_est_en_banda"] += 1
                if hit:
                    out.zona_diag["real_en_banda"] += 1
                if est_ok and hit:
                    out.zona_diag["ambos"] += 1
                elif est_ok and not hit:
                    out.zona_diag["solo_est"] += 1
                elif (not est_ok) and hit:
                    out.zona_diag["solo_real"] += 1
                else:
                    out.zona_diag["ninguno"] += 1
            for pol in POLS:
                kind, stake, reasons = decidir(
                    pol,
                    gap=gap,
                    tren=tren,
                    estirada=estirada,
                    i_ancla=i,
                    gap_prev=gap_prev,
                    tip=tip,
                    m_est=m_est,
                    acuerdo_p8=ac_p8,
                )
                pnl = float(stake if hit else -stake) if stake > 0 else 0.0
                d = Decision(
                    tag=h.tag,
                    tip=tip,
                    real=real,
                    policy=pol,
                    kind=kind,
                    stake=stake,
                    hit=hit,
                    pnl=pnl,
                    score=float(gap),
                    acuerdo=ac_p8,
                    ewma=0.0,
                    reasons=reasons,
                )
                out.decs[pol].append(d)
                out.por_hora[pol][h.tag].append(d)
                if stake > 0:
                    out.motivos_go[pol][reasons[0]] += 1
    return out


def resumen_decs(decs: list[Decision]) -> dict:
    goes = [d for d in decs if d.stake > 0]
    hits = [d for d in goes if d.hit]
    ex = sum(1 for d in goes if dist_anillo(d.tip, d.real) == 0)
    pm1 = sum(1 for d in goes if dist_anillo(d.tip, d.real) == 1)
    pnl = sum(d.pnl for d in decs)
    n = len(decs)
    ng = len(goes)
    return {
        "n": n,
        "go": ng,
        "nogo": n - ng,
        "cov": (ng / n) if n else 0.0,
        "hit": len(hits),
        "hit_rate": (len(hits) / ng) if ng else 0.0,
        "exacto": (ex / ng) if ng else 0.0,
        "borde": (pm1 / ng) if ng else 0.0,
        "pnl": pnl,
        "avg": (pnl / n) if n else 0.0,
    }


def juez_hora(por_hora: dict[str, list[Decision]]) -> dict:
    tags = list(por_hora)
    n_h = len(tags)
    pnls = []
    cobraron = 0
    verdes = 0
    con_go = 0
    for tag in tags:
        ds = por_hora[tag]
        goes = [d for d in ds if d.stake > 0]
        pnl = sum(d.pnl for d in ds)
        pnls.append(pnl)
        if goes:
            con_go += 1
            if any(d.hit for d in goes):
                cobraron += 1
        if pnl > 0:
            verdes += 1
    return {
        "n_h": n_h,
        "con_go": con_go,
        "cobraron": cobraron,
        "verdes": verdes,
        "med_pnl": median(pnls) if pnls else 0.0,
        "sum_pnl": sum(pnls),
    }


def dump_pol(label: str, r: dict, h: dict | None = None) -> None:
    w(f"  [{label}]")
    w(
        f"    eventos={r['n']}  GO={r['go']} ({pct(r['go'], r['n'])})  "
        f"NO_GO={r['nogo']}"
    )
    if r["go"]:
        w(
            f"    exacto {pct(int(r['exacto'] * r['go']), r['go'])}  "
            f"borde {pct(int(r['borde'] * r['go']), r['go'])}  "
            f"banda {pct(r['hit'], r['go'])}"
        )
    else:
        w("    sin GO")
    w(f"    pnl={r['pnl']:+.1f}  avg/evento={r['avg']:+.4f}")
    if h:
        w(
            f"    hora a hora: {h['n_h']} h · con GO {h['con_go']} · "
            f"cobraron banda {h['cobraron']}/{h['con_go'] or h['n_h']} "
            f"({pct(h['cobraron'], h['con_go'] or 1)}) · "
            f"PnL>0 {h['verdes']}/{h['n_h']} ({pct(h['verdes'], h['n_h'])}) · "
            f"med PnL/h {h['med_pnl']:+.1f}"
        )


def fila_cmp(name: str, r: dict, base: dict) -> str:
    return (
        f"  {name:<16} cov {pct(r['go'], r['n'])}  "
        f"banda {pct(r['hit'], r['go'])}  "
        f"pnl {r['pnl']:+.0f}  "
        f"Δbanda {(r['hit_rate'] - base['hit_rate']) * 100:+.1f}pp  "
        f"Δpnl {r['pnl'] - base['pnl']:+.0f}  "
        f"Δcov {(r['cov'] - base['cov']) * 100:+.1f}pp"
    )


def main() -> None:
    w("LAB SENIOR-PODA — R1")
    w("barrido de PUERTA (formas: ventana / +1 / zona / gatillo / ancla)")
    w("chip: LC-01 minutos ±1 · juez: banda d<=1 + PnL 1:1 · hora a hora")
    w("CERO prod · CERO ML/fuzzy · CERO Jaccard · CERO P(tiro=G) como veredicto")
    w("3/4/Tren = FORMAS. No se coronan. Holdout 72 = el de R0 (no novedad).")
    w()

    horas, cinta = load_horas_y_cinta()
    w("precompute mesas (solo control AYUDA; las puertas no necesitan chips)…")
    mesas = precompute_mesas(cinta)
    train, hold = split_holdout(horas, HOLDOUT)

    def _mesa_ok(h) -> bool:
        m = mesas.get(h.tag)
        return bool(m and (m.inter2 or m.classic))

    n_tr_m = sum(1 for h in train if _mesa_ok(h))
    n_ho_m = sum(1 for h in hold if _mesa_ok(h))
    w(f"n={len(horas)} train={len(train)} hold={len(hold)} mesas={len(mesas)}")
    w(
        f"horas con chips P0/P8: train {n_tr_m}/{len(train)} · "
        f"hold {n_ho_m}/{len(hold)}  "
        f"(cinta motor last={cinta.orden[-1] if cinta.orden else '?'})"
    )
    w("  CONTROL_AYUDA_P8 = renglón de control (acuerdo ≥1), no eje.")
    w("  SOLO_ZONA: m_est = (minuto ancla + gap) mod 60  (1 tiro ≈ 1 min).")
    w("  ENTRADA_GR: extra del catálogo (PODA G-R): no abrir si el ancla fue pegada.")
    w()

    rows_by_split: dict[str, dict] = {}
    walked_by_split: dict[str, WalkOut] = {}

    for split_name, subset in (("train", train), ("holdout", hold)):
        w(f"== {split_name.upper()} ==")
        walked = walk(subset, mesas)
        walked_by_split[split_name] = walked
        rows = {}
        for p in POLS:
            r = resumen_decs(walked.decs[p])
            h = juez_hora(walked.por_hora[p])
            rows[p] = (r, h)
            dump_pol(p, r, h)
            mots = walked.motivos_go[p]
            if mots:
                bits = ", ".join(f"{k}={v}" for k, v in sorted(mots.items()))
                w(f"    motivos GO: {bits}")
        rows_by_split[split_name] = rows
        zd = walked.zona_diag
        if zd["n_poda"]:
            n = zd["n_poda"]
            w(
                f"    diag zona (sobre GO de forma R0): n={n}  "
                f"m_est en tip±1 {pct(zd['m_est_en_banda'], n)}  "
                f"real en tip±1 {pct(zd['real_en_banda'], n)}"
            )
            w(
                f"      reloj vs real: d=0 {pct(zd['d0'], n)}  d=1 {pct(zd['d1'], n)}  "
                f"d=2 {pct(zd['d2'], n)}  d≥3 {pct(zd['d3p'], n)}"
            )
            w(
                f"      ambos {zd['ambos']}  solo_est {zd['solo_est']}  "
                f"solo_real {zd['solo_real']}  ninguno {zd['ninguno']}"
            )
        w()

    w("== DIFF HOLDOUT vs PODA_R0 ==")
    base = rows_by_split["holdout"]["PODA_R0"][0]
    for p in PUERTAS:
        if p == "PODA_R0":
            continue
        r = rows_by_split["holdout"][p][0]
        w(fila_cmp(p, r, base))
    w()
    w("== DIFF TRAIN vs PODA_R0 ==")
    base_tr = rows_by_split["train"]["PODA_R0"][0]
    for p in PUERTAS:
        if p == "PODA_R0":
            continue
        r = rows_by_split["train"][p][0]
        w(fila_cmp(p, r, base_tr))
    w()

    hold_m = [h for h in hold if _mesa_ok(h)]
    w(f"== CONTROL AYUDA (no eje) · hold horas con mesa {len(hold_m)}/{len(hold)} ==")
    if hold_m:
        walked_m = walk(hold_m, mesas)
        for p in ("PODA_R0", CONTROL):
            r = resumen_decs(walked_m.decs[p])
            h = juez_hora(walked_m.por_hora[p])
            dump_pol(p, r, h)
        poda_m = resumen_decs(walked_m.decs["PODA_R0"])
        ay_m = resumen_decs(walked_m.decs[CONTROL])
        w(
            f"  CONTROL − PODA_R0 (mesa): Δbanda {(ay_m['hit_rate'] - poda_m['hit_rate']) * 100:+.1f}pp  "
            f"Δpnl {ay_m['pnl'] - poda_m['pnl']:+.1f}  "
            f"Δcov {(ay_m['cov'] - poda_m['cov']) * 100:+.1f}pp"
        )
    w("  (R0 ya: ayuda recorta sin sumar. No se reabre como novedad.)")
    w()

    w("== RANK HOLDOUT (puertas; juez = PnL luego banda) ==")
    ranked = sorted(
        PUERTAS,
        key=lambda p: (
            rows_by_split["holdout"][p][0]["pnl"],
            rows_by_split["holdout"][p][0]["hit_rate"],
            rows_by_split["holdout"][p][0]["cov"],
        ),
        reverse=True,
    )
    for i, p in enumerate(ranked, 1):
        r, h = rows_by_split["holdout"][p]
        rt, _ = rows_by_split["train"][p]
        w(
            f"  {i}. {p:<16} HOLD cov {pct(r['go'], r['n'])} banda {pct(r['hit'], r['go'])} "
            f"pnl {r['pnl']:+.0f}  PnL>0 {h['verdes']}/{h['n_h']}  "
            f"| TRAIN cov {pct(rt['go'], rt['n'])} banda {pct(rt['hit'], rt['go'])} "
            f"pnl {rt['pnl']:+.0f}"
        )
    w()

    w("== LECTURA ==")
    w("  Formas, no coronas. Comparar contra PODA_R0 (R0 ya medida).")
    w("  Gana hold: SOLO_ZONA vs R0. Train misma forma. No es oráculo:")
    w("  el reloj 1:1 del gap vs el minuto real va a d≤1 (~95% hold).")
    w("  Jugar todos los tiros de la ventana diluye; la silla del tip concentra.")
    w("  GATILLO_HORA misma dirección; Δ hold chico. No coronar.")
    w("  FRÍO: VENTANA_2345 · ENTRADA_GR · PODA_SIEMPRE · AYUDA.")
    w("  Siguiente (no ML): zona × gatillo, o zona en el ancla sin el gap.")
    w()

    path = OUT / "LAB_SENIOR_PODA_R1.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"[ok] {path}")


if __name__ == "__main__":
    main()
