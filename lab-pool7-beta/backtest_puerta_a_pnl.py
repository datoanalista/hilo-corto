# -*- coding: utf-8 -*-
"""
PnL histórico Pool7 + Puerta A (media≥68 latched + forma en ALERTA).
Apuesta: $100/bono × 4 = $400 por clic centro (1 cuenta).
Fuente: depurar-all-4G-detail (+ live merge) vía lab-g-explosion.

  python backtest_puerta_a_pnl.py
"""
from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent.parent / "hilo-corto"
GEXP = ROOT / "lab-g-explosion"
GCOLA = ROOT / "lab-g-cola"
sys.path.insert(0, str(GEXP))
sys.path.insert(0, str(GCOLA))
sys.path.insert(0, str(ROOT / "lab-apostador-experto"))

from core_ae import (  # noqa: E402
    dist_anillo,
    indices_g_en_tiros,
    tip_lc01,
)
from core_ex import load_cinta  # noqa: E402
from core_gc import estado_a_min  # noqa: E402

OUT = LAB / "reports" / "BACKTEST_PUERTA_A_PNL.txt"

MEDIA_ON = 68.0
MEDIA_OFF = 40.0
SUMA_COLA = 850
MINUTO_LATE = 40
STAKE = 400.0
POOL7_GAP_MAX = 3

RESET_G_MIN = 40
RESET_NEXT_MAX = 22
RESET_DROP_MIN = 18


def techo_hora(horas_by_tag: dict, tag: str) -> bool:
    import re

    m = re.match(r"^h(\d{1,2})-(\d{6})$", tag.strip(), re.I)
    if not m:
        return False
    hod = int(m.group(1))
    suf = m.group(2)
    prev_tag = f"h{hod - 1}-{suf}" if hod > 0 else None
    if not prev_tag:
        return False
    prev = horas_by_tag.get(prev_tag.lower())
    if not prev:
        return False
    return prev.sum_g >= SUMA_COLA


def es_par_reset(prev: int, nxt: int) -> bool:
    return prev >= RESET_G_MIN and (
        nxt <= RESET_NEXT_MAX or prev - nxt >= RESET_DROP_MIN
    )


def clasificar_forma(seq: list[int]) -> tuple[str, bool]:
    if len(seq) < 2:
        return "sin_datos", False
    if es_par_reset(seq[-2], seq[-1]):
        return "reset_reciente", False
    if len(seq) >= 2:
        last = seq[-1]
        prev = seq[:-1]
        prev_max = max(prev)
        prev_mean = sum(prev) / len(prev)
        if last >= 45 and prev_max <= 32 and last > prev_mean + 12:
            return "pico_aislado", False
    if len(seq) >= 3:
        tail = seq[-3:]
        ok = True
        for i in range(1, len(tail)):
            if tail[i] < tail[i - 1] - 2:
                ok = False
                break
        if ok and tail[-1] > tail[0] + 4:
            return "oleada_subiendo", True
    if len(seq) >= 3:
        tail = seq[-3:]
        if not any(x > 36 or x < 14 for x in tail):
            if tail[2] >= tail[1] >= tail[0] and tail[2] > tail[0]:
                return "piso_escalera", True
    if len(seq) >= 2:
        a, b = seq[-2], seq[-1]
        if not es_par_reset(a, b):
            if 24 <= a <= 42 and 24 <= b <= 42 and abs(a - b) <= 10:
                return "meseta", True
    return "mixta", False


def puerta_clasica_en_T(h, T: int, techo: bool) -> bool:
    if techo:
        return False
    st = estado_a_min(h, T)
    if st["nG"] < 2:
        return False
    if st["meanG"] < MEDIA_ON:
        return False
    if T >= MINUTO_LATE:
        return False
    if st["acum"] >= SUMA_COLA:
        return False
    if st["nG"] == 1 and st["maxG"] >= 85:
        return False
    return True


def puerta_forma_en_T(h, T: int, techo: bool) -> bool:
    if techo:
        return False
    st = estado_a_min(h, T)
    if st["nG"] < 2:
        return False
    if st["meanG"] < MEDIA_OFF:
        return False
    if T >= MINUTO_LATE:
        return False
    if st["acum"] >= SUMA_COLA:
        return False
    if st["nG"] == 1 and st["maxG"] >= 85:
        return False
    media_normal = MEDIA_OFF <= st["meanG"] < MEDIA_ON
    alerta_ok = (
        media_normal
        or (T < 15 and st["nG"] < 2)
        or (st["nG"] == 1 and st["maxG"] < 85)
        or (st["nG"] >= 2 and MEDIA_OFF <= st["meanG"] < MEDIA_ON)
    )
    if not alerta_ok:
        return False
    seq = [g.lumen for g in st["gs"]]
    _, fertil = clasificar_forma(seq)
    return fertil


def puerta_extendida_en_T(h, T: int, techo: bool) -> bool:
    return puerta_clasica_en_T(h, T, techo) or puerta_forma_en_T(h, T, techo)


def first_latch_open(h, techo: bool, extended: bool) -> int | None:
    fn = puerta_extendida_en_T if extended else puerta_clasica_en_T
    for T in range(60):
        if fn(h, T, techo=False):
            return T
    return None


def latched_active(h, m: int, open_at: int | None, techo: bool) -> bool:
    if techo or open_at is None:
        return False
    if m < open_at or m >= MINUTO_LATE:
        return False
    st = estado_a_min(h, max(0, m - 1))
    if st["acum"] >= SUMA_COLA:
        return False
    return True


def gap_tiro_desde_ultima_g(tiros, end: int) -> int | None:
    last = -1
    for i in range(end):
        if getattr(tiros[i], "color", None) == "G":
            last = i
    if last < 0:
        return None
    return end - last


def en_zona_tip(tip: int | None, minuto: int) -> bool:
    if tip is None:
        return False
    return dist_anillo(int(tip), int(minuto)) <= 1


def premio_g(lumen: int, stake: float | None = None) -> float:
    """Escala desde capturas ~$200 stake → premio ≈ lumen×20."""
    s = STAKE if stake is None else stake
    return float(lumen) * 20.0 * (s / 200.0)


def luces_g_hasta(tiros, end: int) -> list[int]:
    out = []
    for i in range(end):
        t = tiros[i]
        if getattr(t, "color", None) == "G":
            out.append(int(t.m0))
    return out


@dataclass
class Stats:
    n_bets: int = 0
    n_wins: int = 0
    pnl: float = 0.0
    by_day: dict = field(default_factory=lambda: defaultdict(float))
    by_week: dict = field(default_factory=lambda: defaultdict(float))
    bank_min: float = float("inf")
    bank_end: float = 0.0
    max_drawdown: float = 0.0
    hit_zero: bool = False


def week_key(dt: datetime) -> str:
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def sim_horas_fixed(horas, horas_by_tag: dict, *, extended: bool, bank_start: float) -> Stats:
    """Simula apuestas como el bot: 1 clic/$400 por minuto piso en banda, con latch Puerta A."""
    st = Stats()
    bank = bank_start
    peak = bank_start

    for h in horas:
        techo = techo_hora(horas_by_tag, h.tag)
        open_at = first_latch_open(h, techo, extended)
        tips_hechos: set[int] = set()
        tiros = h.tiros or []
        if len(tiros) < 2:
            continue

        for i in range(len(tiros)):
            gap = gap_tiro_desde_ultima_g(tiros, i)
            luces = luces_g_hasta(tiros, i)
            tip = tip_lc01(luces) if luces else None

            t = tiros[i]
            min_piso = int(t.m0)

            puerta_dyn = (
                puerta_extendida_en_T(h, max(0, min_piso - 1), techo)
                if extended
                else puerta_clasica_en_T(h, max(0, min_piso - 1), techo)
            )
            puerta_latch = latched_active(h, min_piso, open_at, techo)
            puerta = puerta_dyn or puerta_latch
            ventana = gap is not None and gap <= POOL7_GAP_MAX
            en_zona = en_zona_tip(tip, min_piso)
            if not (puerta and ventana and en_zona):
                continue
            if min_piso in tips_hechos:
                continue
            tips_hechos.add(min_piso)

            st.n_bets += 1
            pnl_round = -STAKE
            if getattr(t, "color", None) == "G" and tip is not None:
                if dist_anillo(int(t.m0), int(tip)) <= 1:
                    lm = int(t.lumen or 0)
                    if lm > 0:
                        pnl_round += premio_g(lm, STAKE)
                        st.n_wins += 1

            st.pnl += pnl_round
            bank += pnl_round
            peak = max(peak, bank)
            st.max_drawdown = max(st.max_drawdown, peak - bank)
            st.bank_min = min(st.bank_min, bank)
            if bank <= 0:
                st.hit_zero = True

            st.by_day[h.dt.strftime("%Y-%m-%d")] += pnl_round
            st.by_week[week_key(h.dt)] += pnl_round

    st.bank_end = bank
    return st


def avg_dict(d: dict) -> tuple[float, float]:
    if not d:
        return 0.0, 0.0
    vals = list(d.values())
    return sum(vals) / len(vals), sum(vals) / max(1, len(set(k[:10] for k in d)))


def main() -> None:
    horas = load_cinta()
    horas_by_tag = {h.tag.lower(): h for h in horas}
    n_days = len({h.dt.date() for h in horas})
    n_weeks = len({week_key(h.dt) for h in horas})

    bank_start = 10_000.0

    st_old = sim_horas_fixed(horas, horas_by_tag, extended=False, bank_start=bank_start)
    st_new = sim_horas_fixed(horas, horas_by_tag, extended=True, bank_start=bank_start)

    lines: list[str] = []

    def w(s: str = "") -> None:
        lines.append(s)
        try:
            print(s)
        except UnicodeEncodeError:
            print(s.encode("ascii", "replace").decode("ascii"))

    w("BACKTEST PnL — Puerta A + Pool7 (histórico)")
    w(f"Horas con G: {len(horas)} · días calendario ~{n_days} · semanas ISO ~{n_weeks}")
    w(f"Apuesta: ${STAKE:.0f}/clic (4×$100) · banca inicial ${bank_start:,.0f}/cuenta")
    w("Premio en acierto: lumen × 20 × (stake/200) — proxy capturas $200→lumen×20")
    w("Reglas: tip LC-01 · zona min piso en tip±1 · gap≤3 tiros · latch Puerta A")
    w("  Clásica: ≥2 G, media≥68, min<40, suma<850, sin techo")
    w("  Ampliada: + forma (oleada/piso/meseta) con media 40–67 en ALERTA")
    w("")

    for label, st in [("Solo Puerta A clásica (media≥68)", st_old), ("Puerta A ampliada (+ forma)", st_new)]:
        avg_day = st.pnl / max(1, n_days)
        avg_week = st.pnl / max(1, n_weeks)
        hr = (100.0 * st.n_wins / st.n_bets) if st.n_bets else 0.0
        w("=" * 72)
        w(label)
        w("-" * 72)
        w(f"  Apuestas: {st.n_bets:,} · aciertos banda en tiro apostado: {st.n_wins:,} ({hr:.1f}%)")
        w(f"  PnL total: ${st.pnl:,.0f} · por apuesta: ${st.pnl / max(1, st.n_bets):,.2f}")
        w(f"  Promedio por día (calendario): ${avg_day:,.0f}")
        w(f"  Promedio por semana (ISO): ${avg_week:,.0f}")
        w(f"  Banca final (1 cuenta): ${st.bank_end:,.0f}")
        w(f"  Mínimo banca: ${st.bank_min:,.0f} · drawdown máx: ${st.max_drawdown:,.0f}")
        w(f"  ¿Llegó a $0? {'SÍ' if st.hit_zero else 'NO'} (banca inicial ${bank_start:,.0f})")
        w("")

    delta = st_new.pnl - st_old.pnl
    w(f"Delta ampliada vs clásica: ${delta:+,.0f} total · +{st_new.n_bets - st_old.n_bets:,} apuestas")
    w("")
    w("Notas:")
    w("  · Sin pill Brillo opaca (cinta no trae brillo); techo = hora tras suma G≥850.")
    w("  · 3 cuentas = ~3× PnL y ~3× riesgo de drawdown si apuestan en paralelo.")
    w("  · Premio real varía por tipo G; proxy puede desviarse ±20% del neto.")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"Escrito: {OUT}")


if __name__ == "__main__":
    main()
