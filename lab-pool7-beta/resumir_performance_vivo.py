# -*- coding: utf-8 -*-
"""Resume jokerbets-performance.jsonl para revisión (humano o agente)."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PERF = (
    Path(__file__).resolve().parent.parent
    / "dashboard"
    / "extraccion"
    / "jokerbets-performance.jsonl"
)


def main() -> None:
    if not PERF.exists():
        print(f"No existe aún: {PERF}")
        print("Correr el bot con clics armados; se llena solo.")
        sys.exit(0)

    lines = PERF.read_text(encoding="utf-8", errors="replace").splitlines()
    events = []
    for ln in lines:
        try:
            events.append(json.loads(ln))
        except json.JSONDecodeError:
            continue

    if not events:
        print("Archivo vacío.")
        return

    t0 = events[0].get("ts", "")
    t1 = events[-1].get("ts", "")
    by_cuenta: dict[str, list] = defaultdict(list)
    for ev in events:
        cid = ev.get("cuentaId") or ev.get("color") or "?"
        by_cuenta[cid].append(ev)

    print("PERFORMANCE VIVO — jokerbets-performance.jsonl")
    print(f"Eventos: {len(events)} · desde {t0} hasta {t1}")
    print()

    for cid, evs in sorted(by_cuenta.items()):
        apuestas = sum(1 for e in evs if e.get("event") == "apuesta_bot")
        premios = [e for e in evs if e.get("event") == "premio"]
        snaps = [e for e in evs if e.get("event") == "saldo_snapshot"]
        frenos = [e for e in evs if str(e.get("event", "")).startswith("freno_emergencia")]
        last_snap = snaps[-1] if snaps else None
        arr = evs[-1].get("arranqueUsd") or 20_000
        saldo = last_snap.get("saldo") if last_snap else None
        peak = last_snap.get("saldoPeak") if last_snap else None
        dd = last_snap.get("drawdown") if last_snap else None
        pnl = (saldo - arr) if saldo is not None else None
        print(f"--- {cid} ---")
        print(f"  Apuestas bot: {apuestas} · premios registrados: {len(premios)}")
        if saldo is not None:
            print(f"  Último saldo: ${saldo:,.0f} · pico ${peak:,.0f} · drawdown ${dd:,.0f}")
            print(f"  PnL vs arranque ${arr:,.0f}: ${pnl:+,.0f}")
        print(f"  Eventos freno emergencia: {len(frenos)}")
        print()


if __name__ == "__main__":
    main()
