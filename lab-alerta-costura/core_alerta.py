# -*- coding: utf-8
"""Nucleo lab-alerta-costura — senales @min 55 vs costura 58-03."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.lectores import Cinta, HoraCruda, Tiro, arranque_proxima, cargar_ingesta  # noqa: E402

ALERT_MIN = 55  # alerta se prende al entrar min 55
SNAPSHOT_MIN = 55  # estado conocido al inicio de min 55 (= hasta fin min 54)
HOLDOUT = 72


@dataclass
class Snap55:
    tag: str
    hod: int
    day: str
    done: list[Tiro]
    ongoing: Tiro | None
    last: Tiro | None
    nG: int
    sumG: int
    lastG: Tiro | None
    sec_desde_G: int | None
    ultimo_R: bool
    ultimo_L_largo: bool
    L_abierto: bool
    L_wrap_proxy: bool
    G_en_50_54: bool
    sin_G: bool
    sin_early_0_9: bool
    arranque_prox_s: int | None
    arranque_prox_cerca: bool


@dataclass
class PairRow:
    tag_n: str
    tag_n1: str
    hod: int
    # target
    costura: bool
    cola_58: bool
    early_03: bool
    # signals from hN @55
    snap: Snap55


def _gs(tiros: list[Tiro]) -> list[Tiro]:
    return [t for t in tiros if t.color == "G" and t.lumen is not None]


def state_at_min(tiros: list[Tiro], min_start: int) -> tuple[list[Tiro], Tiro | None]:
    """Tiros completos antes de min_start:00 y tiro en curso si cruza el corte."""
    cutoff = min_start * 60
    done: list[Tiro] = []
    ongoing: Tiro | None = None
    for t in tiros or []:
        if t.start_s >= cutoff:
            break
        end = t.start_s + t.dur_s
        if end >= cutoff:
            ongoing = t
            break
        done.append(t)
    return done, ongoing


def snap55(h: HoraCruda) -> Snap55:
    tiros = h.tiros_nucleo or []
    done, ongoing = state_at_min(tiros, SNAPSHOT_MIN)
    last = ongoing if ongoing else (done[-1] if done else None)
    gs = _gs(done)
    last_g = gs[-1] if gs else None
    sec_desde = None
    if last_g:
        sec_desde = SNAPSHOT_MIN * 60 - (last_g.start_s + last_g.dur_s + 1)
        sec_desde = max(0, sec_desde)
    elif last:
        sec_desde = SNAPSHOT_MIN * 60 - (last.start_s + last.dur_s + 1)
        sec_desde = max(0, sec_desde)

    ultimo_r = bool(last and last.color == "R")
    ultimo_l_largo = bool(last and last.largo)
    l_abierto = ongoing is not None and ongoing.color == "R"
    l_wrap = False
    if ongoing and ongoing.color == "R":
        end_s = ongoing.start_s + ongoing.dur_s
        # L que aun corre @55 y termina en 58+ o cruza hora
        end_m = end_s // 60
        l_wrap = end_m >= 58 or end_s >= 3600
    elif last and last.color == "R" and last.m0 >= 50:
        l_wrap = last.m0 >= 58 or last.m1 < last.m0 or last.start_s + last.dur_s >= 3540

    g_cola = any(t.m0 >= 50 for t in gs)
    sin_g = len(gs) == 0
    sin_early = not any(t.m0 <= 9 for t in gs)
    ap = arranque_proxima(last) if last else 0
    ap_cerca = ap <= 180 if last else False

    tag = h.tag.lower()
    hod = int(tag.split("-")[0][1:])
    day = tag.split("-")[1]
    return Snap55(
        tag=tag,
        hod=hod,
        day=day,
        done=done,
        ongoing=ongoing,
        last=last,
        nG=len(gs),
        sumG=sum(t.lumen for t in gs),
        lastG=last_g,
        sec_desde_G=sec_desde,
        ultimo_R=ultimo_r,
        ultimo_L_largo=ultimo_l_largo,
        L_abierto=l_abierto,
        L_wrap_proxy=l_wrap,
        G_en_50_54=g_cola,
        sin_G=sin_g,
        sin_early_0_9=sin_early,
        arranque_prox_s=ap if last else None,
        arranque_prox_cerca=ap_cerca,
    )


def target_costura(h_n: HoraCruda, h_n1: HoraCruda) -> tuple[bool, bool, bool]:
    """Positivo = G cola 58+ en hN o 1er G de hN+1 en min 0-3."""
    gs_n = _gs(h_n.tiros_nucleo or [])
    gs_n1 = _gs(h_n1.tiros_nucleo or [])
    cola = any(t.m0 >= 58 for t in gs_n)
    early = False
    if gs_n1:
        first = min(gs_n1, key=lambda t: (t.m0, t.s0))
        early = first.m0 <= 3
    return cola or early, cola, early


def consecutivos(cinta: Cinta) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for i, tag in enumerate(cinta.orden):
        if i + 1 >= len(cinta.orden):
            break
        tag2 = cinta.orden[i + 1]
        hod1 = int(tag.split("-")[0][1:])
        hod2 = int(tag2.split("-")[0][1:])
        day1 = tag.split("-")[1]
        day2 = tag2.split("-")[1]
        if hod2 != (hod1 + 1) % 24:
            continue
        if day1 != day2 and not (hod1 == 23 and hod2 == 0):
            continue
        out.append((tag.lower(), tag2.lower()))
    return out


def build_pairs(cinta: Cinta) -> list[PairRow]:
    rows: list[PairRow] = []
    for t_n, t_n1 in consecutivos(cinta):
        h_n = cinta.get(t_n)
        h_n1 = cinta.get(t_n1)
        costura, cola, early = target_costura(h_n, h_n1)
        snap = snap55(h_n)
        rows.append(
            PairRow(
                tag_n=t_n,
                tag_n1=t_n1,
                hod=snap.hod,
                costura=costura,
                cola_58=cola,
                early_03=early,
                snap=snap,
            )
        )
    return rows


def split_holdout(rows: list[PairRow], holdout: int = HOLDOUT):
    if len(rows) <= holdout:
        return rows, []
    return rows[:-holdout], rows[-holdout:]


def rate(xs: list[PairRow], pred) -> dict:
    if not xs:
        return {"n": 0, "pred": 0, "tp": 0, "fp": 0, "fn": 0, "prec": 0.0, "rec": 0.0, "lift": 0.0}
    pos = sum(1 for r in xs if r.costura)
    base = pos / len(xs)
    sel = [r for r in xs if pred(r)]
    if not sel:
        return {"n": len(xs), "pred": 0, "tp": 0, "fp": 0, "fn": pos, "prec": 0.0, "rec": 0.0, "lift": 0.0, "base": base}
    tp = sum(1 for r in sel if r.costura)
    fp = len(sel) - tp
    fn = pos - tp
    prec = tp / len(sel)
    rec = tp / max(1, pos)
    lift = prec / base if base else 0.0
    return {
        "n": len(xs),
        "pred": len(sel),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "prec": prec,
        "rec": rec,
        "lift": lift,
        "base": base,
        "cov": len(sel) / len(xs),
    }


def fmt_pct(x: float) -> str:
    return f"{100 * x:.0f}%"
