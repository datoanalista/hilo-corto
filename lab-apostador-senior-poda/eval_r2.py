# -*- coding: utf-8 -*-
"""
R2 senior-poda: zona en el ANCLA vs silla-del-tiro (no ML).
  python eval_r2.py → reports/LAB_SENIOR_PODA_R2.txt
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
    dist_anillo,
    hit_banda,
    indices_g_en_tiros,
    load_horas_y_cinta,
    split_holdout,
    tip_lc01,
)

# 6 políticas pedidas. Todas con puerta poda (espera G, +2..+4, Tren/Estirada en +1).
PUERTAS = (
    "PODA_R0",
    "SOLO_ZONA",
    "ZONA_ANCLA",
    "GATILLO_HORA",
    "ZONA_X_GATILLO",
    "ZONA_ANCLA_TECHO",
)
POLS = PUERTAS

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


def puerta_poda(gap: int, tren: bool, estirada: bool) -> tuple[bool, str]:
    """A: no sequía · +2..+4 · +1 solo Tren/Estirada. Igual R0/R1."""
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


def dist_a_mins(tip: int, mins: list[int]) -> int:
    return min(dist_anillo(tip, m) for m in mins) if mins else 99


def decidir(
    pol: str,
    *,
    gap: int,
    tren: bool,
    estirada: bool,
    i_ancla: int,
    tip: int,
    m_est: int,
    en_ancla: bool,
    en_techo: bool,
) -> tuple[str, int, list[str]]:
    go, mot = puerta_poda(gap, tren, estirada)
    if pol == "GATILLO_HORA" and i_ancla == 0:
        return "NO_GO", 0, ["lead"]
    if pol == "ZONA_X_GATILLO" and i_ancla == 0:
        return "NO_GO", 0, ["lead"]
    if not go:
        return "NO_GO", 0, [mot]
    if pol == "PODA_R0":
        return "GO_WEAK", STAKE_WEAK, [mot]
    if pol == "GATILLO_HORA":
        return "GO_WEAK", STAKE_WEAK, [mot]
    if pol == "SOLO_ZONA":
        # Causal: minuto del SLOT (m_ancla + gap), no m0 de la G que cae.
        if not hit_banda(tip, m_est):
            return "NO_GO", 0, ["fuera_zona"]
        return "GO_WEAK", STAKE_WEAK, [mot, "zona"]
    if pol == "ZONA_ANCLA":
        if not en_ancla:
            return "NO_GO", 0, ["ancla_fuera"]
        return "GO_WEAK", STAKE_WEAK, [mot, "ancla"]
    if pol == "ZONA_X_GATILLO":
        if not en_ancla:
            return "NO_GO", 0, ["ancla_fuera"]
        return "GO_WEAK", STAKE_WEAK, [mot, "ancla"]
    if pol == "ZONA_ANCLA_TECHO":
        if not en_techo:
            return "NO_GO", 0, ["techo_fuera"]
        return "GO_WEAK", STAKE_WEAK, [mot, "techo"]
    return "NO_GO", 0, ["desconocida"]


def _bucket() -> dict[str, int | float]:
    return {"n": 0, "hit": 0, "pnl": 0.0}


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
            "en_techo": _bucket(),
            "fuera_techo": _bucket(),
            "silla": _bucket(),
            "no_silla": _bucket(),
            "tip_d0": _bucket(),
            "tip_d1": _bucket(),
            "tip_d2p": _bucket(),
        }
    )
    dist_tip_techo: dict[int, int] = field(default_factory=lambda: defaultdict(int))


def walk(horas) -> WalkOut:
    out = WalkOut()
    for h in horas:
        gs = sorted(h.gs, key=lambda g: g.m0)
        if len(gs) < 2:
            continue
        tiros = list(getattr(h, "tiros", None) or [])
        idxs = indices_g_en_tiros(h)
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
            m_ancla = int(gs[i].m0)
            # Causal: 1 tiro ≈ 1 min. NO usa el m0 de la G que cae.
            m_est = (m_ancla + int(gap)) % 60
            win_ancla = mins_ventana(
                m_ancla, (1, 2, 3, 4) if (tren or estirada) else (2, 3, 4)
            )
            win_techo = mins_ventana(m_ancla, (2, 3, 4))
            en_ancla = tip_apunta(tip, win_ancla)
            en_techo = tip_apunta(tip, win_techo)
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
                # Leak de reloj: filtrar por m0 REAL de la G que cae.
                # Por construcción = los hits del juez. No es política.
                if hit:
                    out.zona_diag["leak_n"] += 1
                pnl_ev = 1.0 if hit else -1.0
                d_techo = dist_a_mins(tip, win_techo)
                out.dist_tip_techo[min(d_techo, 8)] += 1
                for key, ok in (
                    ("en_ancla", en_ancla),
                    ("fuera_ancla", not en_ancla),
                    ("en_techo", en_techo),
                    ("fuera_techo", not en_techo),
                    ("silla", est_ok),
                    ("no_silla", not est_ok),
                    ("tip_d0", d_techo == 0),
                    ("tip_d1", d_techo == 1),
                    ("tip_d2p", d_techo >= 2),
                ):
                    if not ok:
                        continue
                    b = out.ancla_diag[key]
                    b["n"] += 1
                    b["hit"] += int(hit)
                    b["pnl"] += pnl_ev
            for pol in POLS:
                kind, stake, reasons = decidir(
                    pol,
                    gap=gap,
                    tren=tren,
                    estirada=estirada,
                    i_ancla=i,
                    tip=tip,
                    m_est=m_est,
                    en_ancla=en_ancla,
                    en_techo=en_techo,
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
                    acuerdo=False,
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
    w("LAB SENIOR-PODA — R2")
    w("zona EN EL ANCLA vs silla-del-tiro · × gatillo · techo (no persigas)")
    w("chip: LC-01 minutos ±1 · juez: banda d<=1 + PnL 1:1 · hora a hora")
    w("CERO prod · CERO ML/fuzzy · CERO Jaccard · CERO P(tiro=G) como veredicto")
    w("3/4/Tren = FORMAS. No se coronan. Holdout 72 = el de R0 (no novedad).")
    w("R1 HOLD no se reabre: SOLO_ZONA 28.3%/89.0%/+141 · GATILLO +74 · R0 +70")
    w()

    horas, cinta = load_horas_y_cinta()
    train, hold = split_holdout(horas, HOLDOUT)
    w(f"n={len(horas)} train={len(train)} hold={len(hold)}")
    w(f"  (cinta motor last={cinta.orden[-1] if cinta.orden else '?'})")
    w()
    w("  ESTIMACIÓN (todas las puertas de zona):")
    w("    m_est = (m_ancla + gap_del_slot) mod 60   ·  1 tiro ≈ 1 min")
    w("    gap_del_slot = índice_tiro(G_next) − índice_tiro(G_ancla)")
    w("    NO se usa el m0 real de la G que cae. Eso sería leak:")
    w("    filtrar por hit_banda(tip, m0_futuro) = quedarse solo los aciertos")
    w("    del juez → banda 100% por construcción. No se juega.")
    w("  ZONA_ANCLA: tip (al cerrar G ancla) vs {mG+2,+3,+4} ±1;")
    w("    si Tren/Estirada, la ventana incluye mG+1. Cero G futura.")
    w("  ZONA_ANCLA_TECHO: si tip queda FUERA de {mG+2,+3,+4} ±1,")
    w("    NO-GO la ráfaga. No persigas el tip lejano. Sin +1 en el techo.")
    w("  GATILLO_HORA: no abrir en la 1ª G de la hora (R1).")
    w("  ZONA_X_GATILLO: ZONA_ANCLA × GATILLO.")
    w()

    rows_by_split: dict[str, dict] = {}
    walked_by_split: dict[str, WalkOut] = {}

    for split_name, subset in (("train", train), ("holdout", hold)):
        w(f"== {split_name.upper()} ==")
        walked = walk(subset)
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
        w("    colas de R0 según puerta de ANCLA (no silla-del-tiro):")
        dump_bucket("tip→ventana", ad["en_ancla"])
        dump_bucket("tip fuera", ad["fuera_ancla"])
        dump_bucket("tip→techo", ad["en_techo"])
        dump_bucket("tip lejano", ad["fuera_techo"])
        dump_bucket("tip exacto", ad["tip_d0"])
        dump_bucket("tip anillo", ad["tip_d1"])
        dump_bucket("tip d≥2", ad["tip_d2p"])
        dump_bucket("silla est", ad["silla"])
        dump_bucket("no silla", ad["no_silla"])
        bits = "  ".join(
            f"d={k}:{v}" for k, v in sorted(walked.dist_tip_techo.items())
        )
        w(f"    dist(tip, {{+2,+3,+4}}): {bits}")
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

    w("== DIFF HOLDOUT vs SOLO_ZONA (¿el ancla sostiene el +141?) ==")
    base_z = rows_by_split["holdout"]["SOLO_ZONA"][0]
    for p in ("ZONA_ANCLA", "ZONA_X_GATILLO", "ZONA_ANCLA_TECHO", "PODA_R0"):
        r = rows_by_split["holdout"][p][0]
        w(fila_cmp(p, r, base_z))
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
            f"  {i}. {p:<18} HOLD cov {pct(r['go'], r['n'])} banda {pct(r['hit'], r['go'])} "
            f"pnl {r['pnl']:+.0f}  PnL>0 {h['verdes']}/{h['n_h']}  "
            f"| TRAIN cov {pct(rt['go'], rt['n'])} banda {pct(rt['hit'], rt['go'])} "
            f"pnl {rt['pnl']:+.0f}"
        )
    w()

    ho = rows_by_split["holdout"]
    tr = rows_by_split["train"]
    r0h, r0hh = ho["PODA_R0"]
    szh, _ = ho["SOLO_ZONA"]
    zah, zahh = ho["ZONA_ANCLA"]
    zth, _ = ho["ZONA_ANCLA_TECHO"]
    gth, _ = ho["GATILLO_HORA"]
    xh, _ = ho["ZONA_X_GATILLO"]
    ad_h = walked_by_split["holdout"].ancla_diag
    zd_h = walked_by_split["holdout"].zona_diag

    w("== LECTURA ==")
    w("  ESPERADO vs LEAK")
    w("  SOLO_ZONA no usa el m0 de la G que cae. m_est=(m_ancla+gap_del_slot)")
    w("  mod 60. En vivo: te sientas en la silla cuyo reloj = tip±1, sin")
    w("  saber si cae G. El walk solo puntúa eventos G→G.")
    w(
        f"  Esta cinta hold: SOLO_ZONA {pct(szh['go'], szh['n'])} / "
        f"{pct(szh['hit'], szh['go'])} / {szh['pnl']:+.0f}  "
        f"(R1 HOLD era 28.3%/89.0%/+141; cinta +1 h, no se reabre)."
    )
    w(
        f"  Reloj vs real d≤1 {pct(zd_h['d0'] + zd_h['d1'], zd_h['n_poda'])}."
        f"  Cola silla n={int(ad_h['silla']['n'])} "
        f"{pct(int(ad_h['silla']['hit']), int(ad_h['silla']['n']))} "
        f"{ad_h['silla']['pnl']:+.0f} · no-silla n={int(ad_h['no_silla']['n'])} "
        f"{pct(int(ad_h['no_silla']['hit']), int(ad_h['no_silla']['n']))} "
        f"{ad_h['no_silla']['pnl']:+.0f}."
    )
    w(
        f"  LEAK (filtrar por m0 futuro): n={zd_h['leak_n']} banda 100% pnl "
        f"+{zd_h['leak_n']}. Eso NO es SOLO_ZONA. El 88–89% es silla + "
        f"física 1 tiro≈1 min, no oráculo ni leak de minuto."
    )
    w()
    w("  ¿ZONA_ANCLA sostiene el +141?")
    w("  NO. El 89% no sobrevive sin el reloj del slot.")
    w(
        f"  ZONA_ANCLA HOLD {pct(zah['go'], zah['n'])} / "
        f"{pct(zah['hit'], zah['go'])} / {zah['pnl']:+.0f}  "
        f"PnL>0 {zahh['verdes']}/{zahh['n_h']}  vs R0 "
        f"{pct(r0h['go'], r0h['n'])} / {pct(r0h['hit'], r0h['go'])} / "
        f"{r0h['pnl']:+.0f}  vs SOLO_ZONA {szh['pnl']:+.0f}."
    )
    w(
        f"  Train ZONA_ANCLA {pct(tr['ZONA_ANCLA'][0]['go'], tr['ZONA_ANCLA'][0]['n'])} / "
        f"{pct(tr['ZONA_ANCLA'][0]['hit'], tr['ZONA_ANCLA'][0]['go'])} / "
        f"{tr['ZONA_ANCLA'][0]['pnl']:+.0f} vs R0 "
        f"{tr['PODA_R0'][0]['pnl']:+.0f} vs SOLO_ZONA "
        f"{tr['SOLO_ZONA'][0]['pnl']:+.0f}."
    )
    w(
        f"  Sí recorta la cola lejana: hold tip fuera n={int(ad_h['fuera_ancla']['n'])} "
        f"banda {pct(int(ad_h['fuera_ancla']['hit']), int(ad_h['fuera_ancla']['n']))} "
        f"pnl {ad_h['fuera_ancla']['pnl']:+.0f}  "
        f"(train n={int(walked_by_split['train'].ancla_diag['fuera_ancla']['n'])} "
        f"banda 4.2% pnl −415). No persigas paga. No es el 89%."
    )
    w(
        f"  TECHO ≡ ANCLA en esta cinta (incluir mG+1 no movió ningún GO). "
        f"X_GATILLO HOLD {pct(xh['go'], xh['n'])} / {pct(xh['hit'], xh['go'])} / "
        f"{xh['pnl']:+.0f}  (Δ vs ANCLA +3; train +1346 vs +1216)."
    )
    w(
        f"  LOOK (no política): tip EXACTO en +2..+4 hold n="
        f"{int(ad_h['tip_d0']['n'])} banda "
        f"{pct(int(ad_h['tip_d0']['hit']), int(ad_h['tip_d0']['n']))} "
        f"pnl {ad_h['tip_d0']['pnl']:+.0f} · anillo d=1 n="
        f"{int(ad_h['tip_d1']['n'])} banda "
        f"{pct(int(ad_h['tip_d1']['hit']), int(ad_h['tip_d1']['n']))} "
        f"pnl {ad_h['tip_d1']['pnl']:+.0f}. El ±1 del ancla resta."
        f" No se corona. Solo con pedido."
    )
    w("  Puerta viva: SOLO_ZONA (silla, no leak) ≥ ZONA_X_GATILLO (ráfaga")
    w("  en el ancla × no 1ª G) ≥ ZONA_ANCLA ≥ PODA_R0. No cable. No ML.")
    w("  Siguiente (no ML, no cable): ¿tip exacto en +2..+4, o sentarse")
    w("  la silla también cuando el tiro es R (juez de silla vacía)?")
    w("  Formas, no coronas. Cero fuzzy.")
    w()

    path = OUT / "LAB_SENIOR_PODA_R2.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"[ok] {path}")


if __name__ == "__main__":
    main()
