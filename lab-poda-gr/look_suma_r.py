# -*- coding: utf-8 -*-
"""
LOOK: suma de multiplicadores R entre G.
Calza vs horas ±5 (pasado/futuro), no vs el hueco contiguo.
Cero Jaccard. Cero tip. Cero cable.

R1=1  R2=2  R3=5  R4=10
"""
from __future__ import annotations

import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
OJ = Path(r"c:\operacion-joker")
PISO = OJ / "experimento-mente-en-blanco" / "lab-piso"
GCOLA = ROOT / "lab-g-cola"
sys.path.insert(0, str(PISO))
sys.path.insert(0, str(GCOLA))

from core_gc import parse_dt  # noqa: E402
from piso_core import DATA_DEFAULT, _cargar_indice  # noqa: E402

OUT = LAB / "reports" / "LOOK_SUMA_R.txt"
MULT = {1: 1, 2: 2, 3: 5, 4: 10}
NULA = 80
HOLD = 48
MAX_H = 5
SEED = 12
_VEC: list[list[tuple[int, int]]] = []


@dataclass
class Hueco:
    tag: str
    hi: int
    k: int
    suma: int
    n_r: int
    letras: tuple
    m0: int
    m1: int
    g_lumen: int
    g_tipo: int | None


@dataclass
class HoraR:
    tag: str
    dt: datetime
    huecos: list[Hueco] = field(default_factory=list)
    prefijo: int = 0
    sufijo: int = 0
    total: int = 0
    n_r: int = 0
    n_g: int = 0


def peso(t) -> int:
    if str(getattr(t, "lab", "")).upper() != "R":
        return 0
    tipo = getattr(t, "tipo", None)
    if tipo in MULT:
        return MULT[int(tipo)]
    return 0


def armar_horas(path: Path) -> list[HoraR]:
    raw = _cargar_indice(path)
    tags = sorted(raw.keys(), key=parse_dt)
    out: list[HoraR] = []
    for i, tag in enumerate(tags):
        tiros = list(raw[tag] or [])
        gix = [j for j, t in enumerate(tiros) if str(t.lab).upper() == "G"]
        hr = HoraR(
            tag=tag,
            dt=parse_dt(tag),
            n_r=sum(1 for t in tiros if str(t.lab).upper() == "R"),
            n_g=len(gix),
            total=sum(peso(t) for t in tiros),
        )
        if gix:
            hr.prefijo = sum(peso(t) for t in tiros[: gix[0]])
            hr.sufijo = sum(peso(t) for t in tiros[gix[-1] + 1 :])
        for k, (a, b) in enumerate(zip(gix, gix[1:])):
            rs = [t for t in tiros[a + 1 : b] if str(t.lab).upper() == "R"]
            g = tiros[b]
            hr.huecos.append(
                Hueco(
                    tag=tag,
                    hi=i,
                    k=k,
                    suma=sum(peso(t) for t in rs),
                    n_r=len(rs),
                    letras=tuple(int(t.tipo) for t in rs if t.tipo in MULT),
                    m0=int(tiros[a].m0),
                    m1=int(g.m0),
                    g_lumen=int(getattr(g, "lumen", 0) or 0),
                    g_tipo=getattr(g, "tipo", None),
                )
            )
        out.append(hr)
    return out


def armar_vecinos(horas: list[HoraR], max_h: int = MAX_H) -> None:
    global _VEC
    n = len(horas)
    _VEC = [[] for _ in range(n)]
    dts = [h.dt for h in horas]
    for i in range(n):
        t0 = dts[i]
        for j in range(n):
            if j == i:
                continue
            dh = (dts[j] - t0).total_seconds() / 3600.0
            if 0 < abs(dh) <= max_h + 0.05:
                _VEC[i].append((j, int(round(dh))))


def vecinos(horas: list[HoraR], i: int, max_h: int = MAX_H) -> list[tuple[int, int]]:
    if _VEC and len(_VEC) == len(horas):
        return _VEC[i]
    t0 = horas[i].dt
    out = []
    for j, h in enumerate(horas):
        if j == i:
            continue
        dh = (h.dt - t0).total_seconds() / 3600.0
        if 0 < abs(dh) <= max_h + 0.05:
            out.append((j, int(round(dh))))
    return out


def pct(a: int, b: int) -> str:
    if b <= 0:
        return "—"
    return f"{100.0 * a / b:.1f}%"


def linea_lag(titulo: str, hits: dict[int, int], ns: dict[int, int]) -> list[str]:
    rows = [f"  {titulo}"]
    for k in range(-MAX_H, MAX_H + 1):
        if k == 0:
            continue
        rows.append(f"    lag {k:+d}h   {hits[k]:4}/{ns[k]:<4}  {pct(hits[k], ns[k])}")
    pas = sum(hits[k] for k in range(-MAX_H, 0))
    np_ = sum(ns[k] for k in range(-MAX_H, 0))
    fut = sum(hits[k] for k in range(1, MAX_H + 1))
    nf_ = sum(ns[k] for k in range(1, MAX_H + 1))
    rows.append(f"    pasado     {pas:4}/{np_:<4}  {pct(pas, np_)}")
    rows.append(f"    futuro     {fut:4}/{nf_:<4}  {pct(fut, nf_)}")
    return rows


def permutar_firmas(horas: list[HoraR], rng: random.Random) -> list[HoraR]:
    """Mismo reloj / mismos vecinos. Se baraja qué firma vive en cada hora."""
    firmas = [(h.huecos, h.total, h.prefijo, h.sufijo) for h in horas]
    rng.shuffle(firmas)
    out = []
    for h, (hue, tot, pre, suf) in zip(horas, firmas):
        out.append(
            HoraR(
                tag=h.tag,
                dt=h.dt,
                huecos=hue,
                prefijo=pre,
                sufijo=suf,
                total=tot,
                n_r=h.n_r,
                n_g=h.n_g,
            )
        )
    return out


def p_nula(xs: list[float], real: float) -> str:
    if not xs:
        return "—"
    ge = sum(1 for x in xs if x >= real - 1e-12)
    return f"p_nula={ge}/{len(xs)}"


def med(xs: list[float]) -> float:
    if not xs:
        return 0.0
    ys = sorted(xs)
    return ys[len(ys) // 2]


def walk_total(horas: list[HoraR]):
    hits, ns = Counter(), Counter()
    for i, h in enumerate(horas):
        for j, lag in vecinos(horas, i):
            ns[lag] += 1
            if h.total == horas[j].total:
                hits[lag] += 1
    return hits, ns


def walk_max(horas: list[HoraR]):
    hits, ns = Counter(), Counter()
    for i, h in enumerate(horas):
        if not h.huecos:
            continue
        mx = max(x.suma for x in h.huecos)
        for j, lag in vecinos(horas, i):
            if not horas[j].huecos:
                continue
            ns[lag] += 1
            if mx == max(x.suma for x in horas[j].huecos):
                hits[lag] += 1
    return hits, ns


def walk_primero(horas: list[HoraR]):
    hits, ns = Counter(), Counter()
    for i, h in enumerate(horas):
        if not h.huecos:
            continue
        s = h.huecos[0].suma
        for j, lag in vecinos(horas, i):
            if not horas[j].huecos:
                continue
            ns[lag] += 1
            if s == horas[j].huecos[0].suma:
                hits[lag] += 1
    return hits, ns


def walk_ordinal(horas: list[HoraR]):
    hits, ns = Counter(), Counter()
    for i, h in enumerate(horas):
        for hue in h.huecos:
            for j, lag in vecinos(horas, i):
                otros = horas[j].huecos
                if hue.k >= len(otros):
                    continue
                ns[lag] += 1
                if hue.suma == otros[hue.k].suma:
                    hits[lag] += 1
    return hits, ns


def walk_alguna(horas: list[HoraR], campo="suma"):
    """¿La cifra de ESTE hueco aparece en ALGÚN hueco de la hora vecina?"""
    hits, ns = Counter(), Counter()
    for i, h in enumerate(horas):
        for hue in h.huecos:
            val = getattr(hue, campo)
            for j, lag in vecinos(horas, i):
                bolsa = {getattr(x, campo) for x in horas[j].huecos}
                if not bolsa:
                    continue
                ns[lag] += 1
                if val in bolsa:
                    hits[lag] += 1
    return hits, ns


def walk_ventana(horas: list[HoraR], campo="suma"):
    """¿Aparece en la UNIÓN de huecos de las horas ±1..±5 (no contiguo)?"""
    n = hit_p = hit_f = hit_any = 0
    for i, h in enumerate(horas):
        vec = vecinos(horas, i)
        pas = {j for j, lag in vec if lag < 0}
        fut = {j for j, lag in vec if lag > 0}
        for hue in h.huecos:
            val = getattr(hue, campo)
            n += 1
            bolsa_p = {getattr(x, campo) for j in pas for x in horas[j].huecos}
            bolsa_f = {getattr(x, campo) for j in fut for x in horas[j].huecos}
            if val in bolsa_p:
                hit_p += 1
            if val in bolsa_f:
                hit_f += 1
            if val in bolsa_p or val in bolsa_f:
                hit_any += 1
    return n, hit_p, hit_f, hit_any


def walk_par(horas: list[HoraR]):
    """Par (s_k, s_{k+1}) de una hora vs misma ordinal en vecina."""
    hits, ns = Counter(), Counter()
    for i, h in enumerate(horas):
        pares = [
            (h.huecos[k].suma, h.huecos[k + 1].suma)
            for k in range(len(h.huecos) - 1)
        ]
        for k, par in enumerate(pares):
            for j, lag in vecinos(horas, i):
                hs = horas[j].huecos
                if k + 1 >= len(hs):
                    continue
                ns[lag] += 1
                if (hs[k].suma, hs[k + 1].suma) == par:
                    hits[lag] += 1
    return hits, ns


def walk_suma_vs_glumen(horas: list[HoraR], banda: int = 0):
    n = hit = 0
    for h in horas:
        for hue in h.huecos:
            if hue.g_lumen <= 0:
                continue
            n += 1
            if abs(hue.suma - hue.g_lumen) <= banda:
                hit += 1
    return hit, n


def peliculas_ordinal(horas: list[HoraR], lag: int, lim: int = 16) -> list[str]:
    rows = []
    for i, h in enumerate(horas):
        vec = [j for j, k in vecinos(horas, i) if k == lag]
        if not vec:
            continue
        j = vec[0]
        for hue in h.huecos:
            otros = horas[j].huecos
            if hue.k >= len(otros):
                continue
            if hue.suma == otros[hue.k].suma:
                o = otros[hue.k]
                rows.append(
                    f"  {h.tag:<12} hueco#{hue.k} Σ={hue.suma:<3} "
                    f"@{hue.m0:02d}→{hue.m1:02d}   "
                    f"{horas[j].tag:<12} hueco#{o.k} Σ={o.suma} "
                    f"@{o.m0:02d}→{o.m1:02d}"
                )
                if len(rows) >= lim:
                    return rows
    return rows


def un_dia(horas: list[HoraR]) -> list[str]:
    por = defaultdict(list)
    for h in horas:
        por[h.tag.split("-", 1)[-1]].append(h)
    dia = None
    for d, xs in por.items():
        if len(xs) >= 8:
            dia = d
            break
    if not dia:
        return ["  (sin día largo)"]
    rows = [f"  día {dia}  (Σ = suma R entre G de esa hora)"]
    xs = por[dia]
    for h in xs:
        s = " ".join(f"{x.suma}" for x in h.huecos) or "—"
        rows.append(
            f"    {h.tag:<12} nG={h.n_g:<2} nR={h.n_r:<3} "
            f"total={h.total:<4}  huecos[{s}]"
        )
    return rows


def main() -> None:
    path = DATA_DEFAULT
    horas = armar_horas(path)
    armar_vecinos(horas)
    tags = [h.tag for h in horas]
    rng = random.Random(SEED)
    train, hold = horas[:-HOLD], horas[-HOLD:]
    mid = len(train) // 2
    a, b = train[:mid], train[mid:]

    huecos = [x for h in horas for x in h.huecos]
    sums = [x.suma for x in huecos]
    dist = Counter(sums)

    buf: list[str] = []
    w = buf.append
    w("LOOK · suma de R entre G  (no el hueco de al lado)")
    w(f"cinta: {path}")
    w(f"Horas: {len(horas)}  {tags[0]} → {tags[-1]}  hold={HOLD}h")
    w("R1=1  R2=2  R3=5  R4=10   juez = calce exacto de la SUMA")
    w("Ventana civil: |Δt| ≤ 5 h. Contiguo de la misma hora no entra.")
    w("")

    # continuidad
    huecos_civil = 0
    for i in range(1, len(horas)):
        if horas[i].dt - horas[i - 1].dt > timedelta(hours=1, minutes=5):
            huecos_civil += 1
    w(f"Saltos civiles >1 h entre horas seguidas de cinta: {huecos_civil}")
    w(f"Huecos G→G: {len(huecos)}  median Σ={med([float(s) for s in sums]):.0f}  "
      f"min={min(sums) if sums else 0}  max={max(sums) if sums else 0}")
    top = ", ".join(f"{s}×{c}" for s, c in dist.most_common(12))
    w(f"Σ más frecuentes: {top}")
    w("")

    # tautología: ¿la suma es solo n_R?
    if huecos:
        mx = max(x.n_r for x in huecos) or 1
        # Pearson a mano
        def corr(xs, ys):
            n = len(xs)
            if n < 3:
                return 0.0
            mx_ = sum(xs) / n
            my = sum(ys) / n
            num = sum((x - mx_) * (y - my) for x, y in zip(xs, ys))
            dx = sum((x - mx_) ** 2 for x in xs) ** 0.5
            dy = sum((y - my) ** 2 for y in ys) ** 0.5
            return num / (dx * dy) if dx and dy else 0.0

        w("¿La suma es solo el conteo?")
        w(f"  corr(Σ, n_R) = {corr([x.suma for x in huecos], [x.n_r for x in huecos]):+.3f}")
        w(f"  corr(Σ, lumen G que cierra) = {corr([x.suma for x in huecos], [x.g_lumen for x in huecos]):+.3f}")
        hg, ng = walk_suma_vs_glumen(horas, 0)
        hg1, ng1 = walk_suma_vs_glumen(horas, 1)
        w(f"  Σ == lumen G que cierra: {hg}/{ng}  {pct(hg, ng)}")
        w(f"  Σ banda±1 vs lumen G:    {hg1}/{ng1}  {pct(hg1, ng1)}")
        w("")

    # A — alguna cifra en la hora vecina (por lag)
    w("════ A · la Σ de un hueco, ¿está en ALGÚN hueco de la hora a lag k? ════")
    w("  (no es el contiguo: es otra hora)")
    ha, na = walk_alguna(horas, "suma")
    for line in linea_lag("todas las horas", ha, na):
        w(line)
    w("")
    w("════ A2 · nula honesta (se baraja la firma; el reloj no se mueve) ════")

    def nula_alguna(horas_, campo="suma"):
        bag = defaultdict(list)
        for _ in range(NULA):
            sh = permutar_firmas(horas_, rng)
            hits, ns = walk_alguna(sh, campo)
            for k in range(-MAX_H, MAX_H + 1):
                if k == 0 or ns[k] == 0:
                    continue
                bag[k].append(hits[k] / ns[k])
        return bag

    bag_a = nula_alguna(horas, "suma")
    for k in range(-MAX_H, MAX_H + 1):
        if k == 0 or na[k] == 0:
            continue
        real = ha[k] / na[k]
        w(
            f"    lag {k:+d}h   real {pct(ha[k], na[k])}  "
            f"nula_med {100*med(bag_a[k]):.1f}%  {p_nula(bag_a[k], real)}"
        )
    w("")

    n, hp, hf, hy = walk_ventana(horas, "suma")
    w("  ¿La Σ aparece en la UNIÓN de las horas pasadas / futuras (≤5)?")
    w(f"    pasado  {hp}/{n}  {pct(hp, n)}")
    w(f"    futuro  {hf}/{n}  {pct(hf, n)}")
    w(f"    alguno  {hy}/{n}  {pct(hy, n)}")
    w("  (esto solo es alto si la cifra es común; mirar A2 vs nula)")
    w("")

    # mismo con n_R: si n_R calza igual, los pesos no hacen el trabajo
    hr, nr = walk_alguna(horas, "n_r")
    bag_r = nula_alguna(horas, "n_r")
    w("════ A3 · misma mira, pero con n_R (sin pesos) ════")
    for k in range(-MAX_H, MAX_H + 1):
        if k == 0 or nr[k] == 0:
            continue
        real = hr[k] / nr[k]
        w(
            f"    lag {k:+d}h   n_R {pct(hr[k], nr[k])}  "
            f"nula {100*med(bag_r[k]):.1f}%  {p_nula(bag_r[k], real)}   "
            f"| Σ {pct(ha[k], na[k])}"
        )
    w("")

    # B — mismo ordinal
    w("════ B · mismo ordinal: hueco #k de H vs #k de H+lag ════")
    hb, nb = walk_ordinal(horas)

    def nula_walk(horas_, walker):
        bag = defaultdict(list)
        for _ in range(NULA):
            sh = permutar_firmas(horas_, rng)
            hits, ns = walker(sh)
            for k in range(-MAX_H, MAX_H + 1):
                if k == 0 or ns[k] == 0:
                    continue
                bag[k].append(hits[k] / ns[k])
        return bag

    bag_b = nula_walk(horas, walk_ordinal)
    for k in range(-MAX_H, MAX_H + 1):
        if k == 0 or nb[k] == 0:
            continue
        real = hb[k] / nb[k]
        w(
            f"    lag {k:+d}h   {hb[k]:4}/{nb[k]:<4}  {pct(hb[k], nb[k])}  "
            f"nula_med {100*med(bag_b[k]):.1f}%  {p_nula(bag_b[k], real)}"
        )
    w("")

    # C — primer hueco / max / total de hora
    w("════ C · firma de la hora (no el hueco suelto) ════")
    for titulo, walker in (
        ("primer hueco Σ", walk_primero),
        ("max hueco Σ", walk_max),
        ("total R de la hora", walk_total),
    ):
        ht, nt = walker(horas)
        bag = nula_walk(horas, walker)
        w(f"  — {titulo} —")
        for k in range(-MAX_H, MAX_H + 1):
            if k == 0 or nt[k] == 0:
                continue
            real = ht[k] / nt[k]
            mark = ""
            if bag[k] and real > med(bag[k]) + 0.03:
                pn = sum(1 for x in bag[k] if x >= real - 1e-12)
                if pn <= 20:
                    mark = "  << levanta"
            w(
                f"    lag {k:+d}h   {ht[k]:4}/{nt[k]:<4}  {pct(ht[k], nt[k])}  "
                f"nula {100*med(bag[k]):.1f}%  {p_nula(bag[k], real)}{mark}"
            )
        w("")

    # D — par de huecos seguidos (frase, no cifra suelta)
    w("════ D · par (Σ_k, Σ_{k+1}) mismo ordinal en H+lag ════")
    hd, nd = walk_par(horas)
    bag_d = nula_walk(horas, walk_par)
    for k in range(-MAX_H, MAX_H + 1):
        if k == 0 or nd[k] == 0:
            continue
        real = hd[k] / nd[k]
        mark = ""
        if bag_d[k] and real > med(bag_d[k]) + 0.01:
            pn = sum(1 for x in bag_d[k] if x >= real - 1e-12)
            if pn <= 20:
                mark = "  << levanta"
        w(
            f"    lag {k:+d}h   {hd[k]:4}/{nd[k]:<4}  {pct(hd[k], nd[k])}  "
            f"nula {100*med(bag_d[k]):.1f}%  {p_nula(bag_d[k], real)}{mark}"
        )
    w("")

    # E — mitades + hold (ordinal y total)
    w("════ E · ¿aguanta en mitades y hold? (ordinal #k y total hora) ════")
    for nom, xs in (
        ("1ª mitad train", a),
        ("2ª mitad train", b),
        ("hold cola", hold),
    ):
        ho, no = walk_ordinal(xs)
        ht, nt = walk_total(xs)
        w(f"  — {nom} · {len(xs)} h —")
        # compacto: pasado vs futuro
        def pf(hits, ns):
            pas = sum(hits[k] for k in range(-MAX_H, 0))
            np_ = sum(ns[k] for k in range(-MAX_H, 0))
            fut = sum(hits[k] for k in range(1, MAX_H + 1))
            nf_ = sum(ns[k] for k in range(1, MAX_H + 1))
            return pas, np_, fut, nf_

        p1, n1, f1, m1 = pf(ho, no)
        p2, n2, f2, m2 = pf(ht, nt)
        w(f"    ordinal  pasado {pct(p1, n1)}  futuro {pct(f1, m1)}")
        w(f"    total    pasado {pct(p2, n2)}  futuro {pct(f2, m2)}")
    w("")

    # F — capas extra si hay olor: Σ vs total de la vecina; Σ vs prefijo/sufijo
    w("════ F · cruces de escala ════")
    hits_st, ns_st = Counter(), Counter()
    hits_sp, ns_sp = Counter(), Counter()
    for i, h in enumerate(horas):
        for hue in h.huecos:
            for j, lag in vecinos(horas, i):
                ns_st[lag] += 1
                if hue.suma == horas[j].total:
                    hits_st[lag] += 1
                ns_sp[lag] += 1
                if hue.suma in (horas[j].prefijo, horas[j].sufijo):
                    hits_sp[lag] += 1
    w("  hueco.Σ == total de la hora vecina")
    for k in range(-MAX_H, MAX_H + 1):
        if k == 0 or ns_st[k] == 0:
            continue
        w(f"    lag {k:+d}h   {hits_st[k]:4}/{ns_st[k]:<4}  {pct(hits_st[k], ns_st[k])}")
    w("  hueco.Σ == prefijo o sufijo de la vecina")
    for k in range(-MAX_H, MAX_H + 1):
        if k == 0 or ns_sp[k] == 0:
            continue
        w(f"    lag {k:+d}h   {hits_sp[k]:4}/{ns_sp[k]:<4}  {pct(hits_sp[k], ns_sp[k])}")
    w("")

    # G — boost: ¿sumar lumen+boost cambia el eco?
    w("════ G · si sumamos lumen+boost de cada R (no solo la letra) ════")

    def armar_boost():
        raw = _cargar_indice(path)
        tags_ = sorted(raw.keys(), key=parse_dt)
        out = []
        for i, tag in enumerate(tags_):
            tiros = list(raw[tag] or [])
            gix = [j for j, t in enumerate(tiros) if str(t.lab).upper() == "G"]
            hr = HoraR(tag=tag, dt=parse_dt(tag), n_g=len(gix))
            hr.total = sum(
                (int(t.lumen) + int(t.boost))
                for t in tiros
                if str(t.lab).upper() == "R"
            )
            for k, (a, b) in enumerate(zip(gix, gix[1:])):
                rs = [t for t in tiros[a + 1 : b] if str(t.lab).upper() == "R"]
                g = tiros[b]
                hr.huecos.append(
                    Hueco(
                        tag=tag,
                        hi=i,
                        k=k,
                        suma=sum(int(t.lumen) + int(t.boost) for t in rs),
                        n_r=len(rs),
                        letras=tuple(),
                        m0=int(tiros[a].m0),
                        m1=int(g.m0),
                        g_lumen=int(g.lumen or 0),
                        g_tipo=g.tipo,
                    )
                )
            out.append(hr)
        return out

    hb_horas = armar_boost()
    hbo, nbo = walk_ordinal(hb_horas)
    bag_bo = nula_walk(hb_horas, walk_ordinal)
    w("  ordinal con Σ = lumen+boost")
    for k in range(-MAX_H, MAX_H + 1):
        if k == 0 or nbo[k] == 0:
            continue
        real = hbo[k] / nbo[k]
        w(
            f"    lag {k:+d}h   {pct(hbo[k], nbo[k])}  "
            f"nula {100*med(bag_bo[k]):.1f}%  {p_nula(bag_bo[k], real)}"
        )
    w("")

    # H — contiguo de la MISMA hora (solo para no usarlo de titular)
    w("════ H · el contiguo de la MISMA hora (no es la pregunta) ════")
    n_c = hit_c = hit_c1 = 0
    for h in horas:
        xs = h.huecos
        for k in range(len(xs) - 1):
            n_c += 1
            if xs[k].suma == xs[k + 1].suma:
                hit_c += 1
            if abs(xs[k].suma - xs[k + 1].suma) <= 1:
                hit_c1 += 1
    w(f"  Σ == Σ del siguiente hueco: {hit_c}/{n_c}  {pct(hit_c, n_c)}")
    w(f"  banda ±1:                    {hit_c1}/{n_c}  {pct(hit_c1, n_c)}")
    w("")

    # películas
    w("════ películas · ordinal Σ calza a lag −2 y +2 ════")
    w("  — lag −2 —")
    for line in peliculas_ordinal(horas, -2) or ["  (ninguna)"]:
        w(line)
    w("  — lag +2 —")
    for line in peliculas_ordinal(horas, 2) or ["  (ninguna)"]:
        w(line)
    w("")
    w("════ un día ════")
    for line in un_dia(horas):
        w(line)
    w("")
    capa2(horas, a, b, hold, rng, w)

    w("Lectura:")
    w("  Calce = misma suma de pesos R, otra hora ≤5 h.")
    w("  Nula = se baraja la firma; el reloj no se mueve.")
    w("  Si real ≈ nula: la cifra es común, no eco.")
    w("  Capa 2: sin trenes (Σ=0), primer hueco, total ±2, wrap, cifras raras.")
    w("  Cero cable.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(buf) + "\n", encoding="utf-8")
    print(OUT, len(horas), "h", len(huecos), "huecos")


def sin_ceros(horas: list[HoraR]) -> list[HoraR]:
    out = []
    for h in horas:
        nh = HoraR(
            tag=h.tag,
            dt=h.dt,
            huecos=[x for x in h.huecos if x.suma > 0],
            prefijo=h.prefijo,
            sufijo=h.sufijo,
            total=h.total,
            n_r=h.n_r,
            n_g=h.n_g,
        )
        out.append(nh)
    return out


def walk_primero_anti(horas: list[HoraR], lag: int = 1):
    pares = []
    for i, h in enumerate(horas):
        js = [j for j, k in vecinos(horas, i) if k == lag]
        if not js or not h.huecos or not horas[js[0]].huecos:
            continue
        pares.append((h.huecos[0].suma, horas[js[0]].huecos[0].suma))
    return pares


def capa2(horas, a, b, hold, rng, w):
    w("════ CAPA 2 · sin trenes · primer hueco · wrap · raro ════")
    w("")

    hz = sin_ceros(horas)
    ha, na = walk_alguna(hz, "suma")
    bag = defaultdict(list)
    for _ in range(NULA):
        sh = permutar_firmas(hz, rng)
        hits, ns = walk_alguna(sh, "suma")
        for k in range(-MAX_H, MAX_H + 1):
            if k == 0 or ns[k] == 0:
                continue
            bag[k].append(hits[k] / ns[k])
    w("  A' · Σ>0 aparece en algún hueco de H+lag")
    for k in range(-MAX_H, MAX_H + 1):
        if k == 0 or na[k] == 0:
            continue
        real = ha[k] / na[k]
        w(
            f"    lag {k:+d}h   {pct(ha[k], na[k])}  "
            f"nula {100*med(bag[k]):.1f}%  {p_nula(bag[k], real)}"
        )
    w("")

    hb, nb = walk_ordinal(hz)
    bag_b = defaultdict(list)
    for _ in range(NULA):
        sh = permutar_firmas(hz, rng)
        hits, ns = walk_ordinal(sh)
        for k in range(-MAX_H, MAX_H + 1):
            if k == 0 or ns[k] == 0:
                continue
            bag_b[k].append(hits[k] / ns[k])
    w("  B' · ordinal, solo Σ>0")
    for k in range(-MAX_H, MAX_H + 1):
        if k == 0 or nb[k] == 0:
            continue
        real = hb[k] / nb[k]
        w(
            f"    lag {k:+d}h   {hb[k]:4}/{nb[k]:<4}  {pct(hb[k], nb[k])}  "
            f"nula {100*med(bag_b[k]):.1f}%  {p_nula(bag_b[k], real)}"
        )
    w("")

    # primer hueco ±1: anti-calce
    w("  C' · primer hueco de horas pegadas (lag +1)")
    pares = walk_primero_anti(horas, 1)
    eq = sum(1 for x, y in pares if x == y)
    eq0 = sum(1 for x, y in pares if x == y == 0)
    banda = sum(1 for x, y in pares if abs(x - y) <= 1)
    suma_p = [x + y for x, y in pares]
    w(f"    pares H vs H+1: {len(pares)}")
    w(f"    Σ0==Σ1:          {eq}/{len(pares)}  {pct(eq, len(pares))}")
    w(f"    de esos, ambos 0: {eq0}")
    w(f"    |Σ0-Σ1|≤1:       {banda}/{len(pares)}  {pct(banda, len(pares))}")
    w(f"    Σ0+Σ1 mediana={med([float(s) for s in suma_p]):.0f}  "
      f"p50 cada uno={med([float(x) for x, _ in pares]):.0f}")

    nula_eq = []
    nula_b = []
    for _ in range(NULA):
        sh = permutar_firmas(horas, rng)
        ps = walk_primero_anti(sh, 1)
        nula_eq.append(sum(1 for x, y in ps if x == y) / max(1, len(ps)))
        nula_b.append(sum(1 for x, y in ps if abs(x - y) <= 1) / max(1, len(ps)))
    real_eq = eq / max(1, len(pares))
    w(
        f"    nula Σ0==Σ1 med {100*med(nula_eq):.1f}%  "
        f"{p_nula(nula_eq, real_eq)}"
    )
    w(
        f"    nula |d|≤1  med {100*med(nula_b):.1f}%  "
        f"{p_nula(nula_b, banda / max(1, len(pares)))}"
    )
    for nom, xs in (("1ª mitad", a), ("2ª mitad", b), ("hold", hold)):
        ps = walk_primero_anti(xs, 1)
        e = sum(1 for x, y in ps if x == y)
        w(f"    {nom:<10} Σ0==Σ1 {e}/{len(ps)}  {pct(e, len(ps))}")
    w("")

    # total hora ±2 en cortes
    w("  C'' · total R de la hora, lag ±2 (el que levantó)")
    for nom, xs in (
        ("todas", horas),
        ("1ª mitad", a),
        ("2ª mitad", b),
        ("hold", hold),
    ):
        ht, nt = walk_total(xs)
        p2 = ht.get(-2, 0) + ht.get(2, 0)
        n2 = nt.get(-2, 0) + nt.get(2, 0)
        w(f"    {nom:<10} ±2h  {p2}/{n2}  {pct(p2, n2)}")
    # nula total ±2
    nula_t2 = []
    for _ in range(NULA):
        sh = permutar_firmas(horas, rng)
        ht, nt = walk_total(sh)
        n2 = nt.get(-2, 0) + nt.get(2, 0)
        p2 = ht.get(-2, 0) + ht.get(2, 0)
        nula_t2.append(p2 / n2 if n2 else 0.0)
    ht, nt = walk_total(horas)
    real_t2 = (ht.get(-2, 0) + ht.get(2, 0)) / max(1, nt.get(-2, 0) + nt.get(2, 0))
    w(f"    nula ±2 med {100*med(nula_t2):.1f}%  {p_nula(nula_t2, real_t2)}")
    w("")

    # wrap :00
    w("  W · wrap civil :00  (sufijo H-1 vs prefijo H / último vs primer hueco)")
    n_w = eq_sf = eq_ll = eq_s1 = 0
    for i in range(1, len(horas)):
        if horas[i].dt - horas[i - 1].dt > timedelta(hours=1, minutes=5):
            continue
        n_w += 1
        prev, cur = horas[i - 1], horas[i]
        if prev.sufijo == cur.prefijo:
            eq_sf += 1
        if prev.huecos and cur.huecos and prev.huecos[-1].suma == cur.huecos[0].suma:
            eq_ll += 1
        if prev.sufijo == (cur.huecos[0].suma if cur.huecos else None):
            eq_s1 += 1
    nula_sf, nula_ll = [], []
    for _ in range(NULA):
        sh = permutar_firmas(horas, rng)
        e1 = e2 = n = 0
        for i in range(1, len(sh)):
            if sh[i].dt - sh[i - 1].dt > timedelta(hours=1, minutes=5):
                continue
            n += 1
            if sh[i - 1].sufijo == sh[i].prefijo:
                e1 += 1
            if sh[i - 1].huecos and sh[i].huecos and sh[i - 1].huecos[-1].suma == sh[i].huecos[0].suma:
                e2 += 1
        nula_sf.append(e1 / n if n else 0)
        nula_ll.append(e2 / n if n else 0)
    w(f"    pares wrap: {n_w}")
    w(
        f"    sufijo(H-1)==prefijo(H): {eq_sf}/{n_w}  {pct(eq_sf, n_w)}  "
        f"nula {100*med(nula_sf):.1f}%  {p_nula(nula_sf, eq_sf / max(1, n_w))}"
    )
    w(
        f"    último hueco H-1 == primer hueco H: {eq_ll}/{n_w}  {pct(eq_ll, n_w)}  "
        f"nula {100*med(nula_ll):.1f}%  {p_nula(nula_ll, eq_ll / max(1, n_w))}"
    )
    w(f"    sufijo(H-1)==primer hueco H: {eq_s1}/{n_w}  {pct(eq_s1, n_w)}")
    w("")

    # cifras raras: Σ≥20, ¿reaparece en la ventana?
    w("  R · cifras raras (Σ≥20): ¿vuelven en ±5 h?")
    n_r = hit_r = 0
    for i, h in enumerate(horas):
        vec = vecinos(horas, i)
        bolsa = {x.suma for j, _ in vec for x in horas[j].huecos}
        for hue in h.huecos:
            if hue.suma < 20:
                continue
            n_r += 1
            if hue.suma in bolsa:
                hit_r += 1
    nula_r = []
    for _ in range(NULA):
        sh = permutar_firmas(horas, rng)
        n = hit = 0
        for i, h in enumerate(sh):
            vec = vecinos(sh, i)
            bolsa = {x.suma for j, _ in vec for x in sh[j].huecos}
            for hue in h.huecos:
                if hue.suma < 20:
                    continue
                n += 1
                if hue.suma in bolsa:
                    hit += 1
        nula_r.append(hit / n if n else 0)
    w(
        f"    real {hit_r}/{n_r}  {pct(hit_r, n_r)}  "
        f"nula {100*med(nula_r):.1f}%  {p_nula(nula_r, hit_r / max(1, n_r))}"
    )
    w("")

    # películas primer hueco que NO calza (las que sí son raras) y las 8 del total ±2
    w("  películas · total hora calza a ±2")
    n = 0
    for i, h in enumerate(horas):
        js = [j for j, k in vecinos(horas, i) if k == 2]
        if not js:
            continue
        if h.total == horas[js[0]].total:
            w(
                f"    {h.tag} total={h.total}  ==  {horas[js[0]].tag} "
                f"huecos[{' '.join(str(x.suma) for x in h.huecos)}]"
            )
            n += 1
            if n >= 10:
                break
    w("")


if __name__ == "__main__":
    main()
