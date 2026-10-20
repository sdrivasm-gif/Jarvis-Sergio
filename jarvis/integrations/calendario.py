"""Google Calendar: eventos de un día, crear y borrar (calendario principal)."""
import urllib.parse
from datetime import date, datetime, time, timedelta
from typing import Protocol

from jarvis.integrations import google

URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
# ponytail: solo el calendario principal y un máximo de 50 eventos por día, sin paginar.
MAX_EVENTOS = 50


class ClienteCalendario(Protocol):
    def eventos_del_dia(self, dia: date) -> list[dict]: ...  # [{"id", "titulo", "inicio", "fin"}]; "HH:MM" locales, "" si es de todo el día
    def crear_evento(self, titulo: str, inicio: datetime, fin: datetime) -> dict: ...  # {"id": str}; naive, hora local
    def borrar_evento(self, id_evento: str) -> None: ...


def hora_local(momento: dict) -> str:
    valor = momento.get("dateTime")
    return datetime.fromisoformat(valor).astimezone().strftime("%H:%M") if valor else ""


def normalizar_evento(evento: dict) -> dict:
    return {"id": evento.get("id", ""), "titulo": evento.get("summary") or "(sin título)",
            "inicio": hora_local(evento.get("start", {})), "fin": hora_local(evento.get("end", {}))}


class ClienteGoogleCalendario:
    """Cumple ClienteCalendario; solo habla con google.pedir."""

    def eventos_del_dia(self, dia: date) -> list[dict]:
        desde = datetime.combine(dia, time.min).astimezone()
        hasta = datetime.combine(dia + timedelta(days=1), time.min).astimezone()
        datos = google.pedir("GET", URL, params={
            "timeMin": desde.isoformat(), "timeMax": hasta.isoformat(),
            "singleEvents": "true", "orderBy": "startTime", "maxResults": MAX_EVENTOS})
        return [normalizar_evento(e) for e in datos.get("items", [])]

    def crear_evento(self, titulo: str, inicio: datetime, fin: datetime) -> dict:
        datos = google.pedir("POST", URL, cuerpo={
            "summary": titulo,
            "start": {"dateTime": inicio.astimezone().isoformat()},
            "end": {"dateTime": fin.astimezone().isoformat()}})
        return {"id": datos.get("id", "")}

    def borrar_evento(self, id_evento: str) -> None:
        google.pedir("DELETE", URL + "/" + urllib.parse.quote(id_evento, safe=""))


def obtener_cliente() -> ClienteCalendario:
    return ClienteGoogleCalendario()  # sin red ni lectura de .env: eso pasa en la primera petición
