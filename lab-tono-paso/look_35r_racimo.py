# -*- coding: utf-8 -*-
"""
LOOK: ¿35 R seguidas levantan racimo?
35 = forma (cola extrema), no ficha. Unidad = evento causal al tocar el R nº k.
Juez: hora a hora. Sin leak (no usa el largo futuro de la racha, solo que ya llegó a k).
No Jaccard. No P(tiro=G) global. No cable.
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path
from statistics import median

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
sys.path.insert(0, str(ROOT / "lab-apostador-experto"))
sys.path.insert(0, str(ROOT / "lab-g-cola"))
sys.path.insert(0, str(ROOT))

from core_ae import HOLDOUT, load_horas_y_cinta, split_holdout  # noqa: E402
from core_gc import parse_dt  # noqa: E402
from look_sequia_cola import (  # noqa: E402
    clima,
    es_luz,
    foto_hora,
    horas_consecutivas,
    lumen_g,
    tipo_g,
)

UMBRALES = (15, 20, 30, 35, 36)
VENTANA = 3
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


def eval_en(d: dict, i_k: int) -> dict:
    """Postura live al tocar el tiro i_k: ¿cae G en ≤3? ¿racimo tras la que rompe?"""
    tiros = d["tiros"]
    n = d["n"]
    quedan = n - (i_k + 1)
    g_despues = [j for j in d["idxs"] if j > i_k]
    extra_r = (g_despues[0] - i_k - 1) if g_despues else quedan
    g_le3 = any(es_luz(tiros[j]) for j in range(i_k + 1, min(n, i_k + 1 + VENTANA)))
    racimo = False
    sola = False
    if len(g_despues) >= 2:
        racimo = (g_despues[1] - g_despues[0] - 1) <= VENTANA
    elif len(g_despues) == 1:
        sola = True
    g0 = tiros[g_despues[0]] if g_despues else None
    return {
        "tag": d["tag"],
        "clima": d["clima"],
        "nG": d["nG"],
        "quedan": quedan,
        "rompe": bool(g_despues),
        "extra_r": extra_r,
        "g_le3": g_le3,
        "racimo": racimo,
        "sola": sola,
        "g_rompe": g0,
    }


def eventos_intra_lead(docs: list[dict], k: int) -> dict[str, list]:
    out = {"intra": [], "lead": [], "tail": []}
    for d in docs:
        visto = {"intra": False, "lead": False, "tail": False}
        for r in d["rachas"]:
            if r["nR"] < k:
                continue
            origen = r["origen"]
            if visto[origen]:
                continue
            visto[origen] = True
            ev = eval_en(d, r["lo"] + k - 1)
            ev["origen"] = origen
            ev["nR_racha"] = r["nR"]
            out[origen].append(ev)
    return out


def eventos_cruce(docs_by_tag: dict[str, dict], orden: list[str], k: int) -> list[dict]:
    """Cruce verdadero: la cola de H aún no llegó a k; el R nº k cae en el lead de H+1."""
    out = []
    for a, b in zip(orden, orden[1:]):
        if a not in docs_by_tag or b not in docs_by_tag:
            continue
        if not horas_consecutivas(a, b):
            continue
        da, db = docs_by_tag[a], docs_by_tag[b]
        if da["tail"] >= k:
            continue
        if da["tail"] + db["lead"] < k:
            continue
        i_k = k - da["tail"] - 1
        ev = eval_en(db, i_k)
        ev["origen"] = "cruce"
        ev["par"] = f"{a}+{b}"
        ev["tail"] = da["tail"]
        ev["lead"] = db["lead"]
        ev["nR_cruce"] = da["tail"] + db["lead"]
        out.append(ev)
    return out


def base_racimo_rompe(docs: list[dict]) -> tuple[int, int, int]:
    """Cualquier racha que rompe (cualquier largo): ¿2ª G a ≤3 de la que rompe?"""
    n = rac = sola = 0
    for d in docs:
        for r in d["rachas"]:
            if not r["g_rompe"]:
                continue
            n += 1
            gs = r["gs_despues"]
            if len(gs) < 2:
                sola += 1
                continue
            pos = []
            for g in gs[:2]:
                try:
                    pos.append(d["tiros"].index(g))
                except ValueError:
                    pass
            if len(pos) == 2 and (pos[1] - pos[0] - 1) <= VENTANA:
                rac += 1
    return n, rac, sola


def base_g_tras_g(docs: list[dict]) -> tuple[int, int]:
    """Tras cualquier G que no cierra la hora: ¿próxima G en ≤3 tiros?"""
    n = hit = 0
    for d in docs:
        idxs = d["idxs"]
        for a, b in zip(idxs, idxs[1:]):
            n += 1
            if (b - a - 1) <= VENTANA:
                hit += 1
        if idxs and idxs[-1] < d["n"] - 1:
            n += 1  # última G: no hay 2ª en la hora
    return n, hit


def base_g_le3_en_r1(docs: list[dict]) -> tuple[int, int]:
    """Al tocar el 1er R de CUALQUIER racha: ¿G en ≤3? (sin condicionar a cola)."""
    n = hit = 0
    for d in docs:
        for r in d["rachas"]:
            ev = eval_en(d, r["lo"])
            n += 1
            if ev["g_le3"]:
                hit += 1
    return n, hit


def foto_bloque(evs: list[dict], titulo: str) -> None:
    n = len(evs)
    w(f"        {titulo}: n={n}")
    if not n:
        return
    g3 = sum(1 for e in evs if e["g_le3"])
    rompe = sum(1 for e in evs if e["rompe"])
    rac = sum(1 for e in evs if e["racimo"])
    sola = sum(1 for e in evs if e["sola"])
    acaba = n - rompe
    extras = [e["extra_r"] for e in evs if e["rompe"]]
    w(f"           P(próx G ≤3 tiros)     {g3:>4}  {pct(g3, n)}")
    w(f"           aún cae G en la hora   {rompe:>4}  {pct(rompe, n)}")
    w(f"           se acaba sin G         {acaba:>4}  {pct(acaba, n)}")
    w(f"           racimo tras la rompe   {rac:>4}  {pct(rac, n)}   (den=todas; si rompe: {pct(rac, rompe)})")
    w(f"           rompe y queda sola     {sola:>4}  {pct(sola, n)}")
    if extras:
        w(
            f"           R aún hasta esa G: p50={median(extras):.0f}  "
            f"0 más={sum(x == 0 for x in extras)}  "
            f"≤2 más={sum(x <= 2 for x in extras)}  "
            f"≥5 más={sum(x >= 5 for x in extras)}"
        )
    cl = Counter(e["clima"] for e in evs)
    w(
        "           clima: "
        + " · ".join(f"{k} {cl[k]}" for k in ("floja", "normal", "rica"))
    )


def bloque(nombre: str, docs: list[dict], cruce_fn) -> None:
    w(f"\n════════ {nombre}  {len(docs)} horas ════════")
    n_rompe, n_rac, n_sola = base_racimo_rompe(docs)
    n_gg, n_gg3 = base_g_tras_g(docs)
    n_r1, n_r1_3 = base_g_le3_en_r1(docs)
    w("  BASE (sin condicionar a 35)")
    w(
        f"     cualquier racha que ROMPE: racimo ≤3 = {n_rac}/{n_rompe}  {pct(n_rac, n_rompe)}"
        f"  · sola {n_sola}/{n_rompe}  {pct(n_sola, n_rompe)}"
    )
    w(f"     tras cualquier G (pares G→G + última sin 2ª): G en ≤3 = {n_gg3}/{n_gg}  {pct(n_gg3, n_gg)}")
    w(f"     al 1er R de cualquier racha: P(G en ≤3) = {n_r1_3}/{n_r1}  {pct(n_r1_3, n_r1)}")

    for k in UMBRALES:
        el = eventos_intra_lead(docs, k)
        cr = cruce_fn(k)
        intra, lead, tail = el["intra"], el["lead"], el["tail"]
        todos = intra + lead + tail
        w(f"\n  k={k}  (evento = se toca el R nº {k}, sin leak)")
        w(
            f"     horas/eventos: intra {len(intra)} · lead {len(lead)} · "
            f"cola-en-hora {len(tail)} · cruce :00 {len(cr)}"
        )
        foto_bloque(intra, "INTRA (tras G de esa hora)")
        foto_bloque(lead, "LEAD (aún no 1ª G)")
        foto_bloque(tail, "COLA (cierra la hora; no mira H+1)")
        foto_bloque(cr, "CRUCE :00 (cola H + lead H+1; k cae en H+1)")
        if todos:
            foto_bloque(todos, "TODAS las posturas de ESA hora (sin cruce)")
        if k == 35:
            w("     lista k=35 (intra/lead/cola de esa hora):")
            for e in todos:
                g = e["g_rompe"]
                tg = tipo_g(g) if g is not None else None
                lm = lumen_g(g) if g is not None else None
                w(
                    f"       {e['tag']}  {e['origen']} {e['nR_racha']}R  {e['clima']} nG={e['nG']}  "
                    f"g≤3={'sí' if e['g_le3'] else 'no'}  "
                    f"racimo={'sí' if e['racimo'] else 'no'}  "
                    f"{'G'+str(tg)+' lm='+str(lm) if g is not None else 'sin G después'}"
                )
            if cr:
                w("     lista k=35 CRUCE:")
                for e in cr:
                    g = e["g_rompe"]
                    tg = tipo_g(g) if g is not None else None
                    w(
                        f"       {e['par']}  {e['tail']}+{e['lead']}={e['nR_cruce']}R  "
                        f"g≤3={'sí' if e['g_le3'] else 'no'}  "
                        f"racimo={'sí' if e['racimo'] else 'no'}  "
                        f"{'G'+str(tg) if g is not None else 'sin G'}"
                    )


def main() -> None:
    w("LOOK · ¿35 R levantan racimo?  (k = 15 / 20 / 30 / 35 / 36)")
    w("35 = forma (cola extrema), no ficha. Esta hora live es FORMA, no ley.")
    w("Unidad = evento causal al tocar el R nº k. Luz = G núcleo (1–4).")
    w("Dos preguntas distintas:")
    w("  A) P(próxima G en ≤3 tiros | ya van k R)  — ¿se acaba YA la sequía?")
    w("  B) P(racimo tras la que rompe | ya van k R) — ¿viene mancha después?")
    w("Juez: hora a hora. Cero cable.\n")

    horas, cinta = load_horas_y_cinta()
    by_cinta = {}
    for tag in cinta.orden:
        h = cinta.get(tag)
        d = foto_hora(h)
        if d:
            by_cinta[tag] = d

    train, hold = split_holdout(horas, HOLDOUT)
    docs_tr = [d for d in (foto_hora(h) for h in train) if d]
    docs_ho = [d for d in (foto_hora(h) for h in hold) if d]
    tags_tr = {h.tag for h in train}
    tags_ho = {h.tag for h in hold}

    def cruce_de(tags: set):
        def fn(k: int) -> list[dict]:
            xs = eventos_cruce(by_cinta, cinta.orden, k)
            return [e for e in xs if e["par"].split("+")[0] in tags]

        return fn

    w(f"Cinta load_cinta (≥1 G): {len(horas)} h · train {len(train)} · holdout {len(hold)}")
    w(f"Cinta cruda: {len(by_cinta)} h")

    bloque("TRAIN", docs_tr, cruce_de(tags_tr))
    bloque("HOLDOUT 72 h", docs_ho, cruce_de(tags_ho))

    w("\n════════════════════════════════ LECTURA ════════════════════════════════")
    w("Ya estaba: hueco no es pila · SEQUIA3 calla a 3–4 R · racimo O sequía.")
    w("Diff: k=35 (exacto al tocar) · A vs B · intra / lead / cruce :00.")
    w("Si A y B no suben vs base → 35 no nombra racimo. No alarma P7.")

    out = LAB / "reports" / "LOOK_35R_RACIMO.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    w(f"\nGuardado: {out}")


if __name__ == "__main__":
    main()
