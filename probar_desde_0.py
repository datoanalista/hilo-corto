"""Prueba desde 0: borra estado, walk, Excel-informe, ingest de la ultima hora."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.estado import PRIMERA_UTIL
from src.lectores import cargar_crudo
from src.motor import emitir_boleto

ESTADO_DIR = ROOT / "estado"


def _wipe() -> None:
    ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("estado.json", "ultimo_boleto.json", "ultimo_informe.txt"):
        p = ESTADO_DIR / name
        if p.exists():
            p.unlink()


def main() -> None:
    _wipe()
    print("estado vacio. primera util:", PRIMERA_UTIL)

    from walk import walk

    cinta = cargar_crudo()
    ultimo = cinta.orden[-1]
    resultado = walk(PRIMERA_UTIL, None, None)
    resumen = resultado["resumen"]
    (ROOT / "reports").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports" / "walk.json").write_text(
        json.dumps({"resumen": resumen}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(resumen["todas"], ensure_ascii=False, indent=2))

    import export_xls_medicion

    export_xls_medicion.main()

    from ingest_hora import main as ingest_main

    # ingest de la ultima hora cerrada en data
    sys.argv = ["ingest_hora.py", "--tag", ultimo]
    ingest_main()


if __name__ == "__main__":
    main()
