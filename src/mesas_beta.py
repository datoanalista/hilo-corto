# -*- coding: utf-8 -*-
"""Mesas beta (emuladores J3) — sombra para el dashboard.

Cero LIVE. No escribe boleto. No toca motor.py prod.
Chips = minutos G del emulador (Faro nG desde H-1).
INTER2 = acuerdo exacto ≥2 de P0–P5 (Pool 8 UI · LIVE = mismo acuerdo desde 2026-08-30).

  from src.mesas_beta import catalogo_mesas, paneles_beta, panel_inter2
"""
from __future__ import annotations

import importlib
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

from src.estado import PRIMERA_UTIL, siguiente_tag
from src.lectores import Cinta
from src.tablero import contrastar, resumen_historico

OJ = Path(r"c:\operacion-joker")
LAB_EJ = OJ / "experimento-emulador-j3"
HIST_WALK = 80  # horas hacia atrás para histórico beta

CATALOGO = [
    {
        "id": "oficial",
        "nombre": "OFICIAL",
        "version": None,
        "ej": None,
        "beta": False,
        "motor": "INTER2 live · acuerdo ≥2 P0–P5 (boleto prod)",
    },
    {
        "id": "pool-9",
        "nombre": "POOL 9",
        "version": None,
        "ej": None,
        "beta": False,
        "classic": True,
        "pool9": True,
        "motor": "hilo-corto clásico · islas H-1 + costura (sombra)",
    },
    {
        "id": "beta-v1",
        "nombre": "BETA 01",
        "version": "V.1",
        "ej": "EJ-01",
        "beta": True,
        "modulo": "src.emulador_ej01",
        "factory": "ej01",
        "motor": "EJ-01 · pulso ARQ-B (sombra · Faro nG)",
    },
    {
        "id": "beta-v2",
        "nombre": "BETA 01-C",
        "version": "V.2",
        "ej": "EJ-01c",
        "beta": True,
        "modulo": "src.emulador_ej01",
        "factory": "ciego",
        "motor": "EJ-01c · pulso ciego (sombra)",
    },
    {
        "id": "beta-v3",
        "nombre": "BETA 02",
        "version": "V.3",
        "ej": "EJ-02",
        "beta": True,
        "modulo": "src.emulador_ej02",
        "factory": "ej02",
        "motor": "EJ-02 · campanas ARQ-A (sombra · Faro nG)",
    },
    {
        "id": "beta-v4",
        "nombre": "BETA 03",
        "version": "V.4",
        "ej": "EJ-03",
        "beta": True,
        "modulo": "src.emulador_ej03",
        "factory": "ej03",
        "motor": "EJ-03 · gramática ARQ-C (sombra · Faro nG)",
    },
    {
        "id": "beta-v5",
        "nombre": "BETA 05-V2",
        "version": "V.5",
        "ej": "EJ-05v2",
        "beta": True,
        "modulo": "src.emulador_ej05",
        "factory": "ej05",
        "motor": "EJ-05v2 · tríptico (sombra · Faro nG)",
    },
]

_CACHE: dict | None = None  # factories + TiroSim + estimar_nG
_CACHE_FAIL: str | None = None


BOLETO_IDS = [
    "oficial",
    "beta-v1",
    "beta-v2",
    "beta-v3",
    "beta-v4",
    "beta-v5",
]

INTER2_META = {
    "id": "inter2",
    "nombre": "POOL 8",
    "beta": False,
    "inter2": True,
    "motor": "INTER2 · acuerdo exacto ≥2 de P0–P5",
}


def catalogo_mesas() -> list[dict]:
    out = [
        {
            "id": m["id"],
            "nombre": m["nombre"],
            "version": m.get("version"),
            "ej": m.get("ej"),
            "beta": m["beta"],
            "motor": m["motor"],
        }
        for m in CATALOGO
    ]
    out.append(
        {
            "id": INTER2_META["id"],
            "nombre": INTER2_META["nombre"],
            "version": None,
            "ej": None,
            "beta": False,
            "inter2": True,
            "motor": INTER2_META["motor"],
        }
    )
    return out


def acuerdo_ge2(listas: list[list]) -> list[int]:
    cnt: Counter = Counter()
    for xs in listas:
        for c in xs or []:
            try:
                cnt[int(c)] += 1
            except (TypeError, ValueError):
                pass
    return sorted(m for m, n in cnt.items() if n >= 2)


def panel_inter2(oficial: dict, betas: dict) -> dict:
    """Pool 8: minutos exactos en ≥2 de los 6 boletos P0–P5."""
    panels = {"oficial": oficial or {}, **(betas or {})}

    def chips_pred(p: dict) -> list:
        return list((p.get("prediccion") or {}).get("chips") or [])

    chips = acuerdo_ge2([chips_pred(panels.get(pid) or {}) for pid in BOLETO_IDS])
    tiros = _chips_a_tiros(chips)

    by_for: dict[str, dict[str, list]] = defaultdict(dict)
    oficiales_for: dict[str, list] = {}
    meta_for: dict[str, dict] = {}
    for pid in BOLETO_IDS:
        for h in (panels.get(pid) or {}).get("historico") or []:
            ft = h.get("for")
            if not ft:
                continue
            by_for[ft][pid] = list(h.get("chips") or [])
            if ft not in oficiales_for and h.get("oficiales") is not None:
                oficiales_for[ft] = list(h["oficiales"])
            if ft not in meta_for:
                meta_for[ft] = h

    orden_for: list[str] = []
    seen: set[str] = set()
    for h in (oficial or {}).get("historico") or []:
        ft = h.get("for")
        if ft and ft not in seen:
            seen.add(ft)
            orden_for.append(ft)
    for ft in by_for:
        if ft not in seen:
            seen.add(ft)
            orden_for.append(ft)

    hist = []
    for ft in orden_for:
        mmap = by_for.get(ft) or {}
        ch = acuerdo_ge2([mmap.get(pid) or [] for pid in BOLETO_IDS])
        sample = meta_for.get(ft) or {}
        fila = {
            "sobre": sample.get("sobre"),
            "for": ft,
            "lectura": "INTER2 · acuerdo ≥2 P0–P5",
            "chips": ch,
            "tiros": _chips_a_tiros(ch),
            "h1": sample.get("h1") or [],
            "skip": [],
            "puentes": [],
            "flags": ", ".join("%02d:TIBIO" % m for m in ch),
            "cierre": sample.get("cierre"),
            "clima": None,
            "k": len(ch),
            "oficial": False,
            "beta": False,
            "inter2": True,
        }
        ofs = oficiales_for.get(ft)
        if ofs is not None:
            fila = contrastar(fila, ofs, fila["tiros"])
        hist.append(fila)

    pred = (oficial or {}).get("prediccion") or {}
    return {
        "id": INTER2_META["id"],
        "nombre": INTER2_META["nombre"],
        "version": None,
        "ej": None,
        "beta": False,
        "inter2": True,
        "motor": INTER2_META["motor"],
        "prediccion": {
            "for": pred.get("for"),
            "sobre": pred.get("sobre"),
            "chips": chips,
            "tiros": tiros,
            "cierre": pred.get("cierre"),
            "clima": None,
            "k": len(chips),
            "lectura": "INTER2 · acuerdo exacto ≥2 de P0–P5 · sombra",
            "h1": pred.get("h1") or [],
            "skip": [],
            "puentes": [],
        },
        "piso": None,
        "observacion": _slim(hist[-1]) if hist else None,
        "historico": [_slim(f) for f in hist],
        "historico_total": len(hist),
        "resumen": resumen_historico(hist),
    }


def _panel_beta_error(meta: dict, exc: BaseException | str) -> dict:
    msg = str(exc)
    return {
        "id": meta["id"],
        "nombre": meta["nombre"],
        "version": meta.get("version"),
        "ej": meta.get("ej"),
        "beta": True,
        "motor": meta["motor"],
        "error": msg,
        "prediccion": {
            "for": None,
            "sobre": None,
            "chips": [],
            "tiros": [],
            "lectura": "error beta: %s" % msg,
            "h1": [],
            "k": 0,
            "skip": [],
            "puentes": [],
        },
        "piso": None,
        "observacion": None,
        "historico": [],
        "resumen": resumen_historico([]),
    }


def _cargar_lab():
    """Carga factories del lab emulador sin dejar src/ del lab en sys.modules."""
    global _CACHE, _CACHE_FAIL
    if _CACHE is not None:
        return _CACHE
    if _CACHE_FAIL:
        raise RuntimeError(_CACHE_FAIL)

    cupo = LAB_EJ / "src" / "cupo_ciego.py"
    if not cupo.exists():
        _CACHE_FAIL = (
            "Falta experimento-emulador-j3 (cupo_ciego). "
            "Copiá C:\\operacion-joker\\experimento-emulador-j3 "
            "al mismo path en este PC."
        )
        raise RuntimeError(_CACHE_FAIL)

    saved = {
        k: sys.modules[k]
        for k in list(sys.modules)
        if k == "src" or k.startswith("src.")
    }
    for k in list(saved):
        del sys.modules[k]

    paths_added = []
    for p in (
        str(LAB_EJ),
        str(OJ / "experimento-mente-en-blanco" / "lab-piso"),
        str(OJ / "experimento-cinta-r"),
    ):
        if p not in sys.path:
            sys.path.insert(0, p)
            paths_added.append(p)

    try:
        from src.cupo_ciego import estimar_nG  # noqa: WPS433
        from src.emulador_v0 import TiroSim  # noqa: WPS433

        factories = {}
        for meta in CATALOGO:
            if not meta["beta"]:
                continue
            mod = importlib.import_module(meta["modulo"])
            key = meta["factory"]
            if "ej05" in meta["modulo"]:
                factories[meta["id"]] = mod.factory("ej05")
            elif "ej03" in meta["modulo"]:
                factories[meta["id"]] = mod.factory(
                    "ciego" if key == "ciego" else "ej03"
                )
            elif "ej02" in meta["modulo"]:
                factories[meta["id"]] = mod.factory(
                    "ciego" if key == "ciego" else "ej02"
                )
            else:
                factories[meta["id"]] = mod.factory(
                    "ciego" if key == "ciego" else "ej01"
                )
        _CACHE = {
            "factories": factories,
            "TiroSim": TiroSim,
            "estimar_nG": estimar_nG,
        }
    except Exception as exc:
        _CACHE_FAIL = (
            "No se pudo cargar experimento-emulador-j3 (cupo_ciego): %s. "
            "Copiá C:\\operacion-joker\\experimento-emulador-j3 al mismo path."
            % exc
        )
    finally:
        for k in list(sys.modules):
            if k == "src" or k.startswith("src."):
                del sys.modules[k]
        sys.modules.update(saved)
        for p in paths_added:
            if p in sys.path:
                try:
                    sys.path.remove(p)
                except ValueError:
                    pass

    if _CACHE is None:
        raise RuntimeError(_CACHE_FAIL or "lab emulador no disponible")
    return _CACHE


def _a_tiros_sim(hora, TiroSim) -> list:
    out = []
    for t in hora.tiros_nucleo or []:
        lab = "G" if t.color == "G" else "R"
        tipo = t.tipo
        if lab == "G" and tipo is None:
            tipo = 1
        letra = ""
        if lab == "G" and tipo is not None:
            letra = "G%d" % tipo
        elif lab == "R":
            letra = "R%d" % (tipo or 1)
        out.append(
            TiroSim(
                m0=int(t.m0) % 60,
                s0=int(t.s0),
                dur=int(t.dur_s),
                lab=lab,
                tipo=tipo,
                letra=letra,
            )
        )
    return out


def _gs_mins(tiros) -> list[int]:
    out, seen = [], set()
    for t in tiros:
        if getattr(t, "lab", None) != "G":
            continue
        if getattr(t, "tipo", None) == 5:
            continue
        m = int(t.m0) % 60
        if m not in seen:
            seen.add(m)
            out.append(m)
    return sorted(out)


def _chips_a_tiros(chips: list[int]) -> list[dict]:
    return [
        {
            "minuto": m,
            "flag": "TIBIO",
            "rol": "beta",
            "cubre": [(m - 1) % 60, m, (m + 1) % 60],
            "apunta": m,
        }
        for m in chips
    ]


def _generar(emu, tag: str, seed: int, prev_tiros, nG: int):
    try:
        hora = emu.generate_hora(
            tag=tag,
            seed=seed,
            prev_tiros=prev_tiros,
            nG_target=nG,
            h1_marco=None,
        )
    except TypeError:
        hora = emu.generate_hora(
            tag=tag,
            seed=seed,
            prev_tiros=prev_tiros,
            nG_target=nG,
        )
    except Exception:
        return [], []
    return _gs_mins(hora.tiros), hora.tiros


def _slim(f: dict) -> dict:
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
        "chips_log",
        "lectura",
        "beta",
    ]
    return {k: f.get(k) for k in keys if k in f}


def _panel_beta(meta: dict, cinta: Cinta, lab: dict) -> dict:
    emu = lab["factories"][meta["id"]]
    TiroSim = lab["TiroSim"]
    estimar_nG = lab["estimar_nG"]
    seed_base = 4000 + sum(ord(c) for c in meta["id"])

    orden = cinta.orden
    if PRIMERA_UTIL in orden:
        i_first = orden.index(PRIMERA_UTIL)
    else:
        i_first = 0
    i_end = len(orden) - 1
    i0 = max(i_first, i_end - HIST_WALK)

    hist = []
    prev_sim = None

    for i in range(i0, i_end):
        tag = orden[i]
        nxt = orden[i + 1]
        prev_real = _a_tiros_sim(cinta.get(tag), TiroSim)
        prev_use = prev_sim if prev_sim is not None else prev_real
        nG = estimar_nG(prev_use, random.Random(seed_base + i))
        chips, tiros_sim = _generar(emu, nxt, seed_base + i, prev_use, nG)
        tiros = _chips_a_tiros(chips)
        fila = {
            "sobre": tag,
            "for": nxt,
            "lectura": "Beta sombra · no boleto prod · Faro nG",
            "chips": chips,
            "tiros": tiros,
            "h1": list(cinta.get(tag).nucleo),
            "skip": [],
            "puentes": [],
            "flags": ", ".join("%02d:TIBIO" % m for m in chips),
            "cierre": (
                "largo"
                if any(t.largo for t in cinta.get(tag).tiros_nucleo or [])
                else "corto"
            ),
            "clima": None,
            "k": len(chips),
            "oficial": False,
            "beta": True,
        }
        oficiales = list(cinta.get(nxt).nucleo)
        fila = contrastar(fila, oficiales, tiros)
        hist.append(fila)
        prev_sim = tiros_sim

    ultima = orden[-1]
    prev_real = _a_tiros_sim(cinta.get(ultima), TiroSim)
    for_tag = siguiente_tag(ultima)
    nG = estimar_nG(prev_real, random.Random(seed_base + 9999))
    chips, _ = _generar(emu, for_tag, seed_base + 9999, prev_real, nG)
    tiros = _chips_a_tiros(chips)

    return {
        "id": meta["id"],
        "nombre": meta["nombre"],
        "version": meta.get("version"),
        "ej": meta.get("ej"),
        "beta": True,
        "motor": meta["motor"],
        "prediccion": {
            "for": for_tag,
            "sobre": ultima,
            "chips": chips,
            "tiros": tiros,
            "cierre": (
                "largo"
                if any(t.largo for t in cinta.get(ultima).tiros_nucleo or [])
                else "corto"
            ),
            "clima": None,
            "k": len(chips),
            "lectura": "Beta sombra · no boleto prod · Faro nG · cero LIVE",
            "h1": list(cinta.get(ultima).nucleo),
            "skip": [],
            "puentes": [],
        },
        "piso": None,
        "observacion": _slim(hist[-1]) if hist else None,
        "historico": [_slim(f) for f in hist],
        "historico_total": len(hist),
        "resumen": resumen_historico(hist),
    }


def paneles_beta(cinta: Cinta) -> dict[str, dict]:
    out = {}
    try:
        lab = _cargar_lab()
    except Exception as exc:
        for meta in CATALOGO:
            if meta["beta"]:
                out[meta["id"]] = _panel_beta_error(meta, exc)
        return out
    for meta in CATALOGO:
        if not meta["beta"]:
            continue
        try:
            out[meta["id"]] = _panel_beta(meta, cinta, lab)
        except Exception as exc:
            out[meta["id"]] = _panel_beta_error(meta, exc)
    return out
