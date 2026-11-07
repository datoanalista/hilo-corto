"""Dónde fue la racha R máx de ZONA (no de la hora). Solo lectura."""
from __future__ import annotations

from pathlib import Path

from look_api import API, flag19, parsear
from look_banca import zona_ok

OUT = Path(__file__).resolve().parent / "LOOK_RACHA_ZONA.txt"


def walk(tiros, T=19):
    last_g = None
    gaps = []
    prev_g_m = None
    racha = []
    mejor = []
    for t in tiros:
        if t["g"]:
            if prev_g_m is not None:
                gaps.append((t["m0"] - prev_g_m) % 60)
            prev_g_m = t["m0"]
        if t["m0"] <= T:
            if t["g"]:
                last_g = t["m0"]
            continue
        if not zona_ok(t["m0"], last_g, gaps):
            if t["g"]:
                last_g = t["m0"]
            continue
        # esta SÍ se apuesta
        if t["g"]:
            if len(racha) > len(mejor):
                mejor = list(racha)
            racha = []
            last_g = t["m0"]
        else:
            racha.append(t)
            if last_g is None:
                pass
    if len(racha) > len(mejor):
        mejor = list(racha)
    return mejor


def main() -> None:
    _, _, horas = parsear(API)
    flagged = [(k, t) for k, t in horas if flag19(t)]
    champ = []
    champ_k = ""
    n_ap = n_g = 0
    for k, tiros in flagged:
        ap = 0
        g = 0
        last_g = None
        gaps = []
        prev = None
        for t in tiros:
            if t["g"]:
                if prev is not None:
                    gaps.append((t["m0"] - prev) % 60)
                prev = t["m0"]
            if t["m0"] <= 19:
                if t["g"]:
                    last_g = t["m0"]
                continue
            if not zona_ok(t["m0"], last_g, gaps):
                if t["g"]:
                    last_g = t["m0"]
                continue
            ap += 1
            if t["g"]:
                g += 1
                last_g = t["m0"]
        n_ap += ap
        n_g += g
        m = walk(tiros)
        if len(m) > len(champ):
            champ = m
            champ_k = k

    L = [
        "LOOK RACHA ZONA — qué es el 16 R",
        f"indicio @19: {len(flagged)} h  apuestas zona {n_ap}  G en zona {n_g}  "
        f"({100*n_g/n_ap:.1f}% hit)",
        f"Racha R más larga: {len(champ)} apuestas zona  en hora {champ_k}",
        "Esas apuestas (minuto / no es cada tiro de la hora):",
    ]
    for t in champ:
        L.append(f"  min {t['m0']:02d}  {t['ts'][11:16]}  R  (sí se apostó, zona)")
    L.extend(
        [
            "",
            "Entre un R y el siguiente de esa lista hubo minutos SIN apuesta.",
            "G que cayeron fuera de ±1 no se apostaron y no cortan esta racha.",
            "No se persigue. No se ensancha la zona.",
            "",
        ]
    )
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(OUT)
    print(f"racha {len(champ)} en {champ_k}  zona {n_ap} G {n_g}")


if __name__ == "__main__":
    main()
