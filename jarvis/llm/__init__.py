"""Capa del proveedor del modelo. El resto de Jarvis solo conoce `Cliente`."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from jarvis.config import Config


@dataclass
class LlamadaHerramienta:
    id: str
    nombre: str
    argumentos: dict


@dataclass
class Respuesta:
    texto: str = ""
    llamadas: list[LlamadaHerramienta] = field(default_factory=list)


class Cliente(Protocol):
    def responder(self, mensajes: list[dict], herramientas: list[dict], sistema: str) -> Respuesta: ...


def crear_cliente(config: Config) -> Cliente:
    # Import perezoso: solo se carga el SDK del proveedor elegido.
    if config.proveedor == "claude-cli":
        from jarvis.llm.claude_cli import ClienteClaudeCLI

        return ClienteClaudeCLI(config.modelo, config.esfuerzo)
    if config.proveedor == "claude":
        from jarvis.llm.claude import ClienteClaude

        return ClienteClaude(config.clave, config.modelo)
    if config.proveedor == "openrouter":
        from jarvis.llm.openrouter import ClienteOpenRouter

        return ClienteOpenRouter(config.clave, config.modelo)
    raise ValueError(f"Proveedor desconocido: {config.proveedor}")
