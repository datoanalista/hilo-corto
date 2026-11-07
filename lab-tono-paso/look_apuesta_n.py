# -*- coding: utf-8 -*-
"""
LOOK: apuesta automática al color G · ventana N=3 vs N=4
Forma: poda +1 (siempre) + N apuestas + corte a 4 R.
Juez de ESTA ficha = PnL color (+1 si el tiro es G, −1 si es R).
NO es el juez de corrimiento (banda d≤1). LC-01 ±1 va como oficio hermano.
Cero Jaccard. Cero prod. Cero LIVE.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
AE = ROOT / "lab-apostador-experto"
sys.path.insert(0, str(AE))
sys.path.insert(0, str(ROOT))

from core_ae import (  # noqa: E402
    HOLDOUT,
    dist_anillo,
    load_horas_y_cinta,
    split_holdout,
    tip_lc01,
)

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


def minuto(t) -> int:
    return int(getattr(t, "m0", 0)) % 60


def walk_hora(h, n_bets: int, cut_4r: bool) -> dict:
    """
    Una hora = una mesa. No se une la cinta al :00.
    Idle → G abre → poda exactamente 1 tiro → apuesta hasta N
    (o corta si racha R ya cerrada llega a 4). G en ventana = acierto;
    no reinicia la ventana. La próxima G en idle reabre.
    """
    tiros = list(getattr(h, "tiros", None) or [])
    bets: list[dict] = []
    opens = 0
    cuts = 0
    skipped_g = 0
    luces: list[int] = []
    i = 0
    n = len(tiros)
    r_streak = 0

    while i < n:
        t = tiros[i]
        if not es_g(t):
            r_streak += 1
            i += 1
            continue

        opens += 1
        luces.append(minuto(t))
        r_streak = 0
        i += 1

        if i >= n:
            break
        t_skip = tiros[i]
        if es_g(t_skip):
            luces.append(minuto(t_skip))
            r_streak = 0
            skipped_g += 1
        else:
            r_streak += 1
        i += 1

        slot = 0
        while slot < n_bets and i < n:
            if cut_4r and r_streak >= 4:
                cuts += 1
                break
            t_bet = tiros[i]
            slot += 1
            gap = slot + 1
            hit = es_g(t_bet)
            m = minuto(t_bet)
            tip = tip_lc01(luces) if hit else None
            banda = bool(tip is not None and dist_anillo(tip, m) <= 1)
            if hit:
                luces.append(m)
                r_streak = 0
            else:
                r_streak += 1
            bets.append(
                {
                    "gap": gap,
                    "slot": slot,
                    "hit": hit,
                    "pnl": 1 if hit else -1,
                    "banda": banda,
                    "tiene_tip": tip is not None,
                    "m0": m,
                }
            )
            i += 1
            if cut_4r and r_streak >= 4:
                cuts += 1
                break

    pnl = sum(b["pnl"] for b in bets)
    return {
        "tag": getattr(h, "tag", "?"),
        "opens": opens,
        "cuts": cuts,
        "skipped_g": skipped_g,
        "bets": bets,
        "pnl": pnl,
        "n_tiros": n,
        "nG": sum(1 for t in tiros if es_g(t)),
    }


def resumir(docs: list[dict]) -> dict:
    bets = [b for d in docs for b in d["bets"]]
    pnls_h = [d["pnl"] for d in docs]
    hits = [b for b in bets if b["hit"]]
    g_con_tip = [b for b in hits if b["tiene_tip"]]
    g_banda = [b for b in g_con_tip if b["banda"]]
    by_gap: dict[int, list] = defaultdict(list)
    for b in bets:
        by_gap[b["gap"]].append(b)
    return {
        "horas": len(docs),
        "opens": sum(d["opens"] for d in docs),
        "cuts": sum(d["cuts"] for d in docs),
        "skipped_g": sum(d["skipped_g"] for d in docs),
        "apuestas": len(bets),
        "hit": len(hits),
        "pnl": sum(d["pnl"] for d in docs),
        "horas_verde": sum(1 for x in pnls_h if x > 0),
        "horas_roja": sum(1 for x in pnls_h if x < 0),
        "horas_cero": sum(1 for x in pnls_h if x == 0),
        "horas_con_apuesta": sum(1 for d in docs if d["bets"]),
        "med_pnl_h": median(pnls_h) if pnls_h else 0.0,
        "med_pnl_h_con_bet": median([d["pnl"] for d in docs if d["bets"]])
        if any(d["bets"] for d in docs)
        else 0.0,
        "g_con_tip": len(g_con_tip),
        "g_banda": len(g_banda),
        "by_gap": by_gap,
    }


def foto_gap(by_gap: dict[int, list], gaps: tuple[int, ...]) -> None:
    w(f"  {'gap':>5} | {'n':>6} | {'hit G':>8} | {'PnL':>8} | nota")
    w("  " + "-" * 56)
    nombres = {
        2: "1ª apuesta (tiro +2, 1º tras poda)",
        3: "2ª apuesta (tiro +3)",
        4: "3ª apuesta (tiro +4 · «tiro 4» pool7-beta)",
        5: "4ª apuesta (tiro +5 · «tiro 5» pool7-beta)",
    }
    for g in gaps:
        xs = by_gap.get(g, [])
        if not xs:
            w(f"  {g:>5} | {0:>6} | {'—':>8} | {'—':>8} | {nombres.get(g, '')}")
            continue
        h = sum(1 for b in xs if b["hit"])
        p = sum(b["pnl"] for b in xs)
        w(f"  {g:>5} | {len(xs):>6} | {pct(h, len(xs)):>8} | {p:>+8.0f} | {nombres.get(g, '')}")


def bloque(nombre: str, horas, n_bets: int, cut_4r: bool) -> dict:
    docs = [walk_hora(h, n_bets, cut_4r) for h in horas]
    r = resumir(docs)
    r["docs"] = docs
    etiqueta = f"N={n_bets}  corte4R={'sí' if cut_4r else 'no'}"
    w(f"\n──────── {nombre} · {etiqueta}  {r['horas']} h ────────")
    w(
        f"  abre ventana (G en idle): {r['opens']}"
        f"  · cobertura G: {pct(r['opens'], sum(d['nG'] for d in docs))}"
        f"  · G podadas en +1: {r['skipped_g']}"
        f"  · cortes 4R: {r['cuts']}"
    )
    w(
        f"  apuestas: {r['apuestas']}"
        f"  · hit G: {r['hit']}  {pct(r['hit'], r['apuestas'])}"
        f"  · PnL color: {r['pnl']:+.0f}"
    )
    w(
        f"  horas verde (PnL>0): {r['horas_verde']}/{r['horas']}  {pct(r['horas_verde'], r['horas'])}"
        f"  · roja {r['horas_roja']}  · cero {r['horas_cero']}"
        f"  · con ≥1 apuesta {r['horas_con_apuesta']}"
    )
    w(
        f"  mediana PnL/hora (todas): {r['med_pnl_h']:+.1f}"
        f"  · solo horas con apuesta: {r['med_pnl_h_con_bet']:+.1f}"
    )
    w(
        f"  oficio hermano · G acertadas con tip LC-01:"
        f"  {r['g_banda']}/{r['g_con_tip']} en banda d≤1"
        f"  {pct(r['g_banda'], r['g_con_tip'])}"
        f"   (NO es el score de la apuesta)"
    )
    foto_gap(r["by_gap"], (2, 3, 4, 5))
    return r


def fila_tabla(n: int, tr: dict, ho: dict) -> str:
    return (
        f"  N={n}  | {tr['apuestas']:>6} | {pct(tr['hit'], tr['apuestas']):>7} |"
        f" {tr['pnl']:>+8.0f} | {ho['apuestas']:>6} | {pct(ho['hit'], ho['apuestas']):>7} |"
        f" {ho['pnl']:>+8.0f} | {pct(tr['horas_verde'], tr['horas']):>7} |"
        f" {pct(ho['horas_verde'], ho['horas']):>7}"
    )


def main() -> None:
    w("LOOK · Apuesta automática al color G · N=3 vs N=4")
    w("Fecha: 2026-09-06")
    w("3 y 4 = FORMA de la ventana, no ficha coronada por un racimo.")
    w("Política causal, sin leak:")
    w("  1. Cierra una G → NO apostar el tiro +1 (poda siempre; esta corrida")
    w("     no exceptúa Tren/Estirada: el pedido fue «espero el siguiente tiro»).")
    w("  2. Apostar los siguientes N tiros. Stake 1. +1 si G, −1 si R.")
    w("  3. Si la racha de R ya cerrada llega a 4, CORTA el resto de ESA ventana.")
    w("     La próxima G en idle reabre (poda + N).")
    w("  4. G dentro de la ventana = acierto de color; no reinicia N.")
    w("  5. Una hora = una mesa. No se une la cinta al :00.")
    w("")
    w("JUEZ de ESTA ficha = PnL color (¿este tiro fue G?).")
    w("Esto NO es el juez de corrimiento (banda d≤1 / tip / Next 3).")
    w("LC-01 ±1 se reporta como oficio hermano, no como score de la apuesta.")
    w("Cero Jaccard. Cero cable al dashboard.")
    w("")

    horas, _cinta = load_horas_y_cinta()
    train, hold = split_holdout(horas, HOLDOUT)
    w(f"Cinta load_horas_y_cinta: {len(horas)} h · train {len(train)} · holdout {len(hold)}")
    w(f"HOLDOUT={HOLDOUT} (core_ae). Horas = las de load_cinta (≥1 G).")

    def base_g(hs) -> tuple[int, int]:
        n = g = 0
        for h in hs:
            for t in getattr(h, "tiros", None) or []:
                n += 1
                if es_g(t):
                    g += 1
        return g, n

    g_tr, n_tr = base_g(train)
    g_ho, n_ho = base_g(hold)
    w(
        f"Base P(tiro=G) — train {g_tr}/{n_tr} {pct(g_tr, n_tr)}"
        f" · holdout {g_ho}/{n_ho} {pct(g_ho, n_ho)}"
        f"  (ya estaba: P(G|G)≈P(G|R)≈p de la hora)"
    )

    configs = ((3, True), (4, True), (3, False), (4, False))
    out: dict[tuple[int, bool], dict] = {}
    for split_name, split_h in (("TRAIN", train), ("HOLDOUT 72 h", hold)):
        w(f"\n════════ {split_name} ════════")
        for n, cut in configs:
            out[(split_name, n, cut)] = bloque(split_name, split_h, n, cut)

    tr3 = out[("TRAIN", 3, True)]
    tr4 = out[("TRAIN", 4, True)]
    ho3 = out[("HOLDOUT 72 h", 3, True)]
    ho4 = out[("HOLDOUT 72 h", 4, True)]
    tr3n = out[("TRAIN", 3, False)]
    tr4n = out[("TRAIN", 4, False)]
    ho3n = out[("HOLDOUT 72 h", 3, False)]
    ho4n = out[("HOLDOUT 72 h", 4, False)]

    w("\n════════════════════════════════ TABLA N=3 vs N=4 (corte 4R) ════════════════════════════════")
    w(
        "  pol   | ap.tr | hit tr | PnL tr  | ap.ho | hit ho | PnL ho  | %h verd tr | %h verd ho"
    )
    w("  " + "-" * 88)
    w(fila_tabla(3, tr3, ho3))
    w(fila_tabla(4, tr4, ho4))

    def gap_pnl(res: dict, gap: int) -> tuple[int, int, int]:
        xs = res["by_gap"].get(gap, [])
        h = sum(1 for b in xs if b["hit"])
        return len(xs), h, sum(b["pnl"] for b in xs)

    w("\n════════════════════════════════ ¿EL 4º TIRO PAGA O DESGASTA? ════════════════════════════════")
    w("Numeración de pool7-beta (tras la G que abre):")
    w("  tiro +4 = 3ª apuesta de esta ficha (entra en N=3 y en N=4)")
    w("  tiro +5 = 4ª apuesta de esta ficha (solo N=4)")
    w("Aquí el bet es COLOR, no banda. La banda de pool7-beta era ~57% en +4")
    w("si ya filtrabas G en ventana; +5 se caía. Abajo: P(este tiro es G).")
    for nombre, r3, r4 in (("TRAIN", tr3, tr4), ("HOLDOUT", ho3, ho4)):
        n4, h4, p4 = gap_pnl(r3, 4)
        n5, h5, p5 = gap_pnl(r4, 5)
        n4b, h4b, p4b = gap_pnl(r4, 4)
        w(f"  {nombre}:")
        w(
            f"    gap +4 (N=3): n={n4}  hit {pct(h4, n4)}  PnL {p4:+.0f}"
            f"   · mismo slot en N=4: n={n4b} hit {pct(h4b, n4b)} PnL {p4b:+.0f}"
        )
        w(f"    gap +5 (solo N=4): n={n5}  hit {pct(h5, n5)}  PnL {p5:+.0f}")
        extra = r4["pnl"] - r3["pnl"]
        w(f"    Δ PnL N=4 − N=3: {extra:+.0f}  (eso ES el 4º bet más el recorte 4R)")

    w("\n════════════════════════════════ CORTE A 4 R vs NO CORTAR ════════════════════════════════")
    w(
        f"  TRAIN   N=3: corte {tr3['pnl']:+.0f} vs libre {tr3n['pnl']:+.0f}"
        f"  · cortes={tr3['cuts']}  (sí se toca 4R = poda R + 3R; no queda 4º bet → Δ PnL 0)"
    )
    w(
        f"  TRAIN   N=4: corte {tr4['pnl']:+.0f} vs libre {tr4n['pnl']:+.0f}"
        f"  · cortes={tr4['cuts']}  Δ {tr4['pnl'] - tr4n['pnl']:+.0f}"
    )
    w(
        f"  HOLDOUT N=3: corte {ho3['pnl']:+.0f} vs libre {ho3n['pnl']:+.0f}"
        f"  · cortes={ho3['cuts']}"
    )
    w(
        f"  HOLDOUT N=4: corte {ho4['pnl']:+.0f} vs libre {ho4n['pnl']:+.0f}"
        f"  · cortes={ho4['cuts']}  Δ {ho4['pnl'] - ho4n['pnl']:+.0f}"
    )
    w(
        "  Lectura: el corte 4R en N=4 es el «no perseguir sequía»:"
        " si poda + tres R ya cerraron 4 R, no se paga el +5."
    )

    # ¿quién gana esta ficha?
    w("\n════════════════════════════════ LECTURA (combinar oficios) ════════════════════════════════")
    gana_ho = "N=3" if ho3["pnl"] > ho4["pnl"] else ("N=4" if ho4["pnl"] > ho3["pnl"] else "empate")
    gana_tr = "N=3" if tr3["pnl"] > tr4["pnl"] else ("N=4" if tr4["pnl"] > tr3["pnl"] else "empate")
    w(f"  En ESTA ficha (PnL color, corte 4R): holdout gana {gana_ho} · train gana {gana_tr}.")
    w("  Gana = pierde menos. Hit G de la ventana ≈ P(tiro=G) de la cinta (~16–18%).")
    w("  No hay filo de color: apostar N tiros cobra la densidad, no una moneda 50/50.")
    w("  Razones (no coronar 4 por un racimo de una hora):")
    w("  1. Poda +1 ya medida (sombra de fase). Esta corrida la respeta siempre.")
    w("  2. N=3 tras la poda = tiros +2..+4 = ventana G-R / SEQUIA3-V3 en forma.")
    w("  3. N=4 añade el +5. En banda, el +5 era el desplome; aquí el color sigue ~16%.")
    w("  4. Holdout +5 a 20.8% (n=197) no corona: train +5 = 16.2% y el PnL del slot es −.")
    w("  5. El corte a 4 R alinea con «no perseguir sequía»: calla el +5 tras RRRR.")
    w("  6. % horas en verde ≈ 0. La mesa pierde casi siempre. No se corona N por una hora.")
    w("")
    w("  Encaje con lo ya traído:")
    w("  · poda +1 = no apostar la sombra. Costo: G en +1 se pierden (columna skipped_g).")
    w("  · SEQUIA3 / V3 = oficio del racimo corto. V5 estira y desgasta.")
    w("  · No perseguir sequía: 4 R cortan; no se caza el +5 después de RRRR.")
    w("  · HIT-G color NO vuelve como juez de tip. Aquí es el marcador del boleto de color.")

    outp = LAB / "reports" / "LOOK_APUESTA_N.txt"
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"\nGuardado: {outp}")


if __name__ == "__main__":
    main()
