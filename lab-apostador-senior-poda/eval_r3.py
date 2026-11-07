# -*- coding: utf-8 -*-
"""
R3 senior-poda: tip EXACTO en la ráfaga + silla también en R (no ML).
  python eval_r3.py → reports/LAB_SENIOR_PODA_R3.txt
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
    dist_anillo,
    hit_banda,
    indices_g_en_tiros,
    load_horas_y_cinta,
    split_holdout,
    tip_lc01,
)

# Universo G→G (RAMA A + baselines). Misma puerta poda que R0/R2.
POLS_G = (
    "PODA_R0",
    "SOLO_ZONA",
    "ZONA_ANCLA",
    "EXACTO_ANCLA",
)
# Universo asientos (RAMA B). SILLA_G ≡ SOLO_ZONA en el subconjunto G.
POLS_SLOT = (
    "SILLA_G",
    "SILLA_TODOS",
)
POLS = POLS_G + POLS_SLOT

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


def m0_de(t) -> int | None:
    m = getattr(t, "m0", None)
    if m is None:
        return None
    try:
        return int(m) % 60
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


def puerta_poda(gap: int, tren: bool, estirada: bool) -> tuple[bool, str]:
    """A: no sequía · +2..+4 · +1 solo Tren/Estirada. Igual R0/R1/R2."""
    if gap >= 5:
        return False, "sequia"
    if gap == 1:
        if tren:
            return True, "tren"
        if estirada:
            return True, "estirada"
        return False, "poda_mas1"
    if 2 <= gap <= 4:
        return True, f"gap{gap}"
    return False, "fuera"


def mins_ventana(m_ancla: int, gaps: tuple[int, ...]) -> list[int]:
    return [(int(m_ancla) + g) % 60 for g in gaps]


def tip_apunta(tip: int, mins: list[int]) -> bool:
    return any(hit_banda(tip, m) for m in mins)


def tip_exacto(tip: int, mins: list[int]) -> bool:
    t = int(tip) % 60
    return any(t == (int(m) % 60) for m in mins)


def dist_a_mins(tip: int, mins: list[int]) -> int:
    return min(dist_anillo(tip, m) for m in mins) if mins else 99


def decidir_g(
    pol: str,
    *,
    gap: int,
    tren: bool,
    estirada: bool,
    m_est: int,
    tip: int,
    en_ancla: bool,
    en_exacto: bool,
) -> tuple[str, int, list[str]]:
    go, mot = puerta_poda(gap, tren, estirada)
    if not go:
        return "NO_GO", 0, [mot]
    if pol == "PODA_R0":
        return "GO_WEAK", STAKE_WEAK, [mot]
    if pol == "SOLO_ZONA":
        if not hit_banda(tip, m_est):
            return "NO_GO", 0, ["fuera_zona"]
        return "GO_WEAK", STAKE_WEAK, [mot, "zona"]
    if pol == "ZONA_ANCLA":
        if not en_ancla:
            return "NO_GO", 0, ["ancla_fuera"]
        return "GO_WEAK", STAKE_WEAK, [mot, "ancla"]
    if pol == "EXACTO_ANCLA":
        if not en_exacto:
            return "NO_GO", 0, ["exacto_fuera"]
        return "GO_WEAK", STAKE_WEAK, [mot, "exacto"]
    return "NO_GO", 0, ["desconocida"]


def _bucket() -> dict[str, int | float]:
    return {"n": 0, "hit": 0, "pnl": 0.0}


def _add(b: dict, hit: bool, pnl: float) -> None:
    b["n"] += 1
    b["hit"] += int(hit)
    b["pnl"] += pnl


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
            "leak_n": 0,
        }
    )
    ancla_diag: dict[str, dict] = field(
        default_factory=lambda: {
            "en_ancla": _bucket(),
            "fuera_ancla": _bucket(),
            "en_exacto": _bucket(),
            "anillo_ancla": _bucket(),
            "en_techo": _bucket(),
            "fuera_techo": _bucket(),
            "tip_d0": _bucket(),
            "tip_d1": _bucket(),
            "tip_d2p": _bucket(),
            "silla": _bucket(),
            "no_silla": _bucket(),
        }
    )
    dist_tip_techo: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    slot_diag: dict[str, int] = field(
        default_factory=lambda: {
            "n_ventana": 0,
            "n_apostable": 0,
            "go_todos": 0,
            "go_r": 0,
            "go_g_banda": 0,
            "go_g_fuera": 0,
            "apost_r": 0,
            "apost_g_banda": 0,
            "apost_g_fuera": 0,
            "pnl_todos": 0,
            "pnl_solo_g": 0,
            "pnl_color": 0,
            "n_ancla_slot": 0,
            "n_cola_hora": 0,
        }
    )


def _emit(out: WalkOut, pol: str, d: Decision) -> None:
    out.decs[pol].append(d)
    out.por_hora[pol][d.tag].append(d)
    if d.stake > 0:
        out.motivos_go[pol][d.reasons[0]] += 1


def walk(horas) -> WalkOut:
    out = WalkOut()
    for h in horas:
        gs = sorted(h.gs, key=lambda g: g.m0)
        tiros = list(getattr(h, "tiros", None) or [])
        idxs = indices_g_en_tiros(h)
        luces: list[int] = []
        n_g = len(gs)
        if n_g < 1:
            continue
        for i in range(n_g):
            luces.append(gs[i].m0)
            tip = tip_lc01(luces)
            if tip is None:
                continue
            if i < len(idxs):
                ancla = idxs[i]
            else:
                ancla = 0
            tren = g_consecutivas_hasta(tiros, ancla) >= 2 if tiros else False
            dprev = dur_de(tiros[ancla]) if tiros and ancla < len(tiros) else None
            estirada = dprev is not None and dprev >= 100
            m_ancla = int(gs[i].m0)
            win_ancla = mins_ventana(
                m_ancla, (1, 2, 3, 4) if (tren or estirada) else (2, 3, 4)
            )
            win_techo = mins_ventana(m_ancla, (2, 3, 4))
            en_ancla = tip_apunta(tip, win_ancla)
            en_exacto = tip_exacto(tip, win_ancla)
            en_techo = tip_apunta(tip, win_techo)
            hay_next = i + 1 < n_g and i + 1 < len(idxs)
            next_g = idxs[i + 1] if hay_next else None

            if hay_next:
                gap = idxs[i + 1] - idxs[i]
                real = gs[i + 1].m0
                hit = hit_banda(tip, real)
                m_est = (m_ancla + int(gap)) % 60
                go_r0, _ = puerta_poda(gap, tren, estirada)
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
                    if hit:
                        out.zona_diag["leak_n"] += 1
                    pnl_ev = 1.0 if hit else -1.0
                    d_techo = dist_a_mins(tip, win_techo)
                    out.dist_tip_techo[min(d_techo, 8)] += 1
                    d_ancla = dist_a_mins(tip, win_ancla)
                    for key, ok in (
                        ("en_ancla", en_ancla),
                        ("fuera_ancla", not en_ancla),
                        ("en_exacto", en_exacto),
                        ("anillo_ancla", en_ancla and not en_exacto),
                        ("en_techo", en_techo),
                        ("fuera_techo", not en_techo),
                        ("silla", est_ok),
                        ("no_silla", not est_ok),
                        ("tip_d0", d_techo == 0),
                        ("tip_d1", d_techo == 1),
                        ("tip_d2p", d_techo >= 2),
                    ):
                        if ok:
                            _add(out.ancla_diag[key], hit, pnl_ev)
                    _ = d_ancla
                for pol in POLS_G:
                    kind, stake, reasons = decidir_g(
                        pol,
                        gap=gap,
                        tren=tren,
                        estirada=estirada,
                        m_est=m_est,
                        tip=tip,
                        en_ancla=en_ancla,
                        en_exacto=en_exacto,
                    )
                    pnl = float(stake if hit else -stake) if stake > 0 else 0.0
                    _emit(
                        out,
                        pol,
                        Decision(
                            tag=h.tag,
                            tip=tip,
                            real=real,
                            policy=pol,
                            kind=kind,
                            stake=stake,
                            hit=hit,
                            pnl=pnl,
                            score=float(gap),
                            acuerdo=False,
                            ewma=0.0,
                            reasons=reasons,
                        ),
                    )

            # RAMA B: asientos de la ventana, G y R. Cierra en la próxima G
            # o a +4 / fin de hora. m_est = m_ancla+gap. Cero m0 futuro.
            out.slot_diag["n_ancla_slot"] += 1
            if next_g is None:
                out.slot_diag["n_cola_hora"] += 1
            for gap_s in (1, 2, 3, 4):
                idx_s = ancla + gap_s
                if idx_s >= len(tiros):
                    break
                if next_g is not None and idx_s > next_g:
                    break
                t_s = tiros[idx_s]
                es_luz = es_g(t_s)
                m_est_s = (m_ancla + gap_s) % 60
                go_p, mot_s = puerta_poda(gap_s, tren, estirada)
                silla = hit_banda(tip, m_est_s)
                real_s = m0_de(t_s)
                if real_s is None:
                    real_s = m_est_s
                hit_min = bool(es_luz and hit_banda(tip, real_s))
                out.slot_diag["n_ventana"] += 1
                if go_p:
                    out.slot_diag["n_apostable"] += 1
                    if es_luz and hit_min:
                        out.slot_diag["apost_g_banda"] += 1
                    elif es_luz:
                        out.slot_diag["apost_g_fuera"] += 1
                    else:
                        out.slot_diag["apost_r"] += 1
                # (i) solo G: GO si puerta × silla × es G
                if go_p and silla and es_luz:
                    pnl_g = 1.0 if hit_min else -1.0
                    out.slot_diag["pnl_solo_g"] += pnl_g
                    _emit(
                        out,
                        "SILLA_G",
                        Decision(
                            tag=h.tag,
                            tip=tip,
                            real=real_s,
                            policy="SILLA_G",
                            kind="GO_WEAK",
                            stake=STAKE_WEAK,
                            hit=hit_min,
                            pnl=pnl_g,
                            score=float(gap_s),
                            acuerdo=False,
                            ewma=0.0,
                            reasons=[mot_s, "zona", "g_banda" if hit_min else "g_fuera"],
                        ),
                    )
                else:
                    _emit(
                        out,
                        "SILLA_G",
                        Decision(
                            tag=h.tag,
                            tip=tip,
                            real=real_s,
                            policy="SILLA_G",
                            kind="NO_GO",
                            stake=0,
                            hit=False,
                            pnl=0.0,
                            score=float(gap_s),
                            acuerdo=False,
                            ewma=0.0,
                            reasons=["no_g" if not es_luz else ("fuera_zona" if go_p else mot_s)],
                        ),
                    )
                # (ii) todos los asientos: GO si puerta × silla, aunque sea R
                if go_p and silla:
                    if es_luz:
                        hit_t = hit_min
                        pnl_t = 1.0 if hit_min else -1.0
                        tag_c = "g_banda" if hit_min else "g_fuera"
                        if hit_min:
                            out.slot_diag["go_g_banda"] += 1
                        else:
                            out.slot_diag["go_g_fuera"] += 1
                    else:
                        hit_t = False
                        pnl_t = -1.0
                        tag_c = "color_R"
                        out.slot_diag["go_r"] += 1
                    out.slot_diag["go_todos"] += 1
                    out.slot_diag["pnl_todos"] += pnl_t
                    out.slot_diag["pnl_color"] += 1.0 if es_luz else -1.0
                    _emit(
                        out,
                        "SILLA_TODOS",
                        Decision(
                            tag=h.tag,
                            tip=tip,
                            real=real_s,
                            policy="SILLA_TODOS",
                            kind="GO_WEAK",
                            stake=STAKE_WEAK,
                            hit=hit_t,
                            pnl=pnl_t,
                            score=float(gap_s),
                            acuerdo=False,
                            ewma=0.0,
                            reasons=[mot_s, "zona", tag_c],
                        ),
                    )
                else:
                    _emit(
                        out,
                        "SILLA_TODOS",
                        Decision(
                            tag=h.tag,
                            tip=tip,
                            real=real_s,
                            policy="SILLA_TODOS",
                            kind="NO_GO",
                            stake=0,
                            hit=False,
                            pnl=0.0,
                            score=float(gap_s),
                            acuerdo=False,
                            ewma=0.0,
                            reasons=["fuera_zona" if go_p else mot_s],
                        ),
                    )
    return out


def resumen_decs(decs: list[Decision]) -> dict:
    goes = [d for d in decs if d.stake > 0]
    hits = [d for d in goes if d.hit]
    ex = sum(1 for d in goes if dist_anillo(d.tip, d.real) == 0)
    pm1 = sum(1 for d in goes if dist_anillo(d.tip, d.real) == 1)
    pnl = sum(d.pnl for d in decs)
    n = len(decs)
    ng = len(goes)
    n_r = sum(1 for d in goes if "color_R" in d.reasons)
    n_gb = sum(1 for d in goes if "g_banda" in d.reasons)
    n_gf = sum(1 for d in goes if "g_fuera" in d.reasons)
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
        "n_r": n_r,
        "n_g_banda": n_gb,
        "n_g_fuera": n_gf,
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


def dump_pol(label: str, r: dict, h: dict | None = None, *, slot: bool = False) -> None:
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
        if slot and (r["n_r"] or r["n_g_banda"] or r["n_g_fuera"]):
            w(
                f"    asientos GO: R {r['n_r']} ({pct(r['n_r'], r['go'])})  "
                f"G-banda {r['n_g_banda']} ({pct(r['n_g_banda'], r['go'])})  "
                f"G-fuera {r['n_g_fuera']} ({pct(r['n_g_fuera'], r['go'])})"
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
        f"  {name:<18} cov {pct(r['go'], r['n'])}  "
        f"banda {pct(r['hit'], r['go'])}  "
        f"pnl {r['pnl']:+.0f}  "
        f"Δbanda {(r['hit_rate'] - base['hit_rate']) * 100:+.1f}pp  "
        f"Δpnl {r['pnl'] - base['pnl']:+.0f}  "
        f"Δcov {(r['cov'] - base['cov']) * 100:+.1f}pp"
    )


def dump_bucket(label: str, b: dict) -> None:
    n = int(b["n"])
    h = int(b["hit"])
    w(
        f"    {label:<14} n={n}  banda {pct(h, n)}  "
        f"pnl {b['pnl']:+.0f}  (si se jugara esa cola de R0)"
    )


def main() -> None:
    w("LAB SENIOR-PODA — R3")
    w("RAMA A: tip EXACTO en +2..+4 (sin anillo ±1) · RAMA B: silla también en R")
    w("chip: LC-01 minutos · juez: banda d<=1 + PnL 1:1 · hora a hora")
    w("CERO prod · CERO ML/fuzzy · CERO Jaccard · CERO P(tiro=G) como veredicto")
    w("3/4/Tren/exacto/silla = FORMAS. No se coronan. Holdout 72 = el de R0.")
    w("R2 HOLD no se reabre: SOLO_ZONA 28.3%/88.4%/+139 · ANCLA +94 · R0 +68")
    w("LOOK R2 (no ficha): tip exacto techo +2..+4 hold 73.9%/+112 · anillo −18")
    w()

    horas, cinta = load_horas_y_cinta()
    train, hold = split_holdout(horas, HOLDOUT)
    w(f"n={len(horas)} train={len(train)} hold={len(hold)}")
    w(f"  (cinta motor last={cinta.orden[-1] if cinta.orden else '?'})")
    w()
    w("  ESTIMACIÓN (causal, todas las puertas de zona/silla):")
    w("    m_est = (m_ancla + gap_del_slot) mod 60   ·  1 tiro ≈ 1 min")
    w("    gap_del_slot = índice_tiro(slot) − índice_tiro(G_ancla)")
    w("    En RAMA A el slot es la G siguiente. En RAMA B es cada tiro")
    w("    apostable de la ventana (+2..+4, +1 si Tren/Estirada).")
    w("    NO se usa el m0 real de la G que cae. Filtrar por ese m0 = leak")
    w("    → banda 100% por construcción. No se juega.")
    w("  EXACTO_ANCLA: GO la ráfaga si tip == alguno de {mG+2,+3,+4}")
    w("    (o +1 si Tren/Estirada). Sin anillo ±1. Cero G futura.")
    w("  ZONA_ANCLA: lo mismo con anillo tip ±1 (R2).")
    w("  SOLO_ZONA / SILLA_G: GO el asiento G cuya m_est pisa tip ±1.")
    w("  SILLA_TODOS: GO ese asiento AUNQUE el tiro sea R (pierdes 1).")
    w("    Si es G y banda, ganas 1. PnL 1:1 mezcla color + minuto.")
    w()

    rows_by_split: dict[str, dict] = {}
    walked_by_split: dict[str, WalkOut] = {}

    for split_name, subset in (("train", train), ("holdout", hold)):
        w(f"== {split_name.upper()} ==")
        walked = walk(subset)
        walked_by_split[split_name] = walked
        rows = {}
        w("  -- universo G→G (RAMA A + baselines) --")
        for p in POLS_G:
            r = resumen_decs(walked.decs[p])
            hh = juez_hora(walked.por_hora[p])
            rows[p] = (r, hh)
            dump_pol(p, r, hh)
            mots = walked.motivos_go[p]
            if mots:
                bits = ", ".join(f"{k}={v}" for k, v in sorted(mots.items()))
                w(f"    motivos GO: {bits}")
        w("  -- universo asientos (RAMA B) --")
        for p in POLS_SLOT:
            r = resumen_decs(walked.decs[p])
            hh = juez_hora(walked.por_hora[p])
            rows[p] = (r, hh)
            dump_pol(p, r, hh, slot=True)
            mots = walked.motivos_go[p]
            if mots:
                bits = ", ".join(f"{k}={v}" for k, v in sorted(mots.items()))
                w(f"    motivos GO: {bits}")
        rows_by_split[split_name] = rows

        zd = walked.zona_diag
        if zd["n_poda"]:
            n = zd["n_poda"]
            w(
                f"    diag reloj (sobre GO de forma R0): n={n}  "
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
            w(
                f"      LEAK si se filtrara por m0 de la G que cae: "
                f"n={zd['leak_n']}  banda 100%  pnl +{zd['leak_n']:.0f}  "
                f"(no es política; solo contraste)"
            )
        ad = walked.ancla_diag
        w("    colas de R0 según puerta de ANCLA / EXACTO (universo G→G):")
        dump_bucket("tip±1 ancla", ad["en_ancla"])
        dump_bucket("tip fuera", ad["fuera_ancla"])
        dump_bucket("tip EXACTO", ad["en_exacto"])
        dump_bucket("anillo ±1", ad["anillo_ancla"])
        dump_bucket("tip techo", ad["en_techo"])
        dump_bucket("tip lejano", ad["fuera_techo"])
        dump_bucket("techo d=0", ad["tip_d0"])
        dump_bucket("techo d=1", ad["tip_d1"])
        dump_bucket("techo d≥2", ad["tip_d2p"])
        dump_bucket("silla est", ad["silla"])
        dump_bucket("no silla", ad["no_silla"])
        bits = "  ".join(
            f"d={k}:{v}" for k, v in sorted(walked.dist_tip_techo.items())
        )
        w(f"    dist(tip, {{+2,+3,+4}}): {bits}")

        sd = walked.slot_diag
        w("    RAMA B — desglose de asientos (ventana +2..+4 / +1 Tren-Estirada):")
        w(
            f"      anclas con tip={sd['n_ancla_slot']}  "
            f"cola-fin-hora={sd['n_cola_hora']}  "
            f"slots ventana={sd['n_ventana']}  apostables={sd['n_apostable']}"
        )
        w(
            f"      apostables: R {sd['apost_r']}  "
            f"G-banda {sd['apost_g_banda']}  G-fuera {sd['apost_g_fuera']}"
        )
        w(
            f"      GO SILLA_TODOS={sd['go_todos']}  "
            f"R {sd['go_r']} ({pct(sd['go_r'], sd['go_todos'])})  "
            f"G-banda {sd['go_g_banda']} ({pct(sd['go_g_banda'], sd['go_todos'])})  "
            f"G-fuera {sd['go_g_fuera']} ({pct(sd['go_g_fuera'], sd['go_todos'])})"
        )
        w(
            f"      PnL mixto (color+minuto) {sd['pnl_todos']:+.0f}  "
            f"PnL (i) solo G {sd['pnl_solo_g']:+.0f}  "
            f"PnL color-ciego (±1 si G/R, ignora minuto) {sd['pnl_color']:+.0f}"
        )
        go_sz = rows["SOLO_ZONA"][0]["go"]
        pnl_sz = rows["SOLO_ZONA"][0]["pnl"]
        go_sg = rows["SILLA_G"][0]["go"]
        pnl_sg = rows["SILLA_G"][0]["pnl"]
        w(
            f"      sanity SILLA_G vs SOLO_ZONA: GO {go_sg} vs {go_sz}  "
            f"pnl {pnl_sg:+.0f} vs {pnl_sz:+.0f}"
            f"{'  (alineados)' if go_sg == go_sz and pnl_sg == pnl_sz else '  (DIFF: cola-hora o G sin lumen)'}"
        )
        w()

    w("== DIFF HOLDOUT vs PODA_R0 (universo G→G) ==")
    base = rows_by_split["holdout"]["PODA_R0"][0]
    for p in POLS_G:
        if p == "PODA_R0":
            continue
        r = rows_by_split["holdout"][p][0]
        w(fila_cmp(p, r, base))
    w()
    w("== DIFF TRAIN vs PODA_R0 (universo G→G) ==")
    base_tr = rows_by_split["train"]["PODA_R0"][0]
    for p in POLS_G:
        if p == "PODA_R0":
            continue
        r = rows_by_split["train"][p][0]
        w(fila_cmp(p, r, base_tr))
    w()

    w("== DIFF HOLDOUT vs SOLO_ZONA (¿exacto / ancla sostienen la silla?) ==")
    base_z = rows_by_split["holdout"]["SOLO_ZONA"][0]
    for p in ("EXACTO_ANCLA", "ZONA_ANCLA", "PODA_R0"):
        r = rows_by_split["holdout"][p][0]
        w(fila_cmp(p, r, base_z))
    w()
    w("== DIFF HOLDOUT vs ZONA_ANCLA (¿el ±1 del ancla sigue restando?) ==")
    base_a = rows_by_split["holdout"]["ZONA_ANCLA"][0]
    r_ex = rows_by_split["holdout"]["EXACTO_ANCLA"][0]
    w(fila_cmp("EXACTO_ANCLA", r_ex, base_a))
    w()

    w("== RANK HOLDOUT universo G→G (juez = PnL luego banda) ==")
    ranked = sorted(
        POLS_G,
        key=lambda p: (
            rows_by_split["holdout"][p][0]["pnl"],
            rows_by_split["holdout"][p][0]["hit_rate"],
            rows_by_split["holdout"][p][0]["cov"],
        ),
        reverse=True,
    )
    for i, p in enumerate(ranked, 1):
        r, hh = rows_by_split["holdout"][p]
        rt, _ = rows_by_split["train"][p]
        w(
            f"  {i}. {p:<18} HOLD cov {pct(r['go'], r['n'])} banda {pct(r['hit'], r['go'])} "
            f"pnl {r['pnl']:+.0f}  PnL>0 {hh['verdes']}/{hh['n_h']}  "
            f"| TRAIN cov {pct(rt['go'], rt['n'])} banda {pct(rt['hit'], rt['go'])} "
            f"pnl {rt['pnl']:+.0f}"
        )
    w()
    w("== RANK HOLDOUT universo asientos (RAMA B; juez = PnL mixto) ==")
    for i, p in enumerate(("SILLA_G", "SILLA_TODOS"), 1):
        r, hh = rows_by_split["holdout"][p]
        rt, _ = rows_by_split["train"][p]
        w(
            f"  {i}. {p:<18} HOLD GO {r['go']} banda {pct(r['hit'], r['go'])} "
            f"pnl {r['pnl']:+.0f}  PnL>0 {hh['verdes']}/{hh['n_h']}  "
            f"| TRAIN GO {rt['go']} pnl {rt['pnl']:+.0f}"
        )
    w()

    ho = rows_by_split["holdout"]
    tr = rows_by_split["train"]
    r0h, r0hh = ho["PODA_R0"]
    szh, szhh = ho["SOLO_ZONA"]
    zah, zahh = ho["ZONA_ANCLA"]
    exh, exhh = ho["EXACTO_ANCLA"]
    sgh, sghh = ho["SILLA_G"]
    sth, sthh = ho["SILLA_TODOS"]
    ad_h = walked_by_split["holdout"].ancla_diag
    ad_t = walked_by_split["train"].ancla_diag
    sd_h = walked_by_split["holdout"].slot_diag
    sd_t = walked_by_split["train"].slot_diag
    zd_h = walked_by_split["holdout"].zona_diag

    w("== LECTURA ==")
    w("  ESTIMACIÓN vs LEAK")
    w("  m_est=(m_ancla+gap_del_slot) mod 60. No m0 de la G que cae.")
    w(
        f"  Reloj vs real d≤1 {pct(zd_h['d0'] + zd_h['d1'], zd_h['n_poda'])}."
        f"  LEAK (filtrar por m0 futuro): n={zd_h['leak_n']} banda 100% pnl "
        f"+{zd_h['leak_n']}. Eso NO se juega."
    )
    w()
    w("  RAMA A — ¿el exacto sostiene el +112 y el ±1 sigue restando?")
    w(
        f"  EXACTO_ANCLA HOLD {pct(exh['go'], exh['n'])} / "
        f"{pct(exh['hit'], exh['go'])} / {exh['pnl']:+.0f}  "
        f"PnL>0 {exhh['verdes']}/{exhh['n_h']}  vs ZONA_ANCLA "
        f"{pct(zah['go'], zah['n'])} / {pct(zah['hit'], zah['go'])} / "
        f"{zah['pnl']:+.0f}  vs PODA_R0 {r0h['pnl']:+.0f}  vs SOLO_ZONA "
        f"{szh['pnl']:+.0f}."
    )
    w(
        f"  Train EXACTO_ANCLA {pct(tr['EXACTO_ANCLA'][0]['go'], tr['EXACTO_ANCLA'][0]['n'])} / "
        f"{pct(tr['EXACTO_ANCLA'][0]['hit'], tr['EXACTO_ANCLA'][0]['go'])} / "
        f"{tr['EXACTO_ANCLA'][0]['pnl']:+.0f} vs ANCLA "
        f"{tr['ZONA_ANCLA'][0]['pnl']:+.0f} vs R0 {tr['PODA_R0'][0]['pnl']:+.0f} "
        f"vs SOLO_ZONA {tr['SOLO_ZONA'][0]['pnl']:+.0f}."
    )
    w(
        f"  Cola R0 tip EXACTO (ventana ancla, no techo): hold n="
        f"{int(ad_h['en_exacto']['n'])} banda "
        f"{pct(int(ad_h['en_exacto']['hit']), int(ad_h['en_exacto']['n']))} "
        f"pnl {ad_h['en_exacto']['pnl']:+.0f} · anillo ±1 n="
        f"{int(ad_h['anillo_ancla']['n'])} banda "
        f"{pct(int(ad_h['anillo_ancla']['hit']), int(ad_h['anillo_ancla']['n']))} "
        f"pnl {ad_h['anillo_ancla']['pnl']:+.0f}."
    )
    w(
        f"  LOOK techo d=0 (R2 +112): hold n={int(ad_h['tip_d0']['n'])} "
        f"banda {pct(int(ad_h['tip_d0']['hit']), int(ad_h['tip_d0']['n']))} "
        f"pnl {ad_h['tip_d0']['pnl']:+.0f} · techo d=1 n="
        f"{int(ad_h['tip_d1']['n'])} banda "
        f"{pct(int(ad_h['tip_d1']['hit']), int(ad_h['tip_d1']['n']))} "
        f"pnl {ad_h['tip_d1']['pnl']:+.0f}."
    )
    w(
        f"  Train cola exacto-ancla n={int(ad_t['en_exacto']['n'])} "
        f"banda {pct(int(ad_t['en_exacto']['hit']), int(ad_t['en_exacto']['n']))} "
        f"pnl {ad_t['en_exacto']['pnl']:+.0f} · anillo n="
        f"{int(ad_t['anillo_ancla']['n'])} "
        f"pnl {ad_t['anillo_ancla']['pnl']:+.0f}."
    )
    w()
    w("  RAMA B — ¿la silla sirve aunque salga R, o solo cobra con G?")
    w(
        f"  (i) solo G = SILLA_G / SOLO_ZONA: HOLD GO {sgh['go']} "
        f"banda {pct(sgh['hit'], sgh['go'])} pnl {sgh['pnl']:+.0f}  "
        f"PnL>0 {sghh['verdes']}/{sghh['n_h']}  "
        f"(SOLO_ZONA {szh['go']} / {szh['pnl']:+.0f})."
    )
    w(
        f"  (ii) todos los asientos = SILLA_TODOS: HOLD GO {sth['go']} "
        f"banda {pct(sth['hit'], sth['go'])} pnl mixto {sth['pnl']:+.0f}  "
        f"PnL>0 {sthh['verdes']}/{sthh['n_h']}."
    )
    w(
        f"  De los GO de SILLA_TODOS hold: R {sd_h['go_r']} "
        f"({pct(sd_h['go_r'], sd_h['go_todos'])}) · "
        f"G-banda {sd_h['go_g_banda']} "
        f"({pct(sd_h['go_g_banda'], sd_h['go_todos'])}) · "
        f"G-fuera {sd_h['go_g_fuera']} "
        f"({pct(sd_h['go_g_fuera'], sd_h['go_todos'])})."
    )
    w(
        f"  PnL hold: mixto {sd_h['pnl_todos']:+.0f} · (i) solo G "
        f"{sd_h['pnl_solo_g']:+.0f} · color-ciego {sd_h['pnl_color']:+.0f}."
    )
    w(
        f"  Train SILLA_TODOS GO {tr['SILLA_TODOS'][0]['go']} pnl "
        f"{tr['SILLA_TODOS'][0]['pnl']:+.0f} · (i) solo G "
        f"{sd_t['pnl_solo_g']:+.0f} · R {sd_t['go_r']} / "
        f"G-banda {sd_t['go_g_banda']} / G-fuera {sd_t['go_g_fuera']}."
    )
    w(
        "  SOLO_ZONA de R2 NO apostaba R: el walk era G→G. Hold"
    )
    w(
        f"  SOLO_ZONA = {szh['go']} G (banda {sd_h['go_g_banda']} ·"
        f" fuera {sd_h['go_g_fuera']} · R 0). SILLA_TODOS es la"
    )
    w(
        "  misma silla sobre cada tiro apostable cuya m_est pisa"
    )
    w(
        "  tip ±1, también los R. Train SILLA_G vs SOLO_ZONA:"
    )
    w(
        f"  GO {tr['SILLA_G'][0]['go']} vs {tr['SOLO_ZONA'][0]['go']}"
        f" (Δ+{tr['SILLA_G'][0]['go'] - tr['SOLO_ZONA'][0]['go']};"
        f" cola-hora / G sin lumen). Hold alineado."
    )
    w()
    w("  Combinar, no coronar. Tres capas, un taller:")
    w("    A puerta poda · B chip como asiento (silla) o como")
    w("    filtro de ráfaga (ancla ±1 / exacto) · C silla-en-R")
    w("    = el mismo asiento cobrado cuando el color falta.")
    w("  1) Exacto recorta el anillo que resta (hold −11, train −259)")
    w("     y queda entre ANCLA y SILLA. No es el 89%.")
    w("  2) El +112 era LOOK techo d=0 (sin +1). La política pedida")
    w("     (ventana ancla, +1 si Tren/Estirada) da +105. El LOOK")
    w("     +112 sigue; no se corona como política.")
    w("  3) SILLA G-only sigue concentrando: hold +139 / 88.4%.")
    w("  4) SOLO_ZONA no apostaba R (hold 0/181). El 88% es minuto")
    w("     entre G que se sentaron, no un ‘hay que estar’.")
    w("  5) Silla-en-R: 81.5% de los GO hold son miss de color.")
    w("     Mixto −661 · 1/72 verde. FRÍO.")
    w("  6) Color-ciego hold −619: el asiento tampoco paga color.")
    w("  VIVE (olor, no cable): SILLA G-only ≥ EXACTO_ANCLA ≥")
    w("  ZONA_ANCLA ≥ PODA_R0. FRÍO: SILLA_TODOS.")
    w("  No cable. No ML. Formas, no coronas. Cero fuzzy.")
    w()

    path = OUT / "LAB_SENIOR_PODA_R3.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"[ok] {path}")


if __name__ == "__main__":
    main()
