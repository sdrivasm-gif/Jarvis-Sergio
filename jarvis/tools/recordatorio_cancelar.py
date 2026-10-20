"""Cancela UN recordatorio pendiente por id y texto exacto. Siempre pide confirmación."""
from jarvis import recordatorios

NOMBRE = "recordatorio_cancelar"
DESCRIPCION = ("Cancela UN recordatorio pendiente. Pide su id y su texto exacto, tal como los da recordatorios (listar). "
               "Requiere confirmación.")
ESQUEMA = {"type": "object",
           "properties": {"id_recordatorio": {"type": "integer", "description": "Id del recordatorio."},
                          "texto": {"type": "string", "description": "Texto del recordatorio tal como lo da recordatorios."}},
           "required": ["id_recordatorio", "texto"]}
requiere_confirmacion = True  # borra un recordatorio


def ejecutar(id_recordatorio: int, texto: str) -> str:
    try:
        n = int(id_recordatorio)
    except (TypeError, ValueError):
        return f"Error: el id '{id_recordatorio}' no es válido."
    try:
        r = recordatorios.cancelar(n, texto)
    except ValueError as e:
        return f"Error: {e}"
    return f"Recordatorio cancelado (id {r['id']}): {r['texto']} ({recordatorios.hora_legible(r)})."
