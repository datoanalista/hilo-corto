# -*- coding: utf-8 -*-
"""Precisión P8 ∩ P10 cuando coinciden — juez banda d≤1."""
from __future__ import annotations

import sys
from pathlib import Path
from statistics import mean

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
RZ = ROOT / "lab-ruleta-zero"
sys.path.insert(0, str(RZ))
sys.path.insert(0, str(ROOT))

from core_rz import HOLDOUT, load_cinta, split_tags, tag_key  # noqa: E402
from src.boleto_inter2 import precompute_beta_chips  # noqa: E402
from src.estado import PRIMERA_UTIL  # noqa: E402
from src.mesas_beta import BOLETO_IDS, acuerdo_ge2  # noqa: E402
from src.tablero import recorrer, score  # noqa: E402


def percentile(xs, p, fallback=5):
    if not xs:
        return fallback
    ys = sorted(xs)
    idx = min(len(ys) - 1, max(0, int(len(ys) * p)))
    return ys[idx]


def chips_live_rc(luces):
    sorted_l = sorted(set(luces or []))
    tips = set()
    for i in range(len(sorted_l) + 1):
        prefix = sorted_l[:i]
        T = prefix[-1] if prefix else -1
        gh = [prefix[k] - prefix[k - 1] for k in range(1, len(prefix))]
        if T >= 59:
            continue
        gap = percentile(gh, 0.3)
        c = min(59, max(T + 1, T + gap))
        for x in (c, c + 1, c + 2):
            if T < x <= 59:
                tips.add(x)
    return sorted(tips)


def metrics(chips, ofc):
    if not ofc:
        return {"banda": None, "g": 0, "pm1": 0, "n": 0, "k": 0, "hit": False, "exact": 0}
    if not chips:
        return {"banda": 0.0, "g": 0, "pm1": 0, "n": len(ofc), "k": 0, "hit": False, "exact": 0.0}
    g, pm1 = score(chips, ofc)
    n = len(ofc)
    return {
        "banda": (g + pm1) / n,
        "g": g,
        "pm1": pm1,
        "n": n,
        "k": len(chips),
        "hit": (g + pm1) > 0,
        "exact": g / n,
    }


def build_rows(cinta):
    rec = recorrer(cinta)
    hist = {f["for"]: f for f in rec["historico"] if f.get("for")}
    beta_by = precompute_beta_chips(cinta)
    rows = []
    for tag, f in hist.items():
        if tag_key(tag) < tag_key(PRIMERA_UTIL):
            continue
        cm = {"oficial": list(f.get("chips_classic") or f.get("chips") or [])}
        ok = True
        for pid in BOLETO_IDS:
            if pid == "oficial":
                continue
            ch = (beta_by.get(tag) or {}).get(pid)
            if ch is None:
                ok = False
                break
            cm[pid] = list(ch)
        if not ok:
            continue
        p8 = acuerdo_ge2([cm.get(pid) or [] for pid in BOLETO_IDS])
        ofc = sorted(f.get("oficiales") or [])
        if len(ofc) < 2:
            continue
        p10 = chips_live_rc(ofc)
        rows.append(
            {
                "tag": tag,
                "p8": p8,
                "p10": p10,
                "inter": sorted(set(p8) & set(p10)),
                "union": sorted(set(p8) | set(p10)),
                "ofc": ofc,
            }
        )
    return rows


def agg(sub, key):
    bs, ks, ex, hs = [], [], [], []
    empty = 0
    for r in sub:
        m = metrics(r[key], r["ofc"])
        if m["k"] == 0:
            empty += 1
        bs.append(m["banda"] or 0)
        ks.append(m["k"])
        ex.append(m["exact"])
        hs.append(1 if m["hit"] else 0)
    return {
        "banda": mean(bs),
        "k": mean(ks),
        "exact": mean(ex),
        "hit": mean(hs),
        "empty": empty,
        "n": len(sub),
    }


def chip_precision(sub):
    tp = fp = 0
    for r in sub:
        for c in r["inter"]:
            g, pm1 = score([c], r["ofc"])
            if g + pm1 > 0:
                tp += 1
            else:
                fp += 1
    return tp, fp


def main():
    cinta = load_cinta()
    rows = build_rows(cinta)
    tags = sorted({r["tag"] for r in rows}, key=tag_key)
    _, test = split_tags(tags)
    test_set = set(test)

    print(f"P8 INTER2 x P10 LIVE-RC — juez banda d<=1 · holdout={HOLDOUT}h")
    print(f"horas={len(rows)} · P10 = MULTI93 acum al cerrar hora (oracle prefix completo)")
    print()

    for label, sub in [
        ("ALL", rows),
        ("train", [r for r in rows if r["tag"] not in test_set]),
        ("holdout", [r for r in rows if r["tag"] in test_set]),
    ]:
        print(f"=== {label} n={len(sub)} ===")
        for name, key in [
            ("P8 INTER2", "p8"),
            ("P10 LIVE-RC", "p10"),
            ("P8 cap P10 (inter)", "inter"),
            ("P8 union P10", "union"),
        ]:
            a = agg(sub, key)
            print(
                f"  {name:22s}  banda={100*a['banda']:.1f}%  "
                f"exact={100*a['exact']:.1f}%  k={a['k']:.1f}  "
                f"hit={100*a['hit']:.0f}%  horas_vacias={a['empty']}"
            )
        tp, fp = chip_precision(sub)
        nch = tp + fp
        prec = 100 * tp / nch if nch else 0
        avg_inter = mean(len(r["inter"]) for r in sub)
        pct_p8 = 100 * mean(len(r["inter"]) / len(r["p8"]) if r["p8"] else 0 for r in sub)
        print(
            f"  chip-level inter: prec={prec:.1f}%  (n={nch} chips)  "
            f"med k_inter={avg_inter:.1f}  ={pct_p8:.0f}% de P8"
        )
        print()

    # En vivo: inter al ultimo prefix (como dashboard con luces parciales finales)
    print("=== holdout · inter con P10 parcial (solo prefix real, no oracle fin de hora) ===")
    sub = [r for r in rows if r["tag"] in test_set]
    bs = []
    ks = []
    for r in sub:
        p10_live = chips_live_rc(r["ofc"])  # same as full at end
        # partial: after last but one G
        if len(r["ofc"]) >= 2:
            p10_part = chips_live_rc(r["ofc"][:-1])
        else:
            p10_part = chips_live_rc([])
        inter_part = sorted(set(r["p8"]) & set(p10_part))
        m = metrics(inter_part, r["ofc"])
        bs.append(m["banda"] or 0)
        ks.append(m["k"])
    print(
        f"  P8 cap P10 @prefix(n-1): banda={100*mean(bs):.1f}%  k={mean(ks):.1f}"
    )


if __name__ == "__main__":
    main()
