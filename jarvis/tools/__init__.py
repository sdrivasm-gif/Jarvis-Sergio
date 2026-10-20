"""Registro de herramientas: cada *.py de esta carpeta (salvo los que empiezan por _) es una herramienta.

El contrato está documentado en hora.py, que sirve de plantilla.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

CARPETA_TOOLS = Path(__file__).parent
CONTRATO = ("NOMBRE", "DESCRIPCION", "ESQUEMA", "requiere_confirmacion", "ejecutar")


def cargar_herramientas(carpeta: Path = CARPETA_TOOLS) -> dict[str, ModuleType]:
    herramientas = {}
    # ponytail: sorted para un orden estable; si dos archivos repiten NOMBRE gana el último, avisar si llega a pasar.
    for archivo in sorted(carpeta.glob("*.py")):
        if archivo.name.startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location(f"jarvis.tools.{archivo.stem}", archivo)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        for atributo in CONTRATO:
            if not hasattr(modulo, atributo):
                raise ValueError(f"La herramienta {archivo.name} no define '{atributo}'.")
        if not callable(modulo.ejecutar):
            raise ValueError(f"La herramienta {archivo.name}: 'ejecutar' no es invocable.")
        herramientas[modulo.NOMBRE] = modulo
    return herramientas


def definiciones(herramientas: dict[str, ModuleType]) -> list[dict]:
    return [
        {"nombre": m.NOMBRE, "descripcion": m.DESCRIPCION, "esquema": m.ESQUEMA}
        for m in herramientas.values()
    ]
