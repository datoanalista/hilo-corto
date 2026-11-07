"""Tablero sombra de hilo-corto. NO es A01. NO escribe en depuracion/predictores.

Lee la data permitida (sillas + cinta 4G/5G), cierra horas, guarda historico
y deja la apuesta de la proxima. Corre de nuevo cuando hay una hora nueva.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from src.estado import parse_tag
from src.lectores import cargar_crudo
from src.motor import ENCABEZADO
from src.tablero import mins as _mins
from src.tablero import recorrer

REPORTS = ROOT / "reports"
ESTADO_DIR = ROOT / "estado"
HIST_PATH = REPORTS / "historico_live.jsonl"
LOG_MIN = REPORTS / "log_minutos.txt"
APUESTA_TXT = ESTADO_DIR / "apuesta_viva.txt"
BOLETO_PATH = ESTADO_DIR / "ultimo_boleto.json"
LECTURA_PATH = ESTADO_DIR / "ultimo_informe.txt"
ESTADO_PATH = ESTADO_DIR / "estado.json"
XLSX = REPORTS / "tablero_live.xlsx"


def reconstruir() -> dict:
    cinta = cargar_crudo()
    out = recorrer(cinta)
    historico = out["historico"]
    apuesta = out["apuesta"]
    estado = out["estado"]
    ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    estado.guardar(ESTADO_PATH)
    BOLETO_PATH.write_text(
        json.dumps(estado.ultimo_boleto, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lectura = estado.ultimo_boleto.get("lectura") or ""
    LECTURA_PATH.write_text(lectura + "\n", encoding="utf-8")
    APUESTA_TXT.write_text(
        "APUESTA VIVA (sombra hilo-corto, no A01)\n\n" + lectura + "\n\n"
        f"chips: {_mins(apuesta['chips'])}\n"
        f"cierre {apuesta['cierre']}  clima {apuesta['clima']}  k={apuesta['k']}\n",
        encoding="utf-8",
    )
    with HIST_PATH.open("w", encoding="utf-8") as fh:
        for f in historico:
            slim = {k: v for k, v in f.items() if k not in ("tiros", "zonas_anden", "zonas_racimo", "orillas", "meta")}
            fh.write(json.dumps(slim, ensure_ascii=False) + "\n")
    _escribir_log_minutos(historico, apuesta)

    _xlsx(historico, apuesta)
    return {
        "historico": historico,
        "apuesta": apuesta,
        "lectura": lectura,
        "ultima_cerrada": out["ultima_cerrada"],
    }


def _escribir_log_minutos(historico: list[dict], apuesta: dict) -> None:
    lineas = [
        "LOG POR MINUTO PREDICHO (hilo-corto, sombra)",
        "EXACTO = blanco. BORDE = oficial a +-1 del chip. MUERTO = nada en la tripleta.",
        "",
    ]
    for f in historico:
        lineas.append(
            f"=== {f['for']} (sobre {f['sobre']})  "
            f"G {f['g_ok']}/{f['g_of']}  +-1 {f['pm1']}  banda {f['pct']:.0%}  "
            f"cierre {f['cierre']} ==="
        )
        lineas.append(f"oficiales: {_mins(f.get('oficiales') or [])}")
        for c in f.get("chips_log") or []:
            cub = "-".join(f"{x:02d}" for x in c.get("cubre") or [])
            lineas.append(
                f"  chip {c['minuto']:02d}  {c['flag']:6}  cubre {cub:8}  "
                f"{c['veredicto']:6}  {c['detalle']}"
            )
        lineas.append("")
    lineas.append(
        f"=== APUESTA {apuesta['for']} (sobre {apuesta['sobre']}) — sin oficial ==="
    )
    lineas.append(f"chips: {_mins(apuesta['chips'])}")
    lineas.append(apuesta.get("lectura") or "")
    LOG_MIN.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def _xlsx(historico: list[dict], apuesta: dict) -> None:
    wb = Workbook()
    cover = wb.active
    cover.title = "encabezado"
    cover["A1"] = "HILO CORTO — tablero sombra (NO es A01 / LIVE colgado)"
    cover["A1"].font = Font(bold=True, size=14)
    cover["A2"] = (
        "Data unica: hilo-corto/data/data_3dias.txt. "
        "Historico = horas contrastadas. Apuesta = proxima. "
        "Hoja log minutos = cada chip EXACTO/BORDE/MUERTO. Jaccard no entra."
    )
    cover["A4"] = ENCABEZADO
    cover["A4"].alignment = Alignment(wrap_text=True, vertical="top")
    cover.row_dimensions[4].height = 240
    cover.column_dimensions["A"].width = 110

    ws = wb.create_sheet("historico")
    headers = [
        "Fecha",
        "tag",
        "Informe",
        "G oficiales",
        "G acertadas",
        "+-1 acertadas",
        "% banda",
        "minutos oficiales",
        "minutos acertados",
        "+-1 borde",
        "chips",
        "flags",
        "cierre",
        "k",
    ]
    ws.append(headers)
    hf = Font(bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="333333")
    for col in range(1, len(headers) + 1):
        c = ws.cell(1, col)
        c.font = hf
        c.fill = fill
    for f in historico:
        ws.append(
            [
                parse_tag(f["for"]),
                f["for"],
                f["lectura"],
                f.get("g_of"),
                f.get("g_ok"),
                f.get("pm1"),
                f.get("pct"),
                _mins(f.get("oficiales") or []),
                _mins(f.get("acertados") or []),
                ", ".join(f.get("bordes") or []),
                _mins(f.get("chips") or []),
                f.get("flags"),
                f.get("cierre"),
                f.get("k"),
            ]
        )
    for i, row in enumerate(ws.iter_rows(min_row=2, max_row=len(historico) + 1), 2):
        row[0].number_format = "DD/MM/YYYY HH:00"
        row[6].number_format = "0.0%"
        row[2].alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[i].height = 80
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:N{len(historico) + 1}"
    widths = [20, 14, 70, 12, 12, 12, 12, 32, 24, 32, 28, 24, 10, 6]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    wa = wb.create_sheet("apuesta")
    wa["A1"] = f"APUESTA para {apuesta['for']} (sobre {apuesta['sobre']}) — aun sin oficial"
    wa["A1"].font = Font(bold=True, size=14)
    wa["A3"] = apuesta["lectura"]
    wa["A3"].alignment = Alignment(wrap_text=True, vertical="top")
    wa.row_dimensions[3].height = 160
    wa["A5"] = "chips: " + _mins(apuesta["chips"])
    wa.column_dimensions["A"].width = 110

    wl = wb.create_sheet("log minutos")
    wl.append(
        ["tag", "chip", "flag", "cubre", "veredicto", "detalle"]
    )
    for col in range(1, 7):
        c = wl.cell(1, col)
        c.font = hf
        c.fill = fill
    for f in historico:
        for ch in f.get("chips_log") or []:
            cub = "-".join(f"{x:02d}" for x in ch.get("cubre") or [])
            wl.append(
                [
                    f["for"],
                    ch["minuto"],
                    ch.get("flag"),
                    cub,
                    ch.get("veredicto"),
                    ch.get("detalle"),
                ]
            )
    wl.freeze_panes = "A2"
    wl.auto_filter.ref = f"A1:F{wl.max_row}"
    for i, w in enumerate([14, 8, 10, 12, 12, 42], 1):
        wl.column_dimensions[get_column_letter(i)].width = w

    try:
        wb.save(XLSX)
    except PermissionError:
        wb.save(REPORTS / "tablero_live_nuevo.xlsx")


def main() -> None:
    out = reconstruir()
    hist = out["historico"]
    ap = out["apuesta"]
    print("SOMBRA hilo-corto. No se toco A01 ni ultima_prediccion.")
    print(f"ultima hora CERRADA en data: {out['ultima_cerrada']}")
    print(f"historico contrastado: {len(hist)} horas")
    if hist:
        ult8 = hist[-8:]
        print()
        print("=== ultimas 8 ya salidas (apuesta vs oficial) ===")
        for f in ult8:
            print(
                f"{f['for']}  G {f['g_ok']}/{f['g_of']}  +-1 {f['pm1']}  "
                f"banda {f['pct']:.0%}  acertados {_mins(f.get('acertados') or [])}  "
                f"borde {', '.join(f.get('bordes') or []) or '-'}"
            )
        print()
        print("=== ultima hora contrastada, chip a chip ===")
        last = hist[-1]
        for c in last.get("chips_log") or []:
            cub = "-".join(f"{x:02d}" for x in c.get("cubre") or [])
            print(
                f"  {c['minuto']:02d} {c['flag']:6} cubre {cub:8}  "
                f"{c['veredicto']:6}  {c['detalle']}"
            )
        print()
        print("=== APUESTA VIVA (todavia no salio el oficial) ===")
        lectura = out.get("lectura") or ""
        try:
            print(lectura)
        except UnicodeEncodeError:
            sys.stdout.buffer.write((lectura + "\n").encode("utf-8", errors="replace"))
        print("chips:", _mins(ap["chips"]))
    print()
    print("tablero:", XLSX)
    print("log minutos:", LOG_MIN)
    print("apuesta:", APUESTA_TXT)


if __name__ == "__main__":
    main()
