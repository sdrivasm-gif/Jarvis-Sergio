"""Google Drive: buscar archivos por nombre y compartir uno con una persona."""
from typing import Protocol
from urllib.parse import quote

from jarvis.integrations import google

URL = "https://www.googleapis.com/drive/v3/files"
CAMPOS = "files(id,name,mimeType,webViewLink)"


class ClienteDrive(Protocol):
    def buscar(self, nombre: str, maximo: int) -> list[dict]: ...  # [{"id", "nombre", "tipo", "enlace"}]
    def compartir(self, id_archivo: str, correo: str, rol: str) -> None: ...  # rol de Google: "reader" o "writer"


def escapar(texto: str) -> str:
    # Para la q de Drive: sin esto, una comilla en el nombre rompería (o ampliaría) la consulta.
    return texto.replace("\\", "\\\\").replace("'", "\\'")


class ClienteGoogleDrive:
    """Cumple ClienteDrive; solo habla con google.pedir."""

    def buscar(self, nombre: str, maximo: int) -> list[dict]:
        datos = google.pedir("GET", URL, params={"q": f"name contains '{escapar(nombre)}' and trashed = false",
                                                 "pageSize": maximo, "fields": CAMPOS})
        return [{"id": f.get("id", ""), "nombre": f.get("name", ""),
                 "tipo": f.get("mimeType", "").removeprefix("application/vnd.google-apps."),
                 "enlace": f.get("webViewLink", "")} for f in datos.get("files", [])]

    def compartir(self, id_archivo: str, correo: str, rol: str) -> None:
        google.pedir("POST", f"{URL}/{quote(id_archivo, safe='')}/permissions",
                     params={"sendNotificationEmail": "true"},
                     cuerpo={"type": "user", "role": rol, "emailAddress": correo})


def obtener_cliente() -> ClienteDrive:
    return ClienteGoogleDrive()
