"""API del tablero dual. No escribe LIVE. No toca A01.

  python servir.py
  cd dashboard && npm run dev
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import JSONResponse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.boleto_inter2 import LIVE_MODO
from src.lectores import (
    DATA_UNICA,
    _leer_bloques,
    _parse_tag_key,
    cargar_ingesta,
    guardar_pegado,
    leer_bloques_texto,
)
from src.mesas_beta import catalogo_mesas, panel_inter2, paneles_beta
from src.mesas_beta import _chips_a_tiros
from src.tablero import recorrer, resumen_historico

_log = logging.getLogger("hilo-corto.servir")


def _regenerar_logs_tablero() -> None:
    """Sincroniza reports/ y estado/ tras cerrar horas en la cinta."""
    try:
        from tablero_live import reconstruir

        reconstruir()
        _log.info("tablero_live: historico regenerado")
    except Exception as exc:
        _log.warning("tablero_live reconstruir fallo: %s", exc)

# Oficio Piso (mente-en-blanco) — urna + potenciador, sordo a ciudad
_PISO = Path(r"c:\operacion-joker\experimento-mente-en-blanco\lab-piso")
if str(_PISO) not in sys.path:
    sys.path.insert(0, str(_PISO))
try:
    from piso_core import leer_hora as _leer_piso  # noqa: E402
except Exception:  # pragma: no cover
    _leer_piso = None

DIST = ROOT / "dashboard" / "dist"
EXTRACCION_DIR = ROOT / "dashboard" / "extraccion"
EXTRACCION_JS = EXTRACCION_DIR / "extraccion-jokers.js"
EXTRACCION_LINEAS = EXTRACCION_DIR / "extraccion-en-vivo.txt"
EXTRACCION_ESTADO = EXTRACCION_DIR / "extraccion-estado.json"
EXTRACCION_LIMPIAR = EXTRACCION_DIR / "extraccion-limpiar.flag"
EXTRACCION_INYECTAR = EXTRACCION_DIR / "extraccion-inyectar.json"
EXTRACCION_PAUSA = EXTRACCION_DIR / "extraccion-pausa.flag"
EXTRACCION_PID = EXTRACCION_DIR / "extraccion.pid"
JOKERBETS_CONFIG = ROOT / "jokerbets" / "config.json"
JOKERBETS_CUENTAS_ESTADO = EXTRACCION_DIR / "jokerbets-cuentas-estado.json"
JOKERBETS_SENAL = EXTRACCION_DIR / "jokerbets-senal.json"
JOKERBETS_SIMUL_POOL7 = EXTRACCION_DIR / "jokerbets-simul-pool7.json"
JOKERBETS_BOT_ARMADO = EXTRACCION_DIR / "jokerbets-bot-armado.json"
JOKERBETS_APUESTAS_LOG = EXTRACCION_DIR / "jokerbets-apuestas.jsonl"
JOKERBETS_UI_PULSE = EXTRACCION_DIR / "jokerbets-ui-pulse.json"
JOKERBETS_PERF_LOG = EXTRACCION_DIR / "jokerbets-performance.jsonl"
JOKERBETS_MANUAL = EXTRACCION_DIR / "jokerbets-manual.json"
# Cronista tips vivo (lab livegreen) — ledger append-only desde UI
CRONISTA_LIVE = (
    Path(r"c:\operacion-joker\experimento-livegreen") / "reports" / "tips_vivo_live.jsonl"
)

_RE_EN_JUEGO = re.compile(r"en juego", re.I)
_RE_INTERRUMPIDO = re.compile(r"interrumpido", re.I)
_RE_HEADER_HORA = re.compile(r"^h(\d{1,2})-(\d{6})$", re.I)
_RE_TRAMO_CERRADO = re.compile(
    r"^(\d{1,2}):(\d{1,2})-(\d{1,2}):(\d{1,2})\s+(R|G\d?)(?:\s+(\d+))?\s*$",
    re.I,
)
_RE_G_CORTO = re.compile(r"^G([1-4])\s+(\d+)\s*$", re.I)
_RE_G_RELOJ = re.compile(
    r"^(\d{1,2}):(\d{2}):(\d{2})\s+G([1-4])\s+(\d+)\s*$",
    re.I,
)
_RE_G_LARGO = re.compile(
    r"^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})\s+G([1-4])\s+(\d+)\s*$",
    re.I,
)


def _sanitizar_lineas_extraccion(lineas: list[str]) -> list[str]:
    """Quita basura del F5 viejo. Deja a lo sumo el último 'en juego...' limpio."""
    last_vivo = -1
    for i, l in enumerate(lineas):
        s = (l or "").strip()
        if _RE_EN_JUEGO.search(s) and not _RE_INTERRUMPIDO.search(s):
            last_vivo = i
    out: list[str] = []
    for i, l in enumerate(lineas):
        s = (l or "").strip()
        if _RE_INTERRUMPIDO.search(s):
            continue
        if _RE_EN_JUEGO.search(s) and i != last_vivo:
            continue
        out.append(l)
    return out


def _norm_header(tag: str) -> str | None:
    m = _RE_HEADER_HORA.match((tag or "").strip())
    if not m:
        return None
    return f"h{int(m.group(1))}-{m.group(2).lower()}"


def _norm_tramo(line: str) -> str | None:
    m = _RE_TRAMO_CERRADO.match((line or "").strip())
    if not m:
        return None
    m0, s0, m1, s1 = (int(m.group(i)) for i in range(1, 5))
    if m0 > 59 or m1 > 59 or s0 > 59 or s1 > 59:
        return None
    tok = (m.group(5) or "R").upper()
    base = f"{m0:02d}:{s0:02d}-{m1:02d}:{s1:02d} {tok}"
    if m.group(6) is not None:
        return f"{base} {m.group(6)}"
    return base


def _inicio_key(line: str) -> str | None:
    m = re.match(r"^(\d{1,2}):(\d{1,2})", (line or "").strip())
    if not m:
        return None
    return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"


def _parse_cargar_live_texto(texto: str) -> tuple[str, list[str]] | tuple[None, str]:
    """Devuelve (tag, tramos) o (None, error)."""
    lineas = [ln.strip() for ln in (texto or "").splitlines() if ln.strip()]
    if not lineas:
        return None, "Pegá tag + tramos de la hora."
    tag = _norm_header(lineas[0])
    if not tag:
        return None, f"La primera línea tiene que ser el tag (hN-DDMMYY): {lineas[0]}"
    tramos: list[str] = []
    for ln in lineas[1:]:
        if _RE_HEADER_HORA.match(ln):
            return None, "Cargar live es una sola hora: no pegues otro tag."
        if _RE_EN_JUEGO.search(ln):
            continue
        t = _norm_tramo(ln)
        if not t:
            return None, f"No es un tiro de cinta: {ln}"
        tramos.append(t)
    if not tramos:
        return None, "No hay tramos cerrados para cargar."
    # Último gana si el pegado repite el mismo inicio.
    by_ini: dict[str, str] = {}
    for t in tramos:
        k = _inicio_key(t)
        if k:
            by_ini[k] = t
    ordenados = sorted(by_ini.values(), key=lambda s: _inicio_key(s) or s)
    return tag, ordenados


def _merge_hora_en_lineas(
    lineas: list[str], tag: str, tramos_nuevos: list[str]
) -> list[str]:
    """Reemplaza tramos cerrados de `tag` por el pegado; conserva 'en juego'."""
    tag_l = tag.lower()
    idx = next(
        (
            i
            for i, l in enumerate(lineas)
            if _RE_HEADER_HORA.match((l or "").strip())
            and (l or "").strip().lower() == tag_l
        ),
        -1,
    )
    vivos: list[str] = []
    fin = len(lineas)
    if idx >= 0:
        fin = idx + 1
        while fin < len(lineas):
            s = (lineas[fin] or "").strip()
            if not s:
                fin += 1
                continue
            if _RE_HEADER_HORA.match(s):
                break
            if _RE_EN_JUEGO.search(s) and not _RE_INTERRUMPIDO.search(s):
                vivos.append(s)
            fin += 1
    # Último gana si el pegado repite inicio.
    by_ini: dict[str, str] = {}
    for t in tramos_nuevos:
        k = _inicio_key(t)
        if k:
            by_ini[k] = t
    cuerpo = sorted(by_ini.values(), key=lambda s: _inicio_key(s) or s)
    bloque = [tag, *cuerpo, *vivos]
    if idx < 0:
        out = list(lineas)
        while out and not (out[-1] or "").strip():
            out.pop()
        if out:
            out.append("")
        out.extend(bloque)
        return _sanejar_duplicados_inicio(out)
    cola = lineas[fin:]
    while cola and not (cola[0] or "").strip():
        cola = cola[1:]
    cabeza = lineas[:idx]
    while cabeza and not (cabeza[-1] or "").strip():
        cabeza.pop()
    out = list(cabeza)
    if out:
        out.append("")
    out.extend(bloque)
    if cola:
        out.append("")
        out.extend(cola)
    return _sanejar_duplicados_inicio(out)


def _escribir_lineas_atomico(path: Path, lineas: list[str]) -> None:
    """Write + rename para no servir lecturas a medias al poll del front."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(lineas) + ("\n" if lineas else "")
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    try:
        tmp.replace(path)
    except Exception:
        path.write_text(body, encoding="utf-8")
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def _inyectar_hora_en_captura(tag: str, tramos: list[str]) -> list[str]:
    """Escribe una hora en extraccion-en-vivo.txt y avisa al proceso Node."""
    prev: list[str] = []
    if EXTRACCION_LINEAS.exists():
        prev = EXTRACCION_LINEAS.read_text(encoding="utf-8").splitlines()
    merged = _tail_lineas_horas(
        _merge_hora_en_lineas(prev, tag, tramos),
        MAX_EXTRACCION_HORAS,
    )
    _escribir_lineas_atomico(EXTRACCION_LINEAS, merged)
    if _extraccion_corriendo():
        EXTRACCION_INYECTAR.write_text(
            json.dumps({"tag": tag, "tramos": tramos}, ensure_ascii=False),
            encoding="utf-8",
        )
    return merged


def _sanejar_duplicados_inicio(lineas: list[str]) -> list[str]:
    """Por hora: un solo tramo cerrado por MM:SS de inicio. Gana el primero (live)."""
    out: list[str] = []
    i = 0
    while i < len(lineas):
        s = (lineas[i] or "").strip()
        if not _RE_HEADER_HORA.match(s):
            out.append(lineas[i])
            i += 1
            continue
        out.append(lineas[i])
        i += 1
        seen: set[str] = set()
        while i < len(lineas):
            t = (lineas[i] or "").strip()
            if not t:
                out.append(lineas[i])
                i += 1
                continue
            if _RE_HEADER_HORA.match(t):
                break
            if _RE_EN_JUEGO.search(t):
                out.append(lineas[i])
                i += 1
                continue
            nt = _norm_tramo(t)
            if nt:
                k = _inicio_key(nt)
                if k and k in seen:
                    i += 1
                    continue
                if k:
                    seen.add(k)
            out.append(lineas[i])
            i += 1
    return out


def _fingerprint_lineas(lineas: list[str]) -> str:
    n = len(lineas)
    if not n:
        return "0"
    h = n
    step = max(1, n // 24)
    for i in range(0, n, step):
        s = lineas[i] or ""
        h = (31 * h + len(s) + (ord(s[0]) if s else 0)) & 0xFFFFFFFF
    return f"{n}:{h}:{lineas[-1]}:{lineas[0]}"


def _tail_lineas_horas(lineas: list[str], max_horas: int = 120) -> list[str]:
    """Conserva las últimas N horas en captura (evita crecimiento sin límite)."""
    if max_horas <= 0:
        return lineas
    headers = [
        i
        for i, l in enumerate(lineas)
        if _RE_HEADER_HORA.match((l or "").strip())
    ]
    if len(headers) <= max_horas:
        return lineas
    return lineas[headers[-max_horas] :]


HIST_PREVIEW = 4  # horas en GET /api/tablero; el resto bajo demanda
MAX_EXTRACCION_HORAS = 120  # ~5 d captura en extraccion-en-vivo.txt
USUARIO = "admin"
CLAVE = "toto1540"
COOKIE = "hilo_sesion"
_SECRETO = hmac.new(b"hilo-corto", CLAVE.encode(), hashlib.sha256).digest()


def _ficha() -> str:
    return hmac.new(_SECRETO, USUARIO.encode(), hashlib.sha256).hexdigest()


def _analisis_puede_leer(request: Request) -> bool:
    """Dashboard (cookie) o pasadizo: header X-Joker-Analisis-Key = env JOKERBETS_ANALISIS_KEY."""
    if _sesion_ok(request):
        return True
    esperada = os.environ.get("JOKERBETS_ANALISIS_KEY", "").strip()
    if not esperada:
        return False
    recibida = (request.headers.get("x-joker-analisis-key") or "").strip()
    if not recibida:
        return False
    return hmac.compare_digest(recibida, esperada)


def _sesion_ok(request: Request) -> bool:
    raw = request.cookies.get(COOKIE) or ""
    if not raw:
        return False
    return hmac.compare_digest(raw, _ficha())


app = FastAPI(title="hilo-corto", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "http://127.0.0.1:8765",
        "http://localhost:8765",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Pegado(BaseModel):
    texto: str = ""
    guardar: bool = False
    solo_guardar: bool = False


class Acceso(BaseModel):
    usuario: str = ""
    clave: str = ""


class CargarLiveBody(BaseModel):
    texto: str = ""


class SyncCintaBody(BaseModel):
    tag: str = ""


class TipCronista(BaseModel):
    tag: str = ""
    paso: int = 0
    tip: int | None = None
    luz: int
    why: str = ""
    algo: str = "LG-43"


class JokerbetsConfigBody(BaseModel):
    config: dict | None = None


class JokerbetsSenalBody(BaseModel):
    tag: str = ""
    interruptor: str = "OFF"
    puertaA: bool = False
    enZona: bool = False
    enZonaApuesta: bool = False
    enCurso: str = ""
    confirmadoHasta: int = -1
    nTiros: int = 0
    brilloFp: str = ""
    relojMinuto: int | None = None
    relojSegundo: int | None = None
    tip: int | None = None
    tipEstado: str | None = None
    permitirClics: bool = False
    gapTiro: int | None = None
    ventanaCaliente: bool = False
    simulPool7: bool = False
    # Pool 7 auto: Brillo en fuerte / muy fuerte / supernova.
    pool7BrilloOk: bool = False
    # Hora fuerte Brillo (tip±1 + sequía); independiente de Pool 7 SIM.
    puertaGoBrillo: bool = False
    formaG: str = ""
    formaGLabel: str = ""
    formaGApuesta: bool = False
    puertaAFase: str | None = None
    viaApuesta: str | None = None


class JokerbetsBotArmadoBody(BaseModel):
    armado: bool = False


class JokerbetsSimulPool7Body(BaseModel):
    activo: bool = False


class JokerbetsManualBody(BaseModel):
    disparar: bool = False
    montoPorBono: int = 50
    cancelar: bool = False


class JokerbetsPushColorRow(BaseModel):
    color: str = ""
    premio: str | None = None
    montoApuesta: str | None = None
    multiplicador: int | None = None
    saldo: str | None = None
    ganancia: bool = False


class JokerbetsPushEventBody(BaseModel):
    tipo: str = ""
    cuentaId: str = ""
    color: str = ""
    ts: str = ""
    montoApuesta: str | None = None
    premio: str | None = None
    saldo: str | None = None
    multiplicador: int | None = None
    horaTag: str | None = None
    notas: str | None = None
    fuente: str | None = None
    colores: list[JokerbetsPushColorRow] | None = None


def _jokerbets_ntfy_default() -> dict:
    return {
        "enabled": False,
        "server": "https://ntfy.sh",
        "topic": "",
        "priority": "high",
        "tipos": ["ronda_acertada"],
    }


def _normalizar_jokerbets_ntfy(raw: dict | None) -> dict:
    base = _jokerbets_ntfy_default()
    if not isinstance(raw, dict):
        return dict(base)
    tipos_in = raw.get("tipos")
    tipos: list[str] = []
    if isinstance(tipos_in, list):
        for t in tipos_in:
            s = str(t or "").strip().lower()
            if s:
                tipos.append(s)
    if not tipos:
        tipos = list(base["tipos"])
    return {
        "enabled": bool(raw.get("enabled")),
        "server": str(raw.get("server") or base["server"]).rstrip("/"),
        "topic": str(raw.get("topic") or "").strip(),
        "priority": str(raw.get("priority") or base["priority"]).strip().lower()
        or base["priority"],
        "tipos": tipos,
    }


def _jokerbets_config_default() -> dict:
    return {
        "version": 1,
        "activeNotebookId": "nb-local",
        "arranqueUsd": 20000,
        "apuestaModo": "50",
        "notebooks": [
            {
                "id": "nb-local",
                "nombre": "Servidor 1 (local)",
                "cuentas": [
                    {
                        "id": "c-rojo",
                        "color": "rojo",
                        "url": "",
                        "wsPrimaria": False,
                    },
                    {
                        "id": "c-azul",
                        "color": "azul",
                        "url": "",
                        "wsPrimaria": True,
                    },
                    {
                        "id": "c-verde",
                        "color": "verde",
                        "url": "",
                        "wsPrimaria": False,
                    },
                ],
            }
        ],
        "ntfy": _jokerbets_ntfy_default(),
    }


def _leer_jokerbets_config() -> dict:
    if not JOKERBETS_CONFIG.exists():
        return _jokerbets_config_default()
    try:
        data = json.loads(JOKERBETS_CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _jokerbets_config_default()
    if not isinstance(data, dict) or not data.get("notebooks"):
        return _jokerbets_config_default()
    return data


def _normalizar_jokerbets_config(raw: dict) -> dict:
    base = _jokerbets_config_default()
    if not isinstance(raw, dict):
        return base
    out = {**base, **raw}
    nbs = raw.get("notebooks")
    if not isinstance(nbs, list) or not nbs:
        return base
    clean_nbs: list[dict] = []
    for i, nb in enumerate(nbs):
        if not isinstance(nb, dict):
            continue
        nb_id = str(nb.get("id") or f"nb-{i + 1}").strip() or f"nb-{i + 1}"
        cuentas_in = nb.get("cuentas")
        if not isinstance(cuentas_in, list):
            cuentas_in = []
        cols = ["rojo", "azul", "verde"]
        clean_c: list[dict] = []
        for j, c in enumerate(cuentas_in[:3]):
            if not isinstance(c, dict):
                continue
            color = str(c.get("color") or cols[j]).lower()
            if color not in cols:
                color = cols[j]
            bono = str(c.get("bonoColor") or color).lower()
            if bono not in cols:
                bono = color
            clean_c.append(
                {
                    "id": str(c.get("id") or f"{nb_id}-{color}"),
                    "color": color,
                    "bonoColor": bono,
                    "url": str(c.get("url") or "").strip(),
                    "wsPrimaria": bool(c.get("wsPrimaria")),
                }
            )
        while len(clean_c) < 3:
            j = len(clean_c)
            color = cols[j]
            clean_c.append(
                {
                    "id": f"{nb_id}-{color}",
                    "color": color,
                    "url": "",
                    "wsPrimaria": j == 1,
                }
            )
        prim = [k for k, c in enumerate(clean_c) if c.get("wsPrimaria")]
        if len(prim) != 1:
            for k, c in enumerate(clean_c):
                c["wsPrimaria"] = k == 1
        clean_nbs.append(
            {
                "id": nb_id,
                "nombre": str(nb.get("nombre") or nb_id).strip() or nb_id,
                "cuentas": clean_c,
            }
        )
    if not clean_nbs:
        return base
    active = str(out.get("activeNotebookId") or clean_nbs[0]["id"])
    if not any(n["id"] == active for n in clean_nbs):
        active = clean_nbs[0]["id"]
    try:
        arranque = int(out.get("arranqueUsd") or 20000)
    except (TypeError, ValueError):
        arranque = 20000
    ntfy = _normalizar_jokerbets_ntfy(raw.get("ntfy"))
    modo = str(out.get("apuestaModo") or raw.get("apuestaModo") or "50").strip()
    if modo not in ("50", "150", "200"):
        modo = "50"
    return {
        "version": 1,
        "activeNotebookId": active,
        "arranqueUsd": max(0, arranque),
        "apuestaModo": modo,
        "notebooks": clean_nbs,
        "ntfy": ntfy,
    }


def _guardar_jokerbets_config(cfg: dict) -> dict:
    prev_ntfy: dict | None = None
    if JOKERBETS_CONFIG.exists() and isinstance(cfg, dict) and "ntfy" not in cfg:
        try:
            prev_ntfy = json.loads(JOKERBETS_CONFIG.read_text(encoding="utf-8")).get(
                "ntfy"
            )
        except (OSError, json.JSONDecodeError):
            prev_ntfy = None
    norm = _normalizar_jokerbets_config(cfg)
    if isinstance(cfg, dict) and "ntfy" not in cfg and prev_ntfy is not None:
        norm["ntfy"] = _normalizar_jokerbets_ntfy(prev_ntfy)
    JOKERBETS_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    JOKERBETS_CONFIG.write_text(
        json.dumps(norm, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return norm


def _slim_fila(f: dict) -> dict:
    keys = [
        "sobre",
        "for",
        "chips",
        "flags",
        "cierre",
        "clima",
        "k",
        "g_of",
        "g_ok",
        "pm1",
        "oficiales",
        "acertados",
        "bordes",
        "pct",
        "oficial",
        "h1",
        "skip",
        "puentes",
    ]
    out = {k: f.get(k) for k in keys if k in f}
    out["chips_log"] = f.get("chips_log") or []
    out["lectura"] = f.get("lectura") or ""
    return out


def _con_preview_historico(panel: dict, n: int = HIST_PREVIEW) -> dict:
    hist = panel.get("historico") or []
    total = panel.get("historico_total")
    if total is None:
        total = len(hist)
    slim = hist[-n:] if n and len(hist) > n else hist
    return {**panel, "historico": slim, "historico_total": total}


def _panel_joker(recorrido: dict) -> dict:
    hist = recorrido["historico"]
    apuesta = recorrido["apuesta"]
    boleto = recorrido["boleto"]
    ultima = hist[-1] if hist else None
    tag_for = apuesta.get("for")
    tag_sobre = apuesta.get("sobre")
    piso = None
    if _leer_piso:
        for tag_try in (tag_for, tag_sobre):
            if not tag_try:
                continue
            try:
                cand = _leer_piso(tag_try)
            except Exception:
                cand = None
            if cand and cand.get("ok"):
                piso = cand
                if tag_try != tag_for:
                    piso = {**cand, "contexto": "H-1", "nota": "Piso de la hora previa (esta aún no está en lightgreen)"}
                break
        if piso is None and tag_for:
            piso = {"ok": False, "tag": tag_for, "error": "sin piso en lightgreen", "filas": []}
    return {
        "id": "oficial",
        "nombre": "OFICIAL",
        "version": None,
        "ej": None,
        "beta": False,
        "motor": "INTER2 live · acuerdo ≥2 P0–P5 (boleto prod)",
        "live_modo": recorrido.get("live_modo") or LIVE_MODO,
        "prediccion": {
            "for": apuesta.get("for"),
            "sobre": apuesta.get("sobre"),
            "chips": apuesta.get("chips") or [],
            "tiros": apuesta.get("tiros") or boleto.get("tiros") or [],
            "cierre": apuesta.get("cierre"),
            "clima": apuesta.get("clima"),
            "k": apuesta.get("k"),
            "nG_clima": (apuesta.get("meta") or {}).get("nG_clima")
            or (boleto.get("meta") or {}).get("nG_clima"),
            "som02": (apuesta.get("meta") or {}).get("som02")
            or (boleto.get("meta") or {}).get("som02")
            or {},
            "lectura": apuesta.get("lectura") or "",
            "h1": list(recorrido["estado"].ultima().nucleo)
            if recorrido["estado"].ultima()
            else [],
            "skip": apuesta.get("skip") or [],
            "puentes": apuesta.get("puentes") or [],
        },
        "piso": piso,
        "observacion": _slim_fila(ultima) if ultima else None,
        "historico": [_slim_fila(f) for f in hist],
        "historico_total": len(hist),
        "resumen": resumen_historico(hist),
    }


def _panel_classic(recorrido: dict) -> dict:
    """P0 clásico (islas+costura) — sombra desde chips_classic del walk INTER2."""
    hist_live = recorrido["historico"]
    apuesta = recorrido["apuesta"]
    boleto = recorrido["boleto"]
    meta_b = boleto.get("meta") or {}

    def _fila_classic(f: dict) -> dict:
        chips = list(f.get("chips_classic") or [])
        tiros = _chips_a_tiros(chips)
        out = dict(f)
        out["chips"] = chips
        out["tiros"] = tiros
        out["k"] = len(chips)
        out["flags"] = ", ".join("%02d:TIBIO" % m for m in chips)
        if f.get("oficial") and chips:
            from src.tablero import score, clasificar, veredicto_chip

            oficiales = f.get("oficiales") or []
            g, pm1 = score(chips, oficiales)
            ac, bd = clasificar(oficiales, chips)
            out["g_ok"] = g
            out["pm1"] = pm1
            out["acertados"] = ac
            out["bordes"] = bd
            out["pct"] = (g + pm1) / len(oficiales) if oficiales else None
            out["chips_log"] = [veredicto_chip(t, oficiales) for t in tiros]
        return _slim_fila(out)

    hist = [_fila_classic(f) for f in hist_live]
    ultima = hist[-1] if hist else None
    chips_ap = list(meta_b.get("chips_classic") or apuesta.get("chips_classic") or [])
    return {
        "id": "pool-9",
        "nombre": "POOL 9",
        "version": None,
        "ej": None,
        "beta": False,
        "classic": True,
        "pool9": True,
        "motor": "hilo-corto clásico · islas H-1 + costura (sombra)",
        "prediccion": {
            "for": apuesta.get("for"),
            "sobre": apuesta.get("sobre"),
            "chips": chips_ap,
            "tiros": _chips_a_tiros(chips_ap),
            "cierre": apuesta.get("cierre"),
            "clima": apuesta.get("clima"),
            "k": len(chips_ap),
            "lectura": boleto.get("lectura_classic") or "",
            "h1": apuesta.get("h1") or [],
            "skip": apuesta.get("skip") or [],
            "puentes": apuesta.get("puentes") or [],
        },
        "piso": None,
        "observacion": ultima,
        "historico": hist,
        "historico_total": len(hist),
        "resumen": resumen_historico(hist),
    }


def _mesas_completas(cinta) -> tuple[dict, dict]:
    joker = recorrer(cinta)
    oficial = _panel_joker(joker)
    classic = _panel_classic(joker)
    betas = paneles_beta(cinta)
    inter2 = panel_inter2(classic, betas)
    mesas = {
        "oficial": oficial,
        "pool-9": classic,
        **betas,
        "inter2": inter2,
        "joker": oficial,
    }
    return mesas, joker


def armar(texto: str = "", guardar: bool = False) -> dict:
    guardadas: list[str] = []
    alertas_ingesta: list[dict] = []
    if guardar and (texto or "").strip():
        guardadas, alertas_ingesta = guardar_pegado(texto)
    extra = texto or ""
    cinta, abiertas, pegadas = cargar_ingesta(extra)
    if pegadas:
        peg = set(pegadas)
        abiertas = [a for a in abiertas if a["tag"] in peg]
    mesas_full, joker = _mesas_completas(cinta)
    mesas = {
        k: _con_preview_historico(v)
        for k, v in mesas_full.items()
        if k != "joker"
    }
    oficial = mesas["oficial"]
    if guardar and extra.strip() and not guardadas:
        aviso = "Ninguna hora cerrada: no se escribio. "
    elif guardadas:
        aviso = "Horas cerradas agregadas a la cinta oficial. "
        if alertas_ingesta:
            tags_a = ", ".join(a["tag"] for a in alertas_ingesta)
            aviso += f"Alertas ingesta ({tags_a}) en reports/log_alertas_ingesta.txt. "
        _regenerar_logs_tablero()
    else:
        aviso = "Sin escribir archivo. "
    return {
        "ok": True,
        "data": str(DATA_UNICA),
        "pegadas": pegadas,
        "guardadas": guardadas,
        "alertas_ingesta": alertas_ingesta,
        "abiertas": abiertas,
        "ultima_cerrada": joker["ultima_cerrada"],
        "catalogo_mesas": catalogo_mesas(),
        "mesa_default": "oficial",
        "mesas": mesas,
        "joker": oficial,  # compat: misma mesa oficial
        "nota": (
            f"Cinta oficial: hilo-corto/data/data_3dias.txt. {aviso}"
            "Betas = sombra emulador J3. Cero LIVE."
        ),
    }


@app.get("/api/sesion")
def get_sesion(request: Request) -> dict:
    return {"ok": _sesion_ok(request)}


@app.post("/api/entrar")
def post_entrar(body: Acceso) -> Response:
    u = (body.usuario or "").strip()
    c = body.clave or ""
    if u != USUARIO or c != CLAVE:
        r = JSONResponse({"ok": False}, status_code=401)
        r.delete_cookie(COOKIE, path="/")
        return r
    r = JSONResponse({"ok": True})
    r.set_cookie(
        COOKIE,
        _ficha(),
        httponly=True,
        samesite="lax",
        path="/",
        max_age=60 * 60 * 24 * 30,
    )
    return r


@app.post("/api/salir")
def post_salir() -> Response:
    r = JSONResponse({"ok": True})
    r.delete_cookie(COOKIE, path="/")
    return r


@app.get("/api/tablero")
def get_tablero(request: Request) -> dict:
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    try:
        return armar("", False)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@app.get("/api/tablero/historico")
def get_tablero_historico(request: Request, mesa: str = "oficial") -> dict:
    """Histórico completo de una mesa — solo bajo demanda (modal)."""
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    mid = (mesa or "oficial").strip()
    if mid == "lc-01":
        return {"ok": True, "mesa": mid, "historico": [], "total": 0}
    try:
        cinta, _, _ = cargar_ingesta("")
        mesas_full, _ = _mesas_completas(cinta)
        if mid not in mesas_full:
            return JSONResponse(
                {"ok": False, "error": f"mesa desconocida: {mid}"},
                status_code=404,
            )
        panel = mesas_full[mid]
        hist = panel.get("historico") or []
        total = panel.get("historico_total", len(hist))
        return {"ok": True, "mesa": mid, "historico": hist, "total": total}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


NOMBRES_G_RECORDS = {1: "Deluxe", 2: "Luck", 3: "Dice", 4: "Show"}
RECORDS_HIST = Path(
    r"C:\operacion-joker\experimento-nueva-caja-negra\depurar-all-4G-detail.txt"
)
_RECORDS_LOCK = threading.Lock()
_RECORDS_ARCHIVO: dict[str, dict] = {
    "hist": {"mtime": None, "orden": None, "bloques": None},
    "dash": {"mtime": None, "orden": None, "bloques": None},
}


def _fecha_de_tag(tag: str) -> tuple[str, int] | None:
    m = _RE_HEADER_HORA.match((tag or "").strip().lstrip("\ufeff"))
    if not m:
        return None
    hod = int(m.group(1))
    d = m.group(2)
    return f"{d[0:2]}/{d[2:4]}/{d[4:6]}", hod


def _tag_norm(tag: str) -> str:
    y, m, d, h = _parse_tag_key(tag)
    return f"h{h}-{d:02d}{m:02d}{str(y)[-2:]}"


def _siguiente_tag(tag: str) -> str | None:
    try:
        y, m, d, h = _parse_tag_key(tag)
        nxt = datetime(y, m, d, h) + timedelta(hours=1)
    except (ValueError, IndexError, TypeError):
        return None
    return f"h{nxt.hour}-{nxt.day:02d}{nxt.month:02d}{str(nxt.year)[-2:]}"


def _leer_bloques_records(path: Path) -> tuple[list[str], dict[str, list[str]]]:
    texto = path.read_text(encoding="utf-8-sig", errors="replace")
    return leer_bloques_texto(texto)


def _archivo_records(slot: str, path: Path) -> tuple[list[str], dict[str, list[str]]]:
    mtime = path.stat().st_mtime if path.exists() else 0.0
    with _RECORDS_LOCK:
        cached = _RECORDS_ARCHIVO[slot]
        if cached["orden"] is not None and cached["mtime"] == mtime:
            return cached["orden"], cached["bloques"]
    if not path.exists():
        raise FileNotFoundError(str(path))
    orden, bloques = _leer_bloques_records(path)
    orden = sorted(orden, key=_parse_tag_key)
    with _RECORDS_LOCK:
        _RECORDS_ARCHIVO[slot] = {
            "mtime": mtime,
            "orden": orden,
            "bloques": bloques,
        }
    return orden, bloques


def _g_de_linea(line: str, hod: int | None = None) -> dict | None:
    """G reloj (10:06:44 G2 17), corto (G3 36) o tramo (28:57-29:41 G2 30)."""
    s = (line or "").strip()
    if not s:
        return None
    m = _RE_G_RELOJ.match(s)
    if m:
        x = int(m.group(5))
        if x <= 0:
            return None
        return {
            "tipo": int(m.group(4)),
            "x": x,
            "hh": int(m.group(1)),
            "mm": int(m.group(2)),
            "ss": int(m.group(3)),
        }
    m = _RE_G_LARGO.match(s)
    if m:
        x = int(m.group(6))
        if x <= 0:
            return None
        hh = hod if hod is not None else None
        return {
            "tipo": int(m.group(5)),
            "x": x,
            "hh": hh,
            "mm": int(m.group(1)),
            "ss": int(m.group(2)),
        }
    m = _RE_G_CORTO.match(s)
    if m:
        x = int(m.group(2))
        if x <= 0:
            return None
        return {"tipo": int(m.group(1)), "x": x, "hh": None, "mm": None, "ss": None}
    return None


def _hora_reloj(g: dict, hod: int) -> str:
    mm = g.get("mm")
    ss = g.get("ss")
    if mm is None or ss is None:
        return ""
    hh = g.get("hh")
    if hh is None:
        hh = hod
    return f"{int(hh):02d}:{int(mm):02d}:{int(ss):02d}"


def _linea_hist_g(g: dict, hod: int) -> str:
    reloj = _hora_reloj(g, hod)
    cuerpo = f"G{g['tipo']} {g['x']}"
    return f"{reloj} {cuerpo}" if reloj else cuerpo


def _bonos_de_tags(
    bloques: dict[str, list[str]], tags: list[str], fuente: str
) -> list[tuple[tuple, dict]]:
    filas: list[tuple[tuple, dict]] = []
    for tag in tags:
        parsed = _fecha_de_tag(tag)
        if not parsed:
            continue
        fecha, hod = parsed
        try:
            yk, mk, dk, hk = _parse_tag_key(tag)
        except (ValueError, IndexError):
            continue
        for i, ln in enumerate(bloques.get(tag) or []):
            g = _g_de_linea(ln, hod)
            if not g:
                continue
            tipo = g["tipo"]
            x = g["x"]
            hora = _hora_reloj(g, hod)
            mm = g["mm"] if g["mm"] is not None else i
            ss = g["ss"] if g["ss"] is not None else 0
            filas.append(
                (
                    (-x, -yk, -mk, -dk, -hk, -int(mm), -int(ss)),
                    {
                        "tag": tag,
                        "fecha": fecha,
                        "hod": hod,
                        "hora": hora,
                        "m0": int(mm),
                        "s0": int(ss),
                        "tipo": tipo,
                        "nombre": NOMBRES_G_RECORDS[tipo],
                        "x": x,
                        "fuente": fuente,
                    },
                )
            )
    return filas


def _horas_despues(ultima: str, dash_orden: list[str]) -> tuple[list[str], list[str]]:
    """Desde la hora siguiente al histórico: toma las que el dashboard tiene; omite huecos de 1h."""
    if not ultima or not dash_orden:
        return [], []
    by_norm = {_tag_norm(t): t for t in dash_orden}
    lim = _parse_tag_key(dash_orden[-1])
    tomadas: list[str] = []
    omitidas: list[str] = []
    cur = _siguiente_tag(ultima)
    guard = 0
    while cur and guard < 4000:
        guard += 1
        if _parse_tag_key(cur) > lim:
            break
        real = by_norm.get(_tag_norm(cur))
        if real:
            tomadas.append(real)
        else:
            omitidas.append(cur)
        cur = _siguiente_tag(cur)
    return tomadas, omitidas


def _armar_records() -> dict:
    hist_orden, hist_bloques = _archivo_records("hist", RECORDS_HIST)
    dash_orden: list[str] = []
    if DATA_UNICA.exists():
        dash_orden, _dash_bloques = _archivo_records("dash", DATA_UNICA)
    ultima = hist_orden[-1] if hist_orden else ""
    tomadas, omitidas = _horas_despues(ultima, dash_orden)
    filas = _bonos_de_tags(hist_bloques, hist_orden, "historico")
    filas.sort(key=lambda pair: pair[0])
    items = [row for _, row in filas]
    xs = [row["x"] for row in items]
    return {
        "ok": True,
        "n": len(items),
        "min_x": min(xs) if xs else 0,
        "max_x": max(xs) if xs else 0,
        "nombres": {str(k): v for k, v in NOMBRES_G_RECORDS.items()},
        "items": items,
        "historico": {
            "ultima": ultima,
            "n_horas": len(hist_orden),
        },
        "dashboard": {
            "n_horas": len(tomadas),
            "desde": tomadas[0] if tomadas else None,
            "hasta": tomadas[-1] if tomadas else None,
            "omitidas_n": len(omitidas),
            "omitidas": omitidas[:12],
        },
    }


def _append_horas_historico(tags: list[str], bloques: dict[str, list[str]]) -> int:
    """Agrega horas al .txt en formato corto. No toca la cinta del tablero."""
    partes: list[str] = []
    n_h = 0
    for tag in tags:
        parsed = _fecha_de_tag(tag)
        hod = parsed[1] if parsed else 0
        gs: list[str] = []
        for ln in bloques.get(tag) or []:
            g = _g_de_linea(ln, hod)
            if g:
                gs.append(_linea_hist_g(g, hod))
        partes.append(_tag_norm(tag))
        partes.extend(gs)
        partes.append("")
        n_h += 1
    if not n_h:
        return 0
    bloque = "\n".join(partes).rstrip() + "\n"
    with _RECORDS_LOCK:
        raw = ""
        if RECORDS_HIST.exists():
            raw = RECORDS_HIST.read_text(encoding="utf-8-sig", errors="replace")
        if raw and not raw.endswith("\n"):
            raw += "\n"
        if raw and not raw.endswith("\n\n"):
            raw += "\n"
        dest = RECORDS_HIST.with_suffix(".txt.tmp")
        dest.write_text(raw + bloque, encoding="utf-8")
        dest.replace(RECORDS_HIST)
        _RECORDS_ARCHIVO["hist"] = {"mtime": None, "orden": None, "bloques": None}
    return n_h


@app.get("/api/records")
def get_records(request: Request) -> dict:
    """Bonos G1–G4 del histórico 4G (formato corto o tramo largo)."""
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    try:
        return _armar_records()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@app.post("/api/records/cargar")
def post_records_cargar(request: Request) -> dict:
    """Copia al histórico las horas posteriores que el dashboard ya tiene. Hueco de 1 h: omitir."""
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    try:
        hist_orden, _hist_bloques = _archivo_records("hist", RECORDS_HIST)
        if not DATA_UNICA.exists():
            return {"ok": False, "error": "sin cinta de dashboard"}
        dash_orden, dash_bloques = _archivo_records("dash", DATA_UNICA)
        ultima = hist_orden[-1] if hist_orden else ""
        tomadas, _omitidas = _horas_despues(ultima, dash_orden)
        ya = {_tag_norm(t) for t in hist_orden}
        nuevas = [t for t in tomadas if _tag_norm(t) not in ya]
        n_h = _append_horas_historico(nuevas, dash_bloques)
        payload = _armar_records()
        payload["cargadas"] = n_h
        return payload
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@app.get("/api/piso")
def get_piso(request: Request, hora: str = "", T: int | None = None) -> dict:
    """Oficio piso: urna + pintor + extra. Sordo a ciudad. Cero chips."""
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    if not _leer_piso:
        return {"ok": False, "error": "piso_core no disponible", "filas": []}
    tag = (hora or "").strip()
    if not tag:
        return {"ok": False, "error": "falta ?hora=hXX-DDMMYY", "filas": []}
    try:
        return _leer_piso(tag, T=T)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "tag": tag, "filas": []}


def _ultimo_tag_cinta() -> str:
    if not DATA_UNICA.exists():
        return ""
    try:
        chunk = DATA_UNICA.read_bytes()[-16000:].decode("utf-8", errors="ignore")
    except OSError:
        return ""
    last = ""
    for raw in chunk.splitlines():
        s = raw.strip()
        if _RE_HEADER_HORA.match(s):
            last = s
    return last


def guardar_cinta_ligero(texto: str) -> dict:
    """Auto-cinta: pega horas cerradas sin recorrer mesas (eso congelaba el live)."""
    guardadas, alertas_ingesta = guardar_pegado(texto)
    return {
        "ok": True,
        "guardadas": guardadas,
        "alertas_ingesta": alertas_ingesta,
        "ultima_cerrada": _ultimo_tag_cinta(),
        "nota": "solo_guardar: cinta sin recalcular tablero.",
    }


@app.post("/api/tablero")
def post_tablero(request: Request, body: Pegado) -> dict:
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    try:
        if body.solo_guardar:
            return guardar_cinta_ligero(body.texto or "")
        return armar(body.texto or "", body.guardar)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


_proceso_extraccion: subprocess.Popen | None = None


def _leer_pid_extraccion() -> int | None:
    if not EXTRACCION_PID.exists():
        return None
    try:
        pid = int(EXTRACCION_PID.read_text(encoding="utf-8").strip())
        return pid if pid > 0 else None
    except Exception:
        return None


def _escribir_pid_extraccion(pid: int) -> None:
    EXTRACCION_DIR.mkdir(parents=True, exist_ok=True)
    EXTRACCION_PID.write_text(str(pid), encoding="utf-8")


def _borrar_pid_extraccion() -> None:
    try:
        EXTRACCION_PID.unlink(missing_ok=True)
    except Exception:
        pass
    try:
        EXTRACCION_PAUSA.unlink(missing_ok=True)
    except Exception:
        pass


def _pid_vivo(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        import os

        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _matar_pid_extraccion(pid: int) -> None:
    if pid <= 0:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
        return
    try:
        import os

        os.kill(pid, signal.SIGTERM)
    except Exception:
        pass


def _extraccion_corriendo() -> bool:
    global _proceso_extraccion
    if _proceso_extraccion is not None:
        if _proceso_extraccion.poll() is None:
            return True
        _proceso_extraccion = None
    pid = _leer_pid_extraccion()
    if pid is not None and _pid_vivo(pid):
        return True
    if pid is not None:
        _borrar_pid_extraccion()
    return False


def _detener_proceso_extraccion() -> None:
    global _proceso_extraccion
    if _proceso_extraccion is not None and _proceso_extraccion.poll() is None:
        try:
            if sys.platform == "win32":
                _proceso_extraccion.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                _proceso_extraccion.terminate()
            _proceso_extraccion.wait(timeout=10)
        except Exception:
            try:
                _proceso_extraccion.kill()
            except Exception:
                pass
    elif _extraccion_corriendo():
        pid = _leer_pid_extraccion()
        if pid is not None:
            _matar_pid_extraccion(pid)
    _proceso_extraccion = None
    _borrar_pid_extraccion()


@app.post("/api/extraccion/iniciar")
def post_extraccion_iniciar(request: Request) -> dict:
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    global _proceso_extraccion
    if _extraccion_corriendo():
        return {"ok": True, "ya_corria": True}
    node = shutil.which("node")
    if not node:
        return JSONResponse(
            {"ok": False, "error": "No se encontro 'node' en el PATH."}, status_code=500
        )
    if not EXTRACCION_JS.exists():
        return JSONResponse(
            {"ok": False, "error": "Falta dashboard/extraccion/extraccion-jokers.js"},
            status_code=500,
        )
    if not (EXTRACCION_DIR / "node_modules" / "playwright").is_dir():
        return JSONResponse(
            {
                "ok": False,
                "error": (
                    "Falta Playwright en dashboard/extraccion. "
                    "En terminal: cd dashboard/extraccion && npm install"
                ),
            },
            status_code=500,
        )
    cfg = _leer_jokerbets_config()
    nb_id = cfg.get("activeNotebookId")
    nb = next(
        (n for n in cfg.get("notebooks") or [] if n.get("id") == nb_id),
        (cfg.get("notebooks") or [None])[0],
    )
    cuentas = (nb or {}).get("cuentas") or []
    urls_ok = [c for c in cuentas if str(c.get("url") or "").strip()]
    if len(urls_ok) < 3:
        return JSONResponse(
            {
                "ok": False,
                "error": "Ronda B: pegá las 3 URLs en Cuentas → URLs antes de iniciar.",
            },
            status_code=400,
        )
    env = os.environ.copy()
    env["JOKERBETS_MULTI"] = "1"
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    _proceso_extraccion = subprocess.Popen(
        [node, str(EXTRACCION_JS)],
        cwd=str(EXTRACCION_DIR),
        env=env,
        creationflags=flags,
    )
    if _proceso_extraccion.pid:
        _escribir_pid_extraccion(_proceso_extraccion.pid)
    time.sleep(0.8)
    rc = _proceso_extraccion.poll()
    if rc is not None:
        _proceso_extraccion = None
        _borrar_pid_extraccion()
        msg = "El extractor se cerró al arrancar."
        if EXTRACCION_ESTADO.exists():
            try:
                info = json.loads(EXTRACCION_ESTADO.read_text(encoding="utf-8"))
                msg = info.get("mensaje") or msg
            except Exception:
                pass
        return JSONResponse({"ok": False, "error": msg}, status_code=500)
    return {"ok": True, "multi": True, "pid": _proceso_extraccion.pid}


@app.post("/api/extraccion/detener")
def post_extraccion_detener(request: Request) -> dict:
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    global _proceso_extraccion
    _detener_proceso_extraccion()
    try:
        EXTRACCION_PAUSA.unlink(missing_ok=True)
    except Exception:
        pass
    try:
        EXTRACCION_ESTADO.write_text(
            json.dumps(
                {
                    "estado": "detenido",
                    "mensaje": "Extracción detenida.",
                    "actualizado": datetime.now().isoformat(timespec="seconds"),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass
    return {"ok": True}


@app.post("/api/extraccion/pausar")
def post_extraccion_pausar(request: Request) -> dict:
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    try:
        EXTRACCION_PAUSA.touch()
        if EXTRACCION_ESTADO.exists():
            try:
                info = json.loads(EXTRACCION_ESTADO.read_text(encoding="utf-8"))
            except Exception:
                info = {}
            info.update(
                {
                    "estado": "pausado",
                    "mensaje": "Extracción en pausa manual (sala detenida).",
                    "actualizado": datetime.now().isoformat(timespec="seconds"),
                }
            )
            EXTRACCION_ESTADO.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    return {"ok": True, "pausado": True}


@app.post("/api/extraccion/reanudar")
def post_extraccion_reanudar(request: Request) -> dict:
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    try:
        EXTRACCION_PAUSA.unlink(missing_ok=True)
        if EXTRACCION_ESTADO.exists():
            try:
                info = json.loads(EXTRACCION_ESTADO.read_text(encoding="utf-8"))
            except Exception:
                info = {}
            info.update(
                {
                    "estado": "conectado",
                    "mensaje": "Reanudando extracción...",
                    "actualizado": datetime.now().isoformat(timespec="seconds"),
                }
            )
            EXTRACCION_ESTADO.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    return {"ok": True, "pausado": False}


@app.post("/api/extraccion/limpiar")
def post_extraccion_limpiar(request: Request) -> dict:
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    try:
        EXTRACCION_LINEAS.write_text("", encoding="utf-8")
        # Si el proceso Node sigue corriendo, este flag le avisa que tambien
        # tiene que vaciar su buffer en memoria (si no, reescribe lo viejo).
        EXTRACCION_LIMPIAR.touch()
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    return {"ok": True}


@app.post("/api/extraccion/cargar-live")
def post_extraccion_cargar_live(request: Request, body: CargarLiveBody) -> dict:
    """Inyecta/sobrescribe la hora en curso en la captura (tablero + ingesta)."""
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    tag, tramos_o_err = _parse_cargar_live_texto(body.texto or "")
    if tag is None:
        return JSONResponse({"ok": False, "error": tramos_o_err}, status_code=400)
    tramos = tramos_o_err
    try:
        merged = _inyectar_hora_en_captura(tag, tramos)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    return {
        "ok": True,
        "tag": tag,
        "n_tramos": len(tramos),
        "lineas": _sanitizar_lineas_extraccion(merged),
    }


@app.post("/api/extraccion/sync-cinta")
def post_extraccion_sync_cinta(request: Request, body: SyncCintaBody) -> dict:
    """Copia una hora cerrada de la cinta oficial a la captura de Extracción."""
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    tag = _norm_header((body.tag or "").strip())
    if not tag:
        return JSONResponse(
            {"ok": False, "error": "Falta el tag (ej. h18-290826)."},
            status_code=400,
        )
    if not DATA_UNICA.exists():
        return JSONResponse(
            {"ok": False, "error": "No está la cinta oficial."},
            status_code=404,
        )
    try:
        _orden, bloques = _leer_bloques(DATA_UNICA)
        filas = bloques.get(tag) or []
        tramos = [
            t
            for ln in filas
            if (t := _norm_tramo(ln))
        ]
        if not tramos:
            return JSONResponse(
                {"ok": False, "error": f"{tag} no está en la cinta o no tiene tramos."},
                status_code=404,
            )
        merged = _inyectar_hora_en_captura(tag, tramos)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    return {
        "ok": True,
        "tag": tag,
        "n_tramos": len(tramos),
        "lineas": _sanitizar_lineas_extraccion(merged),
    }


@app.get("/api/extraccion/estado")
def get_extraccion_estado(request: Request) -> dict:
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    estado, mensaje = "detenido", ""
    if EXTRACCION_ESTADO.exists():
        try:
            info = json.loads(EXTRACCION_ESTADO.read_text(encoding="utf-8"))
            estado = info.get("estado", estado)
            mensaje = info.get("mensaje", mensaje)
        except Exception:
            pass
    lineas: list[str] = []
    if EXTRACCION_LINEAS.exists():
        try:
            lineas = EXTRACCION_LINEAS.read_text(encoding="utf-8").splitlines()
        except Exception:
            pass
    lineas = _sanejar_duplicados_inicio(_sanitizar_lineas_extraccion(lineas))
    # Solo recorta la respuesta. Escribir el .txt acá pisa al Node y congela G nuevas.
    lineas = _tail_lineas_horas(lineas, MAX_EXTRACCION_HORAS)
    pausado = EXTRACCION_PAUSA.exists()
    corriendo = _extraccion_corriendo() or estado in ("conectado", "esperando", "pausado")
    if pausado and corriendo:
        estado = "pausado"
        if not mensaje or "detenida" not in mensaje:
            mensaje = "Extracción en pausa manual (sala detenida)."
    return {
        "ok": True,
        "corriendo": corriendo,
        "estado": estado,
        "pausado": pausado,
        "mensaje": mensaje,
        "lineas": lineas,
        "lineas_fp": _fingerprint_lineas(lineas),
        "lineas_n": len(lineas),
    }


def _veredicto_tip(tip: int | None, luz: int) -> str:
    if tip is None:
        return "silent"
    d = abs(tip - luz) % 60
    d = min(d, 60 - d)
    if tip == luz:
        return "exacto"
    if d <= 1:
        return "banda"
    return "miss"


def _leer_cronista_live() -> list[dict]:
    if not CRONISTA_LIVE.exists():
        return []
    out: list[dict] = []
    try:
        for raw in CRONISTA_LIVE.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return out


@app.get("/api/tips/cronista")
def get_tips_cronista(request: Request) -> dict:
    """Resumen del ledger vivo (UI) — lectura sombra."""
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    rows = _leer_cronista_live()
    exacto = sum(1 for r in rows if r.get("veredicto") == "exacto")
    banda = sum(1 for r in rows if r.get("veredicto") in ("exacto", "banda"))
    miss = sum(1 for r in rows if r.get("veredicto") == "miss")
    n = len(rows)
    return {
        "ok": True,
        "n": n,
        "exacto": exacto,
        "banda": banda,
        "miss": miss,
        "pct_banda": round(100.0 * banda / n, 1) if n else None,
        "ultimos": rows[-24:],
    }


@app.post("/api/tips/cronista")
def post_tips_cronista(request: Request, body: TipCronista) -> dict:
    """Append tip resuelto desde UI. Idempotente por tag+paso+luz."""
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    tag = (body.tag or "").strip().lower()
    if not tag or body.luz is None:
        return JSONResponse({"ok": False, "error": "tag/luz"}, status_code=400)
    v = _veredicto_tip(body.tip, body.luz)
    key = f"{tag}:{body.paso}:{body.luz}"
    existentes = _leer_cronista_live()
    if any(
        f"{(r.get('tag') or '').lower()}:{r.get('paso')}:{r.get('luz')}" == key
        for r in existentes
    ):
        return {"ok": True, "dup": True, "key": key}
    from datetime import datetime

    ev = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "tag": tag,
        "paso": body.paso,
        "tip": body.tip,
        "luz": body.luz,
        "delta": None if body.tip is None else body.tip - body.luz,
        "veredicto": v,
        "why": body.why or "",
        "fuente": "vivo",
        "algo": body.algo or "LG-43",
        "key": key,
    }
    CRONISTA_LIVE.parent.mkdir(parents=True, exist_ok=True)
    with CRONISTA_LIVE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return {"ok": True, "dup": False, "veredicto": v, "key": key}


def _leer_jokerbets_manual() -> dict:
    base = {
        "pendiente": False,
        "disparada": False,
        "disparadaAt": None,
        "ultimoResultado": None,
        "armadoAt": None,
        "montoPorBono": 50,
    }
    if not JOKERBETS_MANUAL.exists():
        return base
    try:
        raw = json.loads(JOKERBETS_MANUAL.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return base
    if not isinstance(raw, dict):
        return base
    return {
        **base,
        **raw,
        "pendiente": bool(raw.get("pendiente")),
        "disparada": bool(raw.get("disparada")),
    }


def _normalizar_monto_por_bono(n: int) -> int:
    try:
        x = int(round(int(n) / 50) * 50)
    except (TypeError, ValueError):
        x = 50
    return max(50, min(1000, x))


def _armar_jokerbets_manual(monto_por_bono: int = 50) -> dict:
    monto = _normalizar_monto_por_bono(monto_por_bono)
    norm = {
        "pendiente": True,
        "disparada": False,
        "disparadaAt": None,
        "ultimoResultado": None,
        "montoPorBono": monto,
        "armadoAt": datetime.now().isoformat(timespec="seconds"),
    }
    EXTRACCION_DIR.mkdir(parents=True, exist_ok=True)
    JOKERBETS_MANUAL.write_text(
        json.dumps(norm, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return norm


def _cancelar_jokerbets_manual() -> dict:
    norm = {
        "pendiente": False,
        "disparada": False,
        "disparadaAt": None,
        "ultimoResultado": "cancelado por usuario",
        "armadoAt": None,
    }
    EXTRACCION_DIR.mkdir(parents=True, exist_ok=True)
    JOKERBETS_MANUAL.write_text(
        json.dumps(norm, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return norm


def _request_es_localhost(request: Request) -> bool:
    if not request.client:
        return False
    host = (request.client.host or "").strip().lower()
    return host in ("127.0.0.1", "::1", "localhost")


def _color_etiqueta(color: str) -> str:
    m = {"rojo": "Rojo", "azul": "Azul", "verde": "Verde"}
    return m.get(str(color or "").lower(), str(color or "—"))


def _format_monto_push(raw) -> str:
    """Formato miles con punto: $12.600 · $124.900"""
    n = _parse_monto_push(raw)
    if n is None:
        return str(raw).strip() if raw not in (None, "") else "—"
    entero = int(round(n))
    neg = entero < 0
    digits = str(abs(entero))
    partes: list[str] = []
    while digits:
        partes.append(digits[-3:])
        digits = digits[:-3]
    con_miles = ".".join(reversed(partes))
    return f"{'-' if neg else ''}${con_miles}"


def _linea_color_push(row: dict) -> str:
    color = _color_etiqueta(row.get("color") or "")
    if not row.get("ganancia"):
        return f"{color}: —"
    parts = []
    premio = _format_monto_push(row.get("premio"))
    if premio != "—":
        parts.append(f"premio {premio}")
    apuesta = _format_monto_push(row.get("montoApuesta"))
    if apuesta != "—":
        parts.append(f"apuesta {apuesta}")
    mult = row.get("multiplicador")
    if mult is not None:
        try:
            parts.append(f"{int(float(mult))}x")
        except (TypeError, ValueError):
            parts.append(f"{mult}x")
    saldo = row.get("saldo")
    if saldo:
        parts.append(f"saldo {_format_monto_push(saldo)}")
    if not parts:
        return f"{color}: —"
    return f"{color}: " + " · ".join(parts)


def _mensaje_push_ntfy(ev: dict) -> tuple[str, str] | None:
    """Solo ronda con al menos un bono acertado (ganancia real)."""
    tipo = str(ev.get("tipo") or "").lower()
    if tipo != "ronda_acertada":
        return None
    tag = str(ev.get("horaTag") or "—").strip() or "—"
    filas = ev.get("colores")
    if not isinstance(filas, list) or not filas:
        return None
    orden = {"rojo": 0, "azul": 1, "verde": 2}
    sorted_rows = sorted(
        filas,
        key=lambda r: orden.get(str(r.get("color") or "").lower(), 9),
    )
    aciertos = [
        r
        for r in sorted_rows
        if isinstance(r, dict) and r.get("ganancia")
    ]
    if not aciertos:
        return None
    n_ok = len(aciertos)
    title = f"Bono acertado · {tag} · {n_ok}/3"
    body = "\n".join(
        _linea_color_push(r if isinstance(r, dict) else {}) for r in sorted_rows
    )
    return title[:240], body[:4000]


def _es_cobro_ganancia(ev: dict) -> bool:
    """Cobro real de bono: apuesta>0 y premio de cobro (no barra fantasma)."""
    if str(ev.get("tipo") or "").lower() != "premio":
        return False
    premio = _parse_monto_push(ev.get("premio"))
    if premio is None or premio <= 0:
        return False
    apuesta = _parse_monto_push(ev.get("montoApuesta"))
    if apuesta is None or apuesta <= 0:
        return False
    if premio >= apuesta:
        return True
    mult = ev.get("multiplicador")
    if mult is not None:
        try:
            if float(mult) >= 2 and premio >= 50:
                return True
        except (TypeError, ValueError):
            pass
    return False


def _parse_monto_push(raw) -> float | None:
    """Parsea 200, 1.05K, 1,693, $6K."""
    if raw is None or raw == "":
        return None
    s = str(raw).strip().replace(" ", "").replace("$", "")
    if not s:
        return None
    mul = 1.0
    low = s.lower()
    if low.endswith("k"):
        mul = 1000.0
        s = s[:-1]
    elif low.endswith("m"):
        mul = 1_000_000.0
        s = s[:-1]
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", s):
        s = s.replace(",", "")
    elif "," in s and "." not in s:
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    s = re.sub(r"[^\d.]", "", s)
    if not s:
        return None
    try:
        n = float(s) * mul
    except ValueError:
        return None
    return n if math.isfinite(n) else None


def _enviar_ntfy(ev: dict) -> None:
    cfg = _normalizar_jokerbets_ntfy(_leer_jokerbets_config().get("ntfy"))
    if not cfg.get("enabled"):
        return
    topic = str(cfg.get("topic") or "").strip()
    if not topic:
        return
    tipo = str(ev.get("tipo") or "").lower()
    if tipo not in cfg.get("tipos", []):
        return
    msg = _mensaje_push_ntfy(ev)
    if not msg:
        return
    title, body = msg
    server = str(cfg.get("server") or "https://ntfy.sh").rstrip("/")
    url = f"{server}/{topic}"
    req = urllib.request.Request(url, data=body.encode("utf-8"), method="POST")
    req.add_header("Title", title)
    req.add_header("Priority", str(cfg.get("priority") or "high"))
    req.add_header("Tags", "money_with_wings")
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            resp.read(256)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        _log.warning("ntfy push falló: %s", exc)


def _leer_apuestas_log(
    *,
    color: str | None = None,
    cuenta_id: str | None = None,
    limit: int = 80,
) -> list[dict]:
    if not JOKERBETS_APUESTAS_LOG.exists():
        return []
    lim = max(1, min(int(limit or 80), 200))
    try:
        lines = JOKERBETS_APUESTAS_LOG.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    if len(lines) > 400:
        lines = lines[-400:]
    out: list[dict] = []
    for raw in reversed(lines):
        if not raw.strip():
            continue
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if color and ev.get("color") != color:
            continue
        if cuenta_id and ev.get("cuentaId") != cuenta_id:
            continue
        out.append(ev)
        if len(out) >= lim:
            break
    out.reverse()
    return out


def _leer_performance_log(
    *,
    color: str | None = None,
    cuenta_id: str | None = None,
    event: str | None = None,
    limit: int = 500,
) -> list[dict]:
    if not JOKERBETS_PERF_LOG.exists():
        return []
    lim = max(1, min(int(limit or 500), 3000))
    try:
        lines = JOKERBETS_PERF_LOG.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    if len(lines) > 8000:
        lines = lines[-8000:]
    out: list[dict] = []
    for raw in reversed(lines):
        if not raw.strip():
            continue
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if color and ev.get("color") != color:
            continue
        if cuenta_id and ev.get("cuentaId") != cuenta_id:
            continue
        if event and ev.get("event") != event:
            continue
        out.append(ev)
        if len(out) >= lim:
            break
    out.reverse()
    return out


def _armar_resumen_performance() -> dict:
    """Agregados para revisión humana o agente (lee jokerbets-performance.jsonl)."""
    vacio = {
        "ok": True,
        "generado": datetime.now().isoformat(timespec="seconds"),
        "archivo": str(JOKERBETS_PERF_LOG.name),
        "nEventos": 0,
        "desde": None,
        "hasta": None,
        "apuestaModo": None,
        "arranqueUsd": None,
        "porCuenta": {},
    }
    if not JOKERBETS_PERF_LOG.exists():
        return vacio
    try:
        lines = [
            ln
            for ln in JOKERBETS_PERF_LOG.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
    except OSError:
        return vacio
    if not lines:
        return vacio
    events: list[dict] = []
    for raw in lines:
        try:
            events.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    if not events:
        return vacio
    por: dict[str, dict] = {}
    for ev in events:
        cid = str(ev.get("cuentaId") or ev.get("color") or "?")
        if cid not in por:
            por[cid] = {
                "cuentaId": ev.get("cuentaId"),
                "color": ev.get("color"),
                "apuestasBot": 0,
                "premios": 0,
                "frenosEmergencia": 0,
                "ultimoSaldo": None,
                "saldoPeak": None,
                "drawdown": None,
                "pnlDesdeArranque": None,
                "ultimoTs": None,
            }
        row = por[cid]
        evn = ev.get("event") or ""
        if evn == "apuesta_bot":
            row["apuestasBot"] += 1
        elif evn == "premio":
            row["premios"] += 1
        elif str(evn).startswith("freno_emergencia"):
            row["frenosEmergencia"] += 1
        if evn == "saldo_snapshot" or ev.get("saldo") is not None:
            sal = ev.get("saldo")
            if isinstance(sal, (int, float)):
                row["ultimoSaldo"] = sal
                row["saldoPeak"] = ev.get("saldoPeak", row["saldoPeak"])
                row["drawdown"] = ev.get("drawdown", row["drawdown"])
                pnl = ev.get("pnlDesdeArranque")
                if pnl is None and ev.get("arranqueUsd") is not None:
                    pnl = sal - float(ev["arranqueUsd"])
                if pnl is not None:
                    row["pnlDesdeArranque"] = pnl
        row["ultimoTs"] = ev.get("ts") or row["ultimoTs"]

    ult = events[-1]
    return {
        "ok": True,
        "generado": datetime.now().isoformat(timespec="seconds"),
        "archivo": str(JOKERBETS_PERF_LOG.name),
        "nEventos": len(events),
        "desde": events[0].get("ts"),
        "hasta": events[-1].get("ts"),
        "apuestaModo": ult.get("apuestaModo"),
        "arranqueUsd": ult.get("arranqueUsd"),
        "porCuenta": por,
    }


@app.get("/api/jokerbets/analisis/resumen")
def get_jokerbets_analisis_resumen(request: Request) -> dict:
    if not _analisis_puede_leer(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    return _armar_resumen_performance()


@app.get("/api/jokerbets/analisis/log")
def get_jokerbets_analisis_log(
    request: Request,
    color: str | None = None,
    cuentaId: str | None = None,
    event: str | None = None,
    limit: int = 500,
) -> dict:
    if not _analisis_puede_leer(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    events = _leer_performance_log(
        color=(color or "").strip().lower() or None,
        cuenta_id=(cuentaId or "").strip() or None,
        event=(event or "").strip() or None,
        limit=limit,
    )
    return {"ok": True, "events": events, "archivo": JOKERBETS_PERF_LOG.name}


@app.get("/api/jokerbets/apuesta-manual")
def get_jokerbets_apuesta_manual(request: Request) -> dict:
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    return {"ok": True, "manual": _leer_jokerbets_manual()}


@app.post("/api/jokerbets/apuesta-manual")
def post_jokerbets_apuesta_manual(
    request: Request, body: JokerbetsManualBody
) -> dict:
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    if body.cancelar:
        return {"ok": True, "manual": _cancelar_jokerbets_manual()}
    if not body.disparar:
        return JSONResponse({"ok": False, "error": "disparar=false"}, status_code=400)
    saved = _armar_jokerbets_manual(body.montoPorBono)
    return {"ok": True, "manual": saved}


@app.post("/api/jokerbets/push-event")
def post_jokerbets_push_event(
    request: Request, body: JokerbetsPushEventBody
) -> dict:
    """Solo localhost: la extracción avisa; servir reenvía a ntfy (teléfono)."""
    if not _request_es_localhost(request):
        return JSONResponse({"ok": False, "error": "solo localhost"}, status_code=403)
    ev = body.model_dump(exclude_none=True)
    if not ev.get("tipo"):
        return JSONResponse({"ok": False, "error": "tipo vacío"}, status_code=400)
    threading.Thread(
        target=_enviar_ntfy, args=(ev,), daemon=True, name="jokerbets-ntfy"
    ).start()
    return {"ok": True}


@app.get("/api/jokerbets/ui-pulse")
def get_jokerbets_ui_pulse(request: Request) -> dict:
    """Indica al front cuándo refrescar cards (bono terminado / premio). Sin polling pesado."""
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    if not JOKERBETS_UI_PULSE.exists():
        return {"ok": True, "pulse": None}
    try:
        pulse = json.loads(JOKERBETS_UI_PULSE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pulse = None
    return {"ok": True, "pulse": pulse}


@app.get("/api/jokerbets/cuentas/apuestas-log")
def get_jokerbets_apuestas_log(
    request: Request,
    color: str | None = None,
    cuentaId: str | None = None,
    limit: int = 80,
) -> dict:
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    events = _leer_apuestas_log(
        color=(color or "").strip().lower() or None,
        cuenta_id=(cuentaId or "").strip() or None,
        limit=limit,
    )
    return {"ok": True, "events": events}


@app.get("/api/jokerbets/cuentas/estado")
def get_jokerbets_cuentas_estado(request: Request) -> dict:
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    corriendo = _extraccion_corriendo()
    if not JOKERBETS_CUENTAS_ESTADO.exists():
        return {
            "ok": True,
            "corriendo": corriendo,
            "cuentas": None,
            "fuenteWsId": None,
        }
    try:
        data = json.loads(JOKERBETS_CUENTAS_ESTADO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    armado = False
    if JOKERBETS_BOT_ARMADO.exists():
        try:
            armado = bool(
                json.loads(JOKERBETS_BOT_ARMADO.read_text(encoding="utf-8")).get("armado")
            )
        except (OSError, json.JSONDecodeError):
            pass
    return {
        "ok": True,
        "corriendo": corriendo,
        "fuenteWsId": data.get("fuenteWsId"),
        "fuenteWsColor": data.get("fuenteWsColor"),
        "actualizado": data.get("actualizado"),
        "cuentas": data.get("cuentas"),
        "botArmado": data.get("botArmado", armado),
        "apuestaOk": data.get("apuestaOk"),
        "senal": data.get("senal"),
        "manual": data.get("manual") or _leer_jokerbets_manual(),
    }


def _leer_jokerbets_simul_pool7() -> dict:
    vacio = {"activo": False, "actualizado": None}
    if not JOKERBETS_SIMUL_POOL7.exists():
        return vacio
    try:
        j = json.loads(JOKERBETS_SIMUL_POOL7.read_text(encoding="utf-8"))
        return {
            "activo": bool(j.get("activo")),
            "actualizado": j.get("actualizado"),
        }
    except (OSError, json.JSONDecodeError):
        return vacio


@app.get("/api/jokerbets/simulacion-pool7")
def get_jokerbets_simulacion_pool7(request: Request) -> dict:
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    s = _leer_jokerbets_simul_pool7()
    return {"ok": True, "activo": s["activo"], "actualizado": s["actualizado"]}


@app.post("/api/jokerbets/simulacion-pool7")
def post_jokerbets_simulacion_pool7(
    request: Request, body: JokerbetsSimulPool7Body
) -> dict:
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    payload = {
        "activo": bool(body.activo),
        "actualizado": datetime.now().isoformat(timespec="seconds"),
    }
    try:
        EXTRACCION_DIR.mkdir(parents=True, exist_ok=True)
        JOKERBETS_SIMUL_POOL7.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    return {"ok": True, "activo": payload["activo"]}


@app.post("/api/jokerbets/senal")
def post_jokerbets_senal(request: Request, body: JokerbetsSenalBody) -> dict:
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    sim_archivo = _leer_jokerbets_simul_pool7()["activo"]
    sim_on = bool(sim_archivo)
    payload = {
        "actualizado": datetime.now().isoformat(timespec="seconds"),
        "tag": (body.tag or "").strip().lower(),
        "interruptor": body.interruptor or "OFF",
        "puertaA": bool(body.puertaA) or sim_on,
        "enZona": bool(body.enZona),
        "enZonaApuesta": bool(body.enZonaApuesta),
        "enCurso": (body.enCurso or "").strip(),
        "confirmadoHasta": int(body.confirmadoHasta)
        if body.confirmadoHasta is not None
        else -1,
        "nTiros": max(0, int(body.nTiros or 0)),
        "brilloFp": (body.brilloFp or "").strip(),
        "relojMinuto": body.relojMinuto,
        "relojSegundo": body.relojSegundo,
        "tip": body.tip,
        "tipEstado": body.tipEstado,
        "permitirClics": bool(body.permitirClics),
        "gapTiro": body.gapTiro,
        "ventanaCaliente": bool(body.ventanaCaliente),
        "simulPool7": sim_on,
        "pool7BrilloOk": bool(body.pool7BrilloOk),
        "puertaGoBrillo": bool(body.puertaGoBrillo),
        "formaG": (body.formaG or "").strip(),
        "formaGLabel": (body.formaGLabel or "").strip(),
        "formaGApuesta": bool(body.formaGApuesta),
        "puertaAFase": body.puertaAFase,
        "viaApuesta": body.viaApuesta,
    }
    try:
        EXTRACCION_DIR.mkdir(parents=True, exist_ok=True)
        JOKERBETS_SENAL.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    return {"ok": True}


@app.get("/api/jokerbets/bot/armado")
def get_jokerbets_bot_armado(request: Request) -> dict:
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    armado = False
    if JOKERBETS_BOT_ARMADO.exists():
        try:
            armado = bool(
                json.loads(JOKERBETS_BOT_ARMADO.read_text(encoding="utf-8")).get("armado")
            )
        except (OSError, json.JSONDecodeError):
            pass
    return {"ok": True, "armado": armado}


@app.post("/api/jokerbets/bot/armado")
def post_jokerbets_bot_armado(
    request: Request, body: JokerbetsBotArmadoBody
) -> dict:
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    payload = {
        "armado": bool(body.armado),
        "actualizado": datetime.now().isoformat(timespec="seconds"),
    }
    try:
        EXTRACCION_DIR.mkdir(parents=True, exist_ok=True)
        JOKERBETS_BOT_ARMADO.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    return {"ok": True, "armado": payload["armado"]}


@app.get("/api/jokerbets/config")
def get_jokerbets_config(request: Request) -> dict:
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    return {"ok": True, "config": _leer_jokerbets_config()}


@app.post("/api/jokerbets/config")
def post_jokerbets_config(request: Request, body: JokerbetsConfigBody) -> dict:
    if not _sesion_ok(request):
        return JSONResponse({"ok": False, "error": "entrar"}, status_code=401)
    if not body.config:
        return JSONResponse({"ok": False, "error": "config vacío"}, status_code=400)
    try:
        saved = _guardar_jokerbets_config(body.config)
    except OSError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    return {"ok": True, "config": saved}


if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="ui")


class _AccessSilencioso(logging.Filter):
    """No spamear polls del live en consola."""

    _MUTE = (
        "GET /api/extraccion/estado",
        "POST /api/tips/cronista",
        "GET /api/jokerbets/analisis/resumen",
    )

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        return not any(m in msg for m in self._MUTE)


def _configurar_logs() -> None:
    logging.getLogger("uvicorn.access").addFilter(_AccessSilencioso())


def _tag_reloj() -> str:
    d = datetime.now()
    return f"h{d.hour}-{d.day:02d}{d.month:02d}{str(d.year)[-2:]}"


def _resumen_captura_hora(tag: str) -> tuple[int, bool]:
    """Tramos cerrados en tag + si hay ronda en juego."""
    if not EXTRACCION_LINEAS.exists():
        return 0, False
    try:
        lineas = EXTRACCION_LINEAS.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0, False
    tag_l = tag.lower()
    en_bloque = False
    n = 0
    vivo = False
    for l in lineas:
        s = (l or "").strip()
        if not s:
            continue
        if _RE_HEADER_HORA.match(s):
            en_bloque = s.lower() == tag_l
            continue
        if not en_bloque:
            continue
        if _RE_EN_JUEGO.search(s) and not _RE_INTERRUMPIDO.search(s):
            vivo = True
        elif _RE_TRAMO_CERRADO.match(s):
            n += 1
    return n, vivo


def _heartbeat_loop() -> None:
    """Un pulso/minuto: hora en curso + captura, sin spam por request."""
    while True:
        time.sleep(60)
        try:
            tag = _tag_reloj()
            n, vivo = _resumen_captura_hora(tag)
            ext = "ON" if _extraccion_corriendo() else "off"
            extra = " · ronda en curso" if vivo else ""
            print(
                f"[hilo-corto] OK · {tag} · {n} tiros en captura{extra} · extracción {ext}",
                flush=True,
            )
        except Exception:
            pass


def main() -> None:
    import os
    import uvicorn

    _configurar_logs()
    threading.Thread(target=_heartbeat_loop, daemon=True, name="hilo-heartbeat").start()

    host = os.environ.get("HOST", "0.0.0.0")
    # 8765 por defecto: es el puerto que ya espera el CORS y el dashboard.
    port = int(os.environ.get("PORT", "8765"))
    bi = ROOT / "src" / "boleto_inter2.py"
    if not bi.is_file():
        raise SystemExit(f"[hilo-corto] Falta {bi} — no arranca el tablero.")
    print(f"[hilo-corto] Servidor http://{host}:{port} · LIVE {LIVE_MODO}", flush=True)
    threading.Thread(target=_armar_records, daemon=True, name="records-warm").start()
    uvicorn.run("servir:app", host=host, port=port, reload=False, access_log=True)


if __name__ == "__main__":
    main()
