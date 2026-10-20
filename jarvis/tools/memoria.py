"""Memoria a largo plazo: guardar, buscar o listar recuerdos (la lógica está en jarvis/memoria.py)."""
from datetime import datetime

from jarvis import memoria

NOMBRE = "memoria"
DESCRIPCION = ("Memoria a largo plazo del señor. accion='guardar' con texto, solo cuando él pida recordar algo "
               "(preferencias, datos personales no sensibles); 'buscar' con texto; o 'listar'. "
               "Nunca guarda claves, contraseñas ni tarjetas.")
ESQUEMA = {"type": "object",
           "properties": {"accion": {"type": "string", "enum": ["guardar", "buscar", "listar"]},
                          "texto": {"type": "string",
                                    "description": "Lo que hay que recordar (guardar) o el texto a buscar (buscar)."}},
           "required": ["accion"]}
requiere_confirmacion = False  # solo escribe en la carpeta de datos; borrar va aparte y sí confirma
MAX_LISTADO = 20


def ahora() -> datetime:
    return datetime.now()  # los tests lo parchean


def linea(r: dict) -> str:
    return f"- [{r['id']}] {r['creado']}: {r['texto']}"


def ejecutar(accion: str, texto: str = "") -> str:
    try:
        if accion == "guardar":
            r, nuevo = memoria.guardar(texto, ahora())
            return f"{'Recordado' if nuevo else 'Ya lo tenía'} (id {r['id']}): {r['texto']}"
        if accion == "listar":
            recuerdos = memoria.cargar()
            if not recuerdos:
                return "No hay recuerdos guardados."
            return "\n".join([f"Recuerdos guardados: {len(recuerdos)}.", *map(linea, recuerdos[-MAX_LISTADO:])])
        if accion == "buscar":
            if not texto.strip():
                return "Error: falta el texto a buscar."
            encontrados = memoria.buscar(texto)
            if not encontrados:
                return f"No hay recuerdos que contengan '{texto}'."
            return "\n".join([f"Recuerdos que contienen '{texto}':", *map(linea, encontrados[-MAX_LISTADO:])])
        return f"Error: acción desconocida '{accion}'; usa guardar, buscar o listar."
    except ValueError as e:
        return f"Error: {e}"
