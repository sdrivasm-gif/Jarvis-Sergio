"""Configuración de Jarvis a partir de un diccionario de entorno (os.environ en main, dicts en los tests)."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from jarvis.llm.openrouter import MODELO_OPENROUTER_POR_DEFECTO

# proveedor -> (variable de la clave o None si no usa clave, modelo por defecto)
PROVEEDORES = {
    "claude-cli": (None, "sonnet"),
    "claude": ("ANTHROPIC_API_KEY", "claude-sonnet-5-5"),
    "openrouter": ("OPENROUTER_API_KEY", MODELO_OPENROUTER_POR_DEFECTO),
}
PROVEEDOR_POR_DEFECTO = "claude-cli"
ESFUERZO_POR_DEFECTO = "medium"  # solo lo usa claude-cli


class ErrorConfig(Exception):
    pass


@dataclass
class Config:
    proveedor: str
    modelo: str
    clave: str = field(repr=False)  # nunca se imprime ni se registra en logs
    esfuerzo: str = ESFUERZO_POR_DEFECTO


def cargar_config(entorno: Mapping[str, str]) -> Config:
    # ponytail: JARVIS_PROVIDER sigue valiendo como alias antiguo de LLM_PROVIDER; quitarlo cuando nadie lo use.
    proveedor = entorno.get("LLM_PROVIDER") or entorno.get("JARVIS_PROVIDER") or PROVEEDOR_POR_DEFECTO
    if proveedor not in PROVEEDORES:
        raise ErrorConfig(
            f"LLM_PROVIDER='{proveedor}' no es válido; usa 'claude-cli', 'claude' u 'openrouter' en .env."
        )
    variable, modelo_por_defecto = PROVEEDORES[proveedor]
    clave = entorno.get(variable, "").strip() if variable else ""
    if variable and not clave:
        raise ErrorConfig(f"Falta {variable}: ponla en .env para usar el proveedor '{proveedor}'.")
    return Config(proveedor, entorno.get("JARVIS_MODEL") or modelo_por_defecto, clave,
                  entorno.get("JARVIS_EFFORT") or ESFUERZO_POR_DEFECTO)
