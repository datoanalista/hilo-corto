"""Piso de lumen y persistencia. Foto, no boleto. No escribe LIVE."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
CINTA = ROOT / "data" / "data_3dias.txt"
OUT = Path(__file__).resolve().parent / "LOOK_HAPPY.txt"

HDR = re.compile(r"^h(\d{1,2})-(\d{6})$", re.I)
G = re.compile(
    r"^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})\s+G([1-4])(?:\s+(\d+))?", re.I
)

BANDAS = [
    ("muy_apagado", 0, 449),
    ("opaco", 450, 599),
    ("normal", 600, 849),
    ("fuerte", 850, 1099),
    ("muy_fuerte", 1100, 1599),
    ("supernova", 1600, 10**9),
]
ORD = [b[0] for b in BANDAS]


def banda(suma: int) -> str:
    for name, a, b in BANDAS:
        if a <= suma <= b:
            return name
    return "muy_apagado"


def med(xs):
    return median(xs) if xs else None


def fmt(x):
    return "—" if x is None else f"{x:.0f}"


def parsear(path: Path):
    horas = []
    tag = None
    gs = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = raw.strip()
        if not s:
            continue
        m = HDR.match(s)
        if m:
            if tag is not None:
                horas.append((tag, gs))
            tag = s.lower()
            gs = []
            continue
        if tag is None:
            continue
        mg = G.match(s)
        if mg:
            gs.append({"m0": int(mg.group(1)), "lm": int(mg.group(6) or 0)})
    if tag is not None:
        horas.append((tag, gs))
    return horas


def main() -> None:
    horas = parsear(CINTA)
    n = len(horas)
    lineas = [
        "LOOK HAPPY — piso de lumen y si se sostiene",
        f"fuente {CINTA}  horas {n}",
        "alto = lumen/G ≥85  ·  gordo = ≥150  ·  happy-cierre = suma≥850",
        "",
    ]

    # tercios: lumen/G
    ter = {k: [] for k in ("00-19", "20-39", "40-59")}
    ter_f = {k: [] for k in ter}  # solo horas que CIERRAN fuerte+
    sumas = []
    bands = []
    for tag, gs in horas:
        suma = sum(g["lm"] for g in gs)
        sumas.append(suma)
        b = banda(suma)
        bands.append(b)
        fuerte = b in ("fuerte", "muy_fuerte", "supernova")
        for g in gs:
            key = "00-19" if g["m0"] <= 19 else "20-39" if g["m0"] <= 39 else "40-59"
            ter[key].append(g["lm"])
            if fuerte:
                ter_f[key].append(g["lm"])

    lineas.append("— lumen/G por tercio (TODA hora) —")
    for k in ter:
        xs = ter[k]
        altos = sum(1 for x in xs if x >= 85)
        lineas.append(
            f"  {k}  n={len(xs):5d}  med {fmt(med(xs))}  "
            f"%≥85 {100*altos/len(xs) if xs else 0:4.1f}%"
        )
    lineas.append("— lumen/G por tercio (solo horas que CIERRAN fuerte+) —")
    for k in ter_f:
        xs = ter_f[k]
        altos = sum(1 for x in xs if x >= 85)
        gordos = sum(1 for x in xs if x >= 150)
        lineas.append(
            f"  {k}  n={len(xs):5d}  med {fmt(med(xs))}  "
            f"%≥85 {100*altos/len(xs) if xs else 0:4.1f}%  "
            f"%≥150 {100*gordos/len(xs) if xs else 0:4.1f}%"
        )
    lineas.append("")

    # persistencia intra-hora: tras 1er G≥85, las que siguen
    def resto_tras(pred, etiqueta):
        despues = []
        n_h = 0
        for _, gs in horas:
            idx = next((i for i, g in enumerate(gs) if pred(g)), None)
            if idx is None:
                continue
            tail = gs[idx + 1 :]
            if not tail:
                continue
            n_h += 1
            despues.extend(g["lm"] for g in tail)
        altos = sum(1 for x in despues if x >= 85)
        gordos = sum(1 for x in despues if x >= 150)
        bajos = sum(1 for x in despues if x < 50)
        lineas.append(
            f"  {etiqueta}: {n_h} h con cola · nG resto {len(despues)}  "
            f"med {fmt(med(despues))}  %≥85 {100*altos/len(despues) if despues else 0:4.1f}%  "
            f"%≥150 {100*gordos/len(despues) if despues else 0:4.1f}%  "
            f"%<50 {100*bajos/len(despues) if despues else 0:4.1f}%"
        )

    lineas.append("— ¿se sostiene el piso? (G que quedan DESPUÉS del gatillo) —")
    resto_tras(lambda g: g["lm"] >= 85, "1ª G≥85")
    resto_tras(lambda g: g["lm"] >= 150, "1ª G≥150")
    resto_tras(lambda g: g["lm"] < 40, "1ª G<40 (control)")
    # dos altos ya vistos
    n_h = 0
    despues = []
    for _, gs in horas:
        altos_i = [i for i, g in enumerate(gs) if g["lm"] >= 85]
        if len(altos_i) < 2:
            continue
        tail = gs[altos_i[1] + 1 :]
        if not tail:
            continue
        n_h += 1
        despues.extend(g["lm"] for g in tail)
    altos = sum(1 for x in despues if x >= 85)
    lineas.append(
        f"  ya 2× G≥85: {n_h} h · nG resto {len(despues)}  "
        f"med {fmt(med(despues))}  %≥85 {100*altos/len(despues) if despues else 0:4.1f}%"
    )
    lineas.append("")

    # transiciones hora→hora
    trans = Counter()
    for a, b in zip(bands, bands[1:]):
        trans[(a, b)] += 1
    lineas.append("— de esta banda, ¿qué es la SIGUIENTE hora? —")
    for src in ORD:
        tot = sum(trans[(src, d)] for d in ORD)
        if not tot:
            continue
        parts = []
        for d in ORD:
            c = trans[(src, d)]
            if c:
                parts.append(f"{d} {100*c/tot:.0f}%")
        lineas.append(f"  {src:<12} n={tot:4d}  →  " + " · ".join(parts))
    lineas.append("")

    # racha apagada: siguiente
    lineas.append("— tras K horas muy_apagado/opaco seguidas, la que sigue —")
    after_k = defaultdict(Counter)
    run = 0
    for i, b in enumerate(bands):
        if i > 0 and run >= 1:
            after_k[min(run, 5)][b] += 1
        if b in ("muy_apagado", "opaco"):
            run += 1
        else:
            run = 0
    for k in range(1, 6):
        c = after_k[k]
        tot = sum(c.values())
        if not tot:
            continue
        f = c["fuerte"] + c["muy_fuerte"] + c["supernova"]
        lineas.append(
            f"  K={k}  n={tot:4d}  fuerte+ {100*f/tot:5.1f}%  "
            f"normal {100*c['normal']/tot:5.1f}%  "
            f"sigue apag/op {100*(c['muy_apagado']+c['opaco'])/tot:5.1f}%"
        )
    # detección EN CURSO: si la suma ya tocó un piso, ¿el resto sigue gordo?
    lineas.append("— gatillo EN CURSO (suma ya alcanzada) → G que quedan —")
    for umbral, nombre in ((450, "suma≥450"), (600, "suma≥600"), (850, "suma≥850"), (1100, "suma≥1100")):
        despues = []
        n_h = 0
        t_hit = []
        for _, gs in horas:
            acc = 0
            hit = None
            for i, g in enumerate(gs):
                acc += g["lm"]
                if acc >= umbral:
                    hit = i
                    break
            if hit is None:
                continue
            tail = gs[hit + 1 :]
            if not tail:
                continue
            n_h += 1
            t_hit.append(gs[hit]["m0"])
            despues.extend(g["lm"] for g in tail)
        altos = sum(1 for x in despues if x >= 85)
        gordos = sum(1 for x in despues if x >= 150)
        lineas.append(
            f"  {nombre}: {n_h} h  med min-gatillo {fmt(med(t_hit))}  "
            f"resto nG {len(despues)}  med {fmt(med(despues))}  "
            f"%≥85 {100*altos/len(despues) if despues else 0:4.1f}%  "
            f"%≥150 {100*gordos/len(despues) if despues else 0:4.1f}%"
        )
    # a un minuto fijo: lo YA visto vs lo que queda
    lineas.append("— foto @T (lo ya caído) → G posteriores a T —")
    for T in (19, 29, 39):
        lineas.append(f"  corte min {T}:")
        casos = [
            ("0 G≥85 ya", lambda acc, fats: fats == 0),
            ("1 G≥85 ya", lambda acc, fats: fats == 1),
            ("≥2 G≥85 ya", lambda acc, fats: fats >= 2),
            ("suma≥400 ya", lambda acc, fats: acc >= 400),
            ("suma≥600 ya", lambda acc, fats: acc >= 600),
        ]
        for nombre, pred in casos:
            despues = []
            n_h = 0
            for _, gs in horas:
                ya = [g for g in gs if g["m0"] <= T]
                tail = [g for g in gs if g["m0"] > T]
                if not tail:
                    continue
                acc = sum(g["lm"] for g in ya)
                fats = sum(1 for g in ya if g["lm"] >= 85)
                if not pred(acc, fats):
                    continue
                n_h += 1
                despues.extend(g["lm"] for g in tail)
            altos = sum(1 for x in despues if x >= 85)
            lineas.append(
                f"    {nombre:<14} n={n_h:4d}  resto nG {len(despues):4d}  "
                f"med {fmt(med(despues))}  %≥85 {100*altos/len(despues) if despues else 0:4.1f}%"
            )
    # ¿el arranque LEE el cierre? (detector, no apuesta)
    lineas.append("— @19: media de G ya caídas vs cierre fuerte+ —")
    buckets = [("med<40", 0, 40), ("40–49", 40, 50), ("50–67", 50, 68), ("≥68", 68, 10**9)]
    for nombre, a, bmax in buckets:
        n_h = n_f = 0
        for _, gs in horas:
            ya = [g for g in gs if g["m0"] <= 19]
            if len(ya) < 2:
                continue
            m = sum(g["lm"] for g in ya) / len(ya)
            if not (a <= m < bmax):
                continue
            n_h += 1
            if banda(sum(g["lm"] for g in gs)) in ("fuerte", "muy_fuerte", "supernova"):
                n_f += 1
        lineas.append(
            f"  {nombre:<8} n={n_h:4d}  cierra fuerte+ {100*n_f/n_h if n_h else 0:5.1f}%"
        )
    lineas.append("")
    lineas.append("No sentar. Happy hour = régimen de la hora, no un G gordo suelto.")
    lineas.append("No se anticipa. Se detecta en curso.")
    OUT.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
