# -*- coding: utf-8 -*-
"""
LOOK: sequías largas (cola ≥15/20/30/36 R). Unidad = hora.
36 es la FORMA (sequía muy larga), no la ficha.
Juez: hora a hora. No Jaccard. No P(tiro=G) global. No cadenas de toda la cinta.
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path
from statistics import median

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
AE = ROOT / "lab-apostador-experto"
GCOLA = ROOT / "lab-g-cola"
sys.path.insert(0, str(AE))
sys.path.insert(0, str(GCOLA))
sys.path.insert(0, str(ROOT))

from core_ae import HOLDOUT, load_horas_y_cinta, split_holdout  # noqa: E402
from core_gc import parse_dt  # noqa: E402

UMBRALES = (15, 20, 30, 36)
lines: list[str] = []


def w(s: str = "") -> None:
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def pct(a, b) -> str:
    if not b:
        return "—"
    return f"{a / b * 100:.1f}%"


def es_luz(t) -> bool:
    """G núcleo (luz). Extra/G5 no rompe sequía de luces."""
    if str(getattr(t, "color", "")).upper() != "G":
        return False
    tipo = getattr(t, "tipo", None)
    return tipo != 5


def tipo_g(t) -> int | None:
    try:
        return int(getattr(t, "tipo", None))
    except (TypeError, ValueError):
        return None


def lumen_g(t) -> int | None:
    lm = getattr(t, "lumen", None)
    if lm is None:
        return None
    try:
        return int(lm)
    except (TypeError, ValueError):
        return None


def clima(n: int) -> str:
    if n <= 7:
        return "floja"
    if n >= 13:
        return "rica"
    return "normal"


def tiros_de(h) -> list:
    xs = getattr(h, "tiros", None)
    if xs:
        return list(xs)
    return list(getattr(h, "tiros_nucleo", None) or [])


def foto_hora(h) -> dict | None:
    tiros = tiros_de(h)
    if len(tiros) < 8:
        return None
    flags = [es_luz(t) for t in tiros]
    idxs = [i for i, g in enumerate(flags) if g]
    nG = len(idxs)
    n = len(tiros)

    lead = idxs[0] if idxs else n
    tail = (n - 1 - idxs[-1]) if idxs else 0
    intra = []
    for a, b in zip(idxs, idxs[1:]):
        intra.append(b - a - 1)
    intra_max = max(intra) if intra else 0

    # rachas de R (no-luz) con origen
    rachas = []
    i = 0
    while i < n:
        if flags[i]:
            i += 1
            continue
        j = i
        while j < n and not flags[j]:
            j += 1
        largo = j - i
        if i == 0:
            origen = "lead"
        elif j == n:
            origen = "tail"
        else:
            origen = "intra"
        g_antes = tiros[i - 1] if i > 0 and flags[i - 1] else None
        g_rompe = tiros[j] if j < n and flags[j] else None
        gs_despues = [tiros[k] for k in idxs if k >= j]
        rachas.append(
            {
                "lo": i,
                "hi": j - 1,
                "nR": largo,
                "origen": origen,
                "m0_ini": int(getattr(tiros[i], "m0", 0) or 0) % 60,
                "m0_fin": int(getattr(tiros[j - 1], "m0", 0) or 0) % 60,
                "tiros_despues": n - j,
                "min_fin": int(getattr(tiros[j - 1], "m0", 0) or 0) % 60,
                "g_antes": g_antes,
                "g_rompe": g_rompe,
                "gs_despues": gs_despues,
            }
        )
        i = j

    max_r = max((r["nR"] for r in rachas), default=0)
    return {
        "tag": getattr(h, "tag", "?"),
        "n": n,
        "nG": nG,
        "clima": clima(nG),
        "lead": lead,
        "tail": tail,
        "intra_max": intra_max,
        "intra": intra,
        "max_r": max_r,
        "rachas": rachas,
        "tiros": tiros,
        "idxs": idxs,
        "sin_g": nG == 0,
    }


def escenario_tras(r: dict) -> str:
    gs = r["gs_despues"]
    if not gs:
        return "hora_sin_mas_G"
    # racimo: 2ª luz a ≤3 tiros de la rompe
    if len(gs) >= 2:
        # índices relativos: g_rompe es gs[0]; buscar gap en tiros
        t0 = r["hi"] + 1
        # próxima G después de la rompe
        # gs[1] está más adelante en la lista de luces
        return "rompe_y_sigue"
    return "rompe_sola"


def gaps_tras_rompe(r: dict, tiros: list) -> list[int]:
    gs = r["gs_despues"]
    if len(gs) < 2:
        return []
    out = []
    # posiciones de las luces posteriores (incluye rompe)
    pos = []
    for g in gs[:4]:
        try:
            pos.append(tiros.index(g))
        except ValueError:
            continue
    for a, b in zip(pos, pos[1:]):
        out.append(b - a - 1)
    return out


def cubeta_max(x: int) -> str:
    if x < 5:
        return "0-4"
    if x < 10:
        return "5-9"
    if x < 15:
        return "10-14"
    if x < 20:
        return "15-19"
    if x < 30:
        return "20-29"
    if x < 36:
        return "30-35"
    return "36+"


def horas_consecutivas(tag_a: str, tag_b: str) -> bool:
    try:
        return parse_dt(tag_b) - parse_dt(tag_a) == timedelta(hours=1)
    except ValueError:
        return False


def bloque(nombre: str, docs: list[dict], pares_cruce: list[tuple] | None = None) -> None:
    n_h = len(docs)
    w(f"\n════════ {nombre}  {n_h} horas ════════")
    if not docs:
        w("  (vacío)")
        return

    sin_g = sum(1 for d in docs if d["sin_g"])
    w(f"  Horas sin ninguna luz (0 G núcleo): {sin_g}  {pct(sin_g, n_h)}")
    by_clima = Counter(d["clima"] for d in docs)
    w(
        "  Clima: "
        + " · ".join(f"{k} {by_clima[k]}" for k in ("floja", "normal", "rica"))
    )

    cub = Counter(cubeta_max(d["max_r"]) for d in docs)
    w("\n  1. DÓNDE VIVE LA COLA (máx R seguidas DE ESA hora, una cifra por hora)")
    w("     cubo     | horas |  %")
    for k in ("0-4", "5-9", "10-14", "15-19", "20-29", "30-35", "36+"):
        w(f"     {k:<8} | {cub[k]:>5} | {pct(cub[k], n_h)}")
    maxes = [d["max_r"] for d in docs]
    w(
        f"     máx-R de la hora: p50={median(maxes):.0f}  "
        f"p90={sorted(maxes)[max(0, int(0.90 * (len(maxes) - 1)))]}  "
        f"p99={sorted(maxes)[max(0, int(0.99 * (len(maxes) - 1)))]}  "
        f"tope={max(maxes)}"
    )

    w("\n  2. HORAS QUE ALCANZAN el umbral (origen de la racha que lo toca)")
    w("     k   | cualquier | intra (tras G) | lead (aún no 1ª G) | cola (cierra sin romper)")
    for k in UMBRALES:
        any_h = intra_h = lead_h = tail_h = 0
        for d in docs:
            toca = [r for r in d["rachas"] if r["nR"] >= k]
            if not toca:
                continue
            any_h += 1
            if any(r["origen"] == "intra" for r in toca):
                intra_h += 1
            if any(r["origen"] == "lead" for r in toca):
                lead_h += 1
            if any(r["origen"] == "tail" for r in toca):
                tail_h += 1
        w(
            f"     ≥{k:<3}| {any_h:>5} {pct(any_h, n_h):>7} | "
            f"{intra_h:>5} {pct(intra_h, n_h):>7} | "
            f"{lead_h:>5} {pct(lead_h, n_h):>7} | "
            f"{tail_h:>5} {pct(tail_h, n_h):>7}"
        )

    w("\n  3. DESDE el k-ésimo R (postura live: ya van k R, ¿qué queda EN ESA hora?)")
    w("     No es 'la racha completa terminó en G' (eso es tautología de intra/lead).")
    for k in UMBRALES:
        evs = []
        for d in docs:
            hit = None
            for r in d["rachas"]:
                if r["nR"] >= k:
                    hit = r
                    break
            if hit is None:
                continue
            # el k-ésimo R de ESA racha
            i_k = hit["lo"] + (k - 1)
            tiros = d["tiros"]
            n = d["n"]
            quedan = n - (i_k + 1)
            min_k = int(getattr(tiros[i_k], "m0", 0) or 0) % 60
            g_despues = [j for j in d["idxs"] if j > i_k]
            rompe = bool(g_despues)
            extra_r = (g_despues[0] - i_k - 1) if rompe else quedan
            gaps = []
            if len(g_despues) >= 2:
                for a, b in zip(g_despues, g_despues[1:]):
                    gaps.append(b - a - 1)
                    if len(gaps) >= 3:
                        break
            origen = "lead" if not any(j < hit["lo"] for j in d["idxs"]) and hit["origen"] == "lead" else hit["origen"]
            evs.append(
                {
                    "d": d,
                    "r": hit,
                    "i_k": i_k,
                    "quedan": quedan,
                    "min_k": min_k,
                    "rompe": rompe,
                    "extra_r": extra_r,
                    "gaps": gaps,
                    "origen": origen,
                    "g_rompe": tiros[g_despues[0]] if rompe else None,
                    "racimo": bool(gaps and gaps[0] <= 3),
                    "sola": rompe and not gaps,
                    "media": bool(gaps and gaps[0] == 4),
                    "otra": (rompe and not gaps) or bool(gaps and gaps[0] >= 5),
                }
            )
        n = len(evs)
        if not n:
            w(f"     ≥{k}: 0 horas")
            continue
        rompe = sum(1 for e in evs if e["rompe"])
        acaba = n - rompe
        rac = sum(1 for e in evs if e["racimo"])
        sola = sum(1 for e in evs if e["sola"])
        media = sum(1 for e in evs if e["media"])
        otra = sum(1 for e in evs if e["otra"])
        lead = sum(1 for e in evs if e["origen"] == "lead")
        intra = sum(1 for e in evs if e["origen"] == "intra")
        tail = sum(1 for e in evs if e["origen"] == "tail")
        w(f"     ≥{k}: {n} horas  (lead {lead} · intra {intra} · cola {tail})")
        w(f"        se acaba la hora sin G posterior     {acaba:>4}  {pct(acaba, n)}")
        w(f"        aún cae G en lo que queda            {rompe:>4}  {pct(rompe, n)}")
        w(f"           luego racimo (próx G ≤3 tiros)    {rac:>4}  {pct(rac, n)}")
        w(f"           rompe y queda sola (no hay 2ª)    {sola:>4}  {pct(sola, n)}")
        w(f"           rompe + hueco medio (4 R)         {media:>4}  {pct(media, n)}")
        w(f"           rompe + otra sequía / sin 2ª      {otra:>4}  {pct(otra, n)}")
        extras = [e["extra_r"] for e in evs if e["rompe"]]
        if extras:
            w(
                f"           R AÚN por delante hasta esa G: p50={median(extras):.0f}  "
                f"0 más={sum(x==0 for x in extras)}  ≥5 más={sum(x>=5 for x in extras)}"
            )

        tipos = Counter()
        lumens = []
        for e in evs:
            g = e["g_rompe"]
            if g is None:
                continue
            tg = tipo_g(g)
            if tg:
                tipos[tg] += 1
            lm = lumen_g(g)
            if lm is not None:
                lumens.append(lm)
        if rompe:
            tip_s = " ".join(f"G{t}:{tipos[t]}" for t in (1, 2, 3, 4) if tipos[t])
            lum_s = (
                f"lumen p50={median(lumens):.0f}  n={len(lumens)}"
                if lumens
                else "sin lumen"
            )
            w(f"        tinta de la que cae: {tip_s or '—'}  · {lum_s}")

        quedan_t = [e["quedan"] for e in evs]
        quedan_m = [59 - e["min_k"] for e in evs]
        w(
            f"        al tocar el R nº {k}: tiros que quedan p50={median(quedan_t):.0f}  "
            f"minutos hasta :00 p50={median(quedan_m):.0f}"
        )
        sin_cupo = sum(1 for e in evs if e["quedan"] == 0)
        w(f"        tocan k y ya no queda tiro (cierre): {sin_cupo}  {pct(sin_cupo, n)}")

        cl = Counter(e["d"]["clima"] for e in evs)
        w(
            "        clima de esas horas: "
            + " · ".join(f"{k2} {cl[k2]}" for k2 in ("floja", "normal", "rica"))
        )
        if k == 36:
            w("        horas ≥36:")
            for e in evs:
                g = e["g_rompe"]
                tg = tipo_g(g) if g is not None else None
                lm = lumen_g(g) if g is not None else None
                w(
                    f"          {e['d']['tag']}  nG={e['d']['nG']} {e['d']['clima']}  "
                    f"{e['origen']} {e['r']['nR']}R  quedan={e['quedan']}  "
                    f"{'G'+str(tg)+' lm='+str(lm) if g is not None else 'sin G después'}  "
                    f"gaps_tras={e['gaps'][:3]}"
                )

    # baseline tinta de todas las G (para comparar rompe)
    base_t = Counter()
    base_lm = []
    for d in docs:
        for i in d["idxs"]:
            t = d["tiros"][i]
            tg = tipo_g(t)
            if tg:
                base_t[tg] += 1
            lm = lumen_g(t)
            if lm is not None:
                base_lm.append(lm)
    n_base = sum(base_t.values())
    w("\n  4. TINTA BASE de la misma tanda (todas las luces, no la cola)")
    if n_base:
        w(
            "     "
            + "  ".join(f"G{t} {pct(base_t[t], n_base)}" for t in (1, 2, 3, 4))
            + (f"  · lumen p50={median(base_lm):.0f}" if base_lm else "")
        )
    else:
        w("     (sin luces)")

    w("\n  5. MESA FRÍA al arrancar (lead) vs INTRA vs COLA — ≥15 como foto")
    for origen, label in (
        ("lead", "aún no 1ª G"),
        ("intra", "tras una G"),
        ("tail", "cierra la hora"),
    ):
        hs = [
            d
            for d in docs
            if any(r["origen"] == origen and r["nR"] >= 15 for r in d["rachas"])
        ]
        w(f"     {label}: {len(hs)} h  {pct(len(hs), n_h)}")
        if hs:
            rompe = sum(
                1
                for d in hs
                for r in d["rachas"]
                if r["origen"] == origen and r["nR"] >= 15 and r["g_rompe"]
            )
            # una racha lead/tail por hora
            n_r = sum(
                1
                for d in hs
                for r in d["rachas"]
                if r["origen"] == origen and r["nR"] >= 15
            )
            w(f"        de esas rachas ≥15, rompen con G: {rompe}/{n_r}  {pct(rompe, n_r)}")

    if pares_cruce is not None:
        w("\n  6. SEQUÍA QUE CRUZA el :00 (cola H + lead H+1, horas consecutivas)")
        n_par = len(pares_cruce)
        w(f"     pares consecutivos: {n_par}")
        if n_par:
            w("     k   | pares | % pares | H+1 abre G | H+1 se acaba 0 G")
            for k in UMBRALES:
                xs = [p for p in pares_cruce if p["nR"] >= k]
                abre = sum(1 for p in xs if p["abre"])
                cero = sum(1 for p in xs if p["h1_cero"])
                w(
                    f"     ≥{k:<3}| {len(xs):>5} | {pct(len(xs), n_par):>7} | "
                    f"{abre:>4} {pct(abre, len(xs)):>7} | "
                    f"{cero:>4} {pct(cero, len(xs)):>7}"
                )
            tops = sorted(pares_cruce, key=lambda p: -p["nR"])[:5]
            if tops:
                w("     top cruces:")
                for p in tops:
                    w(
                        f"        {p['a']} + {p['b']}: {p['nR']} R  "
                        f"({p['tail']}+{p['lead']})  "
                        f"{'abre G' if p['abre'] else 'H+1 sin G'}"
                    )


def pares_de_cruce(docs_by_tag: dict[str, dict], orden: list[str]) -> list[dict]:
    out = []
    for a, b in zip(orden, orden[1:]):
        if a not in docs_by_tag or b not in docs_by_tag:
            continue
        if not horas_consecutivas(a, b):
            continue
        da, db = docs_by_tag[a], docs_by_tag[b]
        nR = da["tail"] + db["lead"]
        out.append(
            {
                "a": a,
                "b": b,
                "tail": da["tail"],
                "lead": db["lead"],
                "nR": nR,
                "abre": (not db["sin_g"]),
                "h1_cero": db["sin_g"],
            }
        )
    return out


def main() -> None:
    w("LOOK · cola de sequías largas (15 / 20 / 30 / 36 R)")
    w("36 = forma (sequía muy larga), no ficha. Unidad = hora.")
    w("Luz = G núcleo (tipo 1–4). Extra/G5 no rompe la sequía de luces.")
    w("Juez: hora a hora. No Jaccard. No P(tiro=G). No cadena de toda la cinta.\n")

    horas, cinta = load_horas_y_cinta()
    # horas (load_cinta) tira mesas 0 G; cinta las trae
    by_cinta = {}
    for tag in cinta.orden:
        h = cinta.get(tag)
        d = foto_hora(h)
        if d:
            by_cinta[tag] = d

    docs_h = []
    for h in horas:
        d = foto_hora(h)
        if d:
            docs_h.append(d)

    train, hold = split_holdout(horas, HOLDOUT)
    docs_tr = [foto_hora(h) for h in train]
    docs_tr = [d for d in docs_tr if d]
    docs_ho = [foto_hora(h) for h in hold]
    docs_ho = [d for d in docs_ho if d]

    w(f"Cinta load_cinta (con ≥1 G): {len(horas)} h · train {len(train)} · holdout {len(hold)}")
    w(f"Cinta cruda (incluye 0 G): {len(by_cinta)} h de {len(cinta.orden)} tags")
    n0 = sum(1 for d in by_cinta.values() if d["sin_g"])
    w(f"Horas 0 G núcleo en cruda: {n0}")

    tags_tr = [h.tag for h in train]
    tags_ho = [h.tag for h in hold]
    # cruce en cada tanda, usando vecinos de la cruda
    pares_all = pares_de_cruce(by_cinta, cinta.orden)
    pares_tr = [p for p in pares_all if p["a"] in set(tags_tr)]
    pares_ho = [p for p in pares_all if p["a"] in set(tags_ho)]

    bloque("TRAIN (horas con ≥1 G, split oficial)", docs_tr, pares_tr)
    bloque("HOLDOUT 72 h (horas con ≥1 G)", docs_ho, pares_ho)

    # 0-G hours as their own photo
    ceros = [d for d in by_cinta.values() if d["sin_g"]]
    w("\n════════ HORAS 0 G (cruda; no entran al split de load_cinta) ════════")
    w(f"  n={len(ceros)}")
    if ceros:
        leads = [d["lead"] for d in ceros]
        w(
            f"  toda la mesa es R: p50={median(leads):.0f} tiros  "
            f"≥15:{sum(x>=15 for x in leads)}  ≥20:{sum(x>=20 for x in leads)}  "
            f"≥30:{sum(x>=30 for x in leads)}  ≥36:{sum(x>=36 for x in leads)}"
        )
        w("  tags: " + ", ".join(d["tag"] for d in ceros[:12]) + (" …" if len(ceros) > 12 else ""))

    w("\n════════════════════════════════ LECTURA ════════════════════════════════")
    w("Ya estaba: hueco no es pila · gap≥5 no perseguir (banda ~10%) ·")
    w("SEQUIA3 / Next 3 callan a los 3–4 R · LC-01 no se estira por tono ·")
    w("espera G→G = sombra de L · p es de ESA hora · racimo corto O sequía.")
    w("Diff de este look: situar 36 en la cola ≥15/20/30 y nombrar escenarios")
    w("hora a hora (rompe / racimo / se acaba / cruza :00). No cable.")

    out = LAB / "reports" / "LOOK_SEQUIA_COLA.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    w(f"\nGuardado: {out}")


if __name__ == "__main__":
    main()
