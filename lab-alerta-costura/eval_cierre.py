# -*- coding: utf-8
"""Eval cierre abierto/cerrado — replica dashboard @min55 vs target costura."""
from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
sys.path.insert(0, str(ROOT))

from core_alerta import build_pairs, split_holdout, cargar_ingesta  # noqa: E402

ALERT_MIN = 55
COLA_MIN = 50
CORTE_LARGO_S = 70


def _gs(tiros):
    return [t for t in (tiros or []) if t.color == "G" and t.lumen is not None]


def tiros_hasta(tiros, T):
    return sorted(
        [t for t in (tiros or []) if t.m0 <= T],
        key=lambda t: (t.m0, t.s0),
    )


def duracion_s(t):
    a = t.m0 * 60 + t.s0
    b = t.m1 * 60 + t.s1
    return (b - a + 3600) % 3600


def l_wrap_proxy(ultimo):
    if not ultimo or ultimo.color != "R":
        return False
    if ultimo.m1 < ultimo.m0 or ultimo.m0 >= 58:
        return True
    if ultimo.m0 >= COLA_MIN and duracion_s(ultimo) >= CORTE_LARGO_S:
        fin = ultimo.m0 + duracion_s(ultimo) // 60
        return fin >= 58
    return False


def cierre_abierto_min55(h_n) -> bool | None:
    """True=abierto, False=cerrado, None=antes min55 (no aplica)."""
    T = ALERT_MIN
    tiros = h_n.tiros_nucleo or []
    xs = tiros_hasta(tiros, T)
    gs = _gs(xs)
    ultimo = xs[-1] if xs else None
    ultimo_r = bool(ultimo and ultimo.color == "R")
    g_cola = any(g.m0 >= 58 for g in gs)  # raro @55
    g_en_cola = any(COLA_MIN <= g.m0 <= T for g in gs)
    l_wrap = l_wrap_proxy(ultimo)
    sin_early = not any(g.m0 <= 9 for g in gs)

    if g_cola:
        return True
    if sin_early and not g_en_cola and not ultimo_r and not l_wrap:
        return False
    if ultimo_r or g_en_cola or l_wrap:
        return True
    return False


def eval_set(rows, label):
    tp = fp = tn = fn = 0
    for r in rows:
        pred = cierre_abierto_min55(
            type("H", (), {"tiros_nucleo": __import__("src.lectores", fromlist=["cargar_ingesta"]).cargar_ingesta("") or None})()
        )
    return tp, fp, tn, fn


def main():
    cinta, _, _ = cargar_ingesta("")
    rows = build_pairs(cinta)
    train, hold = split_holdout(rows)

    def score(sub, name):
        tp = fp = tn = fn = 0
        n_on = n_off = 0
        for r in sub:
            h = cinta.get(r.tag_n)
            pred = cierre_abierto_min55(h)
            y = r.costura
            if pred:
                n_on += 1
                if y:
                    tp += 1
                else:
                    fp += 1
            else:
                n_off += 1
                if y:
                    fn += 1
                else:
                    tn += 1
        n = len(sub)
        prec_on = tp / (tp + fp) if (tp + fp) else 0
        prec_off = tn / (tn + fn) if (tn + fn) else 0
        rec = tp / (tp + fn) if (tp + fn) else 0
        acc = (tp + tn) / n if n else 0
        base = sum(1 for r in sub if r.costura) / n if n else 0
        print(f"\n=== {name} · n={n} ===")
        print(f"  Target costura (real):     {sum(1 for r in sub if r.costura)}/{n} ({100*base:.0f}%)")
        print(f"  Cierre abierto (icono ON):  {n_on}/{n} ({100*n_on/n:.0f}%)")
        print(f"  Cierre cerrado (sin icono): {n_off}/{n} ({100*n_off/n:.0f}%)")
        print()
        print(f"  Cuando dice ABIERTO @55:")
        print(f"    acierta (hubo costura):  {tp}/{tp+fp} = {100*prec_on:.0f}% precision")
        print(f"    falla (no hubo costura): {fp}/{tp+fp} = {100*(1-prec_on if tp+fp else 0):.0f}%")
        print(f"    recall (detecta costura): {tp}/{tp+fn} = {100*rec:.0f}%")
        print()
        print(f"  Cuando dice CERRADO @55:")
        print(f"    acierta (no costura):    {tn}/{tn+fn} = {100*prec_off:.0f}% precision OFF")
        print(f"    falla (si hubo costura): {fn}/{tn+fn} = {100*(1-prec_off if tn+fn else 0):.0f}%")
        print()
        print(f"  Accuracy global (abierto+cerrado): {tp+tn}/{n} = {100*acc:.0f}%")
        print(f"  vs baseline 'siempre abierto':   {100*base:.0f}%")

    score(rows, "TODA LA CINTA")
    score(train, "TRAIN")
    score(hold, "HOLDOUT 72")

    # Confirmado vs olor (post-hoc: target desglosado)
    print("\n=== TARGET desglosado (toda cinta) ===")
    cola = sum(1 for r in rows if r.cola_58)
    early = sum(1 for r in rows if r.early_03)
    solo_cola = sum(1 for r in rows if r.cola_58 and not r.early_03)
    solo_early = sum(1 for r in rows if r.early_03 and not r.cola_58)
    ambos = sum(1 for r in rows if r.cola_58 and r.early_03)
    ninguno = sum(1 for r in rows if not r.costura)
    print(f"  cola 58+ solo: {solo_cola} · early 0-3 solo: {solo_early} · ambos: {ambos} · ninguno: {ninguno}")


if __name__ == "__main__":
    main()
