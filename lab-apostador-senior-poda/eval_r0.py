# -*- coding: utf-8 -*-
"""
R0 senior-poda: puerta de poda × tip LC-01 × pools-ayuda.
  python eval_r0.py → reports/LAB_SENIOR_PODA_R0.txt
Cero prod. Cero LIVE. Cero ML/fuzzy.
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

POLS = ("LC01_ALL", "SEQUIA3_VIEJO", "PODA", "PODA_AYUDA_P8", "PODA_AYUDA_K2")

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
    """A: ancla ya hubo (gap conocido) · no sequía · +2..+4 · +1 solo Tren/Estirada."""
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


def decidir(pol: str, *, gap: int, tren: bool, estirada: bool, acuerdo_p8: bool, acuerdo_p0: bool):
    if pol == "LC01_ALL":
        return "GO_WEAK", STAKE_WEAK, ["all_g"]
    if pol == "SEQUIA3_VIEJO":
        if 1 <= gap <= 3:
            return "GO_WEAK", STAKE_WEAK, [f"seq3_gap={gap}"]
        return "NO_GO", 0, [f"seq3_fuera={gap}"]
    go, motivo = puerta_poda(gap, tren, estirada)
    if not go:
        return "NO_GO", 0, [motivo]
    if pol == "PODA":
        return "GO_WEAK", STAKE_WEAK, [motivo]
    if pol == "PODA_AYUDA_P8":
        if acuerdo_p8:
            return "GO_WEAK", STAKE_WEAK, [motivo, "ayuda_p8"]
        return "NO_GO", 0, [motivo, "sin_ayuda_p8"]
    if pol == "PODA_AYUDA_K2":
        n = int(acuerdo_p0) + int(acuerdo_p8)
        if n >= 2:
            return "GO_WEAK", STAKE_WEAK, [motivo, "ayuda_k2"]
        return "NO_GO", 0, [motivo, f"ayuda_k={n}"]
    return "NO_GO", 0, ["desconocida"]


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
        chips_p0 = mesa.classic or []
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
            ac_p8 = acuerdo_tip(tip, chips_p8)
            ac_p0 = acuerdo_tip(tip, chips_p0)
            for pol in POLS:
                kind, stake, reasons = decidir(
                    pol,
                    gap=gap,
                    tren=tren,
                    estirada=estirada,
                    acuerdo_p8=ac_p8,
                    acuerdo_p0=ac_p0,
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


def main() -> None:
    w("LAB SENIOR-PODA — R0")
    w("puerta: espera G post-sequía · poda +1 salvo Tren/Estirada · +2..+4")
    w("chip: LC-01 minutos ±1 · ayuda: acuerdo pools (no unión)")
    w("juez: banda d<=1 + PnL 1:1 en jugadas · hora a hora")
    w("CERO prod · CERO ML/fuzzy")
    w()

    horas, cinta = load_horas_y_cinta()
    w("precompute mesas (P0 classic + P8 INTER2)…")
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
    w("  AYUDA holdout solo es legible en horas con mesa; PODA/SEQUIA3/ALL no necesitan chips.")
    w()

    for split_name, subset in (("train", train), ("holdout", hold)):
        w(f"== {split_name.upper()} ==")
        walked = walk(subset, mesas)
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
        w()
        if split_name == "holdout":
            w("== DIFF HOLDOUT (vs baselines) ==")
            base_s3 = rows["SEQUIA3_VIEJO"][0]
            base_all = rows["LC01_ALL"][0]
            poda = rows["PODA"][0]
            w(
                f"  PODA − SEQUIA3_VIEJO:  Δbanda {(poda['hit_rate'] - base_s3['hit_rate']) * 100:+.1f}pp  "
                f"Δpnl {poda['pnl'] - base_s3['pnl']:+.1f}  "
                f"Δcov {(poda['cov'] - base_s3['cov']) * 100:+.1f}pp"
            )
            w(
                f"  PODA − LC01_ALL:       Δbanda {(poda['hit_rate'] - base_all['hit_rate']) * 100:+.1f}pp  "
                f"Δpnl {poda['pnl'] - base_all['pnl']:+.1f}  "
                f"Δcov {(poda['cov'] - base_all['cov']) * 100:+.1f}pp"
            )
            ayuda = rows["PODA_AYUDA_P8"][0]
            k2 = rows["PODA_AYUDA_K2"][0]
            w(
                f"  PODA_AYUDA_P8 − PODA:  Δbanda {(ayuda['hit_rate'] - poda['hit_rate']) * 100:+.1f}pp  "
                f"Δpnl {ayuda['pnl'] - poda['pnl']:+.1f}  "
                f"Δcov {(ayuda['cov'] - poda['cov']) * 100:+.1f}pp"
            )
            w(
                f"  PODA_AYUDA_K2 − PODA:  Δbanda {(k2['hit_rate'] - poda['hit_rate']) * 100:+.1f}pp  "
                f"Δpnl {k2['pnl'] - poda['pnl']:+.1f}  "
                f"Δcov {(k2['cov'] - poda['cov']) * 100:+.1f}pp"
            )
            w()
            hold_m = [h for h in hold if _mesa_ok(h)]
            if hold_m and len(hold_m) < len(hold):
                w(f"== HOLDOUT SOLO HORAS CON MESA ({len(hold_m)}/{len(hold)}) — lectura AYUDA ==")
                walked_m = walk(hold_m, mesas)
                for p in ("PODA", "PODA_AYUDA_P8", "PODA_AYUDA_K2"):
                    r = resumen_decs(walked_m.decs[p])
                    h = juez_hora(walked_m.por_hora[p])
                    dump_pol(p, r, h)
                poda_m = resumen_decs(walked_m.decs["PODA"])
                ayuda_m = resumen_decs(walked_m.decs["PODA_AYUDA_P8"])
                k2_m = resumen_decs(walked_m.decs["PODA_AYUDA_K2"])
                w(
                    f"  AYUDA_P8 − PODA (mesa): Δbanda {(ayuda_m['hit_rate'] - poda_m['hit_rate']) * 100:+.1f}pp  "
                    f"Δpnl {ayuda_m['pnl'] - poda_m['pnl']:+.1f}  "
                    f"Δcov {(ayuda_m['cov'] - poda_m['cov']) * 100:+.1f}pp"
                )
                w(
                    f"  AYUDA_K2 − PODA (mesa): Δbanda {(k2_m['hit_rate'] - poda_m['hit_rate']) * 100:+.1f}pp  "
                    f"Δpnl {k2_m['pnl'] - poda_m['pnl']:+.1f}  "
                    f"Δcov {(k2_m['cov'] - poda_m['cov']) * 100:+.1f}pp"
                )
                w()

    w("== LECTURA ==")
    w("  Go/No-Go vigente (pill) ya habla esta puerta. Este R0 mide el APOSTADOR.")
    w("  SEQUIA3_VIEJO = misma ventana que el lab 2026-09-04 (incluye +1).")
    w("  Ayuda ≠ segundo tip: solo recorta stake. Cero unión de chips.")
    w("  ML/fuzzy: no en R0. Primero la puerta. Fuzzy senior ya se midió")
    w("  sin esta poda (SENIOR_FUZZY hold pnl −167). Otro edificio: no se nombra.")
    w()

    path = OUT / "LAB_SENIOR_PODA_R0.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"[ok] {path}")


if __name__ == "__main__":
    main()
