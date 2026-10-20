"""Recordatorios: crear o listar (la lógica está en jarvis/recordatorios.py)."""
from datetime import datetime, timedelta

from jarvis import recordatorios

NOMBRE = "recordatorios"
DESCRIPCION = ("Recordatorios con fecha y hora. accion='crear' con texto y, o bien cuando ('AAAA-MM-DD HH:MM', hora local), "
               "o bien en_minutos (solo uno de los dos); o 'listar' los pendientes. Jarvis avisa una sola vez al llegar la hora.")
ESQUEMA = {"type": "object",
           "properties": {"accion": {"type": "string", "enum": ["crear", "listar"]},
                          "texto": {"type": "string", "description": "Qué hay que recordar."},
                          "cuando": {"type": "string", "description": "Fecha y hora local: AAAA-MM-DD HH:MM."},
                          "en_minutos": {"type": "integer", "description": "Dentro de cuántos minutos, en lugar de cuando."}},
           "required": ["accion"]}
requiere_confirmacion = False  # solo escribe en la carpeta de datos; cancelar va aparte y sí confirma
MAX_MINUTOS = 525600
MAX_LISTADO = 20


def ahora() -> datetime:
    return datetime.now().replace(microsecond=0)  # los tests lo parchean


def crear(texto: str, cuando: str, en_minutos) -> str:
    t = ahora()
    texto_cuando = str(cuando or "").strip()  # null del modelo = sin cuando
    hay_cuando = bool(texto_cuando)
    hay_minutos = en_minutos not in (None, "")
    if hay_cuando == hay_minutos:
        return "Error: indica cuándo con cuando ('AAAA-MM-DD HH:MM') o con en_minutos, solo uno de los dos."
    if hay_cuando:
        try:
            momento = datetime.strptime(texto_cuando.replace("T", " "), "%Y-%m-%d %H:%M")
        except ValueError:
            return f"Error: cuando debe tener el formato AAAA-MM-DD HH:MM (recibí '{cuando}')."
    else:
        try:
            n = int(en_minutos)
        except (TypeError, ValueError):
            n = 0
        if not 1 <= n <= MAX_MINUTOS:
            return f"Error: en_minutos debe ser un número entero entre 1 y {MAX_MINUTOS}."
        momento = t + timedelta(minutes=n)
    r = recordatorios.crear(texto, momento, t)
    return f"Recordatorio creado (id {r['id']}) para el {recordatorios.hora_legible(r)}: {r['texto']}"


def ejecutar(accion: str, texto: str = "", cuando: str = "", en_minutos: int | None = None) -> str:
    try:
        if accion == "crear":
            return crear(texto, cuando, en_minutos)
        if accion == "listar":
            pendientes = recordatorios.pendientes()
            if not pendientes:
                return "No hay recordatorios pendientes."
            return "\n".join(["Recordatorios pendientes:", *(
                f"- [{r['id']}] {recordatorios.hora_legible(r)} — {r['texto']}" for r in pendientes[:MAX_LISTADO])])
        return f"Error: acción desconocida '{accion}'; usa crear o listar."
    except ValueError as e:
        return f"Error: {e}"
