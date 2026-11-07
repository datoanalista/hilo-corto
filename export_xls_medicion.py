"""Desde 0: estado vacio, walk e informe hora a hora en Excel."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from src.estado import Estado, PRIMERA_UTIL, parse_tag
from src.lectores import cargar_crudo
from src.motor import ENCABEZADO, emitir_boleto

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
ESTADO_DIR = ROOT / "estado"


def dist(a: int, b: int) -> int:
    d = abs(a - b) % 60
    return min(d, 60 - d)


def min_d(m: int, s: set[int]) -> int:
    return min(dist(m, x) for x in s) if s else 99


def mins(xs: list[int]) -> str:
    return ", ".join(f"{m:02d}" for m in xs)


def clasificar(oficiales: list[int], chips: list[int]) -> tuple[list[int], list[str]]:
    """Minutos exactos y +-1 que tocan el borde de un chip."""
    acertados = []
    bordes = []
    if not chips:
        return acertados, bordes
    for m in oficiales:
        chip = min(chips, key=lambda c: dist(m, c))
        d = dist(m, chip)
        if d == 0:
            acertados.append(m)
        elif d == 1:
            lado = "+1" if (chip + 1) % 60 == m else "-1"
            bordes.append(f"{m:02d} ({lado} de {chip:02d})")
    return acertados, bordes


def main() -> None:
    cinta = cargar_crudo()
    i0 = cinta.orden.index(PRIMERA_UTIL)
    estado = Estado()
    filas = []

    for i in range(i0, len(cinta.orden) - 1):
        tag = cinta.orden[i]
        nxt = cinta.orden[i + 1]
        estado.cerrar(cinta.get(tag))
        doc = emitir_boleto(estado)
        boleto = doc["boleto"]
        nuc = set(cinta.get(nxt).nucleo)
        g = pm1 = 0
        acertados = []
        bordes = []
        for m in sorted(nuc):
            d = min_d(m, set(boleto)) if boleto else 99
            if d == 0:
                g += 1
            elif d == 1:
                pm1 += 1
        acertados, bordes = clasificar(sorted(nuc), boleto)
        meta = doc.get("meta") or {}
        filas.append(
            {
                "fecha": parse_tag(nxt),
                "tag": nxt,
                "sobre": tag,
                "lectura": doc.get("lectura") or "",
                "g_of": len(nuc),
                "g_ok": g,
                "pm1": pm1,
                "oficiales": sorted(nuc),
                "acertados": acertados,
                "bordes": bordes,
                "chips": sorted(boleto),
                "flags": ", ".join(
                    f"{t['minuto']:02d}:{t['flag']}" for t in doc.get("tiros") or []
                ),
                "zonas": "; ".join(z["nota"] for z in doc.get("zonas_racimo") or []),
                "clima": meta.get("clima"),
                "k": len(boleto),
                "cierre": "largo" if meta.get("prev_largo") else "corto",
                "columnas": meta.get("columnas") or 0,
            }
        )

    wb = Workbook()
    cover = wb.active
    cover.title = "encabezado"
    cover["A1"] = "HILO CORTO — entregable predictivo"
    cover["A1"].font = Font(bold=True, size=16)
    cover["A2"] = "El informe hora a hora es la evidencia. No es un dado. Los nombres no se reimprimen."
    cover["A3"] = ENCABEZADO
    cover["A3"].alignment = Alignment(wrap_text=True, vertical="top")
    cover.row_dimensions[3].height = 240
    cover.column_dimensions["A"].width = 110
    cover.merge_cells("A3:F12")

    ws = wb.create_sheet("informe hora a hora")

    headers = [
        "Fecha",
        "tag",
        "Informe",
        "G oficiales",
        "G acertadas",
        "+-1 acertadas",
        "% banda vs G",
        "minutos G oficiales",
        "minutos acertados",
        "+-1 borde",
        "chips",
        "flags",
        "zonas",
        "clima",
        "cierre",
        "k",
    ]
    ws.append(headers)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="333333")
    thin = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC"),
    )
    ncols = len(headers)
    for col in range(1, ncols + 1):
        cell = ws.cell(1, col)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", wrap_text=True)

    for r in filas:
        pct = (r["g_ok"] + r["pm1"]) / r["g_of"] if r["g_of"] else None
        ws.append(
            [
                r["fecha"],
                r["tag"],
                r["lectura"],
                r["g_of"],
                r["g_ok"],
                r["pm1"],
                pct,
                mins(r["oficiales"]),
                mins(r["acertados"]),
                ", ".join(r["bordes"]),
                mins(r["chips"]),
                r["flags"],
                r["zonas"],
                r["clima"],
                r["cierre"],
                r["k"],
            ]
        )

    n = len(filas)
    last = n + 1
    tot_of = sum(r["g_of"] for r in filas)
    tot_g = sum(r["g_ok"] for r in filas)
    tot_pm1 = sum(r["pm1"] for r in filas)
    ws.append(
        [
            "TOTAL",
            f"{n} horas",
            "",
            tot_of,
            tot_g,
            tot_pm1,
            (tot_g + tot_pm1) / tot_of if tot_of else None,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]
    )
    total_row = last + 1
    for col in range(1, ncols + 1):
        c = ws.cell(total_row, col)
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="EEEEEE")

    for row in ws.iter_rows(min_row=2, max_row=total_row, min_col=1, max_col=ncols):
        for cell in row:
            cell.border = thin
            if cell.column == 1 and cell.row <= last:
                cell.number_format = "DD/MM/YYYY HH:00"
            elif cell.column in (4, 5, 6, 16):
                cell.number_format = "0"
                cell.alignment = Alignment(horizontal="center")
            elif cell.column == 7:
                cell.number_format = "0.0%"
                cell.alignment = Alignment(horizontal="center")
            elif cell.column == 3:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            elif cell.column in (8, 9, 10, 11, 12, 13):
                cell.alignment = Alignment(wrap_text=True, vertical="top", horizontal="left")

    for i in range(2, last + 1):
        ws.row_dimensions[i].height = 95

    ws.auto_filter.ref = f"A1:P{last}"
    ws.freeze_panes = "A2"
    widths = [20, 14, 72, 12, 12, 14, 14, 36, 28, 36, 28, 28, 36, 10, 10, 6]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.cell(
        total_row + 2,
        1,
        "Desde 0: estado vacio, primera hora util h10-230726. "
        "El encabezado (hoja 1) dice por que no es azar, con pruebas. "
        "Este hoja es el producto: cada fila evidencia SEGURO (cinta) y TIBIO (anillo). "
        "minutos acertados = G en el blanco. +-1 borde = G a un minuto del chip. "
        "% banda = (G + +-1) / G oficiales. +-2 = fuera. Jaccard no entra.",
    )
    ws.merge_cells(
        start_row=total_row + 2, start_column=1, end_row=total_row + 2, end_column=ncols
    )
    ws.row_dimensions[total_row + 2].height = 36

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / "informe_hora_a_hora.xlsx"
    try:
        wb.save(out)
    except PermissionError:
        out = REPORTS / "informe_hora_a_hora_nuevo.xlsx"
        wb.save(out)

    # copia de nombre viejo para quien ya tenia el archivo abierto
    alias = REPORTS / "medicion_hora_G_pm1.xlsx"
    try:
        wb.save(alias)
    except PermissionError:
        alias = REPORTS / "medicion_hora_G_pm1_nuevo.xlsx"
        wb.save(alias)

    print(out)
    print(alias)
    print(
        f"desde_0 filas={n}  G_of={tot_of}  G_ok={tot_g}  pm1={tot_pm1}  "
        f"pct={(tot_g + tot_pm1) / tot_of:.4f}"
    )
    return estado, filas[-1] if filas else None


if __name__ == "__main__":
    main()
