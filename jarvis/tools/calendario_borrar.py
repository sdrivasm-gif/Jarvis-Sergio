"""Borra un evento del calendario de Google por su id. Siempre pide confirmación."""
from jarvis.integrations import calendario, google

NOMBRE = "calendario_borrar"
DESCRIPCION = "Borra un evento del calendario de Google por su id (el que da calendario_eventos). Requiere confirmación."
ESQUEMA = {"type": "object",
           "properties": {"id_evento": {"type": "string",
                                        "description": "Id del evento, tal como lo da calendario_eventos."}},
           "required": ["id_evento"]}
requiere_confirmacion = True  # borra un evento (va a la papelera de Google Calendar)


def ejecutar(id_evento: str) -> str:
    # ponytail: el usuario confirma el id, no el título; mostrar el título resuelto antes de confirmar.
    i = id_evento.strip()
    if not google.ID_VALIDO.fullmatch(i):
        return f"Error: el id de evento '{id_evento}' no es válido."
    try:
        calendario.obtener_cliente().borrar_evento(i)
    except google.ErrorIntegracion as e:
        return f"Error: {e}"
    return f"Evento borrado (id: {i})."
