"""Gmail: buscar correos (solo metadatos y resumen) y enviar a una dirección."""
import base64
import html
from email.message import EmailMessage
from typing import Protocol
from urllib.parse import quote

from jarvis.integrations import google

URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
CABECERAS = ["From", "Subject", "Date"]


class ClienteCorreo(Protocol):
    def buscar(self, consulta: str, maximo: int) -> list[dict]: ...  # [{"id", "de", "asunto", "fecha", "resumen"}]
    def enviar(self, para: str, asunto: str, cuerpo: str) -> str: ...  # id del mensaje enviado


def normalizar_mensaje(mensaje: dict) -> dict:
    c = {h["name"].casefold(): h["value"] for h in mensaje.get("payload", {}).get("headers", [])}
    return {"id": mensaje.get("id", ""), "de": c.get("from", ""), "asunto": c.get("subject") or "(sin asunto)",
            "fecha": c.get("date", ""), "resumen": html.unescape(mensaje.get("snippet", ""))}


class ClienteGoogleCorreo:
    """Cumple ClienteCorreo; solo habla con google.pedir."""

    def buscar(self, consulta: str, maximo: int) -> list[dict]:
        lista = google.pedir("GET", URL, params={"q": consulta, "maxResults": maximo})
        # ponytail: una petición por correo (N+1); con 5 basta. Para más, usar la API batch de Gmail.
        return [normalizar_mensaje(google.pedir("GET", f"{URL}/{quote(m['id'], safe='')}",
                                                params={"format": "metadata", "metadataHeaders": CABECERAS}))
                for m in lista.get("messages", [])[:maximo]]

    def enviar(self, para: str, asunto: str, cuerpo: str) -> str:
        m = EmailMessage()  # la política por defecto rechaza saltos de línea en las cabeceras
        m["To"] = para
        m["Subject"] = asunto
        m.set_content(cuerpo)
        raw = base64.urlsafe_b64encode(m.as_bytes()).decode("ascii")
        return google.pedir("POST", f"{URL}/send", cuerpo={"raw": raw}).get("id", "")


def obtener_cliente() -> ClienteCorreo:
    return ClienteGoogleCorreo()
