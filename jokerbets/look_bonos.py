"""Foto de bonos en la cinta oficial. No es boleto. No escribe LIVE."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CINTA = ROOT / "data" / "data_3dias.txt"
OUT = Path(__file__).resolve().parent / "LOOK_BONOS.txt"

HDR = re.compile(r"^h(\d{1,2})-(\d{6})$", re.I)
G = re.compile(
    r"^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})\s+G([1-4])(?:\s+(\d+))?", re.I
)
R = re.compile(r"^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})\s+R\b", re.I)

# mismo corte que brilloInfo ESCALA_TOTAL
BANDAS = [
    ("muy_apagado", 0, 449),
    ("opaco", 450, 599),
    ("normal", 600, 849),
    ("fuerte", 850, 1099),
    ("muy_fuerte", 1100, 1599),
    ("supernova", 1600, 10**9),
]


def banda(suma: int) -> str:
    for name, a, b in BANDAS:
        if a <= suma <= b:
            return name
    return "muy_apagado"


def parsear(path: Path):
    horas = []
    tag = None
    gs = []
    rs = 0
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = raw.strip()
        if not s:
            continue
        m = HDR.match(s)
        if m:
            if tag is not None:
                horas.append((tag, gs, rs))
            tag = s.lower()
            gs = []
            rs = 0
            continue
        if tag is None:
            continue
        mg = G.match(s)
        if mg:
            gs.append(
                {
                    "m0": int(mg.group(1)),
                    "tipo": int(mg.group(5)),
                    "lm": int(mg.group(6) or 0),
                }
            )
            continue
        if R.match(s):
            rs += 1
    if tag is not None:
        horas.append((tag, gs, rs))
    return horas


def tren_max(gs) -> int:
    if not gs:
        return 0
    best = cur = 1
    for a, b in zip(gs, gs[1:]):
        # tren = G pegadas (el cierre de una es el arranque de la otra ±1 min)
        if b["m0"] - a["m0"] <= 2:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best


def main() -> None:
    horas = parsear(CINTA)
    n = len(horas)
    lineas = [
        "LOOK BONOS — cinta oficial hilo-corto",
        f"fuente {CINTA}",
        f"horas {n}",
        "",
        "Tintas: G1 Deluxe · G2 Luck · G3 Dice · G4 Showhow",
        "Banda = suma lumen de la hora (misma escala Brillo).",
        "Tren aquí = G con arranque a ≤2 min de la anterior (foto, no ley).",
        "",
    ]

    tipos = Counter()
    bandas = Counter()
    ngs = []
    sumas = []
    fuerte_tags = []
    apag_run = 0
    max_apag = 0
    arranques_tras_apag = Counter()  # banda de la hora que rompe racha apagada
    post_tren_sin_g45 = 0
    post_tren_n = 0

    prev_apag = False
    for tag, gs, rs in horas:
        suma = sum(g["lm"] for g in gs)
        ng = len(gs)
        ngs.append(ng)
        sumas.append(suma)
        b = banda(suma)
        bandas[b] += 1
        for g in gs:
            tipos[g["tipo"]] += 1
        tlen = tren_max(gs)
        if tlen >= 2:
            post_tren_n += 1
            after = [g for g in gs if g["m0"] >= 45]
            if not after:
                post_tren_sin_g45 += 1
        es_apag = b in ("muy_apagado", "opaco")
        if prev_apag and not es_apag:
            arranques_tras_apag[b] += 1
        if es_apag:
            apag_run += 1
            max_apag = max(max_apag, apag_run)
        else:
            apag_run = 0
        prev_apag = es_apag
        if b in ("fuerte", "muy_fuerte", "supernova"):
            hod = int(tag.split("-")[0][1:])
            fuerte_tags.append((hod, b, ng, suma, tlen))

    lineas.append("— cupo de G por hora —")
    if ngs:
        xs = sorted(ngs)
        lineas.append(
            f"nG med {xs[len(xs)//2]}  p25 {xs[len(xs)//4]}  p75 {xs[(3*len(xs))//4]}  "
            f"min {xs[0]}  max {xs[-1]}"
        )
    lineas.append("")
    lineas.append("— banda de hora (suma lumen) —")
    for name, a, b in BANDAS:
        c = bandas[name]
        pct = 100.0 * c / n if n else 0
        lineas.append(f"  {name:<12} {a:>5}-{b if b < 10**8 else '…':<5}  {c:4d}  {pct:5.1f}%")
    n_f = bandas["fuerte"] + bandas["muy_fuerte"] + bandas["supernova"]
    lineas.append(f"  entrar-olor (fuerte+): {n_f}/{n} = {100.0*n_f/n:.1f}%" if n else "")
    lineas.append("")
    tot_g = sum(tipos.values()) or 1
    lineas.append("— tinta de cada bono (toda la cinta) —")
    for t, name in ((1, "Deluxe"), (2, "Luck"), (3, "Dice"), (4, "Showhow")):
        c = tipos[t]
        lineas.append(f"  G{t} {name:<8} {c:5d}  {100.0*c/tot_g:5.1f}%")
    lineas.append("")
    lineas.append("— racha de horas apagadas/opacas seguidas —")
    lineas.append(f"  racha máxima observada: {max_apag} h")
    lineas.append("  qué banda rompe una racha apagada:")
    for name, _, _ in BANDAS:
        if arranques_tras_apag[name]:
            lineas.append(f"    {name:<12} {arranques_tras_apag[name]}")
    lineas.append("")
    lineas.append("— tren y cierre 45–59 —")
    if post_tren_n:
        lineas.append(
            f"  horas con tren≥2: {post_tren_n}  ·  de esas, 0 G desde min 45: "
            f"{post_tren_sin_g45} ({100.0*post_tren_sin_g45/post_tren_n:.1f}%)"
        )
    lineas.append("")
    lineas.append("— hod de horas fuerte+ (olor de reloj, no boleto) —")
    hod_c = Counter(h for h, *_ in fuerte_tags)
    for hod in range(24):
        if hod_c[hod]:
            lineas.append(f"  h{hod:02d}  {hod_c[hod]}")
    lineas.append("")
    lineas.append("No sentar. No es REGLA. Es foto para la etapa 1.")
    OUT.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(OUT, n, "h")


if __name__ == "__main__":
    main()
