"""Carpeta de datos local (JARVIS_DATOS) y listas JSON que sobreviven a los reinicios."""
import json
import os
import threading
from pathlib import Path

CARPETA_POR_DEFECTO = Path(__file__).resolve().parents[1] / "datos"
# ponytail: el cerrojo no coordina dos procesos de Jarvis; usar un archivo de bloqueo.
cerrojo = threading.Lock()  # lo toma quien lee-modifica-escribe; no es reentrante


def carpeta() -> Path:
    # ponytail: notas.py conserva su propia carpeta_datos (fase 2); unificarlas.
    return Path(os.environ.get("JARVIS_DATOS") or CARPETA_POR_DEFECTO)


def leer_lista(nombre: str) -> list[dict]:
    ruta = carpeta() / nombre
    if not ruta.exists():
        return []
    try:
        lista = json.loads(ruta.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        lista = None
    if not isinstance(lista, list) or not all(isinstance(e, dict) for e in lista):
        raise ValueError(f"el archivo de datos {nombre} está dañado; revísalo o bórralo.") from None
    return lista


def escribir_lista(nombre: str, lista: list[dict]) -> None:
    # ponytail: reescribe el archivo entero (vale para cientos de registros); usar sqlite si crece.
    carpeta().mkdir(parents=True, exist_ok=True)
    ruta = carpeta() / nombre
    tmp = ruta.with_name(nombre + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(json.dumps(lista, ensure_ascii=False, indent=1))
        f.flush()
        os.fsync(f.fileno())  # en disco antes del replace: un apagón no deja el archivo vacío
    os.replace(tmp, ruta)
