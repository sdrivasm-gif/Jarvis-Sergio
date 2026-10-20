"""Cliente simulado para los tests: nunca llama a una API."""
from __future__ import annotations

import copy

from jarvis.llm import Respuesta


class ClienteFalso:
    def __init__(self, respuestas: list[Respuesta]):
        self._respuestas = list(respuestas)
        self.recibidos: list[dict] = []

    def responder(self, mensajes: list[dict], herramientas: list[dict], sistema: str) -> Respuesta:
        # Copia profunda: el bucle sigue mutando el historial después de la llamada.
        self.recibidos.append(copy.deepcopy(
            {"mensajes": mensajes, "herramientas": herramientas, "sistema": sistema}
        ))
        if not self._respuestas:
            raise RuntimeError("ClienteFalso sin respuestas")
        return self._respuestas.pop(0)
