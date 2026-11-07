# -*- coding: utf-8 -*-
"""Freno emergencia: saldo <= umbral -> no apostar hasta hora siguiente."""
import sim_freno_puerta_a as s
import backtest_puerta_a_pnl as bt

FLOOR = 6_000.0
BANK0 = 20_000.0
STAKE = 800.0
s.STAKE = STAKE


def sim_emergency(*, floor: float = FLOOR, stake: float = STAKE, bank0: float = BANK0):
    s.STAKE = stake
    horas = bt.load_cinta()
    hb = {h.tag.lower(): h for h in horas}
    bank = bank0
    peak = bank
    cur = None
    paused = False
    n_bets = n_skip = triggers = 0
    pnl = 0.0
    bank_min = bank
    max_dd = 0.0
    hit_zero = False
    hours_brake: set[str] = set()
    first_brake_at_bet = None

    for b in s.iter_bets(horas, hb):
        if b["tag"] != cur:
            cur = b["tag"]
            paused = False

        if paused:
            n_skip += 1
            continue

        if bank <= floor:
            paused = True
            triggers += 1
            hours_brake.add(cur)
            n_skip += 1
            continue

        n_bets += 1
        p = b["pnl"]
        pnl += p
        bank += p
        if bank <= floor:
            paused = True
            triggers += 1
            hours_brake.add(cur)
            if first_brake_at_bet is None:
                first_brake_at_bet = n_bets
        if bank <= 0:
            hit_zero = True
        peak = max(peak, bank)
        max_dd = max(max_dd, peak - bank)
        bank_min = min(bank_min, bank)

    return {
        "pnl": pnl,
        "n_bets": n_bets,
        "n_skip": n_skip,
        "triggers": triggers,
        "bank_min": bank_min,
        "max_dd": max_dd,
        "hit_zero": hit_zero,
        "bank_end": bank,
        "hours": len(hours_brake),
        "first_brake_bet": first_brake_at_bet,
    }


def sim_no_brake(stake=STAKE, bank0=BANK0):
    s.STAKE = stake
    r = s.sim_none()
    bank = bank0
    touches_6k = 0
    horas = bt.load_cinta()
    hb = {h.tag.lower(): h for h in horas}
    for b in s.iter_bets(horas, hb):
        bank += b["pnl"]
        if bank <= FLOOR:
            touches_6k += 1
    return r, touches_6k, bank


def main():
    no, touches, bank_end_nb = sim_no_brake()
    em = sim_emergency()
    em150 = sim_emergency(stake=600.0)

    print("=== Puerta A ampliada | arranque $20.000/cuenta ===")
    print()
    print("SIN freno de emergencia ($200/bono, $800/clic):")
    print(f"  Ganancia total simulada: ${no.pnl:,.0f}")
    print(f"  Peor saldo en el camino: ${no.bank_min:,.0f}")
    print(f"  Caida max desde pico: ${no.max_dd:,.0f}")
    print(f"  Llego a $0: {'si' if no.hit_zero else 'no'}")
    print(f"  Pasos con saldo <= $6.000 (sin actuar): {touches}")
    print()
    print("CON freno emergencia: si saldo <= $6.000 -> standby hasta hora siguiente")
    print(f"  Ganancia total: ${em['pnl']:,.0f}")
    print(f"  Peor saldo: ${em['bank_min']:,.0f}")
    print(f"  Caida max: ${em['max_dd']:,.0f}")
    print(f"  Apuestas hechas / saltadas: {em['n_bets']} / {em['n_skip']}")
    print(f"  Veces que entro el freno: {em['triggers']} | horas tocadas: {em['hours']}")
    print(f"  Llego a $0: {'si' if em['hit_zero'] else 'no'}")
    if em["first_brake_bet"]:
        print(f"  Primera activacion tras apuesta nro: {em['first_brake_bet']}")
    cost = no.pnl - em["pnl"]
    print(f"  Costo vs sin freno: ${cost:,.0f} ({100*cost/max(1,no.pnl):.2f}%)")
    print()
    print("Mismo freno $6k pero apuesta $150/bono ($600/clic):")
    print(f"  Ganancia ${em150['pnl']:,.0f} | freno disparo {em150['triggers']} veces | min ${em150['bank_min']:,.0f}")


if __name__ == "__main__":
    main()
