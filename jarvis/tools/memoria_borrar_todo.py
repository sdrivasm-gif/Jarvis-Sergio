"""Borra TODOS los recuerdos. Siempre pide confirmación."""
from jarvis import memoria

NOMBRE = "memoria_borrar_todo"
DESCRIPCION = "Borra TODOS los recuerdos de la memoria. Solo si el señor lo pide expresamente. Requiere confirmación."
ESQUEMA = {"type": "object", "properties": {}, "required": []}
requiere_confirmacion = True  # borra toda la memoria


def ejecutar() -> str:
    # ponytail: la confirmación no muestra cuántos recuerdos se borrarán; pasarlo al texto de confirmación.
    try:
        n = memoria.borrar_todo()
    except ValueError as e:
        return f"Error: {e}"
    return f"Borré los {n} recuerdo(s) de la memoria." if n else "No había recuerdos que borrar."
