# Hilo corto

Caja negra: data de horas -> informe de tiros (no un mapa de 40 minutos).

El juez es la **banda d<=1** (G y +-1). +-2 se trata como fuera.
Jaccard no entra.

Cada chip es una isla de H-1 (TIBIO: cubre persist y ambos +-1)
mas costura si el cierre fue largo (SEGURO exacto ~95%).
No se rellena con tiros frios. El lado +1 vs -1 no se nombra:
no hay senal. Las orillas (cruce de dos islas) se informan,
no se disparan. Las zonas son andenes (cupo/teatro) y racimos
de islas; p(G) por anden es plano.

## Como se corre

Tablero sombra en vivo (historico + apuesta de la proxima).
No toca A01 ni el boleto colgado.

```text
python tablero_live.py
```

Desde 0 (Excel de laboratorio):

```text
python probar_desde_0.py
```

Hora a hora suelta:

```text
python ingest_hora.py --tag h12-230726
python walk.py --from h10-230726
python emitir.py
python export_xls_medicion.py
python coherencia_informe.py
```

La data es **un solo archivo** (cinta G/R por hora):

`hilo-corto/data/data_3dias.txt`

Se agrega solo desde el tablero (horas cerradas).

## Archivos

- `src/motor.py` — informe (tiros + zonas + orillas)
- `reports/medicion_hora_G_pm1.xlsx`
- `ACTA_BANDA.txt` — techo, colapso, que se ve
