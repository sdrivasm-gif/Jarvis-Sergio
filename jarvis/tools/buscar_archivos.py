"""Busca archivos por nombre (nunca abre ni lee su contenido)."""
import fnmatch
import os
from pathlib import Path

NOMBRE = "buscar_archivos"
DESCRIPCION = ("Busca archivos por su nombre dentro de una carpeta y sus subcarpetas. Solo devuelve rutas: "
               "no lee el contenido. Admite comodines como *.pdf.")
ESQUEMA = {
    "type": "object",
    "properties": {
        "carpeta": {"type": "string", "description": "Carpeta donde buscar, p. ej. C:\\Users\\rivas\\Documents o ~/Documents."},
        "patron": {"type": "string", "description": "Parte del nombre o comodín (*.pdf); no distingue mayúsculas."},
    },
    "required": ["carpeta", "patron"],
}
requiere_confirmacion = False  # solo lista nombres; no lee ni cambia nada
MAX_RESULTADOS = 50
MAX_PROFUNDIDAD = 5


def es_env(nombre: str) -> bool:
    n = nombre.casefold()
    return n.startswith(".env") or n.endswith(".env")


def ejecutar(carpeta: str, patron: str) -> str:
    if not patron.strip():
        return "Error: falta el patrón de búsqueda."
    base = Path(carpeta).expanduser()
    if not base.is_dir():
        return f"Error: la carpeta '{carpeta}' no existe."
    p = patron.strip().casefold()
    if not any(c in p for c in "*?["):
        p = f"*{p}*"
    # ponytail: sin tope de tiempo ni de carpetas visitadas; si buscar en C:\ tarda, añadir uno
    encontrados = []
    # ponytail: os.walk no entra en symlinks pero sí en junctions de Windows (solo lo acota MAX_PROFUNDIDAD);
    # si un junction provoca bucles o salidas de la carpeta, saltar los dirs con os.path.isjunction (3.12+).
    for raiz, dirs, archivos in os.walk(base):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        if len(Path(raiz).relative_to(base).parts) >= MAX_PROFUNDIDAD:
            dirs.clear()
        for nombre in archivos:
            if not es_env(nombre) and fnmatch.fnmatchcase(nombre.casefold(), p):
                encontrados.append(str(Path(raiz) / nombre))
        if len(encontrados) > MAX_RESULTADOS:
            break
    if not encontrados:
        return f"No encontré archivos que coincidan con '{patron}' en '{carpeta}'."
    hay_mas = len(encontrados) > MAX_RESULTADOS
    visibles = sorted(encontrados[:MAX_RESULTADOS])
    salida = [f"Encontré {len(visibles)} archivo(s):", *visibles]
    if hay_mas:
        salida.append("(hay más; acota la búsqueda)")
    return "\n".join(salida)
