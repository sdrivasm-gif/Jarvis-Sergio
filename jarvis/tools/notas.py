"""Notas del usuario en un archivo de texto local (una nota por línea)."""
import os
from datetime import datetime
from pathlib import Path

NOMBRE = "notas"
DESCRIPCION = ("Guarda, lista o busca notas del usuario en un archivo local. "
               "accion='crear' con texto, 'listar', o 'buscar' con texto.")
ESQUEMA = {
    "type": "object",
    "properties": {
        "accion": {"type": "string", "enum": ["crear", "listar", "buscar"]},
        "texto": {"type": "string", "description": "Contenido de la nota (crear) o texto a buscar (buscar)."},
    },
    "required": ["accion"],
}
requiere_confirmacion = False  # solo escribe dentro de la carpeta de datos
CARPETA_DATOS_POR_DEFECTO = Path(__file__).resolve().parents[2] / "datos"
ARCHIVO = "notas.txt"
MAX_NOTAS = 20


def carpeta_datos() -> Path:
    return Path(os.environ.get("JARVIS_DATOS") or CARPETA_DATOS_POR_DEFECTO)


def ejecutar(accion: str, texto: str = "") -> str:
    ruta = carpeta_datos() / ARCHIVO
    if accion == "crear":
        limpio = " ".join(texto.split())
        if not limpio:
            return "Error: la nota está vacía."
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with ruta.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M} | {limpio}\n")
        return "Nota guardada."
    if accion not in ("listar", "buscar"):
        return f"Error: acción desconocida '{accion}'; usa crear, listar o buscar."
    if accion == "buscar" and not texto.strip():
        return "Error: falta el texto a buscar."
    lineas = ruta.read_text(encoding="utf-8").splitlines() if ruta.exists() else []
    if accion == "listar":
        # ponytail: solo las últimas 20, sin paginar ni borrar/editar; añadir paginación y acciones si hacen falta
        return "\n".join(lineas[-MAX_NOTAS:]) if lineas else "No hay notas."
    coinciden = [l for l in lineas if texto.casefold() in l.casefold()]
    if not coinciden:
        return f"No hay notas que contengan '{texto}'."
    return "\n".join(coinciden[-MAX_NOTAS:])
