"""Abre una app instalada en Windows buscándola por nombre en la lista del menú Inicio (Get-StartApps)."""
import json
import os
import subprocess
import unicodedata

NOMBRE = "abrir_app"
DESCRIPCION = ("Abre una aplicación instalada en este equipo Windows por su nombre, tal como aparece "
               "en el menú Inicio (p. ej. 'Calculadora', 'Spotify'). Requiere confirmación del usuario.")
ESQUEMA = {
    "type": "object",
    "properties": {"nombre": {"type": "string", "description": "Nombre de la aplicación en el menú Inicio."}},
    "required": ["nombre"],
}
requiere_confirmacion = True  # abre un programa: efecto real fuera de la carpeta de datos
# Comando fijo: el nombre que pide el modelo nunca entra en él, solo se compara con la salida.
COMANDO_APPS = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                "[Console]::OutputEncoding = [Text.Encoding]::UTF8; Get-StartApps | ConvertTo-Json -Compress"]
TIMEOUT_APPS = 15
MAX_CANDIDATOS = 5
EXCLUIDAS = ("uninstall", "desinstal")


def listar_apps() -> list[dict]:
    # ponytail: lanza PowerShell en cada llamada (1-2 s); cachear la lista si molesta la espera.
    salida = subprocess.run(COMANDO_APPS, capture_output=True, timeout=TIMEOUT_APPS, check=True).stdout
    texto = salida.decode("utf-8-sig").strip()  # PowerShell puede anteponer BOM
    if not texto:
        return []
    apps = json.loads(texto)
    return apps if isinstance(apps, list) else [apps]  # con una sola app, ConvertTo-Json da un objeto suelto


def abrir(app_id: str) -> None:
    os.startfile("shell:AppsFolder\\" + app_id)  # por atributo, para que la guardia de los tests lo intercepte


def normalizar(texto: str) -> str:
    sin_tildes = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return sin_tildes.casefold().strip()


def ejecutar(nombre: str) -> str:
    buscado = normalizar(nombre)
    if not buscado:
        return "Error: falta el nombre de la aplicación."
    # ponytail: no abre desinstaladores por lista de palabras; el usuario confirma el nombre pedido,
    # no el AppID resuelto (mostrar la app resuelta antes de confirmar exigiría cambiar el bucle).
    apps = [a for a in listar_apps() if not any(x in normalizar(a["Name"]) for x in EXCLUIDAS)]
    candidatas = [a for a in apps if normalizar(a["Name"]) == buscado][:1]
    if not candidatas:
        candidatas = [a for a in apps if buscado in normalizar(a["Name"])]
    if not candidatas:
        return f"No encontré ninguna aplicación instalada llamada '{nombre}'."
    if len(candidatas) > 1:
        nombres = ", ".join(a["Name"] for a in candidatas[:MAX_CANDIDATOS])
        return f"Hay varias aplicaciones que coinciden con '{nombre}': {nombres}. ¿Cuál abro?"
    abrir(candidatas[0]["AppID"])
    return f"Abrí {candidatas[0]['Name']}."
