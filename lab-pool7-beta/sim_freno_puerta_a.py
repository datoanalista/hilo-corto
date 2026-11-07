# -*- coding: utf-8 -*-
"""Simula Puerta A ampliada + stake + reglas de freno (histórico cinta)."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent.parent / "hilo-corto"
for p in (ROOT / "lab-g-explosion", ROOT / "lab-g-cola", ROOT / "lab-apostador-experto"):
    sys.path.insert(0, str(p))

from core_ae import dist_anillo, tip_lc01  # noqa: E402

import backtest_puerta_a_pnl as bt  # noqa: E402
from backtest_puerta_a_pnl import (  # noqa: E402
    POOL7_GAP_MAX,
    en_zona_tip,
    estado_a_min,
    first_latch_open,
    gap_tiro_desde_ultima_g,
    latched_active,
    luces_g_hasta,
    premio_g,
    puerta_clasica_en_T,
    puerta_extendida_en_T,
    techo_hora,
)

BANK0 = 20_000.0
STAKE = 800.0  # 4×200


@dataclass
class Res:
    pnl: float = 0.0
    n_bets: int = 0
    n_skipped: int = 0
    n_wins: int = 0
    bank_min: float = field(default_factory=lambda: BANK0)
    max_dd: float = 0.0
    hit_zero: bool = False
    bank_end: float = 0.0
    triggers: int = 0


def iter_bets(horas, horas_by_tag):
    """Genera oportunidades de apuesta en orden cronológico."""
    for h in horas:
        techo = techo_hora(horas_by_tag, h.tag)
        open_at = first_latch_open(h, techo, True)
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
            Tm = max(0, min_piso - 1)
            puerta_dyn = puerta_extendida_en_T(h, Tm, techo)
            puerta_latch = latched_active(h, min_piso, open_at, techo)
            puerta = puerta_dyn or puerta_latch
            ventana = gap is not None and gap <= POOL7_GAP_MAX
            en_zona = en_zona_tip(tip, min_piso)
            if not (puerta and ventana and en_zona):
                continue
            if min_piso in tips_hechos:
                continue
            tips_hechos.add(min_piso)
            st = estado_a_min(h, Tm)
            win = False
            pnl_if_bet = -STAKE
            if getattr(t, "color", None) == "G" and tip is not None:
                if dist_anillo(int(t.m0), int(tip)) <= 1:
                    lm = int(t.lumen or 0)
                    if lm > 0:
                        pnl_if_bet += premio_g(lm, STAKE)
                        win = True
            yield {
                "tag": h.tag,
                "min_piso": min_piso,
                "meanG": st["meanG"] or 0.0,
                "maxG": st["maxG"] or 0.0,
                "clasica": puerta_clasica_en_T(h, Tm, techo),
                "techo": techo,
                "win": win,
                "pnl": pnl_if_bet,
                "lumen_hit": int(t.lumen or 0) if win else 0,
                "tiro_g": getattr(t, "color", None) == "G",
            }


def sim(rule_id: str, *, dd_lim: float = 25_000) -> Res:
    horas = bt.load_cinta()
    horas_by_tag = {h.tag.lower(): h for h in horas}
    r = Res()
    bank = BANK0
    peak = BANK0
    trough = BANK0
    cur_tag = None
    loss_streak = 0
    paused = False
    skip_count = 0

    for b in iter_bets(horas, horas_by_tag):
        if b["tag"] != cur_tag:
            cur_tag = b["tag"]
            loss_streak = 0
            paused = False
            skip_count = 0

        dd = peak - bank

        if paused:
            resume = False
            if rule_id == "hora_siguiente":
                resume = False
            elif rule_id == "repunte_saldo_3k":
                resume = bank >= trough + 3_000
            elif rule_id == "g_grande_400":
                resume = b["tiro_g"] and (b["lumen_hit"] >= 400 or b["maxG"] >= 400)
            elif rule_id == "media68":
                resume = b["meanG"] >= 68
            elif rule_id == "2_tiros_espera":
                skip_count += 1
                resume = skip_count >= 2
            elif rule_id == "mix_hora_si_repunte":
                resume = bank >= trough + 2_000 or b["meanG"] >= 68
            if resume:
                paused = False
                skip_count = 0

        if not paused:
            fire = dd >= dd_lim or loss_streak >= 3 or bank <= 16_000
            if fire:
                paused = True
                trough = bank
                r.triggers += 1

        if paused:
            r.n_skipped += 1
            continue

        r.n_bets += 1
        pnl = b["pnl"]
        r.pnl += pnl
        bank += pnl
        if b["win"]:
            r.n_wins += 1
            loss_streak = 0
        else:
            loss_streak += 1
        peak = max(peak, bank)
        trough = min(trough, bank)
        r.max_dd = max(r.max_dd, peak - bank)
        r.bank_min = min(r.bank_min, bank)
        if bank <= 0:
            r.hit_zero = True

    r.bank_end = bank
    return r


def sim_none() -> Res:
    horas = bt.load_cinta()
    horas_by_tag = {h.tag.lower(): h for h in horas}
    r = Res()
    bank = BANK0
    peak = BANK0
    for b in iter_bets(horas, horas_by_tag):
        r.n_bets += 1
        r.pnl += b["pnl"]
        bank += b["pnl"]
        if b["win"]:
            r.n_wins += 1
        peak = max(peak, bank)
        r.max_dd = max(r.max_dd, peak - bank)
        r.bank_min = min(r.bank_min, bank)
        if bank <= 0:
            r.hit_zero = True
    r.bank_end = bank
    return r


def main():
    horas = bt.load_cinta()
    horas_by_tag = {h.tag.lower(): h for h in horas}
    # recovery analysis inline fixed
    events = 0
    rest_pnls = []
    rest_n = 0
    big_after = 0
    for h in horas:
        techo = techo_hora(horas_by_tag, h.tag)
        open_at = first_latch_open(h, techo, True)
        tips_hechos: set[int] = set()
        tiros = h.tiros or []
        streak = 0
        triggered = False
        rest: list[tuple[float, int]] = []
        for i in range(len(tiros)):
            gap = gap_tiro_desde_ultima_g(tiros, i)
            luces = luces_g_hasta(tiros, i)
            tip = tip_lc01(luces) if luces else None
            t = tiros[i]
            min_piso = int(t.m0)
            Tm = max(0, min_piso - 1)
            puerta_dyn = puerta_extendida_en_T(h, Tm, techo)
            puerta_latch = latched_active(h, min_piso, open_at, techo)
            puerta = puerta_dyn or puerta_latch
            ventana = gap is not None and gap <= POOL7_GAP_MAX
            en_zona = en_zona_tip(tip, min_piso)
            if not (puerta and ventana and en_zona):
                continue
            if min_piso in tips_hechos:
                continue
            tips_hechos.add(min_piso)
            pnl = -STAKE
            lm = 0
            win = False
            if getattr(t, "color", None) == "G" and tip is not None:
                if dist_anillo(int(t.m0), int(tip)) <= 1:
                    lm = int(t.lumen or 0)
                    if lm > 0:
                        pnl += premio_g(lm, STAKE)
                        win = True
            if not triggered:
                streak = 0 if win else streak + 1
                if streak >= 3:
                    triggered = True
                    events += 1
                continue
            rest.append((pnl, lm))
        if triggered and rest:
            s = sum(x[0] for x in rest)
            rest_pnls.append(s)
            rest_n += len(rest)
            big_after += sum(1 for x in rest if x[1] >= 400)

    bt.STAKE = 600.0
    base600 = bt.sim_horas_fixed(horas, horas_by_tag, extended=True, bank_start=BANK0)
    bt.STAKE = STAKE
    base800 = sim_none()
    import sim_freno_puerta_a as sfp

    sfp.STAKE = 600.0
    base150_freno = sim("mix_hora_si_repunte", dd_lim=25_000)
    sfp.STAKE = 800.0

    rules = [
        ("Pausa hasta siguiente hora", "hora_siguiente", 25_000),
        ("Pausa hasta repunte $3k desde fondo de freno", "repunte_saldo_3k", 25_000),
        ("Standby hasta G grande (>=400) o max hora >=400", "g_grande_400", 25_000),
        ("Standby hasta media G >=68 otra vez", "media68", 25_000),
        ("Esperar 2 oportunidades y reanudar", "2_tiros_espera", 25_000),
        ("Mix: repunte $2k en saldo O media>=68 (recomendado)", "mix_hora_si_repunte", 25_000),
        ("Freno temprano (DD $20k) + siguiente hora", "hora_siguiente", 20_000),
    ]

    print("=== Puerta A ampliada | banca $20.000 | apuesta $200/bono ($800/clic) ===")
    print(f"Sin freno: PnL ${base800.pnl:,.0f} | min ${base800.bank_min:,.0f} | DD ${base800.max_dd:,.0f} | apuestas {base800.n_bets}")
    print(f"Referencia $150/bono sin freno: PnL ${base600.pnl:,.0f} | DD ${base600.max_drawdown:,.0f}")
    print(
        f"$150 + freno mix: PnL ${base150_freno.pnl:,.0f} | DD ${base150_freno.max_dd:,.0f} | apuestas {base150_freno.n_bets}"
    )
    print()
    print("=== Reglas de freno (disparo: 3 fallos seguidos, o DD desde pico, o banca <= $16k) ===")
    for label, rid, dd_lim in rules:
        res = sim(rid, dd_lim=dd_lim)
        print(
            f"{label}: PnL ${res.pnl:,.0f} | min ${res.bank_min:,.0f} | DD ${res.max_dd:,.0f} | "
            f"apuestas {res.n_bets} | saltadas {res.n_skipped} | frenos {res.triggers} | cero {res.hit_zero}"
        )
    print()
    print("=== ¿La hora se recupera tras 3 fallos seguidos? (mismo histórico, $800/clic) ===")
    print(f"Horas donde hubo 3 fallos Pool7 seguidos con puerta abierta: {events}")
    if rest_pnls:
        print(f"Apuestas que quedaban en esa hora (promedio): {rest_n / events:.1f}")
        print(f"PnL de esas apuestas restantes (promedio por hora): ${sum(rest_pnls)/len(rest_pnls):,.0f}")
        print(f"% horas donde lo restante sumaba positivo: {100*sum(1 for x in rest_pnls if x>0)/len(rest_pnls):.1f}%")
        print(f"% apuestas restantes con G>=400 en banda: {100*big_after/max(1,rest_n):.1f}%")


if __name__ == "__main__":
    main()
