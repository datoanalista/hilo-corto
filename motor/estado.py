"""
Estado interno: tablero de las últimas N horas.
Se actualiza al cerrar cada hora.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Set, Optional


class TableroEstado:
    """Ventana deslizante de casillas G del núcleo (foto estricta)."""

    def __init__(self, ventana: int = 4, path: Optional[Path] = None):
        self.ventana = ventana
        self.path = path or Path("estado/tablero.json")
        # lista de (tag, set de casillas), más reciente al final
        self.historial: List[tuple[str, Set[int]]] = []
        self.ultimo_tag: Optional[str] = None
        self._cargar()

    def _cargar(self) -> None:
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.historial = [
                (item["tag"], set(item["casillas"])) for item in data.get("historial", [])
            ]
            self.ultimo_tag = data.get("ultimo_tag")
            self.ventana = data.get("ventana", self.ventana)

    def guardar(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ventana": self.ventana,
            "ultimo_tag": self.ultimo_tag,
            "historial": [
                {"tag": t, "casillas": sorted(c)} for t, c in self.historial
            ],
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        # escritura atómica + reintentos
        tmp = self.path.with_suffix(".tmp")
        for intento in range(5):
            try:
                tmp.write_text(text, encoding="utf-8")
                tmp.replace(self.path)
                return
            except OSError:
                import time
                time.sleep(0.15 * (intento + 1))
        self.path.write_text(text, encoding="utf-8")

    def cerrar_hora(self, tag: str, casillas: Set[int]) -> None:
        """Incorpora la hora que acaba de cerrar."""
        if self.historial and self.historial[-1][0] == tag:
            self.historial[-1] = (tag, set(casillas))
        else:
            self.historial.append((tag, set(casillas)))
        if len(self.historial) > self.ventana + 2:
            self.historial = self.historial[-(self.ventana + 2):]
        self.ultimo_tag = tag
        self.guardar()

    def previas(self, n: int = 3) -> List[tuple[str, Set[int]]]:
        """Últimas n horas cerradas (más reciente primero)."""
        return list(reversed(self.historial[-n:])) if self.historial else []

    def n_horas(self) -> int:
        return len(self.historial)