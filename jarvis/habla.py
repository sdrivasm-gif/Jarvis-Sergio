"""Cómo habla Jarvis: sintetiza cada frase (edge-tts, ElevenLabs o SAPI) y la reproduce mientras prepara la siguiente."""
# Al cargarse solo importa la biblioteca estándar y jarvis: edge_tts y ctypes se importan dentro de las funciones.
# Siempre voz.ErrorVoz / voz.HablanteSAPI / voz.partir_frases al llamar: un test recarga jarvis.voz.
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import queue
import re
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from jarvis import voz
from jarvis.bucle import legible

MOTORES = ("edge", "sapi", "elevenlabs")
VOZ_EDGE, VELOCIDAD, TONO = "es-MX-JorgeNeural", "+15%", "-5Hz"
ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{}?output_format=mp3_44100_128"
ELEVENLABS_MODELO = "eleven_flash_v2_5"
TIEMPO_SINTESIS = 10.0       # s por frase; si se pasa, el motor se da por caído
TROZO_ESPERA = 0.1           # s: esperar() va en trozos para que Ctrl+C entre en Windows
SONDEO_MCI = 0.05            # s entre consultas de "status ... mode"
ALIAS_MCI = "jarvis_voz"
CARPETA_AUDIO = Path(tempfile.gettempdir()) / "jarvis-voz"
SIN_EDGE = 'Voz: falta edge-tts (pip install -e ".[voz]"); uso la voz de Windows.'
AVISO_RESPALDO = "Voz: {nombre} falló ({causa}); sigo con la voz de Windows hasta reiniciar Jarvis."


# --- configuración (puras; los mensajes muestran legible(valor), nunca el valor de una clave) ---

def motor_de(entorno) -> str:
    valor = entorno.get("JARVIS_VOZ_MOTOR", "")
    motor = valor.strip().casefold() or "edge"
    if motor not in MOTORES:
        raise voz.ErrorVoz(f"JARVIS_VOZ_MOTOR='{legible(valor)}' no es válido; usa edge, sapi o elevenlabs.")
    return motor


def _variable(entorno, nombre: str, defecto: str, patron: str, ayuda: str) -> str:
    valor = entorno.get(nombre, "").strip() or defecto
    if not re.fullmatch(patron, valor):
        raise voz.ErrorVoz(f"{nombre}='{legible(valor)}' no es válido; {ayuda}")
    return valor


def voz_edge_de(entorno) -> tuple[str, str, str]:
    return (_variable(entorno, "JARVIS_VOZ_NOMBRE", VOZ_EDGE, r"[A-Za-z0-9-]{5,60}",
                      "usa un nombre de voz como es-MX-JorgeNeural."),
            _variable(entorno, "JARVIS_VOZ_VELOCIDAD", VELOCIDAD, r"[+-][0-9]{1,3}%",
                      "usa un porcentaje con signo, por ejemplo +15% o -10%."),
            _variable(entorno, "JARVIS_VOZ_TONO", TONO, r"[+-][0-9]{1,3}Hz",
                      "usa hercios con signo, por ejemplo -5Hz o +0Hz."))


def elevenlabs_de(entorno) -> tuple[str, str, str]:
    """(clave, id_voz, modelo). Ningún mensaje lleva la clave."""
    clave = entorno.get("ELEVENLABS_API_KEY", "").strip()
    id_voz = entorno.get("ELEVENLABS_VOICE_ID", "").strip()
    for nombre, valor in (("ELEVENLABS_API_KEY", clave), ("ELEVENLABS_VOICE_ID", id_voz)):
        if not valor:
            raise voz.ErrorVoz(f"Falta {nombre} en .env (JARVIS_VOZ_MOTOR=elevenlabs).")
    if not re.fullmatch(r"[A-Za-z0-9]{10,40}", id_voz):
        raise voz.ErrorVoz("ELEVENLABS_VOICE_ID no es válido; copia el ID de la voz (solo letras y números).")
    return clave, id_voz, entorno.get("ELEVENLABS_MODEL_ID", "").strip() or ELEVENLABS_MODELO


# --- archivos temporales (solo audio que dice Jarvis) ---

def archivo_temporal(carpeta: Path) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    fd, ruta = tempfile.mkstemp(suffix=".mp3", dir=carpeta)
    os.close(fd)
    return Path(ruta)


def borrar(ruta) -> None:
    if ruta is None:
        return
    with contextlib.suppress(OSError):
        Path(ruta).unlink(missing_ok=True)


def limpiar_carpeta(carpeta: Path) -> None:
    """Borra los *.mp3 que quedaron de una sesión que se cerró de golpe."""
    for ruta in carpeta.glob("*.mp3"):
        borrar(ruta)


class SintetizadorEdge:
    """Voces neurales de Microsoft (edge-tts, sin clave, con internet). Devuelve la ruta de un MP3 temporal."""

    def __init__(self, nombre: str, velocidad: str, tono: str, carpeta: Path, comunicar=None):
        self.nombre, self.velocidad, self.tono = nombre, velocidad, tono
        self.carpeta, self.comunicar = carpeta, comunicar

    def __call__(self, frase: str) -> Path:
        # ponytail: una conexión nueva por frase (≈100–300 ms); reutilizar un bucle y un websocket si hace falta.
        comunicar = self.comunicar
        if comunicar is None:
            import edge_tts  # resuelto al llamar: la guardia de los tests lo anula

            comunicar = edge_tts.Communicate
        ruta = archivo_temporal(self.carpeta)
        try:
            guardar = comunicar(frase, voice=self.nombre, rate=self.velocidad, pitch=self.tono).save(str(ruta))
            asyncio.run(asyncio.wait_for(guardar, TIEMPO_SINTESIS))
            if ruta.stat().st_size == 0:
                raise voz.ErrorVoz("edge-tts no devolvió audio.")
        except BaseException:
            borrar(ruta)
            raise
        return ruta


class SintetizadorElevenLabs:
    """API REST oficial de ElevenLabs con urllib. La clave va solo en la cabecera xi-api-key."""

    def __init__(self, clave: str, id_voz: str, modelo: str, carpeta: Path, pedir=None):
        self._clave, self.id_voz, self.modelo, self.carpeta, self.pedir = clave, id_voz, modelo, carpeta, pedir

    def __call__(self, frase: str) -> Path:
        pedir = self.pedir or urllib.request.urlopen  # resuelto al llamar: la guardia de los tests lo intercepta
        req = urllib.request.Request(
            ELEVENLABS_URL.format(self.id_voz),
            data=json.dumps({"text": frase, "model_id": self.modelo}).encode("utf-8"),
            headers={"xi-api-key": self._clave, "Content-Type": "application/json", "Accept": "audio/mpeg"},
            method="POST")
        try:
            with pedir(req, timeout=TIEMPO_SINTESIS) as r:
                datos = r.read()
        except urllib.error.HTTPError as e:
            raise voz.ErrorVoz(f"ElevenLabs respondió {e.code}.") from None
        except OSError as e:  # URLError y tiempo agotado; el texto del error no se muestra
            raise voz.ErrorVoz(f"sin conexión con ElevenLabs ({type(e).__name__}).") from None
        if not datos:
            raise voz.ErrorVoz("ElevenLabs no devolvió audio.")
        ruta = archivo_temporal(self.carpeta)
        ruta.write_bytes(datos)
        return ruta


def enviar_mci(comando: str) -> str:
    """Manda una orden MCI (winmm) y devuelve su respuesta. Sin test: necesita Windows y audio (la guardia la anula)."""
    import ctypes

    winmm = ctypes.windll.winmm
    buf = ctypes.create_unicode_buffer(256)
    codigo = winmm.mciSendStringW(comando, buf, 255, None)
    if codigo != 0:
        error = ctypes.create_unicode_buffer(256)
        winmm.mciGetErrorStringW(codigo, error, 255)
        raise voz.ErrorVoz(f"el reproductor de Windows falló: {error.value or codigo}")
    return buf.value


class ReproductorMCI:
    """Reproduce un MP3 con MCI de Windows. Todas las órdenes salen del hilo que lo llama (el de reproducción)."""

    def __init__(self, mci=None):
        self.mci = mci

    def __call__(self, ruta: Path, parar, al_empezar) -> None:
        mci = self.mci or enviar_mci  # resuelto al llamar: la guardia de los tests lo intercepta
        if '"' in str(ruta):  # la orden solo lleva una ruta nuestra entre comillas; nunca el texto hablado
            raise voz.ErrorVoz("ruta de audio no válida.")
        mci(f'open "{ruta}" type mpegvideo alias {ALIAS_MCI}')
        try:
            mci(f"play {ALIAS_MCI}")
            al_empezar()
            while mci(f"status {ALIAS_MCI} mode") in ("playing", "seeking"):
                if parar():
                    mci(f"stop {ALIAS_MCI}")
                    break
                time.sleep(SONDEO_MCI)
        finally:
            with contextlib.suppress(Exception):
                mci(f"close {ALIAS_MCI}")


class HablanteCola:
    """encolar no bloquea; esperar bloquea hasta que suena todo; decir = trocear + encolar + esperar.

    Un hilo sintetiza la frase N+1 mientras otro reproduce la N. Si el motor falla, la cola queda caída el resto
    de la sesión y lo no dicho se dice con `respaldo` (SAPI) en esperar(), desde el hilo que llama.
    Sin `sintetizar` (modo sapi) no hay hilos: lo encolado se dice con un solo respaldo.decir por turno.
    """
    # ponytail: sin reintentar el motor caído en toda la sesión; reintentar tras N minutos si hace falta.
    # ponytail: en respaldo, el resto del turno suena al terminar la respuesta, no al momento.

    def __init__(self, respaldo, sintetizar=None, reproducir=None, mostrar=print, nombre="sapi"):
        self.respaldo, self.sintetizar, self.reproducir = respaldo, sintetizar, reproducir
        self.mostrar, self.nombre = mostrar, nombre
        self._cond = threading.Condition()  # protege lo de abajo
        self._gen = self._pendientes = 0
        self._no_dichas: list[str] = []
        self._caido = self._avisado = False
        self._causa = ""
        self._frases: queue.Queue = queue.Queue()            # (gen, frase)
        self._audios: queue.Queue = queue.Queue(maxsize=1)   # (gen, frase, ruta | None): prepara solo una por delante
        self._hilos: list[threading.Thread] = []
        self.al_empezar = None  # gancho de medir_voz: se llama al empezar a sonar cada audio

    def encolar(self, frase: str) -> None:
        if not frase.strip():
            return
        with self._cond:
            if self.sintetizar is None or (self._caido and self._pendientes == 0):
                self._no_dichas.append(frase)
                return
            self._pendientes += 1
            if not self._hilos:
                self._hilos = [threading.Thread(target=self._sintetizar_siempre, name="jarvis-sintesis", daemon=True),
                               threading.Thread(target=self._reproducir_siempre, name="jarvis-reproduccion",
                                                daemon=True)]
                for h in self._hilos:
                    h.start()
            self._frases.put((self._gen, frase))  # también ya caído si hay algo en curso: así se respeta el orden

    def esperar(self) -> None:
        try:
            with self._cond:
                while self._pendientes > 0:
                    if not all(h.is_alive() for h in self._hilos):
                        raise voz.ErrorVoz("la cola de voz se detuvo.")
                    self._cond.wait(TROZO_ESPERA)
                no_dichas, self._no_dichas = self._no_dichas, []
                avisar = self._caido and not self._avisado
                self._avisado = self._avisado or avisar
            if avisar:
                self.mostrar(AVISO_RESPALDO.format(nombre=self.nombre, causa=self._causa))
            if no_dichas:
                self.respaldo.decir(" ".join(no_dichas))  # hilo principal: Ctrl+C mata ese PowerShell
        except BaseException:
            self.cortar()
            raise

    def cortar(self) -> None:
        with self._cond:
            self._gen += 1  # lo encolado antes se descarta sin esperar a nadie
            self._pendientes = 0
            self._no_dichas.clear()
            self._cond.notify_all()

    def decir(self, texto: str) -> None:
        frases, _ = voz.partir_frases(texto, final=True)
        for f in frases:
            self.encolar(f)
        self.esperar()

    def _empezo(self) -> None:
        if self.al_empezar:
            self.al_empezar()

    def _caer(self, e: Exception) -> None:
        with self._cond:
            if not self._caido:
                self._caido = True
                # Solo el tipo si no es nuestro: el texto de un error de red podría llevar la URL.
                self._causa = str(e) if isinstance(e, voz.ErrorVoz) else type(e).__name__

    def _sintetizar_siempre(self) -> None:
        while True:
            gen, frase = self._frases.get()
            ruta = None
            try:
                if gen == self._gen and not self._caido:
                    ruta = self.sintetizar(frase)
            except Exception as e:
                self._caer(e)
            finally:
                self._audios.put((gen, frase, ruta))  # todo pasa por aquí: el orden se conserva

    def _reproducir_siempre(self) -> None:
        while True:
            gen, frase, ruta = self._audios.get()
            dicha = False
            try:
                if gen == self._gen and ruta and not self._caido:
                    self.reproducir(ruta, lambda: gen != self._gen, self._empezo)
                    dicha = True
            except Exception as e:
                self._caer(e)
            finally:
                borrar(ruta)
                with self._cond:
                    if gen == self._gen:
                        if not dicha:
                            self._no_dichas.append(frase)
                        self._pendientes -= 1
                        self._cond.notify_all()


def crear_hablante(entorno, mostrar=print, carpeta: Path | None = None) -> HablanteCola:
    """El hablante de JARVIS_VOZ_MOTOR (configuración inválida → ErrorVoz). Sin edge_tts, avisa y usa SAPI."""
    carpeta = carpeta or CARPETA_AUDIO  # resuelto al llamar: los tests lo cambian
    motor = motor_de(entorno)
    sapi = voz.HablanteSAPI()
    if motor == "sapi":
        return HablanteCola(sapi, nombre="sapi")
    if motor == "edge":
        nombre, velocidad, tono = voz_edge_de(entorno)  # se valida antes de importar
        try:
            import edge_tts
        except ImportError:
            mostrar(SIN_EDGE)
            return HablanteCola(sapi, nombre="sapi")
        sintetizar = SintetizadorEdge(nombre, velocidad, tono, carpeta, edge_tts.Communicate)
        etiqueta = f"edge ({nombre})"
    else:
        sintetizar, etiqueta = SintetizadorElevenLabs(*elevenlabs_de(entorno), carpeta), "elevenlabs"
    limpiar_carpeta(carpeta)
    return HablanteCola(sapi, sintetizar, ReproductorMCI(), mostrar, etiqueta)
