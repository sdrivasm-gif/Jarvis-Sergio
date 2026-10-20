"""Busca archivos en Google Drive por parte del nombre."""
from jarvis.integrations import drive, google

NOMBRE = "drive_buscar"
DESCRIPCION = "Busca archivos en el Google Drive del usuario por parte del nombre. Devuelve hasta 10 con tipo, enlace e id."
ESQUEMA = {"type": "object",
           "properties": {"nombre": {"type": "string", "description": "Parte del nombre del archivo."}},
           "required": ["nombre"]}
requiere_confirmacion = False  # solo lee
MAX_ARCHIVOS = 10


def ejecutar(nombre: str) -> str:
    if not nombre.strip():
        return "Error: falta el nombre a buscar."
    try:
        archivos = drive.obtener_cliente().buscar(nombre.strip(), MAX_ARCHIVOS)
    except google.ErrorIntegracion as e:
        return f"Error: {e}"
    if not archivos:
        return f"No encontré archivos en Drive con '{nombre}'."
    lineas = [f"- {a['nombre']} ({a['tipo']}) — {a['enlace']} (id: {a['id']})" for a in archivos]
    return "\n".join([f"Encontré {len(archivos)} archivo(s) en Drive:", *lineas])
