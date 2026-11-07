"""Recorrido sombra: apuesta vs oficial. No escribe archivos. No es A01."""

from __future__ import annotations

import sys
from pathlib import Path

from src.estado import Estado, PRIMERA_UTIL, siguiente_tag
from src.lectores import Cinta, _parse_tag_key
from src.motor import dist_anillo, emitir_boleto


def _primera_disponible(cinta: Cinta, primera: str) -> str:
    """Si se perdió la semilla de cinta, arranca en la primera hora que quede."""
    if primera in cinta.horas:
        return primera
    if not cinta.orden:
        raise ValueError(f"no esta {primera}")
    try:
        piso = _parse_tag_key(primera)
    except Exception:
        return cinta.orden[0]
    for tag in cinta.orden:
        try:
            if _parse_tag_key(tag) >= piso:
                return tag
        except Exception:
            continue
    return cinta.orden[0]

_INTER2_MOD = None


def _inter2_mod():
    """INTER2 live — import diferido (evita ciclo mesas_beta ↔ tablero)."""
    global _INTER2_MOD
    if _INTER2_MOD is not None:
        return _INTER2_MOD
    root = Path(__file__).resolve().parent.parent
    rp = str(root)
    if rp not in sys.path:
        sys.path.insert(0, rp)
    mod_path = root / "src" / "boleto_inter2.py"
    if not mod_path.is_file():
        raise ModuleNotFoundError(
            f"No está {mod_path}. Corré servir.py desde hilo-corto/."
        )
    from src import boleto_inter2

    _INTER2_MOD = boleto_inter2
    return _INTER2_MOD


def mins(xs: list[int]) -> str:
    return ", ".join(f"{m:02d}" for m in xs)


def clasificar(oficiales: list[int], chips: list[int]) -> tuple[list[int], list[str]]:
    acertados = []
    bordes = []
    if not chips:
        return acertados, bordes
    for m in oficiales:
        chip = min(chips, key=lambda c: dist_anillo(m, c))
        d = dist_anillo(m, chip)
        if d == 0:
            acertados.append(m)
        elif d == 1:
            lado = "+1" if (chip + 1) % 60 == m else "-1"
            bordes.append(f"{m:02d} ({lado} de {chip:02d})")
    return acertados, bordes


def veredicto_chip(t: dict, oficiales: list[int]) -> dict:
    m = t["minuto"]
    nuc = set(oficiales)
    cubre = t.get("cubre") or [m]
    if m in nuc:
        marca = "EXACTO"
        detalle = f"oficial {m:02d} en el blanco"
    else:
        tocados = sorted(x for x in nuc if dist_anillo(m, x) == 1)
        if tocados:
            x = tocados[0]
            lado = "+1" if (m + 1) % 60 == x else "-1"
            marca = "BORDE"
            detalle = f"oficial {x:02d} ({lado} de chip {m:02d})"
        else:
            marca = "MUERTO"
            detalle = "ningun oficial en la tripleta"
    return {
        "minuto": m,
        "flag": t.get("flag"),
        "rol": t.get("rol"),
        "apunta": t.get("apunta"),
        "cubre": cubre,
        "veredicto": marca,
        "detalle": detalle,
    }


def score(chips: list[int], oficiales: list[int]) -> tuple[int, int]:
    if not chips:
        return 0, 0
    bs = set(chips)
    g = pm1 = 0
    for x in oficiales:
        d = min(dist_anillo(x, c) for c in bs)
        if d == 0:
            g += 1
        elif d == 1:
            pm1 += 1
    return g, pm1


def fila_apuesta(tag: str, doc: dict) -> dict:
    return {
        "sobre": tag,
        "for": doc["for"],
        "lectura": doc.get("lectura") or "",
        "chips": doc["boleto"],
        "tiros": doc.get("tiros") or [],
        "zonas_anden": doc.get("zonas_anden") or [],
        "zonas_racimo": doc.get("zonas_racimo") or [],
        "orillas": doc.get("orillas") or [],
        "h1": doc.get("foto") or [],
        "skip": (doc.get("resto") or {}).get("skip") or [],
        "puentes": (doc.get("resto") or {}).get("puentes") or [],
        "flags": ", ".join(
            f"{t['minuto']:02d}:{t['flag']}" for t in doc.get("tiros") or []
        ),
        "cierre": "largo" if doc["meta"].get("prev_largo") else "corto",
        "clima": doc["meta"].get("clima"),
        "k": len(doc["boleto"]),
        "oficial": False,
        "meta": doc.get("meta") or {},
    }


def contrastar(fila: dict, oficiales: list[int], tiros: list[dict]) -> dict:
    g, pm1 = score(fila["chips"], oficiales)
    ac, bd = clasificar(oficiales, fila["chips"])
    log_chips = [veredicto_chip(t, oficiales) for t in tiros]
    out = dict(fila)
    out.update(
        {
            "oficial": True,
            "g_of": len(oficiales),
            "g_ok": g,
            "pm1": pm1,
            "oficiales": oficiales,
            "acertados": ac,
            "bordes": bd,
            "pct": (g + pm1) / len(oficiales) if oficiales else None,
            "chips_log": log_chips,
        }
    )
    return out


def recorrer(cinta: Cinta, primera: str = PRIMERA_UTIL, live_modo: str | None = None) -> dict:
    bi = _inter2_mod()
    LIVE_MODO = bi.LIVE_MODO
    aplicar_inter2_live = bi.aplicar_inter2_live
    precompute_beta_chips = bi.precompute_beta_chips

    if live_modo is None:
        live_modo = LIVE_MODO
    semilla = _primera_disponible(cinta, primera)
    i0 = cinta.orden.index(semilla)
    estado = Estado()
    filas = []
    beta_by_for = precompute_beta_chips(cinta) if live_modo == LIVE_MODO else None

    for i in range(i0, len(cinta.orden)):
        tag = cinta.orden[i]
        estado.cerrar(cinta.get(tag))
        doc = emitir_boleto(estado)
        chips_classic = list(doc.get("boleto") or [])
        nxt = cinta.orden[i + 1] if i + 1 < len(cinta.orden) else None

        if live_modo == LIVE_MODO and nxt:
            doc = aplicar_inter2_live(
                doc,
                chips_classic,
                (beta_by_for or {}).get(nxt) or {},
            )

        fila = fila_apuesta(tag, doc)
        fila["chips_classic"] = chips_classic
        fila["live_modo"] = live_modo
        if doc.get("meta", {}).get("inter2_fallback"):
            fila["inter2_fallback"] = True

        if nxt:
            oficiales = list(cinta.get(nxt).nucleo)
            fila = contrastar(fila, oficiales, doc.get("tiros") or [])
        filas.append(fila)

    apuesta = filas[-1]
    historico = [f for f in filas if f.get("oficial")]
    boleto = emitir_boleto(estado)
    chips_classic_ap = list(boleto.get("boleto") or [])
    ultima = cinta.orden[-1]
    for_tag = siguiente_tag(ultima)
    if live_modo == LIVE_MODO:
        boleto = aplicar_inter2_live(
            boleto,
            chips_classic_ap,
            (beta_by_for or {}).get(for_tag) or {},
        )
    estado.ultimo_boleto = boleto
    return {
        "historico": historico,
        "apuesta": apuesta,
        "lectura": apuesta.get("lectura") or "",
        "ultima_cerrada": cinta.orden[-1],
        "boleto": boleto,
        "estado": estado,
        "live_modo": live_modo,
    }


def resumen_historico(historico: list[dict]) -> dict:
    n = len(historico)
    if n == 0:
        return {
            "n": 0,
            "banda": None,
            "colapso": None,
            "horas_con_banda": 0,
            "racha": 0,
            "g_hora": None,
            "score_hora": None,
            "seguro_ok": 0,
            "seguro_n": 0,
        }
    g = sum(r["g_ok"] for r in historico)
    p1 = sum(r["pm1"] for r in historico)
    of = sum(r["g_of"] for r in historico)
    hit = sum(1 for r in historico if r["g_ok"] + r["pm1"] > 0)
    racha = cur = 0
    for r in historico:
        if r["g_ok"] + r["pm1"] > 0:
            cur += 1
            racha = max(racha, cur)
        else:
            cur = 0
    seg_ok = seg_n = 0
    for r in historico:
        for c in r.get("chips_log") or []:
            if c.get("flag") == "SEGURO":
                seg_n += 1
                if c.get("veredicto") == "EXACTO":
                    seg_ok += 1
    return {
        "n": n,
        "banda": (g + p1) / of if of else None,
        "colapso": 1 - hit / n,
        "horas_con_banda": hit,
        "racha": racha,
        "g_hora": g / n,
        "score_hora": (g + p1) / n,
        "seguro_ok": seg_ok,
        "seguro_n": seg_n,
        "exactos": g,
        "pm1": p1,
        "oficiales": of,
    }
