"""Detección automática de fallos en ingesta (origen vs captura incompleta)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.lectores import (
    DATA_UNICA,
    Tiro,
    _leer_bloques,
    _tiros_de,
    hora_cerrada,
    leer_bloques_texto,
)

ROOT = Path(__file__).resolve().parents[1]
LOG_ALERTAS = ROOT / "reports" / "log_alertas_ingesta.txt"

# Umbrales operativos (fallo emisor origen vs juego normal).
# R de 60–150 s = ronda larga normal (Venus L ≥70 s); no se loguea.
G_MAX_ORIGEN_S = 180
EMISION_GAP_MIN_S = 300  # ~5 min sin cierre → caída origen (G o R congelado)


def _tramo_a_linea(bloque: list[str], t: Tiro) -> str:
    pref = f"{t.m0:02d}:{t.s0:02d}-{t.m1:02d}:{t.s1:02d}"
    for ln in bloque:
        s = (ln or "").strip()
        if s.startswith(pref):
            return s
    tok = t.color
    if t.color == "G" and t.tipo is not None:
        tok = f"G{t.tipo}"
    extra = f" {t.lumen}" if t.lumen is not None else ""
    return pref + " " + tok + extra


def marca_tramo(t: Tiro) -> str | None:
    if t.color == "G" and t.dur_s > G_MAX_ORIGEN_S:
        return "origen_caida"
    if t.dur_s >= EMISION_GAP_MIN_S:
        return "origen_anomalo"
    return None


def _confianza(tramos: list[dict], cerrada: bool) -> str:
    if not cerrada:
        return "captura_incompleta"
    marcas = {t["marca"] for t in tramos if t.get("marca")}
    if "origen_caida" in marcas:
        return "baja"
    if "origen_anomalo" in marcas:
        return "media"
    return "alta"


def auditar_hora(
    tag: str,
    bloques: dict[str, list[str]],
    *,
    cerrada: bool | None = None,
) -> dict | None:
    """Audita una hora. None si no hay nada que reportar."""
    tiros = _tiros_de(bloques, tag)
    if not tiros:
        return None
    if cerrada is None:
        cerrada = hora_cerrada(tiros)

    bloque = bloques.get(tag) or []
    tramos: list[dict] = []
    for t in tiros:
        marca = marca_tramo(t)
        if not marca:
            continue
        umbral = (
            f"G>{G_MAX_ORIGEN_S}s"
            if marca == "origen_caida"
            else f"dur>={EMISION_GAP_MIN_S}s"
        )
        tramos.append(
            {
                "linea": _tramo_a_linea(bloque, t),
                "marca": marca,
                "dur_s": t.dur_s,
                "color": t.color,
                "tipo": t.tipo,
                "umbral": umbral,
            }
        )

    if cerrada and not tramos:
        return None

    conf = _confianza(tramos, cerrada)
    if cerrada and conf == "alta":
        return None

    marcas_hora: list[str] = sorted({t["marca"] for t in tramos})
    if not cerrada:
        marcas_hora = ["captura_incompleta"]

    return {
        "tag": tag,
        "n_tiros": len(tiros),
        "cerrada": cerrada,
        "confianza": conf,
        "marcas_hora": marcas_hora,
        "tramos": tramos,
        "nota": (
            "Hora abierta (<40 tiros o sin corte): no entra a cinta."
            if not cerrada
            else (
                "Tramos con duración imposible para emisor origen; "
                "excluir de stats L/largo al cablear motor."
                if tramos
                else ""
            )
        ),
    }


def auditar_texto_pegado(texto: str) -> list[dict]:
    """Todas las horas del pegado con alertas (cerradas o abiertas)."""
    orden, bloques = leer_bloques_texto(texto)
    out: list[dict] = []
    for tag in orden:
        rep = auditar_hora(tag, bloques)
        if rep:
            out.append(rep)
    return out


def auditar_tags_en_cinta(tags: list[str]) -> list[dict]:
    """Re-audita tags ya en data_3dias.txt (sin escribir cinta)."""
    if not tags or not DATA_UNICA.exists():
        return []
    _orden, bloques = _leer_bloques(DATA_UNICA)
    out: list[dict] = []
    for tag in tags:
        rep = auditar_hora(tag, bloques, cerrada=True)
        if rep:
            out.append(rep)
    return out


def escribir_log_alerta(alerta: dict, *, origen: str = "ingesta") -> Path:
    """Append: un bloque por hora identificada."""
    LOG_ALERTAS.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"=== {stamp} · {origen} ===",
        f"tag: {alerta['tag']}",
        f"confianza: {alerta['confianza']}",
        f"n_tiros: {alerta['n_tiros']}",
        f"cerrada: {'si' if alerta['cerrada'] else 'no'}",
        f"marcas: {', '.join(alerta['marcas_hora'])}",
    ]
    if alerta.get("nota"):
        lines.append(f"nota: {alerta['nota']}")
    if alerta.get("tramos"):
        lines.append("tramos:")
        for t in alerta["tramos"]:
            lines.append(
                f"  · {t['linea']} · {t['marca']} · dur={t['dur_s']}s ({t['umbral']})"
            )
    lines.append("")
    with LOG_ALERTAS.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return LOG_ALERTAS


def registrar_alertas(
    alertas: list[dict], *, origen: str = "ingesta"
) -> Path | None:
    if not alertas:
        return None
    for a in alertas:
        escribir_log_alerta(a, origen=origen)
    return LOG_ALERTAS
