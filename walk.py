"""Walk de laboratorio: emite, puntúa, no escribe boleto de producción."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.estado import Estado, PRIMERA_UTIL
from src.lectores import cargar_crudo
from src.motor import dist_anillo, emitir_boleto

REPORTS = ROOT / "reports"


def _hits(boleto: list[int], luces: list[int]) -> int:
    return len(set(boleto) & set(luces))


def _cubrir(boleto: list[int], luces: list[int]) -> tuple[int, int]:
    """Oficiales en G (d=0) y en +-1. +-2 queda fuera."""
    if not boleto:
        return 0, 0
    bs = set(boleto)
    g = pm1 = 0
    for x in luces:
        d = min(dist_anillo(x, b) for b in bs)
        if d == 0:
            g += 1
        elif d == 1:
            pm1 += 1
    return g, pm1


def _azar(k: int, nG: int) -> float:
    if k <= 0:
        return 0.0
    return k * nG / 60.0


def walk(desde: str, hasta: str | None, k: int | None) -> dict:
    cinta = cargar_crudo()
    if desde not in cinta.horas:
        raise SystemExit(f"desde {desde} no está en la data")

    i0 = cinta.orden.index(desde)
    i1 = len(cinta.orden) - 1
    if hasta:
        if hasta not in cinta.horas:
            raise SystemExit(f"hasta {hasta} no está en la data")
        i1 = cinta.orden.index(hasta)

    estado = Estado()
    filas = []

    for i in range(i0, i1):
        tag = cinta.orden[i]
        nxt = cinta.orden[i + 1]
        estado.cerrar(cinta.get(tag))
        boleto_doc = emitir_boleto(estado, k=k)
        boleto = boleto_doc["boleto"]
        real = cinta.get(nxt)
        k_ef = len(boleto)
        hits_n, pm1_n = _cubrir(boleto, real.nucleo)
        hits_h = _hits(boleto, real.holgada)
        score_n = hits_n + pm1_n
        copia = cinta.get(tag).nucleo
        hits_copia = _hits(copia, real.nucleo)
        filas.append(
            {
                "based_on": tag,
                "for": nxt,
                "k": k_ef,
                "nG": len(real.nucleo),
                "nG_nucleo": len(real.nucleo),
                "nG_holgada": len(real.holgada),
                "hits_nucleo": hits_n,
                "pm1_nucleo": pm1_n,
                "score_banda": score_n,
                "colapso": int(score_n == 0),
                "hits_holgada": hits_h,
                "azar_nucleo": _azar(k_ef, len(real.nucleo)),
                "azar_holgada": _azar(k_ef, len(real.holgada)),
                "hits_copia_prev": hits_copia,
                "k_copia": len(copia),
                "azar_copia": _azar(len(copia), len(real.nucleo)),
                "columnas": estado.calentamiento(),
                "jaccard_prev": (
                    _hits(copia, real.nucleo)
                    / max(1, len(set(copia) | set(real.nucleo)))
                ),
            }
        )

    def mean(key: str, rows: list[dict]) -> float:
        if not rows:
            return 0.0
        return sum(r[key] for r in rows) / len(rows)

    maduras = [r for r in filas if r["columnas"] >= 4]
    resumen = {
        "desde": desde,
        "hasta": cinta.orden[i1],
        "n_horas_puntuadas": len(filas),
        "k_pedido": k,
        "todas": {
            "n": len(filas),
            "hits_nucleo": mean("hits_nucleo", filas),
            "pm1_nucleo": mean("pm1_nucleo", filas),
            "score_banda": mean("score_banda", filas),
            "colapso": mean("colapso", filas),
            "azar_nucleo": mean("azar_nucleo", filas),
            "hits_holgada": mean("hits_holgada", filas),
            "azar_holgada": mean("azar_holgada", filas),
            "hits_copia_prev": mean("hits_copia_prev", filas),
            "azar_copia": mean("azar_copia", filas),
            "k_medio": mean("k", filas),
        },
        "desde_4a": {
            "n": len(maduras),
            "hits_nucleo": mean("hits_nucleo", maduras),
            "pm1_nucleo": mean("pm1_nucleo", maduras),
            "score_banda": mean("score_banda", maduras),
            "colapso": mean("colapso", maduras),
            "azar_nucleo": mean("azar_nucleo", maduras),
            "hits_holgada": mean("hits_holgada", maduras),
            "azar_holgada": mean("azar_holgada", maduras),
            "hits_copia_prev": mean("hits_copia_prev", maduras),
            "k_medio": mean("k", maduras),
        },
    }
    t = resumen["todas"]
    if t["azar_nucleo"]:
        t["lift_vs_azar"] = t["hits_nucleo"] / t["azar_nucleo"]
        t["lift_vs_copia"] = t["hits_nucleo"] / t["hits_copia_prev"] if t["hits_copia_prev"] else None
    m = resumen["desde_4a"]
    if m["n"] and m["azar_nucleo"]:
        m["lift_vs_azar"] = m["hits_nucleo"] / m["azar_nucleo"]
        m["lift_vs_copia"] = m["hits_nucleo"] / m["hits_copia_prev"] if m["hits_copia_prev"] else None

    return {"resumen": resumen, "filas": filas}


def grid(desde: str, hasta: str | None) -> list[dict]:
    out = []
    for k in range(8, 29, 2):
        r = walk(desde, hasta, k)["resumen"]["desde_4a"]
        r = dict(r)
        r["k"] = k
        out.append(r)
        print(
            f"k={k:2d}  hits={r['hits_nucleo']:.3f}  azar={r['azar_nucleo']:.3f}  "
            f"lift={r.get('lift_vs_azar', 0):.3f}  copia={r['hits_copia_prev']:.3f}  "
            f"k_med={r['k_medio']:.1f}",
            flush=True,
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk histórico de hilo-corto (lab).")
    parser.add_argument("--from", dest="desde", default=PRIMERA_UTIL)
    parser.add_argument("--to", dest="hasta", default=None, help="última hora INCLUSIVA a puntuar como target")
    parser.add_argument("--k", type=int, default=None)
    parser.add_argument("--grid", action="store_true", help="probar k=8..28 y no guardar filas")
    parser.add_argument("--no-filas", action="store_true")
    args = parser.parse_args()

    REPORTS.mkdir(parents=True, exist_ok=True)

    if args.grid:
        tabla = grid(args.desde, args.hasta)
        (REPORTS / "grid_k.json").write_text(
            json.dumps(tabla, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        mejor = max(tabla, key=lambda r: (r.get("lift_vs_azar") or 0, r["hits_nucleo"]))
        print("mejor lift:", json.dumps(mejor, ensure_ascii=False))
        return

    resultado = walk(args.desde, args.hasta, args.k)
    resumen = resultado["resumen"]
    payload = resultado if not args.no_filas else {"resumen": resumen}
    (REPORTS / "walk.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lineas = [
        "HILO-CORTO — walk de laboratorio",
        f"desde {resumen['desde']}  hasta {resumen['hasta']}  n={resumen['n_horas_puntuadas']}",
        f"k pedido={resumen['k_pedido']}",
        "",
        "todas las horas puntuadas:",
        json.dumps(resumen["todas"], ensure_ascii=False, indent=2),
        "",
        "desde la 4ª columna (cilindro armado):",
        json.dumps(resumen["desde_4a"], ensure_ascii=False, indent=2),
        "",
        "No se escribió boleto de producción.",
    ]
    texto = "\n".join(lineas) + "\n"
    (REPORTS / "WALK.txt").write_text(texto, encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main()
