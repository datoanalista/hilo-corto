# -*- coding: utf-8 -*-
"""
Juez: BANDA d<=1 del corrimiento (minuto tip vs minuto real de la G).
Hora a hora. No Jaccard. No conteo de cadenas R-G-R en toda la cinta.
Replica Next 3: tip LC-01 al cerrar cada G; poda +1; ventana +2..+4.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
AE = ROOT / "lab-apostador-experto"
sys.path.insert(0, str(AE))
sys.path.insert(0, str(ROOT))

from core_ae import HOLDOUT, dist_anillo, load_horas_y_cinta, split_holdout, tip_lc01

lines: list[str] = []


def w(s: str = "") -> None:
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def es_g(t) -> bool:
    return str(getattr(t, "color", "")).upper().startswith("G")


def paso_firmado(origen: int, dest: int) -> int:
    """Corrimiento firmado en el anillo 0..59, rango -30..+30."""
    d = (int(dest) - int(origen)) % 60
    if d > 30:
        d -= 60
    return d


def idxs_g(tiros) -> list[int]:
    return [i for i, t in enumerate(tiros) if es_g(t)]


def walk_hora(h) -> dict:
    tiros = getattr(h, "tiros", None) or []
    gs = idxs_g(tiros)
    eventos = []
    luces: list[int] = []

    for k, gi in enumerate(gs):
        m0 = int(tiros[gi].m0) % 60
        if k == 0:
            luces.append(m0)
            continue
        tip = tip_lc01(luces)
        gap = gi - gs[k - 1]
        if tip is None:
            luces.append(m0)
            continue
        d = dist_anillo(tip, m0)
        delta = paso_firmado(tip, m0)
        eventos.append(
            {
                "tag": h.tag,
                "gap": gap,
                "tip": tip,
                "real": m0,
                "d": d,
                "delta": delta,
                "exacto": d == 0,
                "banda": d <= 1,
                "ventana_gr": 2 <= gap <= 4,
                "poda_mas1": gap == 1,
            }
        )
        luces.append(m0)

    n_ev = len(eventos)
    gr = [e for e in eventos if e["ventana_gr"]]
    return {
        "tag": h.tag,
        "nG": len(gs),
        "n_ev": n_ev,
        "n_gr": len(gr),
        "banda_gr": sum(1 for e in gr if e["banda"]),
        "exacto_gr": sum(1 for e in gr if e["exacto"]),
        "eventos": eventos,
    }


def pct(a, b) -> str:
    if not b:
        return "  —"
    return f"{a / b * 100:5.1f}%"


def bloque_hora(rows: list[dict], titulo: str) -> None:
    evs = [e for r in rows for e in r["eventos"]]
    gr = [e for e in evs if e["ventana_gr"]]
    mas1 = [e for e in evs if e["poda_mas1"]]
    horas_con_gr = [r for r in rows if r["n_gr"] > 0]
    horas_banda = [r for r in horas_con_gr if r["banda_gr"] > 0]
    horas_mayoria = [r for r in horas_con_gr if r["n_gr"] and r["banda_gr"] / r["n_gr"] >= 0.5]

    w(f"\n════════════════════════════════ {titulo} ════════════════════════════════")
    w(f"Horas: {len(rows)} · horas con al menos una G-R (gap 2..4): {len(horas_con_gr)}")
    w(
        f"De esas horas, el corrimiento cobró banda d≤1 al menos una vez: "
        f"{len(horas_banda)}/{len(horas_con_gr)} ({pct(len(horas_banda), len(horas_con_gr)).strip()})"
    )
    w(
        f"Horas donde la MAYORÍA de G de la ventana G-R cayeron en tip ±1: "
        f"{len(horas_mayoria)}/{len(horas_con_gr)} ({pct(len(horas_mayoria), len(horas_con_gr)).strip()})"
    )

    w("\nJuez oficial · cuando SÍ llegó una G (no se pregunta si el tiro es G):")
    w(f"{'Fase':<28} | {'N G':>6} | {'Exacto d=0':>11} | {'Banda d≤1':>11} | {'mediana Δ':>10}")
    w(f"{'-'*28}-+-{'-'*6}-+-{'-'*11}-+-{'-'*11}-+-{'-'*10}")

    def linea(nombre, xs):
        if not xs:
            return
        med = median(e["delta"] for e in xs)
        w(
            f"{nombre:<28} | {len(xs):>6,} | {pct(sum(e['exacto'] for e in xs), len(xs)):>11} | "
            f"{pct(sum(e['banda'] for e in xs), len(xs)):>11} | {med:>+7.0f} min"
        )

    linea("Tiro +1 (sombra / poda)", mas1)
    linea("Ventana G-R (+2,+3,+4)", gr)
    linea("  solo gap 2 (1º tras R)", [e for e in gr if e["gap"] == 2])
    linea("  solo gap 3 (2º tras R)", [e for e in gr if e["gap"] == 3])
    linea("  solo gap 4 (3º tras R)", [e for e in gr if e["gap"] == 4])
    linea("Sequía gap ≥5 (fuera)", [e for e in evs if e["gap"] >= 5])

    w("\nCorrimiento residual Δ = minuto_G − tip  (anillo, + adelante / − atrás)")
    w("Solo G que sí cayeron en ventana G-R. Esto es física de fase, no color.")
    cnt = Counter(e["delta"] for e in gr)
    for dlt in range(-5, 6):
        c = cnt[dlt]
        bar = "█" * (c * 40 // max(1, max(cnt.values()) if cnt else 1))
        w(f"  Δ {dlt:+3d} min  {c:>5,}  {pct(c, len(gr)):>7}  {bar}")

    w("\nDistribución HORA A HORA (tasa de banda dentro de esa hora, ventana G-R):")
    buckets = Counter()
    for r in horas_con_gr:
        p = r["banda_gr"] / r["n_gr"]
        if p == 0:
            buckets["0% (hora sorda)"] += 1
        elif p < 0.34:
            buckets["1–33%"] += 1
        elif p < 0.67:
            buckets["34–66%"] += 1
        elif p < 1:
            buckets["67–99%"] += 1
        else:
            buckets["100% (hora clavada)"] += 1
    for k in ("0% (hora sorda)", "1–33%", "34–66%", "67–99%", "100% (hora clavada)"):
        w(f"  {k:<22} {buckets[k]:>4} horas  {pct(buckets[k], len(horas_con_gr))}")

    # 8 horas de ejemplo: 4 clavadas, 4 sordas
    clavadas = sorted(
        [r for r in horas_con_gr if r["n_gr"] >= 2 and r["banda_gr"] == r["n_gr"]],
        key=lambda r: -r["n_gr"],
    )[:4]
    sordas = sorted(
        [r for r in horas_con_gr if r["n_gr"] >= 2 and r["banda_gr"] == 0],
        key=lambda r: -r["n_gr"],
    )[:4]
    if clavadas:
        w("\nEjemplos de hora CLAVADA (todas las G de la ventana G-R en tip ±1):")
        for r in clavadas:
            bits = []
            for e in r["eventos"]:
                if not e["ventana_gr"]:
                    continue
                bits.append(f"tip {e['tip']:02d}→G {e['real']:02d} (d={e['d']})")
            w(f"  {r['tag']}  nG={r['nG']}  " + " · ".join(bits))
    if sordas:
        w("\nEjemplos de hora SORDA (G llegó en ventana, pero el minuto no era el tip):")
        for r in sordas:
            bits = []
            for e in r["eventos"]:
                if not e["ventana_gr"]:
                    continue
                bits.append(f"tip {e['tip']:02d}→G {e['real']:02d} (d={e['d']}, Δ{e['delta']:+d})")
            w(f"  {r['tag']}  nG={r['nG']}  " + " · ".join(bits))


def main() -> None:
    w("LECTURA VIGENTE de este lab. Juez: banda d≤1 del CORRIMIENTO.")
    w("Unidad: la hora. No se cuenta R-R-G en la cinta entera. Jaccard no entra.")
    w("Pregunta correcta: cuando la G llegó, ¿cayó en el minuto que pintó el corrimiento?\n")

    horas, _ = load_horas_y_cinta()
    train, hold = split_holdout(horas, HOLDOUT)
    w(f"Cinta {len(horas)} h · train {len(train)} · holdout {len(hold)}")

    rows_tr = [walk_hora(h) for h in train]
    rows_ho = [walk_hora(h) for h in hold]
    bloque_hora(rows_tr, "TRAIN")
    bloque_hora(rows_ho, "HOLDOUT 72 h")

    w("\n════════════════════════════════ TRAMPA vs JUEZ ════════════════════════════════")
    w("Trampa (lo de ayer): P(el tiro es G | el reloj está en tip ±1) ≈ 17%.")
    w("Eso es densidad de G (9/54). Promediar color. No es el oficio.")
    w("Juez: P(el minuto de esa G está a d≤1 del tip | la G YA cayó en la ventana).")
    w("Eso es corrimiento de fase. El Next 3 pinta MINUTOS, no una cadena R/G fija.")

    out = LAB / "reports" / "LAB_NEXT3_CORRIMIENTO.txt"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    w(f"\nGuardado: {out}")


if __name__ == "__main__":
    main()
