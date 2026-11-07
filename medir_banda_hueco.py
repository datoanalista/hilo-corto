# -*- coding: utf-8 -*-
"""Banda: BASE vs capas HUECO (lab). No escribe boleto prod.

Capas:
  HUECO-HZ     hazard min1 muerto — saca el minuto 01 del boleto
  HUECO-SOM02  sombra reloj (mediana huecos H-1 + fermión/cupo)

  python medir_banda_hueco.py

Juez: banda d<=1. Prod = dashboard.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.estado import Estado, PRIMERA_UTIL  # noqa: E402
from src.lectores import cargar_crudo  # noqa: E402
from src.motor import dist_anillo, emitir_boleto, min_dist_a_conjunto  # noqa: E402

OUT = ROOT / "reports" / "BANDA_HUECO.txt"
OUTJ = ROOT / "reports" / "BANDA_HUECO.json"
DESDE = PRIMERA_UTIL


def cubrir(boleto, luces):
    if not boleto:
        return 0, 0
    bs = set(boleto)
    g = pm1 = 0
    for x in luces:
        d = min(dist_anillo(x, b) for b in bs)
        if d == 0:
            g += 1
        elif d == 1:
            pm1 += 1
    return g, pm1


def paso_sombra(foto: list[int]) -> int:
    xs = sorted({(m % 60) for m in (foto or [])})
    if len(xs) < 2:
        return 4
    gaps = []
    for i in range(len(xs) - 1):
        gaps.append((xs[i + 1] - xs[i]) % 60)
    gaps.append((xs[0] + 60 - xs[-1]) % 60)
    gaps = [g for g in gaps if 1 <= g <= 20]
    if not gaps:
        return 4
    return int(round(median(gaps)))


def aplicar_hz(doc: dict) -> list[int]:
    """Hazard: minuto 01 muerto — no chip en 01."""
    return sorted(m for m in (doc.get("boleto") or []) if (m % 60) != 1)


def aplicar_som02(doc: dict) -> list[int]:
    base = list(doc.get("boleto") or [])
    foto = list(doc.get("foto") or [])
    if not foto:
        return sorted(set(base))
    clima = int((doc.get("meta") or {}).get("nG_clima") or 10)
    bs = set(base)
    if len(bs) >= clima:
        return sorted(bs)
    paso = paso_sombra(foto)
    cand = (max(foto) + paso) % 60
    if cand in bs or min_dist_a_conjunto(cand, bs) < 2:
        return sorted(bs)
    # hazard: no plantar sombra en 01
    if cand == 1:
        return sorted(bs)
    bs.add(cand)
    return sorted(bs)


def aplicar_hz_luego_som02(doc: dict) -> list[int]:
    """Primero HZ sobre BASE, luego sombra sobre ese boleto."""
    foto = list(doc.get("foto") or [])
    clima = int((doc.get("meta") or {}).get("nG_clima") or 10)
    bs = set(aplicar_hz(doc))
    if not foto or len(bs) >= clima:
        return sorted(bs)
    paso = paso_sombra(foto)
    cand = (max(foto) + paso) % 60
    if cand == 1 or cand in bs or min_dist_a_conjunto(cand, bs) < 2:
        return sorted(bs)
    bs.add(cand)
    return sorted(bs)


def walk_variant(nombre, boleto_fn):
    cinta = cargar_crudo()
    i0 = cinta.orden.index(DESDE)
    estado = Estado()
    n = ksum = gsum = psum = col = 0
    azar = 0.0
    for i in range(i0, len(cinta.orden) - 1):
        estado.cerrar(cinta.get(cinta.orden[i]))
        if estado.calentamiento() < 4:
            continue
        doc = emitir_boleto(estado)
        bol = boleto_fn(doc)
        nuc = cinta.get(cinta.orden[i + 1]).nucleo
        g, pm1 = cubrir(bol, nuc)
        n += 1
        ksum += len(bol)
        gsum += g
        psum += pm1
        col += int(g + pm1 == 0)
        azar += (len(bol) * len(nuc) / 60.0) if bol else 0.0
    return {
        "nombre": nombre,
        "n": n,
        "k_medio": ksum / n,
        "G_hora": gsum / n,
        "pm1_hora": psum / n,
        "score_banda": (gsum + psum) / n,
        "colapso": col / n,
        "azar_nucleo": azar / n,
        "score_por_ficha": (gsum + psum) / ksum if ksum else 0,
    }


def veredicto(base, other):
    db = other["score_banda"] - base["score_banda"]
    de = other["score_por_ficha"] - base["score_por_ficha"]
    if db > 0.05 and de >= -0.01:
        return "PROMETE", db, de
    if db > 0.05 and de < -0.02:
        return "FRÍO (gordo)", db, de
    if abs(db) <= 0.05:
        return "K0", db, de
    return "DESCARTA", db, de


def main():
    variants = [
        ("BASE", lambda d: list(d.get("boleto") or [])),
        ("HUECO-HZ", aplicar_hz),
        ("HUECO-SOM02", aplicar_som02),
        ("HZ→SOM02", aplicar_hz_luego_som02),
    ]
    rows = []
    for name, fn in variants:
        print("midiando %s…" % name)
        rows.append(walk_variant(name, fn))

    base = rows[0]
    lines = [
        "BANDA — BASE vs HUECO (HZ primero)",
        "stamp %s" % datetime.now().strftime("%Y-%m-%d %H:%M"),
        "prod: hilo-corto · BASE = motor.py (sin tocar)",
        "HUECO-HZ: saca minuto 01 del boleto (hazard)",
        "HUECO-SOM02: +1 sombra (mediana huecos H-1)",
        "juez: banda d<=1 · n cilindro>=4 · lab sin boleto prod",
        "",
    ]
    for r in rows:
        lines.append("── %s ──" % r["nombre"])
        lines.append(
            "  n=%d  k=%.2f  G/h=%.2f  ±1/h=%.2f  score=%.2f"
            % (r["n"], r["k_medio"], r["G_hora"], r["pm1_hora"], r["score_banda"])
        )
        lines.append(
            "  colapso=%.2f%%  score/ficha=%.3f"
            % (100 * r["colapso"], r["score_por_ficha"])
        )
        lines.append("")

    lines.append("════════════════════════════════")
    lines.append("Δ vs BASE")
    lines.append("════════════════════════════════")
    censos = []
    for r in rows[1:]:
        st, db, de = veredicto(base, r)
        censos.append((r["nombre"], st, db, de))
        lines.append(
            "  %-12s  %s  Δscore=%+.3f  Δeff=%+.4f  Δk=%+.2f"
            % (
                r["nombre"],
                st,
                db,
                de,
                r["k_medio"] - base["k_medio"],
            )
        )
    lines += [
        "",
        "══ LECTURA ══",
        "  HZ primero (pedido). SOM02 = referencia previa.",
        "  Nada se cablea al dashboard sin OK.",
        "",
        "FIN",
    ]
    text = "\n".join(lines) + "\n"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    OUTJ.write_text(
        json.dumps({"rows": rows, "censos": censos}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(text)
    print("->", OUT)


if __name__ == "__main__":
    main()
