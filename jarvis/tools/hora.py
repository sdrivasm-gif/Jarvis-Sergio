"""Herramienta de ejemplo y PLANTILLA para herramientas nuevas.

Para agregar una herramienta, copia este archivo a jarvis/tools/<nombre>.py y cambia:
- NOMBRE: identificador único que verá el modelo.
- DESCRIPCION: qué hace, en una frase; el modelo decide con ella cuándo usarla.
- ESQUEMA: JSON Schema de los argumentos de ejecutar().
- requiere_confirmacion: True si la acción tiene efectos reales (enviar, borrar, comprar,
  publicar, modificar calendario). Entonces el bucle pide un "s" explícito antes de ejecutarla.
- ejecutar(**args) -> str: hace el trabajo y devuelve texto para el modelo.
No hay que tocar ningún otro archivo: jarvis/tools/__init__.py la descubre sola.
Los archivos que empiezan por _ se ignoran.
"""
from datetime import datetime

NOMBRE = "hora"
DESCRIPCION = "Devuelve la fecha y hora local actuales."
ESQUEMA = {"type": "object", "properties": {}, "required": []}
requiere_confirmacion = False


def ejecutar(**args) -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")
