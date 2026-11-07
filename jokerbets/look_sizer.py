"""Sizer dinámico vs ficha fija $150. API, zona, interruptor. No LIVE."""
from __future__ import annotations

from pathlib import Path

from look_api import API, flag19, parsear
from look_escala import sim

OUT = Path(__file__).resolve().parent / "LOOK_SIZER.txt"


def correr(flagged, modo, banca0=20_000):
    """modo: fijo150 | cada5_escalon | cada4_escalon | prop5
    escalon: +50 si min(w) >= 1.5× start; =150 si min(w) < start; tope 250
    prop5: ficha = clip(150 * min(w)/start, 150, 250) redondeada a 50, cada 5 h
    """
    w = [banca0, banca0, banca0]
    ficha = 150
    piso_w = list(w)
    piso_p = sum(w)
    ruinas = 0
    fichas = []
    n_up = n_dn = 0
    for i, (_, tiros) in enumerate(flagged):
        fichas.append(ficha)
        _, _, _, acc, _ = sim(tiros, ficha)
        for j in range(3):
            w[j] += acc[j]
            piso_w[j] = min(piso_w[j], w[j])
            if w[j] <= 0:
                ruinas += 1
                w[j] = banca0
        piso_p = min(piso_p, sum(w))
        k = 5 if "5" in modo or modo == "fijo150" else 4
        if modo == "fijo150":
            continue
        if (i + 1) % k != 0:
            continue
        mn = min(w)
        old = ficha
        if modo.startswith("cada"):
            if mn >= 1.5 * banca0:
                ficha = min(250, ficha + 50)
            elif mn < banca0:
                ficha = 150
        elif modo == "prop5":
            raw = 150 * (mn / banca0)
            ficha = int(round(raw / 50) * 50)
            ficha = max(150, min(250, ficha))
        if ficha > old:
            n_up += 1
        elif ficha < old:
            n_dn += 1
    return {
        "cierre": w,
        "pnl": [x - banca0 for x in w],
        "casa": sum(w) - 3 * banca0,
        "piso_w": piso_w,
        "piso_p": piso_p,
        "ruinas": ruinas,
        "ficha_med": sum(fichas) / len(fichas) if fichas else 0,
        "ficha_max": max(fichas) if fichas else 0,
        "n_up": n_up,
        "n_dn": n_dn,
    }


def linea(nombre, r, banca0=20_000):
    return (
        f"  {nombre}: casa {r['casa']:+.0f}  "
        f"piso pozo {r['piso_p']:.0f} ({100*r['piso_p']/(3*banca0):.0f}%)  "
        f"vidas@0 {r['ruinas']}\n"
        f"    wallets cierre {r['cierre'][0]:.0f}/{r['cierre'][1]:.0f}/{r['cierre'][2]:.0f}"
        f"  suelo {min(r['piso_w']):.0f} ({100*min(r['piso_w'])/banca0:.0f}%)\n"
        f"    ficha med {r['ficha_med']:.0f}  máx {r['ficha_max']:.0f}  "
        f"subidas {r['n_up']}  bajadas {r['n_dn']}"
    )


def main() -> None:
    _, _, horas = parsear(API)
    flagged = [(k, t) for k, t in horas if flag19(t)]
    # ~3 semanas: 21/43.4 * 281 ≈ 136 h de indicio
    n21 = max(1, int(round(len(flagged) * 21 / 43.4)))
    r_fijo = correr(flagged, "fijo150")
    r4 = correr(flagged, "cada4_escalon")
    r5 = correr(flagged, "cada5_escalon")
    rprop = correr(flagged, "prop5")
    # 3 semanas fijo, después si min>=1.5 start → 200 el resto
    r21 = correr(flagged[:n21], "fijo150")
    # restante a 200 si creció
    w_ok = min(r21["cierre"]) >= 1.5 * 20_000
    L = [
        "LOOK SIZER — dinámico vs $150 fijo",
        f"indicio {len(flagged)} h · arranque $20k × 3 · zona · interruptor",
        "El ejemplo 4–5 h fuertes es FORMA. Se miden 4, 5 y proporcional.",
        "",
        linea("$150 FIJO (todo el tramo)", r_fijo),
        "",
        linea("escalón cada 4 h de indicio (+50 si min≥30k, reset si <20k)", r4),
        "",
        linea("escalón cada 5 h de indicio", r5),
        "",
        linea("proporcional cada 5 h (150×pozo/20k, clip 150–250)", rprop),
        "",
        f"— revisión a ~3 semanas ({n21} h de indicio, ~21 d) —",
        linea("solo esas 3 semanas, $150 fijo", r21),
        f"  ¿min wallet ≥ $30k al corte? {w_ok}  "
        f"min cierre {min(r21['cierre']):.0f}",
        "  Si sí: el resto del tramo podría pasar a $200 a mano.",
        "  Eso es revisión, no un agente tiro a tiro.",
        "",
        "Lectura",
        "  · Si el dinámico no mejora suelo NI reduce ruina, es capa extra.",
        "  · 4–5 h fuertes = racha ganadora. Subir ahí = techo de costura",
        "    en ficha (la hora siguiente a pico ya está OFF; esta es otra).",
        "  · Fijo + revisión a 3 semanas es el mismo oficio sin segundo interruptor.",
        "",
    ]
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
