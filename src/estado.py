"""Estado interno: se actualiza al cerrar cada hora civil."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from .lectores import HoraCruda, arranque_proxima

PRIMERA_UTIL = "h10-230726"
VENTANA_CILINDRO = 4
MAX_HORAS_GUARDADAS = 12


def parse_tag(tag: str) -> datetime:
    cuerpo = tag[1:]
    hora_s, ddmmyy = cuerpo.split("-")
    dd = int(ddmmyy[0:2])
    mm = int(ddmmyy[2:4])
    yy = int(ddmmyy[4:6])
    return datetime(2000 + yy, mm, dd, int(hora_s))


def format_tag(dt: datetime) -> str:
    return f"h{dt.hour}-{dt.strftime('%d%m%y')}"


def siguiente_tag(tag: str) -> str:
    return format_tag(parse_tag(tag) + timedelta(hours=1))


@dataclass
class HoraCerrada:
    tag: str
    nucleo: list[int]
    extra: list[int]
    holgada: list[int]
    n_tiros: int
    n_largos: int
    nG: int
    last_start_s: int | None = None
    last_dur_s: int | None = None
    last_largo: bool | None = None
    last_color: str | None = None
    t0_proxima: int = 0


@dataclass
class Estado:
    horas: list[HoraCerrada] = field(default_factory=list)
    ultimo_boleto: dict | None = None

    def n_cerradas(self) -> int:
        return len(self.horas)

    def calentamiento(self) -> int:
        """0 = sin columnas; 1–3 = cilindro incompleto; 4+ = ventana llena."""
        return min(self.n_cerradas(), VENTANA_CILINDRO)

    def ultima(self) -> HoraCerrada | None:
        return self.horas[-1] if self.horas else None

    def cola(self, n: int) -> list[HoraCerrada]:
        if n <= 0:
            return []
        return self.horas[-n:]

    def cerrar(self, cruda: HoraCruda) -> HoraCerrada:
        if self.horas and self.horas[-1].tag == cruda.tag:
            self.horas.pop()
        last = cruda.tiros_nucleo[-1] if cruda.tiros_nucleo else None
        cerrada = HoraCerrada(
            tag=cruda.tag,
            nucleo=list(cruda.nucleo),
            extra=list(cruda.extra),
            holgada=list(cruda.holgada),
            n_tiros=len(cruda.tiros_nucleo),
            n_largos=cruda.n_largos,
            nG=len(cruda.nucleo),
            last_start_s=last.start_s if last else None,
            last_dur_s=last.dur_s if last else None,
            last_largo=last.largo if last else None,
            last_color=last.color if last else None,
            t0_proxima=arranque_proxima(last) if last else 0,
        )
        self.horas.append(cerrada)
        if len(self.horas) > MAX_HORAS_GUARDADAS:
            self.horas = self.horas[-MAX_HORAS_GUARDADAS:]
        return cerrada

    def guardar(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "maquina": "hilo-corto",
            "horas": [asdict(h) for h in self.horas],
            "ultimo_boleto": self.ultimo_boleto,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def cargar(cls, path: Path) -> Estado:
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        horas = [HoraCerrada(**h) for h in raw.get("horas", [])]
        return cls(horas=horas, ultimo_boleto=raw.get("ultimo_boleto"))
