"""Recordatorios con fecha y hora en datos/recordatorios.json. Cada uno se dispara una sola vez."""
from datetime import date, datetime

from jarvis import datos, secretos

ARCHIVO = "recordatorios.json"
MAX_CARACTERES = 300
# registro: {"id": int, "texto": str, "cuando": "AAAA-MM-DDTHH:MM:SS", "creado": "...", "estado": "pendiente"|"disparado"}
#           al dispararse se añade "disparado": "AAAA-MM-DDTHH:MM:SS". Hora local, sin zona horaria.
# ponytail: los disparados se acumulan (purgar los de más de 30 días) y no hay zona horaria; el aviso llega tarde
# si Jarvis estaba cerrado, pero llega una sola vez.


def cargar() -> list[dict]:
    return datos.leer_lista(ARCHIVO)


def momento(r: dict) -> datetime:
    return datetime.fromisoformat(r["cuando"])


def hora_legible(r: dict) -> str:
    return momento(r).strftime("%Y-%m-%d %H:%M")


def aviso(r: dict) -> str:
    return f"Recordatorio ({hora_legible(r)}): {r['texto']}"


def crear(texto: str, cuando: datetime, ahora: datetime) -> dict:
    limpio = " ".join(texto.split())
    if not limpio:
        raise ValueError("falta el texto del recordatorio.")
    if len(limpio) > MAX_CARACTERES:
        raise ValueError(f"el recordatorio es demasiado largo (máximo {MAX_CARACTERES} caracteres).")
    tipo = secretos.detectar(limpio)
    if tipo:
        raise ValueError(secretos.rechazo(tipo))
    if cuando <= ahora:
        raise ValueError(f"esa hora ya pasó ({cuando:%Y-%m-%d %H:%M}).")
    with datos.cerrojo:
        lista = cargar()
        r = {"id": max((r["id"] for r in lista), default=0) + 1, "texto": limpio,
             "cuando": cuando.isoformat(timespec="seconds"), "creado": ahora.isoformat(timespec="seconds"),
             "estado": "pendiente"}
        datos.escribir_lista(ARCHIVO, lista + [r])
        return r


def pendientes() -> list[dict]:
    return sorted((r for r in cargar() if r["estado"] == "pendiente"), key=momento)


def del_dia(dia: date) -> list[dict]:
    return sorted((r for r in cargar() if momento(r).date() == dia), key=momento)


def cancelar(id_recordatorio: int, texto: str) -> dict:
    with datos.cerrojo:
        lista = cargar()
        r = next((r for r in lista if r["id"] == id_recordatorio and r["estado"] == "pendiente"), None)
        if r is None:
            raise ValueError(f"no hay ningún recordatorio pendiente con id {id_recordatorio}.")
        if " ".join(texto.split()).casefold() != r["texto"].casefold():
            raise ValueError(f"el recordatorio {id_recordatorio} no dice eso; dice: '{r['texto']}'. No cancelé nada.")
        lista.remove(r)
        datos.escribir_lista(ARCHIVO, lista)
        return r


def vencidos(ahora: datetime) -> list[dict]:
    # Sin reloj propio: la terminal, la voz y la UI le pasan la hora.
    with datos.cerrojo:
        lista = cargar()
        listos = sorted((r for r in lista if r["estado"] == "pendiente" and momento(r) <= ahora), key=momento)
        if not listos:
            return []  # sin nada que disparar no se escribe
        for r in listos:
            r["estado"] = "disparado"
            r["disparado"] = ahora.isoformat(timespec="seconds")
        datos.escribir_lista(ARCHIVO, lista)  # antes de devolver: como mucho un aviso aunque Jarvis se caiga
        return listos
