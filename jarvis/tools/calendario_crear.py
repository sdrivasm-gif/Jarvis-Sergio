"""Crea un evento en el calendario de Google. Siempre pide confirmación."""
from datetime import datetime, timedelta

from jarvis.integrations import calendario, google

NOMBRE = "calendario_crear"
DESCRIPCION = "Crea un evento en el calendario de Google del usuario. Requiere confirmación."
ESQUEMA = {"type": "object",
           "properties": {"titulo": {"type": "string", "description": "Título del evento."},
                          "inicio": {"type": "string",
                                     "description": "Fecha y hora local de inicio: AAAA-MM-DD HH:MM."},
                          "duracion_minutos": {"type": "integer",
                                               "description": "Duración en minutos; 60 si el usuario no dice otra."}},
           # duracion_minutos es obligatoria para que la confirmación siempre muestre cuánto dura el evento.
           "required": ["titulo", "inicio", "duracion_minutos"]}
requiere_confirmacion = True  # modifica el calendario
DURACION_POR_DEFECTO = 60
MAX_DURACION = 1440


def ejecutar(titulo: str, inicio: str, duracion_minutos: int = DURACION_POR_DEFECTO) -> str:
    titulo = " ".join(titulo.split())
    if not titulo:
        return "Error: falta el título del evento."
    try:
        comienzo = datetime.strptime(inicio.strip().replace("T", " "), "%Y-%m-%d %H:%M")
    except ValueError:
        return f"Error: inicio debe tener el formato AAAA-MM-DD HH:MM (recibí '{inicio}')."
    try:
        duracion = int(duracion_minutos)
    except (TypeError, ValueError):
        duracion = 0
    if not 1 <= duracion <= MAX_DURACION:
        return "Error: la duración debe ser un número entero de minutos entre 1 y 1440."
    # ponytail: si el evento acaba otro día, solo se muestra la hora de fin; no hay zona horaria
    # explícita (se usa la del equipo).
    fin = comienzo + timedelta(minutes=duracion)
    try:
        creado = calendario.obtener_cliente().crear_evento(titulo, comienzo, fin)
    except google.ErrorIntegracion as e:
        return f"Error: {e}"
    return f"Evento creado: {titulo}, {comienzo:%Y-%m-%d %H:%M}–{fin:%H:%M} (id: {creado['id']})."
