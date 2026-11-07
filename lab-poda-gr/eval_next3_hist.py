# -*- coding: utf-8 -*-
"""
ARCHIVO. JUEZ INVÁLIDO. No ejecutar como veredicto.

Cobraba color / cadenas globales (R-R-G en toda la cinta).
Eso es densidad, no corrimiento. Ver JUEZ.txt.

Lectura vigente: eval_corrimiento_hora.py → reports/LAB_NEXT3_CORRIMIENTO.txt
Informe anulado: reports/LAB_NEXT3_HIST.txt
"""
import sys

print(
    "JUEZ INVÁLIDO. No correr este script.\n"
    "Vigente: python eval_corrimiento_hora.py",
    file=sys.stderr,
)
sys.exit(2)
