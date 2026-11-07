"""Lectores de data cruda: sillas y cintas. Nada más."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_UNICA = ROOT / "data" / "data_3dias.txt"

TAG_RE = re.compile(r"^h\d{1,2}-\d{6}$")
CORTE_LARGO_S = 70


@dataclass
class Tiro:
    casilla: int
    m0: int
    s0: int
    m1: int
    s1: int
    start_s: int
    dur_s: int
    largo: bool
    color: str
    tipo: int | None = None
    lumen: int | None = None


@dataclass
class HoraCruda:
    tag: str
    nucleo: list[int]
    holgada: list[int]
    extra: list[int]
    tiros_nucleo: list[Tiro] = field(default_factory=list)
    n_largos: int = 0


def arranque_proxima(last: Tiro) -> int:
    """Segundo 0..3599 donde arranca el primer tiro de la hora siguiente."""
    crudo = last.start_s + last.dur_s + 1
    if crudo >= 3600:
        return crudo - 3600
    return 0


@dataclass
class Cinta:
    orden: list[str]
    horas: dict[str, HoraCruda]

    def get(self, tag: str) -> HoraCruda:
        if tag not in self.horas:
            raise KeyError(f"hora no está en la data cruda: {tag}")
        return self.horas[tag]

    def siguiente(self, tag: str) -> str | None:
        try:
            i = self.orden.index(tag)
        except ValueError as exc:
            raise KeyError(tag) from exc
        if i + 1 >= len(self.orden):
            return None
        return self.orden[i + 1]

    def anterior(self, tag: str) -> str | None:
        try:
            i = self.orden.index(tag)
        except ValueError as exc:
            raise KeyError(tag) from exc
        if i <= 0:
            return None
        return self.orden[i - 1]


def _duracion_s(m0: int, s0: int, m1: int, s1: int) -> int:
    a = m0 * 60 + s0
    b = m1 * 60 + s1
    return (b - a) % 3600


def _parse_intervalo_casilla(line: str) -> int:
    cabeza = line.split()[0]
    inicio = cabeza.split("-")[0]
    return int(inicio.split(":")[0])


def _parse_tiro(line: str) -> Tiro:
    partes = line.split()
    a, b = partes[0].split("-")
    m0, s0 = (int(x) for x in a.split(":"))
    m1, s1 = (int(x) for x in b.split(":"))
    dur = _duracion_s(m0, s0, m1, s1)
    color = "R"
    tipo = None
    lumen = None
    if len(partes) > 1:
        tok = partes[1]
        if tok.startswith("G"):
            color = "G"
            if len(tok) > 1 and tok[1].isdigit():
                tipo = int(tok[1])
            if len(partes) > 2 and partes[2].isdigit():
                lumen = int(partes[2])
    return Tiro(
        casilla=m0,
        m0=m0,
        s0=s0,
        m1=m1,
        s1=s1,
        start_s=m0 * 60 + s0,
        dur_s=dur,
        largo=dur >= CORTE_LARGO_S,
        color=color,
        tipo=tipo,
        lumen=lumen,
    )


def leer_bloques_texto(texto: str) -> tuple[list[str], dict[str, list[str]]]:
    orden: list[str] = []
    bloques: dict[str, list[str]] = {}
    tag: str | None = None
    for cruda in texto.splitlines():
        line = cruda.strip()
        if not line:
            continue
        if TAG_RE.match(line):
            tag = line
            if tag not in bloques:
                bloques[tag] = []
                orden.append(tag)
            continue
        if tag is None:
            continue
        bloques[tag].append(line)
    return orden, bloques


def _leer_bloques(path: Path) -> tuple[list[str], dict[str, list[str]]]:
    return leer_bloques_texto(path.read_text(encoding="utf-8"))


def _unicos_ordenados(casillas: list[int]) -> list[int]:
    vistos: set[int] = set()
    out: list[int] = []
    for c in casillas:
        if c not in vistos:
            vistos.add(c)
            out.append(c)
    out.sort()
    return out


def _parse_tag_key(tag: str) -> tuple[int, int, int, int]:
    cuerpo = tag[1:]
    hora_s, ddmmyy = cuerpo.split("-")
    return (2000 + int(ddmmyy[4:6]), int(ddmmyy[2:4]), int(ddmmyy[0:2]), int(hora_s))


def _tiros_de(detalle: dict[str, list[str]], tag: str) -> list[Tiro]:
    out: list[Tiro] = []
    for ln in detalle.get(tag, []):
        if not ln or not ln[0].isdigit():
            continue
        out.append(_parse_tiro(ln))
    return out


def _nucleo_de_tiros(tiros: list[Tiro]) -> list[int]:
    return _unicos_ordenados(
        [t.casilla for t in tiros if t.color == "G" and t.tipo != 5]
    )


def _holgada_de_tiros(tiros: list[Tiro]) -> list[int]:
    return _unicos_ordenados([t.casilla for t in tiros if t.color == "G"])


def hora_cerrada(tiros: list[Tiro]) -> bool:
    """La hora actual en ingesta (truncada) no se cierra."""
    if len(tiros) < 40:
        return False
    last = tiros[-1]
    if last.m1 < last.m0:
        return True
    return last.m1 >= 50 or (last.start_s + last.dur_s) >= 3500


def _hora_desde_tiros(tag: str, tiros: list[Tiro]) -> HoraCruda:
    nucleo = _nucleo_de_tiros(tiros)
    return HoraCruda(
        tag=tag,
        nucleo=nucleo,
        holgada=list(nucleo),
        extra=[],
        tiros_nucleo=tiros,
        n_largos=sum(1 for t in tiros if t.largo),
    )


def cinta_desde_bloques(
    orden_tags: list[str], bloques: dict[str, list[str]]
) -> tuple[Cinta, list[dict]]:
    """Cierra las horas que llegan al corte. Las truncadas salen como abiertas."""
    tags = list(orden_tags)
    tags.sort(key=_parse_tag_key)
    horas: dict[str, HoraCruda] = {}
    orden: list[str] = []
    abiertas: list[dict] = []
    for tag in tags:
        tiros = _tiros_de(bloques, tag)
        if not tiros:
            continue
        if not hora_cerrada(tiros):
            last = tiros[-1]
            abiertas.append(
                {
                    "tag": tag,
                    "n_tiros": len(tiros),
                    "nucleo": _nucleo_de_tiros(tiros),
                    "luces": _holgada_de_tiros(tiros),
                    "ultimo_minuto": last.m1 % 60,
                    "ultimo": (
                        f"{last.m0:02d}:{last.s0:02d}-"
                        f"{last.m1:02d}:{last.s1:02d} {last.color}"
                    ),
                    "nota": "hora abierta: no se usa para predecir",
                }
            )
            continue
        horas[tag] = _hora_desde_tiros(tag, tiros)
        orden.append(tag)
    return Cinta(orden=orden, horas=horas), abiertas


def mezclar_bloques(
    base_orden: list[str],
    base: dict[str, list[str]],
    extra_orden: list[str],
    extra: dict[str, list[str]],
) -> tuple[list[str], dict[str, list[str]]]:
    bloques = {k: list(v) for k, v in base.items()}
    orden = list(base_orden)
    for tag in extra_orden:
        bloques[tag] = list(extra[tag])
        if tag not in orden:
            orden.append(tag)
    return orden, bloques


def cargar_ingesta(extra_texto: str = "") -> tuple[Cinta, list[dict], list[str]]:
    """Data unica + texto pegado (pisa el mismo tag). No escribe el archivo."""
    if not DATA_UNICA.exists():
        raise FileNotFoundError(f"no esta la data unificada: {DATA_UNICA}")
    orden, bloques = _leer_bloques(DATA_UNICA)
    pegadas: list[str] = []
    if extra_texto and extra_texto.strip():
        o2, b2 = leer_bloques_texto(extra_texto)
        pegadas = list(o2)
        orden, bloques = mezclar_bloques(orden, bloques, o2, b2)
    cinta, abiertas = cinta_desde_bloques(orden, bloques)
    return cinta, abiertas, pegadas


def cargar_crudo() -> Cinta:
    """Un solo archivo: cinta G/R por hora (data unificada de la caja)."""
    cinta, _abiertas, _pegadas = cargar_ingesta("")
    return cinta


def escribir_cinta(orden: list[str], bloques: dict[str, list[str]], path: Path | None = None) -> Path:
    """ Reescribe la data unica en orden cronologico. """
    dest = path or DATA_UNICA
    tags = list(orden)
    tags.sort(key=_parse_tag_key)
    lineas: list[str] = []
    for tag in tags:
        lineas.append(tag)
        lineas.extend(bloques.get(tag) or [])
        lineas.append("")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lineas).rstrip() + "\n", encoding="utf-8")
    return dest


def guardar_pegado(texto: str) -> tuple[list[str], list[dict]]:
    """Agrega a la cinta oficial solo horas CERRADAS. Las abiertas no se escriben.

    Returns:
        (tags_guardadas, alertas_ingesta) — alertas solo para horas con fallo detectado.
    """
    from src.alertas_ingesta import auditar_texto_pegado, registrar_alertas

    if not (texto or "").strip():
        return [], []
    alertas = auditar_texto_pegado(texto)
    o2, b2 = leer_bloques_texto(texto)
    cinta_tmp, abiertas = cinta_desde_bloques(o2, b2)
    abiertas_set = {a["tag"] for a in abiertas}
    cerradas = [t for t in o2 if t in cinta_tmp.horas and t not in abiertas_set]
    if not cerradas:
        if alertas:
            registrar_alertas(alertas, origen="ingesta_sin_cierre")
        return [], alertas
    extra_b = {t: list(b2[t]) for t in cerradas}
    if not DATA_UNICA.exists():
        escribir_cinta(cerradas, extra_b)
        if alertas:
            registrar_alertas(alertas)
        return list(cerradas), alertas
    orden, bloques = _leer_bloques(DATA_UNICA)
    nuevas = [
        t for t in cerradas if t not in bloques or list(bloques[t]) != extra_b[t]
    ]
    if nuevas:
        extra_nuevas = {t: extra_b[t] for t in nuevas}
        orden, bloques = mezclar_bloques(orden, bloques, nuevas, extra_nuevas)
        escribir_cinta(orden, bloques)
    if alertas:
        registrar_alertas(alertas)
    return list(cerradas), alertas
