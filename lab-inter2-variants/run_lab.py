# -*- coding: utf-8 -*-
"""
Lab INTER2 variantes — Pool 8 sombra (umbral · peso · P9).
  python run_lab.py

No toca Pool 8 prod. Producto = candidato Pool 11+ si gana holdout.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from statistics import mean

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
RZ = ROOT / "lab-ruleta-zero"
sys.path.insert(0, str(LAB))
sys.path.insert(0, str(RZ))
sys.path.insert(0, str(ROOT))

from core_rz import DETAIL, HOLDOUT, banda_score, load_cinta, split_tags, tag_key  # noqa: E402
from motors_inter2 import POOL9_ID, build_strategies, pool_train_weights, ref_inter2  # noqa: E402

from src.boleto_inter2 import precompute_beta_chips  # noqa: E402
from src.estado import PRIMERA_UTIL  # noqa: E402
from src.mesas_beta import BOLETO_IDS  # noqa: E402
from src.tablero import recorrer, score  # noqa: E402

DATA3 = ROOT / "data" / "data_3dias.txt"
OUT = LAB / "reports"
OUT.mkdir(exist_ok=True)
lines: list[str] = []


def w(s=""):
    lines.append(s)
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))


def load_cinta_path(path: Path):
    from src.lectores import cinta_desde_bloques, leer_bloques_texto

    orden, bloques = leer_bloques_texto(path.read_text(encoding="utf-8"))
    cinta, _ = cinta_desde_bloques(orden, bloques)
    return cinta


def build_rows(cinta):
    rec = recorrer(cinta)
    hist = {f["for"]: f for f in rec["historico"] if f.get("for")}
    beta_by = precompute_beta_chips(cinta)
    rows = []
    for tag, f in hist.items():
        if tag_key(tag) < tag_key(PRIMERA_UTIL):
            continue
        cm = {
            "oficial": list(f.get("chips_classic") or f.get("chips") or []),
            POOL9_ID: list(f.get("chips_classic") or []),
        }
        ok = True
        for pid in BOLETO_IDS:
            if pid == "oficial":
                continue
            ch = (beta_by.get(tag) or {}).get(pid)
            if ch is None:
                ok = False
                break
            cm[pid] = list(ch)
        inter2 = list(f.get("chips") or [])
        ofc = sorted(f.get("oficiales") or [])
        if not ok or len(ofc) < 2:
            continue
        rows.append(
            {
                "tag": tag,
                "chips_map": cm,
                "inter2_ref": inter2,
                "oficiales": ofc,
                "nG": len(ofc),
            }
        )
    rows.sort(key=lambda r: tag_key(r["tag"]))
    return rows


def metrics(chips: list[int], oficiales: list[int]) -> dict:
    if not oficiales:
        return {"banda": None, "g": 0, "pm1": 0, "n": 0, "k": 0, "hit": False, "exact": None}
    g, pm1 = score(chips, oficiales)
    n = len(oficiales)
    bs = banda_score(chips, oficiales)
    return {
        "banda": bs["banda"],
        "g": g,
        "pm1": pm1,
        "n": n,
        "k": len(chips),
        "hit": bs["hit"],
        "exact": g / n,
    }


def walk(rows, test_tags: set[str], strategies: dict[str, callable]):
    names = list(strategies.keys())
    tr_rows: list[dict] = []
    te_rows: list[dict] = []
    for row in rows:
        tag = row["tag"]
        ofc = row["oficiales"]
        cm = row["chips_map"]
        bucket = te_rows if tag in test_tags else tr_rows
        out = {"tag": tag, "nG": row["nG"]}
        for nm, fn in strategies.items():
            try:
                ch = fn(cm)
            except Exception:
                ch = []
            m = metrics(ch, ofc)
            for k, v in m.items():
                out[f"{nm}_{k}"] = v
        # sanity: ref should match stored inter2 most of the time
        bucket.append(out)
    return tr_rows, te_rows, names


def agg(rows: list[dict], name: str) -> dict | None:
    bs = [r[f"{name}_banda"] for r in rows if r.get(f"{name}_banda") is not None]
    if not bs:
        return None
    ks = [r[f"{name}_k"] for r in rows]
    hs = [r[f"{name}_hit"] for r in rows]
    ex = [r[f"{name}_exact"] for r in rows if r.get(f"{name}_exact") is not None]
    zeros = sum(1 for r in rows if r.get(f"{name}_k", 0) == 0)
    return {
        "banda": mean(bs),
        "k": mean(ks),
        "hit": mean(hs),
        "exact": mean(ex) if ex else None,
        "k0": zeros,
        "n": len(bs),
    }


def pareto_front(candidates: list[tuple[str, dict]], ref_banda: float, ref_k: float):
    """Mejor banda con k menor, o misma banda ±0.3pp y k menor."""
    out = []
    for name, te in candidates:
        if te["banda"] >= ref_banda - 0.003 and te["k"] < ref_k - 0.3:
            out.append((name, te))
        elif te["banda"] > ref_banda + 0.003 and te["k"] <= ref_k + 0.5:
            out.append((name, te))
    out.sort(key=lambda x: (-x[1]["banda"], x[1]["k"]))
    return out


def run_source(label: str, cinta):
    tags = sorted(
        {r["tag"] for r in build_rows(cinta)},
        key=tag_key,
    )
    train_tags, test_tags = split_tags(tags)
    rows = build_rows(cinta)
    train_rows = [r for r in rows if r["tag"] not in test_tags]
    test_set = set(test_tags)
    tw = pool_train_weights(train_rows)
    strategies = build_strategies(tw)

    w(f"{'=' * 72}")
    w(f"FUENTE {label} · horas={len(rows)} · train={len(train_tags)} · holdout={len(test_tags)}")
    w(f"  pesos train-calibrados: " + ", ".join(f"{p}={tw[p]:.2f}" for p in BOLETO_IDS))
    w()

    tr, te, names = walk(rows, test_set, strategies)
    ref = "REF-INTER2-ge2"
    ref_te = agg(te, ref)
    ref_tr = agg(tr, ref)
    if not ref_te:
        w("  sin holdout")
        return

    w("== RANKING holdout — banda · k · exact · Δ vs REF ==")
    w(f"  {'motor':22s}  ho_banda  ho_k  ho_exact  hit%  k=0  Δpp")
    ranking = []
    for nm in names:
        te_a = agg(te, nm)
        tr_a = agg(tr, nm)
        if not te_a:
            continue
        d = te_a["banda"] - ref_te["banda"]
        ranking.append((te_a["banda"], nm, tr_a, te_a, d))
        w(
            f"  {nm:22s}  {100*te_a['banda']:5.1f}%  {te_a['k']:5.1f}  "
            f"{100*(te_a['exact'] or 0):5.1f}%  {100*te_a['hit']:5.0f}%  "
            f"{te_a['k0']:3d}  {100*d:+5.1f}pp"
        )
    ranking.sort(reverse=True)
    w()
    w(f"  REF train {100*ref_tr['banda']:.1f}% k={ref_tr['k']:.1f} · "
      f"holdout {100*ref_te['banda']:.1f}% k={ref_te['k']:.1f}")
    w()

    w("== H1 UMBRAL / menos fichas — vs REF ==")
    for nm in names:
        if not nm.startswith("I8-ge") and not nm.startswith("I8-ge2") and "cap" not in nm:
            continue
        if nm == ref or "+P9" in nm:
            continue
        te_a = agg(te, nm)
        if te_a:
            w(
                f"  {nm:22s}  banda={100*te_a['banda']:.1f}%  k={te_a['k']:.1f}  "
                f"Δ={100*(te_a['banda']-ref_te['banda']):+.1f}pp  "
                f"Δk={te_a['k']-ref_te['k']:+.1f}"
            )
    w()

    w("== H2 PESO desigual ==")
    for nm in names:
        if not nm.startswith("W-"):
            continue
        te_a = agg(te, nm)
        if te_a:
            w(
                f"  {nm:22s}  banda={100*te_a['banda']:.1f}%  k={te_a['k']:.1f}  "
                f"Δ={100*(te_a['banda']-ref_te['banda']):+.1f}pp"
            )
    w()

    w("== H3 incluir P9 ==")
    for nm in names:
        if "P9" not in nm and nm != "I8∩P9":
            continue
        te_a = agg(te, nm)
        if te_a:
            w(
                f"  {nm:22s}  banda={100*te_a['banda']:.1f}%  k={te_a['k']:.1f}  "
                f"Δ={100*(te_a['banda']-ref_te['banda']):+.1f}pp"
            )
    w()

    w("== PARETO — misma/más banda con menos fichas (holdout) ==")
    cands = [(nm, agg(te, nm)) for nm in names if agg(te, nm)]
    cands = [(n, a) for n, a in cands if n != ref]
    pf = pareto_front(cands, ref_te["banda"], ref_te["k"])
    if pf:
        for nm, te_a in pf[:8]:
            w(
                f"  {nm:22s}  banda={100*te_a['banda']:.1f}%  k={te_a['k']:.1f}  "
                f"Δb={100*(te_a['banda']-ref_te['banda']):+.1f}pp  "
                f"Δk={te_a['k']-ref_te['k']:+.1f}"
            )
    else:
        w("  (ninguno domina REF en banda/k)")
    w()

    w("== TOP 5 holdout banda ==")
    for i, (b, nm, _, te_a, d) in enumerate(ranking[:5], 1):
        w(f"  {i}. {nm}  {100*b:.1f}%  k={te_a['k']:.1f}  ΔREF={100*d:+.1f}pp")
    w()

    # Match ref inter2 from recorrer vs recomputed
    mism = 0
    for row in rows:
        if row["tag"] in test_set:
            a = ref_inter2(row["chips_map"])
            b = row["inter2_ref"]
            if set(a) != set(b):
                mism += 1
    w(f"  sanity REF vs recorrer inter2 mism en holdout: {mism}/{len(test_tags)}")
    w()
    return ranking, ref_te


def main():
    w("LAB INTER2 VARIANTES — Pool 8 sombra")
    w(f"detail: {DETAIL}")
    w(f"juez: banda d≤1 · holdout={HOLDOUT}h")
    w()

    cinta = load_cinta()
    run_source("depurar-all-4G-detail", cinta)

    if DATA3.exists():
        w()
        run_source("data_3dias", load_cinta_path(DATA3))

    w("== NOTAS ==")
    w("  Pool 8 prod NO tocado. Candidatos = pool sombra nuevo si humano OK.")
    w("  REF-INTER2-ge2 = acuerdo ≥2 P0–P5 (Pool 8 actual).")
    w("  P9 = chips_classic (Pool 9). Pesos TRAIN solo en train tags.")
    w()

    out = OUT / "LAB_INTER2_VARIANTS.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    w(f"Reporte: {out}")


if __name__ == "__main__":
    main()
