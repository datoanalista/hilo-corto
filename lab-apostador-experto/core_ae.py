# -*- coding: utf-8 -*-
"""Núcleo lab-apostador-experto — solo lectura. Cero prod."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
GEXP = ROOT / "lab-g-explosion"
sys.path.insert(0, str(GEXP))
sys.path.insert(0, str(ROOT))

from core_ex import load_cinta  # noqa: E402
from src.boleto_inter2 import aplicar_inter2_live, precompute_beta_chips  # noqa: E402
from src.estado import PRIMERA_UTIL, Estado, siguiente_tag  # noqa: E402
from src.lectores import cargar_ingesta  # noqa: E402
from src.motor import emitir_boleto  # noqa: E402

HOLDOUT = 72
STAKE_WEAK = 1
STAKE_STRONG = 3
EWMA_ALPHA = 0.08


def p30(xs: list[float], fallback: float = 5.0) -> float:
    if not xs:
        return fallback
    ys = sorted(xs)
    idx = min(len(ys) - 1, max(0, int(len(ys) * 0.30)))
    return float(ys[idx])


def tip_lc01(luces: list[int]) -> int | None:
    xs = sorted({int(m) % 60 for m in luces})
    if not xs:
        return None
    T = xs[-1]
    if T >= 59:
        return None
    gaps = [xs[i] - xs[i - 1] for i in range(1, len(xs))]
    gap = max(1, int(round(p30(gaps, 5.0))))
    return min(59, T + gap)


def dist_anillo(a: int, b: int) -> int:
    d = abs((a % 60) - (b % 60))
    return min(d, 60 - d)


def hit_banda(tip: int, real: int) -> bool:
    return dist_anillo(tip, real) <= 1


@dataclass
class Memoria:
    ewma: float = 0.40
    miss_streak: int = 0
    n: int = 0

    def update(self, hit: bool) -> None:
        self.n += 1
        x = 1.0 if hit else 0.0
        self.ewma = (1 - EWMA_ALPHA) * self.ewma + EWMA_ALPHA * x
        self.miss_streak = 0 if hit else self.miss_streak + 1


@dataclass
class Decision:
    tag: str
    tip: int
    real: int
    policy: str
    kind: str
    stake: int
    hit: bool
    pnl: float
    score: float
    acuerdo: bool
    ewma: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class MesaChips:
    classic: list[int]
    inter2: list[int]


def precompute_mesas(cinta) -> dict[str, MesaChips]:
    """tag_for → chips Pool0 classic + Pool8 INTER2. Walk causal igual tablero."""
    if PRIMERA_UTIL not in cinta.horas:
        primera = cinta.orden[0]
    else:
        primera = PRIMERA_UTIL
    i0 = cinta.orden.index(primera)
    estado = Estado()
    beta_by_for = precompute_beta_chips(cinta)
    out: dict[str, MesaChips] = {}
    for i in range(i0, len(cinta.orden)):
        tag = cinta.orden[i]
        estado.cerrar(cinta.get(tag))
        doc = emitir_boleto(estado)
        classic = list(doc.get("boleto") or [])
        nxt = cinta.orden[i + 1] if i + 1 < len(cinta.orden) else siguiente_tag(tag)
        doc_i2 = aplicar_inter2_live(doc, classic, beta_by_for.get(nxt) or {})
        inter2 = list(doc_i2.get("boleto") or classic)
        out[nxt] = MesaChips(classic=classic, inter2=inter2)
    return out


def acuerdo_tip(tip: int, chips: list[int]) -> bool:
    if not chips:
        return False
    return any(dist_anillo(tip, c) <= 1 for c in chips)


def decidir_senior(
    tip: int,
    chips_p8: list[int],
    mem: Memoria,
    *,
    theta_weak: float = 0.42,
    theta_strong: float = 0.62,
) -> tuple[str, int, float, list[str]]:
    reasons: list[str] = []
    acuerdo = acuerdo_tip(tip, chips_p8)
    lc_edge = 1.0
    ewma_norm = max(0.0, min(1.0, (mem.ewma - 0.25) / 0.35))
    miss_pen = min(3, mem.miss_streak) / 3.0
    score = (
        0.40 * lc_edge
        + 0.30 * (1.0 if acuerdo else 0.0)
        + 0.30 * ewma_norm
        - 0.15 * miss_pen
    )
    reasons.append(f"ewma={mem.ewma:.2f}")
    reasons.append(f"miss_streak={mem.miss_streak}")
    reasons.append("acuerdo_P8" if acuerdo else "sin_acuerdo_P8")
    if mem.miss_streak >= 2 and mem.ewma < 0.38:
        reasons.append("gate_racha_fria")
        return "NO_GO", 0, score, reasons
    if score >= theta_strong and acuerdo:
        reasons.append("gema")
        return "GO_STRONG", STAKE_STRONG, score, reasons
    if score >= theta_weak:
        reasons.append("piedra")
        return "GO_WEAK", STAKE_WEAK, score, reasons
    reasons.append("pasar")
    return "NO_GO", 0, score, reasons


def decidir_ewma_gate(mem: Memoria, floor: float = 0.36) -> tuple[str, int, float, list[str]]:
    if mem.n >= 8 and mem.ewma < floor:
        return "NO_GO", 0, mem.ewma, [f"ewma_bajo={mem.ewma:.2f}"]
    return "GO_WEAK", STAKE_WEAK, mem.ewma, ["ewma_ok"]


def decidir_soft(
    tip: int,
    chips_p8: list[int],
    mem: Memoria,
    *,
    theta_weak: float = 0.42,
) -> tuple[str, int, float, list[str]]:
    """Fuzzy senior sin STRONG: solo WEAK / NO_GO."""
    kind, stake, score, reasons = decidir_senior(
        tip, chips_p8, mem, theta_weak=theta_weak, theta_strong=9.0
    )
    if kind == "GO_STRONG":
        kind, stake = "GO_WEAK", STAKE_WEAK
        reasons = list(reasons) + ["soft_no_strong"]
    return kind, stake, score, reasons


def indices_g_en_tiros(h) -> list[int]:
    """Índices en h.tiros de cada G (orden de aparición)."""
    out = []
    for i, t in enumerate(h.tiros or []):
        if getattr(t, "color", None) == "G":
            out.append(i)
    return out


def gap_tiros_entre_g(h, i_g: int, j_g: int) -> int | None:
    """
    Cuántos tiros hay desde G_i hasta G_j (j_idx - i_idx).
    Ventana vigente: tras una G, esperar hasta VENTANA_SEQUIA tiros;
    si gap > ventana → sequía (no cazar esa G).
    """
    idxs = indices_g_en_tiros(h)
    if i_g < 0 or j_g >= len(idxs) or j_g != i_g + 1:
        return None
    return idxs[j_g] - idxs[i_g]


VENTANA_SEQUIA = 3  # gap_tiros <= 3 → cazar; >3 → sequía / esperar ancla

# Políticas sequía (nombre histórico SEQUIA5* = alias de SEQUIA*)
_POLS_SEQUIA_BASE = frozenset(
    {
        "SEQUIA",
        "SEQUIA5",  # alias
        "SEQUIA_P8",
        "SEQUIA_EWMA",
        "SEQUIA5_EWMA",  # alias
        "SEQUIA_SOFT",
        "SEQUIA_P8_EWMA",
        "SEQUIA_P8_SOFT",
        "SEQUIA_MISS2",  # R3: en ventana, NO_GO si miss_streak>=2
    }
)


def _decidir_pol(
    pol: str,
    *,
    tip: int,
    chips_p8: list[int],
    mem: Memoria,
    gap: int,
    en_ventana: bool,
) -> tuple[str, int, float, list[str]] | None:
    if pol == "ALWAYS_TIP":
        return "GO_WEAK", STAKE_WEAK, mem.ewma, ["always"]
    if pol == "NEVER":
        return "NO_GO", 0, 0.0, ["never"]
    if pol == "EWMA_GATE":
        return decidir_ewma_gate(mem)
    if pol == "SENIOR_FUZZY":
        return decidir_senior(tip, chips_p8, mem)

    if pol not in _POLS_SEQUIA_BASE:
        return None

    if not en_ventana:
        return "NO_GO", 0, mem.ewma, [f"sequia_gap={gap}"]

    base_r = [f"ventana_gap={gap}"]
    acuerdo = acuerdo_tip(tip, chips_p8)

    if pol in ("SEQUIA", "SEQUIA5"):
        return "GO_WEAK", STAKE_WEAK, mem.ewma, base_r

    if pol in ("SEQUIA_EWMA", "SEQUIA5_EWMA"):
        kind, stake, score, reasons = decidir_ewma_gate(mem)
        return kind, stake, score, base_r + reasons

    if pol == "SEQUIA_P8":
        if acuerdo:
            return "GO_WEAK", STAKE_WEAK, mem.ewma, base_r + ["acuerdo_P8"]
        return "NO_GO", 0, mem.ewma, base_r + ["sin_acuerdo_P8"]

    if pol == "SEQUIA_SOFT":
        kind, stake, score, reasons = decidir_soft(tip, chips_p8, mem)
        return kind, stake, score, base_r + reasons

    if pol == "SEQUIA_P8_EWMA":
        if not acuerdo:
            return "NO_GO", 0, mem.ewma, base_r + ["sin_acuerdo_P8"]
        kind, stake, score, reasons = decidir_ewma_gate(mem)
        return kind, stake, score, base_r + ["acuerdo_P8"] + reasons

    if pol == "SEQUIA_P8_SOFT":
        if not acuerdo:
            return "NO_GO", 0, mem.ewma, base_r + ["sin_acuerdo_P8"]
        kind, stake, score, reasons = decidir_soft(tip, chips_p8, mem)
        return kind, stake, score, base_r + reasons

    if pol == "SEQUIA_MISS2":
        if mem.miss_streak >= 2:
            return "NO_GO", 0, mem.ewma, base_r + [f"miss2={mem.miss_streak}"]
        return "GO_WEAK", STAKE_WEAK, mem.ewma, base_r + ["miss_ok"]

    return None


def walk_eventos(
    horas, mesas: dict[str, MesaChips], policies: list[str]
) -> dict[str, list[Decision]]:
    out: dict[str, list[Decision]] = {p: [] for p in policies}
    mems = {p: Memoria() for p in policies}

    for h in horas:
        gs = sorted(h.gs, key=lambda g: g.m0)
        if len(gs) < 2:
            continue
        mesa = mesas.get(h.tag) or MesaChips([], [])
        chips_p8 = mesa.inter2 or mesa.classic
        idxs_g = indices_g_en_tiros(h)
        luces: list[int] = []
        for i in range(len(gs) - 1):
            luces.append(gs[i].m0)
            tip = tip_lc01(luces)
            if tip is None:
                continue
            real = gs[i + 1].m0
            hit = hit_banda(tip, real)
            if len(idxs_g) >= i + 2:
                gap = idxs_g[i + 1] - idxs_g[i]
            else:
                gap = 1
            en_ventana = gap <= VENTANA_SEQUIA

            for pol in policies:
                mem = mems[pol]
                decided = _decidir_pol(
                    pol,
                    tip=tip,
                    chips_p8=chips_p8,
                    mem=mem,
                    gap=gap,
                    en_ventana=en_ventana,
                )
                if decided is None:
                    continue
                kind, stake, score, reasons = decided
                pnl = float(stake if hit else -stake) if stake > 0 else 0.0
                out[pol].append(
                    Decision(
                        tag=h.tag,
                        tip=tip,
                        real=real,
                        policy=pol,
                        kind=kind,
                        stake=stake,
                        hit=hit,
                        pnl=pnl,
                        score=score,
                        acuerdo=acuerdo_tip(tip, chips_p8),
                        ewma=mem.ewma,
                        reasons=reasons,
                    )
                )
                if pol == "NEVER":
                    continue
                # Observa tip siempre (también en NO_GO) para calibrar memoria
                mem.update(hit)
    return out


def split_holdout(horas, n_hold: int = HOLDOUT):
    if len(horas) <= n_hold + 10:
        return horas, []
    return horas[:-n_hold], horas[-n_hold:]


def resumen(decs: list[Decision]) -> dict:
    if not decs:
        return {
            "n": 0,
            "go": 0,
            "hit_go": 0,
            "hit_rate_go": 0.0,
            "pnl": 0.0,
            "avg_pnl": 0.0,
            "n_strong": 0,
            "n_weak": 0,
            "n_nogo": 0,
            "coverage_go": 0.0,
            "acuerdo_rate": 0.0,
        }
    goes = [d for d in decs if d.stake > 0]
    hits = [d for d in goes if d.hit]
    pnl = sum(d.pnl for d in decs)
    return {
        "n": len(decs),
        "go": len(goes),
        "hit_go": len(hits),
        "hit_rate_go": (len(hits) / len(goes)) if goes else 0.0,
        "pnl": pnl,
        "avg_pnl": pnl / len(decs),
        "n_strong": sum(1 for d in decs if d.kind == "GO_STRONG"),
        "n_weak": sum(1 for d in decs if d.kind == "GO_WEAK"),
        "n_nogo": sum(1 for d in decs if d.kind == "NO_GO"),
        "coverage_go": len(goes) / len(decs),
        "acuerdo_rate": sum(1 for d in decs if d.acuerdo) / len(decs),
    }


def load_horas_y_cinta():
    horas = load_cinta()
    cinta, _, _ = cargar_ingesta("")
    return horas, cinta
