"""Reimprime el ultimo informe (lectura humana, luego JSON)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOLETO_PATH = ROOT / "estado" / "ultimo_boleto.json"
LECTURA_PATH = ROOT / "estado" / "ultimo_informe.txt"
ESTADO_PATH = ROOT / "estado" / "estado.json"


def main() -> None:
    if LECTURA_PATH.exists():
        print(LECTURA_PATH.read_text(encoding="utf-8"))
    if BOLETO_PATH.exists():
        print(BOLETO_PATH.read_text(encoding="utf-8"))
        return
    if ESTADO_PATH.exists():
        raw = json.loads(ESTADO_PATH.read_text(encoding="utf-8"))
        boleto = raw.get("ultimo_boleto")
        if boleto:
            print(boleto.get("lectura") or "")
            print(json.dumps(boleto, ensure_ascii=False, indent=2))
            return
    raise SystemExit("no hay boleto: corre ingest_hora.py primero")


if __name__ == "__main__":
    main()
