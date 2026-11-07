"""Libro: normal vs fuerte, zona vs todos, colchón $20.000.
Modelo de caja (declarado): 3 cuentas × $200 = $600 por tiro apostado.
R → −600. G → una cuenta cobra $50×lumen, casa = 50×lm − 600.
Color cubierto (3 cuentas). No es boleto. No escribe LIVE.
"""
from __future__ import annotations

import re
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
CINTA = ROOT / "data" / "data_3dias.txt"
OUT = Path(__file__).resolve().parent / "LOOK_BANCA.txt"

HDR = re.compile(r"^h(\d{1,2})-(\d{6})$", re.I)
TIRO = re.compile(
    r"^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})\s+(R|G[1-4])(?:\s+(\d+))?", re.I
)


def banda(suma: int) -> str:
    if suma < 450:
        return "muy_apagado"
    if suma < 600:
        return "opaco"
    if suma < 850:
        return "normal"
    if suma < 1100:
        return "fuerte"
    if suma < 1600:
        return "muy_fuerte"
    return "supernova"


def parsear(path: Path):
    horas = []
    tag = None
    tiros = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = raw.strip()
        if not s:
            continue
        m = HDR.match(s)
        if m:
            if tag is not None:
                horas.append((tag, tiros))
            tag = s.lower()
            tiros = []
            continue
        if tag is None:
            continue
        mt = TIRO.match(s)
        if not mt:
            continue
        tok = mt.group(5).upper()
        tiros.append(
            {
                "m0": int(mt.group(1)),
                "g": tok.startswith("G"),
                "lm": int(mt.group(6) or 0) if tok.startswith("G") else 0,
            }
        )
    if tag is not None:
        horas.append((tag, tiros))
    return horas


def med(xs):
    return median(xs) if xs else None


def pnl_tiro(t):
    if t["g"]:
        return 50 * t["lm"] - 600
    return -600


def zona_ok(m, last_g, gaps):
    if last_g is None:
        return False
    gap = int(median(gaps)) if gaps else 5
    tip = last_g + gap
    return min((m - tip) % 60, (tip - m) % 60) <= 1


def sim_hora(tiros, entrar_desde, solo_zona):
    last_g = None
    gaps = []
    prev_g_m = None
    n = n_g = 0
    pnl = 0
    lms = []
    for t in tiros:
        if t["g"]:
            if prev_g_m is not None:
                gaps.append((t["m0"] - prev_g_m) % 60)
            prev_g_m = t["m0"]
        if t["m0"] <= entrar_desde:
            if t["g"]:
                last_g = t["m0"]
            continue
        if solo_zona and not zona_ok(t["m0"], last_g, gaps):
            if t["g"]:
                last_g = t["m0"]
            continue
        n += 1
        pnl += pnl_tiro(t)
        if t["g"]:
            n_g += 1
            lms.append(t["lm"])
            last_g = t["m0"]
        # si no apostamos zona, igual actualizamos last_g al pasar G
    return n, n_g, pnl, lms


def ruin_cuenta(pnls_hora, banca=20_000, apuesta=200):
    """Cada hora: pnl casa / 3 ≈ pnl por cuenta (colores a la larga)."""
    c = banca
    min_c = banca
    ruinas = 0
    horas_ok = 0
    for p in pnls_hora:
        c += p / 3
        min_c = min(min_c, c)
        if c <= 0:
            ruinas += 1
            c = banca  # se recuenta como otra vida, para tasa
        else:
            horas_ok += 1
    return ruinas, min_c, c


def main() -> None:
    horas = parsear(CINTA)
    lineas = [
        "LOOK BANCA — normal vs fuerte · zona vs todos · colchón",
        f"horas {len(horas)}  modelo: casa 50×lm−600 por G, −600 por R",
        "cuenta ≈ casa/3. Apuesta $200. Colchón $20.000.",
        "",
    ]

    # lumen por cierre
    por_banda = {k: [] for k in ("opaco", "normal", "fuerte", "muy_fuerte", "supernova")}
    for _, tiros in horas:
        gs = [t for t in tiros if t["g"]]
        s = sum(t["lm"] for t in gs)
        b = banda(s)
        if b in por_banda:
            por_banda[b].extend(t["lm"] for t in gs)
    lineas.append("— lumen/G según cómo CIERRA la hora —")
    for b, xs in por_banda.items():
        if not xs:
            continue
        altos = sum(1 for x in xs if x >= 85)
        lineas.append(
            f"  {b:<12} nG={len(xs):5d}  med {median(xs):.0f}  "
            f"media {sum(xs)/len(xs):.0f}  %≥85 {100*altos/len(xs):.1f}%"
        )
    lineas.append("")

    # políticas sobre horas con indicio @19
    def flag19(tiros):
        ya = [t for t in tiros if t["g"] and t["m0"] <= 19]
        if len(ya) < 2:
            return False
        return (sum(t["lm"] for t in ya) / len(ya)) >= 68

    flagged = [(tag, tiros) for tag, tiros in horas if flag19(tiros)]
    lineas.append(f"— horas con indicio @19 (media≥68, ≥2 G): {len(flagged)} —")

    def pack(nombre, filas, solo_zona, T=19):
        ns = gs = 0
        pnls = []
        lms = []
        for _, tiros in filas:
            n, ng, p, lm = sim_hora(tiros, T, solo_zona)
            ns += n
            gs += ng
            pnls.append(p)
            lms.extend(lm)
        tot = sum(pnls)
        ruinas, min_c, _ = ruin_cuenta(pnls)
        med_h = median(pnls) if pnls else 0
        lineas.append(
            f"  {nombre}: tiros {ns}  G {gs} ({100*gs/ns if ns else 0:.1f}%)  "
            f"pnl casa {tot:+.0f}  med/hora {med_h:+.0f}"
        )
        lineas.append(
            f"    por cuenta ≈ {tot/3:+.0f}  ·  vidas a $0 recargando $20k: {ruinas} "
            f"en {len(pnls)} h  ·  suelo marca {min_c:.0f}"
        )
        if lms:
            lineas.append(
                f"    lumen apostado med {median(lms):.0f} media {sum(lms)/len(lms):.0f}"
            )

    pack("TODAS las horas, TODO tiro post-19", horas, False)
    pack("TODAS las horas, solo ZONA tip±1", horas, True)
    pack("indicio @19, TODO tiro post-19", flagged, False)
    pack("indicio @19, solo ZONA tip±1", flagged, True)
    lineas.append("")

    # si además exigimos que el cierre sea fuerte+ (oráculo, techo, no se usa)
    fuerte_f = []
    normal_f = []
    for tag, tiros in flagged:
        s = sum(t["lm"] for t in tiros if t["g"])
        b = banda(s)
        if b in ("fuerte", "muy_fuerte", "supernova"):
            fuerte_f.append((tag, tiros))
        elif b == "normal":
            normal_f.append((tag, tiros))
    lineas.append(
        f"— del indicio @19, cierran fuerte+ {len(fuerte_f)} / "
        f"normal {len(normal_f)} (oráculo, no se puede exigir en vivo) —"
    )
    pack("oráculo fuerte+, ZONA", fuerte_f, True)
    pack("oráculo normal, ZONA", normal_f, True)
    pack("oráculo fuerte+, TODO", fuerte_f, False)
    pack("oráculo normal, TODO", normal_f, False)
    lineas.append("")

    # colchón: cuántos tiros zona caben
    lineas.append("— colchón $20.000 / $200 = 100 tiros por cuenta —")
    lineas.append("  $400 (doble) = 50 tiros. Casa $600 / tiro en juego.")
    lineas.append("  SILLA_TODOS (acta) seca: 81% de los asientos son R.")
    lineas.append("  SOLO_ZONA hold: cov 28% banda 89% pnl +141 (silla, no color).")
    lineas.append("")
    lineas.append("Modelo de cobro es supuesto de mesa. Si el color no paga lm×$50,")
    lineas.append("estos PnL no sirven. Verificar un G real (recibo) antes de REGLA.")
    OUT.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
