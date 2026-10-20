"""Lista los eventos de un día del calendario de Google."""
from datetime import date, timedelta

from jarvis.integrations import calendario, google

NOMBRE = "calendario_eventos"
DESCRIPCION = ("Lista los eventos de un día del calendario de Google del usuario (hoy por defecto), "
               "con hora, título e id.")
ESQUEMA = {"type": "object",
           "properties": {"fecha": {"type": "string",
                                    "description": "Día AAAA-MM-DD, o 'hoy' o 'mañana'. Por defecto, hoy."}},
           "required": []}
requiere_confirmacion = False  # solo lee


def hoy() -> date:
    return date.today()  # los tests lo parchean


def resolver_fecha(fecha: str) -> date | None:
    texto = fecha.strip().casefold()
    if texto in ("", "hoy"):
        return hoy()
    if texto in ("mañana", "manana"):
        return hoy() + timedelta(days=1)
    try:
        return date.fromisoformat(texto)
    except ValueError:
        return None


def ejecutar(fecha: str = "") -> str:
    dia = resolver_fecha(fecha)
    if dia is None:
        return f"Error: la fecha '{fecha}' no es válida; usa AAAA-MM-DD, 'hoy' o 'mañana'."
    try:
        eventos = calendario.obtener_cliente().eventos_del_dia(dia)
    except google.ErrorIntegracion as e:
        return f"Error: {e}"
    if not eventos:
        return f"No hay eventos el {dia.isoformat()}."
    lineas = [f"- {e['inicio']}–{e['fin']} {e['titulo']} (id: {e['id']})" if e["inicio"]
              else f"- Todo el día: {e['titulo']} (id: {e['id']})" for e in eventos]
    return "\n".join([f"Eventos del {dia.isoformat()}:", *lineas])
