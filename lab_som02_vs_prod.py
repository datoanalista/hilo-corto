# -*- coding: utf-8 -*-
"""Lab SOM02 vs prod — monitoreo Δ sombra (motor cableado 2026-08-29).

  python lab_som02_vs_prod.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.estado import Estado, PRIMERA_UTIL  # noqa: E402
from src.lectores import cargar_crudo  # noqa: E402
from src.motor import dist_anillo, emitir_boleto, paso_sombra  # noqa: E402

OUT = ROOT / "reports" / "LAB_SOM02_VS_PROD.txt"
OUTJ = ROOT / "reports" / "LAB_SOM02_VS_PROD.json"
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


def resultado_ficha(cand: int, luces: list[int]) -> str:
    if not luces:
        return "sin_luces"
    d = min(dist_anillo(cand, x) for x in luces)
    if d == 0:
        return "EXACTO"
    if d == 1:
        return "VECINO"
    return "FALLA"


def main():
    cinta = cargar_crudo()
    i0 = cinta.orden.index(DESDE)
    estado = Estado()

    filas = []
    propuestas = []  # solo horas donde entró cand nuevo
    motivo_no = Counter()
    res_ficha = Counter()

    base_g = base_p = base_k = base_col = 0
    som_g = som_p = som_k = som_col = 0
    n = 0
    horas_con_ficha = 0
    score_solo_cuando_entra_base = 0
    score_solo_cuando_entra_som = 0
    n_entra = 0

    for i in range(i0, len(cinta.orden) - 1):
        based = cinta.orden[i]
        for_tag = cinta.orden[i + 1]
        estado.cerrar(cinta.get(based))
        if estado.calentamiento() < 4:
            continue

        doc = emitir_boleto(estado)
        bol_base = sorted(
            t["minuto"]
            for t in doc.get("tiros") or []
            if t.get("rol") != "sombra"
        )
        bol_som = list(doc.get("boleto") or [])
        som02_meta = (doc.get("meta") or {}).get("som02") or {}
        cand = som02_meta.get("cand") if som02_meta.get("entrada") else None
        motivo = som02_meta.get("motivo") or ("ok" if cand is not None else "sin_entrada")
        paso = som02_meta.get("paso") or paso_sombra(list(doc.get("foto") or []))
        nuc = cinta.get(for_tag).nucleo

        bg, bp = cubrir(bol_base, nuc)
        sg, sp = cubrir(bol_som, nuc)
        sb = bg + bp
        ss = sg + sp

        n += 1
        base_g += bg
        base_p += bp
        base_k += len(bol_base)
        base_col += int(sb == 0)
        som_g += sg
        som_p += sp
        som_k += len(bol_som)
        som_col += int(ss == 0)

        fila = {
            "based_on": based,
            "for": for_tag,
            "nG": len(nuc),
            "k_base": len(bol_base),
            "k_som": len(bol_som),
            "cand": cand,
            "motivo": motivo,
            "paso": paso_sombra(list(doc.get("foto") or [])),
            "foto_max": max(doc.get("foto") or [0]) % 60 if doc.get("foto") else None,
            "score_base": sb,
            "score_som": ss,
            "delta": ss - sb,
            "hits_base": bg,
            "pm1_base": bp,
            "hits_som": sg,
            "pm1_som": sp,
        }

        if cand is not None:
            horas_con_ficha += 1
            n_entra += 1
            score_solo_cuando_entra_base += sb
            score_solo_cuando_entra_som += ss
            rf = resultado_ficha(cand, nuc)
            res_ficha[rf] += 1
            fila["resultado_ficha"] = rf
            propuestas.append(fila)
        else:
            motivo_no[motivo] += 1
            fila["resultado_ficha"] = None

        filas.append(fila)

    def media(s):
        return s / n if n else 0.0

    resumen = {
        "n": n,
        "BASE": {
            "k": media(base_k),
            "hits": media(base_g),
            "pm1": media(base_p),
            "score": media(base_g + base_p),
            "colapso": media(base_col),
            "eff": (base_g + base_p) / base_k if base_k else 0,
        },
        "SOM02": {
            "k": media(som_k),
            "hits": media(som_g),
            "pm1": media(som_p),
            "score": media(som_g + som_p),
            "colapso": media(som_col),
            "eff": (som_g + som_p) / som_k if som_k else 0,
        },
        "horas_con_ficha_nueva": horas_con_ficha,
        "pct_entra": 100.0 * horas_con_ficha / n if n else 0,
        "cuando_entra": {
            "n": n_entra,
            "score_base": score_solo_cuando_entra_base / n_entra if n_entra else 0,
            "score_som": score_solo_cuando_entra_som / n_entra if n_entra else 0,
            "delta": (
                (score_solo_cuando_entra_som - score_solo_cuando_entra_base) / n_entra
                if n_entra
                else 0
            ),
        },
        "resultado_ficha": dict(res_ficha),
        "motivo_no": dict(motivo_no),
    }

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    b, s = resumen["BASE"], resumen["SOM02"]
    lines = [
        "LAB SOM02 vs PROD (BASE) — fichas + rendimiento",
        "stamp %s" % stamp,
        "Lab: hilo-corto · juez banda d<=1 · cilindro>=4",
        "BASE = emitir_boleto sin chip sombra (islas+costura). "
        "SOM02 = boleto prod (incluye sombra si cupo).",
        "Cero LIVE. motor.py no tocado.",
        "",
        "══ CÓMO SE PROPONE LA FICHA ══",
        "",
        "  1. foto = islas H-1 (nucleo previo)",
        "  2. paso = mediana de huecos entre islas (1..20)",
        "  3. cand = (max(foto) + paso) %% 60",
        "  4. Entra solo si: k < clima · cand≠01 · no en boleto · d>=2 a chips",
        "",
        "══ RESUMEN RENDIMIENTO (n=%d) ══" % n,
        "",
        "  quien     k      hits    ±1     score   colapso  score/ficha",
        "  BASE      %.2f   %.2f   %.2f   %.2f    %.2f%%   %.3f"
        % (b["k"], b["hits"], b["pm1"], b["score"], 100 * b["colapso"], b["eff"]),
        "  SOM02     %.2f   %.2f   %.2f   %.2f    %.2f%%   %.3f"
        % (s["k"], s["hits"], s["pm1"], s["score"], 100 * s["colapso"], s["eff"]),
        "  Δ         %+.2f   %+.2f   %+.2f   %+.2f    %+.2f pp  %+.4f"
        % (
            s["k"] - b["k"],
            s["hits"] - b["hits"],
            s["pm1"] - b["pm1"],
            s["score"] - b["score"],
            100 * (s["colapso"] - b["colapso"]),
            s["eff"] - b["eff"],
        ),
        "",
        "══ FICHAS PROPUESTAS ══",
        "",
        "  Horas donde entra chip nuevo: %d / %d (%.1f%%)"
        % (horas_con_ficha, n, resumen["pct_entra"]),
        "  Horas sin ficha nueva:        %d" % (n - horas_con_ficha),
        "",
        "  Motivo de NO entrar:",
    ]
    for m, c in motivo_no.most_common():
        lines.append("    %-22s  %d" % (m, c))

    lines += [
        "",
        "  Resultado de la ficha nueva vs luces reales (solo cuando entra):",
    ]
    tot_f = sum(res_ficha.values()) or 1
    for k in ("EXACTO", "VECINO", "FALLA", "sin_luces"):
        if k in res_ficha:
            lines.append(
                "    %-10s  %4d  (%.1f%%)"
                % (k, res_ficha[k], 100.0 * res_ficha[k] / tot_f)
            )
    ce = resumen["cuando_entra"]
    lines += [
        "",
        "  Solo en horas donde SÍ entra la ficha (n=%d):" % ce["n"],
        "    score BASE  %.2f" % ce["score_base"],
        "    score SOM02 %.2f" % ce["score_som"],
        "    Δ           %+.2f" % ce["delta"],
        "",
        "══ MUESTRA DE FICHAS (primeras 25 que entraron) ══",
        "",
        "  %-12s %4s %4s %4s %6s %5s %5s %6s"
        % ("for", "cand", "paso", "nG", "res", "BASE", "SOM", "Δ"),
    ]
    for f in propuestas[:25]:
        lines.append(
            "  %-12s %4d %4d %4d %6s %5d %5d %+6d"
            % (
                f["for"],
                f["cand"],
                f["paso"],
                f["nG"],
                f["resultado_ficha"],
                f["score_base"],
                f["score_som"],
                f["delta"],
            )
        )
    if len(propuestas) > 25:
        lines.append("  … +%d más (ver JSON)" % (len(propuestas) - 25))

    # top wins / losses when ficha enters
    ganan = sorted(
        [f for f in propuestas if f["delta"] > 0],
        key=lambda x: -x["delta"],
    )[:8]
    pierden = sorted(
        [f for f in propuestas if f["delta"] < 0],
        key=lambda x: x["delta"],
    )[:8]
    lines += ["", "══ DONDE LA FICHA SUBE SCORE (top) ══", ""]
    for f in ganan:
        lines.append(
            "  %s  cand=%02d  %s  BASE=%d → SOM=%d (Δ%+d)"
            % (f["for"], f["cand"], f["resultado_ficha"], f["score_base"], f["score_som"], f["delta"])
        )
    lines += ["", "══ DONDE BAJA O EMPATA PEOR (top) ══", ""]
    if not pierden:
        lines.append("  (ninguna hora con Δ<0 al entrar ficha — raro; mirar JSON)")
    for f in pierden:
        lines.append(
            "  %s  cand=%02d  %s  BASE=%d → SOM=%d (Δ%+d)"
            % (f["for"], f["cand"], f["resultado_ficha"], f["score_base"], f["score_som"], f["delta"])
        )

    # Note: adding a chip can only help or keep score same for covering MORE lights;
    # delta can be 0 if the new chip doesn't cover anything new. Can't lower score
    # unless... wait covering is count of lights near boleto, adding chips can only
    # increase or keep. So delta >= 0 always. Pierden would be empty.
    # Unless I'm wrong - yes adding chips can only help or stay. Good.

    lines += [
        "",
        "══ VEREDICTO LAB ══",
        "",
        "  Δscore global: %+.3f" % (s["score"] - b["score"]),
        "  Δk:            %+.2f" % (s["k"] - b["k"]),
        "  Δeff:          %+.4f" % (s["eff"] - b["eff"]),
        "  Ficha aterriza (Exact+vecino): %.1f%% de las propuestas"
        % (100.0 * (res_ficha.get("EXACTO", 0) + res_ficha.get("VECINO", 0)) / tot_f),
        "",
        "  Censo: VIVE prod (SOM02 cableado motor 2026-08-29). Monitorear Δ online.",
        "FIN",
    ]

    text = "\n".join(lines) + "\n"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    OUTJ.write_text(
        json.dumps(
            {"stamp": stamp, "resumen": resumen, "propuestas": propuestas, "filas": filas},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
    print("->", OUT)
    print("->", OUTJ)


if __name__ == "__main__":
    main()
