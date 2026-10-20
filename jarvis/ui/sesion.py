"""Estado compartido entre conversar (hilo principal) y el servidor de la UI (un hilo por petición)."""
from __future__ import annotations

import contextlib
import math
import queue
import secrets
import threading
import time

from jarvis import voz
from jarvis.bucle import legible, texto_confirmacion

# ponytail: con voz, el texto de la página espera a que termine la escucha en curso (≤ 8 s); cortar la escucha
#   cuando llegue texto.
# ponytail: los subtítulos son texto plano (sin markdown); pintar negritas y listas construyendo el DOM a mano.
# ponytail: el historial de conversar sigue sin límite; recortarlo en bucle.py cuando crezca.
ESTADOS = ("reposo", "escuchando", "pensando", "hablando")
QUIENES = ("usuario", "jarvis", "aviso", "sistema")
MAX_MENSAJES = 200            # subtítulos guardados (los más recientes)
ESPERA_ENTRADA = 1.0          # s: sin texto, entrada devuelve "" y conversar revisa los recordatorios
TIEMPO_CONFIRMACION = 60.0    # s sin respuesta → NO
TROZO_ESPERA = 0.5            # s: las esperas van en trozos para que Ctrl+C entre en Windows
CONFIRMA_EN_PANTALLA = "Necesito tu confirmación en la pantalla."
VOZ_APAGADA = "La voz se apagó; sigo solo con texto."


class Sesion:
    def __init__(self, token: str | None = None, espera_entrada: float = ESPERA_ENTRADA,
                 tiempo_confirmacion: float = TIEMPO_CONFIRMACION):
        self.token = token or secrets.token_urlsafe(32)
        self.espera_entrada = espera_entrada
        self.tiempo_confirmacion = tiempo_confirmacion
        self.estado = "reposo"
        self.ocupado = False
        self.voz = False
        self.cerrada = False
        self._cerrojo = threading.RLock()
        self._cola: queue.Queue[str] = queue.Queue()
        self._mensajes: list[dict] = []
        self._ultimo = 0
        self._confirmacion: dict | None = None
        self._id_confirmacion = 0
        self._respuesta = None
        self._respondida = threading.Event()

    def poner_estado(self, estado: str) -> None:
        if estado not in ESTADOS:
            raise ValueError(f"estado desconocido: {estado}")
        with self._cerrojo:
            self.estado = estado

    @contextlib.contextmanager
    def durante(self, estado: str):
        with self._cerrojo:
            anterior = self.estado
        self.poner_estado(estado)
        try:
            yield
        finally:
            self.poner_estado(anterior)

    def anotar(self, quien: str, texto) -> dict:
        if quien not in QUIENES:
            raise ValueError(f"quién desconocido: {quien}")
        with self._cerrojo:
            self._ultimo += 1
            mensaje = {"id": self._ultimo, "quien": quien, "texto": str(texto)}
            self._mensajes.append(mensaje)
            del self._mensajes[:-MAX_MENSAJES]
            return mensaje

    def anotar_linea(self, linea: str) -> None:
        if linea.startswith("jarvis> Recordatorio ("):
            self.anotar("aviso", linea.removeprefix("jarvis> "))
        elif linea.startswith("jarvis> "):
            self.anotar("jarvis", linea.removeprefix("jarvis> "))
        elif linea.startswith("tú (voz)> "):
            self.anotar("usuario", linea.removeprefix("tú (voz)> "))
        else:
            self.anotar("sistema", linea)

    def enviar(self, texto: str) -> bool:
        with self._cerrojo:
            if self.cerrada or self.ocupado or not self._cola.empty():
                return False
            self.ocupado = True
            self.anotar("usuario", texto.strip())
            self._cola.put(texto.strip())
            return True

    def entrada(self, prompt: str = "", espera: float | None = None) -> str:
        with self._cerrojo:
            if self.cerrada:
                raise EOFError  # conversar se despide
            if self._cola.empty():
                self.ocupado = False
            self.estado = "reposo"
        espera = self.espera_entrada if espera is None else espera
        try:
            texto = self._cola.get(timeout=espera) if espera > 0 else self._cola.get_nowait()
        except queue.Empty:
            return ""
        return self.ocupar(texto)

    def ocupar(self, texto: str) -> str:
        if texto:
            with self._cerrojo:
                self.ocupado = True
                self.estado = "pensando"
        return texto

    def confirmar(self, nombre: str, argumentos: dict) -> bool:
        texto = texto_confirmacion(nombre, argumentos).removesuffix("[s/N] ").rstrip("\n")
        segundos = math.ceil(self.tiempo_confirmacion)
        with self._cerrojo:
            self._id_confirmacion += 1
            self._confirmacion = {"id": self._id_confirmacion, "texto": texto, "segundos": segundos}
            self._respuesta = None
            self._respondida.clear()
        limite = time.monotonic() + self.tiempo_confirmacion
        try:
            while not self.cerrada and not self._respondida.is_set():
                resta = limite - time.monotonic()
                if resta <= 0:
                    break
                self._respondida.wait(min(TROZO_ESPERA, resta))
        finally:  # también con Ctrl+C: la confirmación desaparece de la página y la excepción sigue
            with self._cerrojo:
                respondida = self._respondida.is_set()
                si = respondida and self._respuesta is True
                self._confirmacion = None
        n = legible(nombre)
        if si:
            self.anotar("sistema", f"Confirmado: {n}.")
        elif respondida:
            self.anotar("sistema", f"Cancelado: {n}.")
        else:
            self.anotar("sistema", f"Sin respuesta en {segundos} s: {n} cancelado.")
        return si

    def responder(self, id_confirmacion, si) -> bool:
        with self._cerrojo:
            if (self._confirmacion is None or self._confirmacion["id"] != id_confirmacion
                    or self._respondida.is_set()):
                return False
            self._respuesta = si is True  # un "sí" o un 1 cuentan como NO
            self._respondida.set()
            return True

    def instantanea(self, desde: int = 0) -> dict:
        with self._cerrojo:
            pendiente = self._confirmacion is not None and not self._respondida.is_set()
            return {"estado": self.estado, "ocupado": self.ocupado, "voz": self.voz,
                    "confirmacion": dict(self._confirmacion) if pendiente else None,
                    "mensajes": [dict(m) for m in self._mensajes if m["id"] > desde],
                    "ultimo": self._ultimo}

    def cerrar(self) -> None:
        with self._cerrojo:
            self.cerrada = True


class OyenteConEstado:
    def __init__(self, oyente, sesion: Sesion):
        self.oyente, self.sesion = oyente, sesion

    def escuchar(self) -> str | None:
        with self.sesion.durante("escuchando"):
            return self.oyente.escuchar()


class HablanteConEstado:
    def __init__(self, hablante, sesion: Sesion):
        self.hablante, self.sesion = hablante, sesion

    def decir(self, texto: str) -> None:
        with self.sesion.durante("hablando"):
            self.hablante.decir(texto)


def piezas_ui(sesion: Sesion) -> dict:
    return {"entrada": sesion.entrada, "salida": sesion.anotar_linea, "confirmar": sesion.confirmar, "fragmento": None}


def piezas_ui_voz(sesion: Sesion, oyente, hablante, palabras: list[str]) -> dict:
    sesion.voz = True
    oyente = OyenteConEstado(oyente, sesion)
    hablante = HablanteConEstado(hablante, sesion)
    entrada_voz = voz.entrada_por_voz(oyente, hablante, palabras, sesion.anotar_linea)
    activa = True

    def entrada(prompt: str = "") -> str:
        nonlocal activa
        if not activa:
            return sesion.entrada(prompt)
        texto = sesion.entrada(prompt, espera=0)
        if texto:
            return texto  # lo escrito en la página tiene prioridad
        try:
            return sesion.ocupar(entrada_voz(prompt))
        except EOFError:
            if sesion.cerrada:
                raise
            activa = False  # el micrófono se rompió: Jarvis no se cierra, sigue con texto
            sesion.voz = False
            sesion.anotar("sistema", VOZ_APAGADA)
            return ""

    def confirmar(nombre: str, argumentos: dict) -> bool:
        if activa:
            voz.decir_sin_fallar(hablante, CONFIRMA_EN_PANTALLA, sesion.anotar_linea)
        return sesion.confirmar(nombre, argumentos)  # siempre con los botones: nunca se confirma hablando

    return {"entrada": entrada, "salida": voz.salida_por_voz(hablante, sesion.anotar_linea),
            "confirmar": confirmar, "fragmento": None}
