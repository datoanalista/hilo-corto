"""Cierra una hora en el estado y emite el boleto de la próxima."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from datetime import timedelta

from src.estado import Estado, format_tag, parse_tag
from src.lectores import cargar_crudo
from src.motor import emitir_boleto

ESTADO_PATH = ROOT / "estado" / "estado.json"
BOLETO_PATH = ROOT / "estado" / "ultimo_boleto.json"
LECTURA_PATH = ROOT / "estado" / "ultimo_informe.txt"


def main() -> None:
    parser = argparse.ArgumentParser(description="Cierra una hora y emite boleto de la siguiente.")
    parser.add_argument("--tag", required=True, help="tag de la hora que acaba de cerrar, ej. h12-230726")
    parser.add_argument("--k", type=int, default=None, help="tamaño del boleto (default de la máquina)")
    parser.add_argument("--estado", type=Path, default=ESTADO_PATH)
    args = parser.parse_args()

    cinta = cargar_crudo()
    if args.tag not in cinta.horas:
        raise SystemExit(f"tag {args.tag} no está en la data cruda")

    estado = Estado.cargar(args.estado)
    dt = parse_tag(args.tag)
    cilindro = []
    for back in (3, 2, 1, 0):
        t = format_tag(dt - timedelta(hours=back))
        if t in cinta.horas:
            cilindro.append(t)
    if cilindro:
        t0 = cilindro[0]
        estado.horas = [h for h in estado.horas if parse_tag(h.tag) < parse_tag(t0)]
        for t in cilindro:
            estado.cerrar(cinta.get(t))
    else:
        estado.cerrar(cinta.get(args.tag))
    boleto = emitir_boleto(estado, k=args.k)
    estado.ultimo_boleto = boleto
    estado.guardar(args.estado)
    BOLETO_PATH.write_text(json.dumps(boleto, ensure_ascii=False, indent=2), encoding="utf-8")
    lectura = boleto.get("lectura") or ""
    LECTURA_PATH.write_text(lectura + "\n", encoding="utf-8")
    print(lectura)
    print()
    print(json.dumps(boleto, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
