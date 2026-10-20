"""Parte del día: devuelve los datos de hoy (eventos, correos, notas, recordatorios) para que el modelo los resuma."""
from datetime import datetime

from jarvis import hoy

NOMBRE = "parte_del_dia"
DESCRIPCION = ("Reúne el parte de hoy: eventos del calendario, correos sin leer, notas recientes y recordatorios del día. "
               "Devuelve los datos para que los resumas con tu tono, en pocas frases.")
ESQUEMA = {"type": "object", "properties": {}, "required": []}
requiere_confirmacion = False  # solo lee


def ahora() -> datetime:
    return datetime.now()  # los tests lo parchean


def ejecutar() -> str:
    return hoy.envolver(hoy.reunir(ahora()))
