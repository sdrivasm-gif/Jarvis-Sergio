"""Voz de Jarvis: escucha (faster-whisper local) y habla (voz de Windows). Opcional: sin los extras [voz] Jarvis sigue con texto."""
# Al cargarse solo importa la biblioteca estándar y jarvis.bucle: faster_whisper y sounddevice se importan
# dentro de las funciones que los usan. Aquí nada escribe en pantalla por su cuenta: lo visible pasa por `mostrar`.
from __future__ import annotations

import base64
import contextlib
import io
import math
import re
import subprocess
import time
import unicodedata
import wave
from array import array
from collections import deque
from pathlib import Path
from typing import Callable, Iterable, Iterator, Protocol

from jarvis.bucle import legible, texto_confirmacion

FRECUENCIA = 16000
MUESTRAS_POR_BLOQUE = 480                 # 30 ms
BYTES_POR_BLOQUE = 960
UMBRAL = 400                              # RMS int16 a partir del cual un bloque es voz
BLOQUES_INICIO = 3                        # 90 ms seguidos de voz para empezar
BLOQUES_PREVIOS = 10                      # 300 ms antes del inicio (no cortar la primera sílaba)
BLOQUES_SILENCIO = 25                     # 0,75 s de silencio terminan la frase
BLOQUES_ESPERA = 267                      # 8 s sin voz → None
BLOQUES_MAXIMOS = 500                     # 15 s como máximo
MODELO_POR_DEFECTO = "base"
PALABRA_POR_DEFECTO = "jarvis"
ACTIVAR = frozenset({"on", "si", "sí", "1", "true"})
AFIRMATIVAS_VOZ = frozenset({"si", "confirmo"})        # ya normalizadas (sin tilde)
COMANDOS_VOZ = {"salir": "/salir", "adios": "/salir", "parte del dia": "/hoy"}
RESPUESTA_ACTIVACION = "¿Sí, señor?"
PIDE_SI = "Di sí para confirmar; cualquier otra respuesta cancela."
MAX_HABLADO = 1200
CORTE = "… El resto está en pantalla."
POWERSHELL = "powershell.exe"             # Windows PowerShell 5.1 trae System.Speech; pwsh 7 no
# El script es constante y el texto le llega por stdin en base64: no hay forma de inyectar comandos.
SCRIPT_SAPI = (
    "$ErrorActionPreference = 'Stop'\n"
    "Add-Type -AssemblyName System.Speech\n"
    "$t = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String([Console]::In.ReadToEnd().Trim()))\n"
    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
    "$v = $s.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'es*' } |"
    " Sort-Object { $_.VoiceInfo.Culture.Name -ne 'es-MX' } | Select-Object -First 1\n"
    "if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }\n"
    "$s.Speak($t)\n"
)
COMANDO_SAPI = [POWERSHELL, "-NoProfile", "-NonInteractive", "-EncodedCommand",
                base64.b64encode(SCRIPT_SAPI.encode("utf-16-le")).decode("ascii")]
FALTAN_DEPENDENCIAS = 'Faltan las dependencias de voz: instálalas con  pip install -e ".[voz]"  (ver jarvis/README.md).'
URL = re.compile(r"(?:https?://|www\.)[^\s()<>]*[^\s()<>.,;:!?'\"]", re.IGNORECASE)


class ErrorVoz(Exception):
    """La voz no se puede usar (faltan extras, micrófono, modelo o la voz de Windows falló)."""


class Oyente(Protocol):
    def escuchar(self) -> str | None: ...       # texto transcrito, o None si hubo silencio


class Hablante(Protocol):
    def decir(self, texto: str) -> None: ...    # bloquea hasta terminar de hablar


# --- texto (puro) ---

def normalizar(texto: str) -> str:
    sin_tildes = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return " ".join(re.sub(r"[\W_]+", " ", sin_tildes.casefold()).split())


def palabras_activacion(entorno) -> list[str]:
    palabras = [p.strip() for p in (entorno.get("JARVIS_PALABRA_ACTIVACION") or PALABRA_POR_DEFECTO).split(",")
                if normalizar(p)]
    return palabras or [PALABRA_POR_DEFECTO]


def activada(argv: list[str], entorno) -> bool:
    return "--voz" in argv or entorno.get("JARVIS_VOZ", "").strip().casefold() in ACTIVAR


def umbral_de(entorno) -> int:
    valor = entorno.get("JARVIS_VOZ_UMBRAL", "")
    if not valor.strip():
        return UMBRAL
    try:
        umbral = int(valor)
    except ValueError:
        umbral = 0
    if not 1 <= umbral <= 32767:
        raise ErrorVoz(f"JARVIS_VOZ_UMBRAL='{valor}' no es válido; usa un entero entre 1 y 32767.")
    return umbral


def quitar_palabra(texto: str | None, palabras: list[str]) -> str | None:
    """La orden es lo que va después de la palabra de activación ("" si solo se dijo la palabra; None si no está)."""
    if not texto:
        return None
    fichas = [(normalizar(m.group()), m.end()) for m in re.finditer(r"\w+", texto)]
    for palabra in palabras:
        objetivo = normalizar(palabra).split()
        k = len(objetivo)
        for i in range(len(fichas) - k + 1):
            if [f for f, _ in fichas[i:i + k]] == objetivo:
                return texto[fichas[i + k - 1][1]:].lstrip(" ,.;:!?-").strip()
    return None


def es_afirmativa(texto: str | None, palabras: Iterable[str] = ()) -> bool:
    # Ante la duda, NO: solo cuenta si todas las palabras (sin la de activación) son "sí" o "confirmo".
    if not texto:
        return False
    quitar = {f for p in palabras for f in normalizar(p).split()}
    fichas = [f for f in normalizar(texto).split() if f not in quitar]
    return bool(fichas) and all(f in AFIRMATIVAS_VOZ for f in fichas)


def _linea_para_voz(linea: str) -> str:
    linea = re.sub(r"^\s*(?:#{1,6}\s+|>\s*|[-*+•]\s+)", "", linea)
    if re.fullmatch(r"[\s|:\-=_*]*", linea):  # vacías, --- y separadores de tabla
        return ""
    if "|" in linea:
        linea = ", ".join(c.strip() for c in linea.strip().strip("|").split("|") if c.strip())
    linea = re.sub(r"[*`~]+", "", linea).replace("_", " ")
    linea = "".join(c for c in linea if c.isprintable() and (unicodedata.category(c) != "So" or c == "°"))
    linea = " ".join(linea.split()).strip(" ,")
    if linea and not linea.endswith(tuple(".!?:;,…")):
        linea += "."
    return linea


def limpiar_para_voz(texto: str) -> str:
    """Quita markdown, URLs, emojis y caracteres de control del texto que se dice; la pantalla muestra el original."""
    t = re.sub(r"```.*?(?:```|\Z)", " (código omitido) ", texto, flags=re.S)
    t = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = URL.sub("enlace", t)
    hablado = " ".join(filter(None, map(_linea_para_voz, t.splitlines())))
    if len(hablado) > MAX_HABLADO:
        hablado = hablado[:MAX_HABLADO].rsplit(" ", 1)[0] + CORTE
    return hablado


def texto_confirmacion_hablado(nombre: str, argumentos: dict) -> str:
    # Mismo orden y mismo escape que bucle.texto_confirmacion, sin recortar ni quitar URLs: se oye lo que se confirma.
    # ponytail: un cuerpo muy largo se lee entero; si molesta, cortarlo y remitir a la pantalla.
    partes = [f"¿Ejecutar {legible(nombre).replace('_', ' ')}?"]
    partes += [f"{legible(k).replace('_', ' ')}: {' '.join(legible(v).split())}."
               for k, v in sorted(argumentos.items(), key=lambda kv: "\n" in str(kv[1]))]
    return " ".join(partes + [PIDE_SI])


# --- audio (puro, biblioteca estándar) ---

def rms(bloque: bytes) -> float:
    # ponytail: array("h") usa el orden nativo de bytes (little-endian en x86/ARM Windows), igual que el micrófono.
    a = array("h")
    a.frombytes(bloque)
    return math.sqrt(sum(m * m for m in a) / len(a)) if a else 0.0


def bloques_de_wav(ruta) -> Iterator[bytes]:
    with wave.open(str(ruta), "rb") as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, FRECUENCIA):
            raise ValueError(f"el audio debe ser WAV mono de 16 bits a 16000 Hz: {Path(ruta).name}")
        while len(bloque := w.readframes(MUESTRAS_POR_BLOQUE)) == BYTES_POR_BLOQUE:
            yield bloque  # el último bloque, si está incompleto, se descarta


def recortar_frase(bloques: Iterable[bytes], umbral: int = UMBRAL, espera: int = BLOQUES_ESPERA,
                   silencio_fin: int = BLOQUES_SILENCIO, maximo: int = BLOQUES_MAXIMOS,
                   previos: int = BLOQUES_PREVIOS, inicio: int = BLOQUES_INICIO) -> bytes | None:
    """PCM de la primera frase (por energía), con los bloques previos; None si en `espera` bloques nadie habló."""
    # ponytail: detección por energía (RMS); con ruido de fondo variable, usar un VAD (webrtcvad o el de Silero).
    antes: deque[bytes] = deque(maxlen=previos)
    frase = None
    seguidos = callado = esperados = 0
    for b in bloques:
        voz = rms(b) >= umbral
        if frase is None:
            antes.append(b)
            seguidos = seguidos + 1 if voz else 0
            if seguidos >= inicio:
                frase = list(antes)
            else:
                esperados += 1
                if esperados >= espera:
                    return None
            continue
        frase.append(b)
        callado = 0 if voz else callado + 1
        if callado >= silencio_fin or len(frase) >= maximo:
            break
    return None if frase is None else b"".join(frase)


def wav_en_memoria(pcm: bytes) -> io.BytesIO:
    """WAV mono de 16 bits a 16 kHz en memoria: el audio nunca toca el disco."""
    memoria = io.BytesIO()
    with wave.open(memoria, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FRECUENCIA)
        w.writeframes(pcm)
    memoria.seek(0)
    return memoria


# --- motores reales (carga perezosa) ---

def bloques_del_microfono() -> Iterator[bytes]:
    # Sin test: necesita micrófono. Al cerrar el generador se cierra el flujo.
    import sounddevice as sd

    with sd.RawInputStream(samplerate=FRECUENCIA, channels=1, dtype="int16", blocksize=MUESTRAS_POR_BLOQUE) as flujo:
        while True:
            datos, _ = flujo.read(MUESTRAS_POR_BLOQUE)  # lectura corta: Ctrl+C responde
            yield bytes(datos)


def transcriptor_whisper(modelo: str, palabra: str) -> Callable[[bytes], str]:
    from faster_whisper import WhisperModel

    m = WhisperModel(modelo, device="cpu", compute_type="int8")

    def transcribir(pcm: bytes) -> str:
        # ponytail: beam_size=1 por latencia; initial_prompt sesga a "Jarvis" (si da activaciones falsas, quitarlo).
        segmentos, _ = m.transcribe(wav_en_memoria(pcm), language="es", beam_size=1, vad_filter=True,
                                    condition_on_previous_text=False, initial_prompt=palabra.strip().capitalize() + ".")
        return " ".join(s.text.strip() for s in segmentos if s.text.strip())

    return transcribir


class OyenteLocal:
    def __init__(self, transcribir: Callable[[bytes], str], fuente: Callable[[], Iterator[bytes]] = bloques_del_microfono,
                 umbral: int = UMBRAL):
        self.transcribir, self.fuente, self.umbral = transcribir, fuente, umbral

    def escuchar(self) -> str | None:
        # El micrófono se abre y se cierra en cada escucha: mientras Jarvis habla nadie graba y no queda audio viejo.
        with contextlib.closing(self.fuente()) as bloques:
            pcm = recortar_frase(bloques, self.umbral)
        if pcm is None:
            return None
        return self.transcribir(pcm).strip() or None


class HablanteSAPI:
    """Habla con la voz de Windows (SAPI) en un PowerShell aparte: matarlo corta la voz al momento."""

    def __init__(self, abrir=None):
        self.abrir = abrir

    def decir(self, texto: str) -> None:
        # ponytail: un PowerShell por frase (≈0,5–1 s de arranque); un proceso persistente sería más rápido.
        # ponytail: no se interrumpe cuando habla el usuario (sin cancelación de eco, el micrófono oiría a Jarvis);
        #   con auriculares, vigilar el micrófono mientras habla y llamar a proceso.kill().
        # ponytail: sin detalle del error (stderr a DEVNULL para no bloquear la tubería).
        if not texto.strip():
            return
        abrir = self.abrir or subprocess.Popen  # resuelto al llamar: la guardia de los tests lo intercepta
        proceso = abrir(COMANDO_SAPI, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            proceso.stdin.write(base64.b64encode(texto.encode("utf-8")))
            proceso.stdin.close()
            while proceso.poll() is None:
                time.sleep(0.05)  # espera corta: así Ctrl+C entra
        finally:
            if proceso.poll() is None:
                proceso.kill()
        if proceso.returncode != 0:
            raise ErrorVoz(f"la voz de Windows falló (código {proceso.returncode}).")


# --- conexión con bucle.conversar ---

def decir_sin_fallar(hablante, texto: str, mostrar) -> None:
    try:
        hablante.decir(texto)
    except Exception as e:
        mostrar(f"(no pude hablar: {e})")


def entrada_por_voz(oyente, hablante, palabras: list[str], mostrar=print) -> Callable[[str], str]:
    """Sustituye a input(): solo pasa lo dicho tras la palabra de activación; un silencio devuelve ""."""
    despierto = False

    def entrada(prompt: str = "") -> str:
        nonlocal despierto
        try:
            texto = oyente.escuchar()
        except EOFError:
            raise
        except Exception as e:
            mostrar(f"Error del micrófono: {e}")
            raise EOFError from None  # conversar se despide
        if despierto:
            despierto = False
            comando = (texto or "").strip()
        else:
            if not texto:
                return ""  # cada silencio vuelve a conversar, que así avisa de los recordatorios casi al momento
            comando = quitar_palabra(texto, palabras)
            if comando is None:
                return ""  # no iba dirigido a Jarvis: ni se muestra ni se envía
            if comando == "":
                despierto = True
                mostrar(f"tú (voz)> {texto.strip()}")
                mostrar("jarvis> " + RESPUESTA_ACTIVACION)
                decir_sin_fallar(hablante, RESPUESTA_ACTIVACION, mostrar)
                return ""
        if not comando:
            return ""
        mostrar(f"tú (voz)> {comando}")
        return COMANDOS_VOZ.get(normalizar(comando), comando)

    return entrada


def salida_por_voz(hablante, mostrar=print) -> Callable[[str], None]:
    def salida(texto: str) -> None:
        mostrar(texto)  # en pantalla, el texto original
        hablado = limpiar_para_voz(texto.removeprefix("jarvis> "))
        if hablado:
            decir_sin_fallar(hablante, hablado, mostrar)

    return salida


def confirmar_por_voz(oyente, hablante, palabras: list[str], mostrar=print) -> Callable[[str, dict], bool]:
    """Falla a NO: silencio, ambigüedad, errores o Ctrl+C cancelan, y si no se pudo preguntar no se escucha."""
    def confirmar(nombre: str, argumentos: dict) -> bool:
        mostrar(texto_confirmacion(nombre, argumentos).removesuffix("[s/N] ") + "[responde «sí» por voz]")
        try:
            hablante.decir(texto_confirmacion_hablado(nombre, argumentos))
            respuesta = oyente.escuchar()
        except (Exception, KeyboardInterrupt) as e:
            mostrar(f"(confirmación cancelada: {type(e).__name__})")
            return False
        mostrar(f"tú (voz)> {respuesta.strip() if respuesta else '(silencio)'}")
        return es_afirmativa(respuesta, palabras)

    return confirmar


def piezas_de_voz(oyente, hablante, palabras: list[str], mostrar=print) -> dict:
    """Argumentos para bucle.conversar: sin fragmento (no hay streaming) la respuesta llega entera a salida."""
    return {"entrada": entrada_por_voz(oyente, hablante, palabras, mostrar),
            "salida": salida_por_voz(hablante, mostrar),
            "confirmar": confirmar_por_voz(oyente, hablante, palabras, mostrar),
            "fragmento": None}


def motores(entorno) -> tuple[OyenteLocal, HablanteSAPI, list[str]]:
    """Comprueba micrófono y modelo y devuelve (oyente, hablante, palabras); si algo falta, ErrorVoz. No muestra nada."""
    palabras = palabras_activacion(entorno)
    umbral = umbral_de(entorno)
    try:
        import sounddevice as sd

        sd.query_devices(kind="input")
    except ImportError:
        raise ErrorVoz(FALTAN_DEPENDENCIAS) from None
    except Exception as e:
        raise ErrorVoz(f"no encuentro un micrófono: {e}") from None
    try:
        # ponytail: con un nombre de modelo (base), la primera vez faster-whisper lo descarga de Hugging Face;
        # con una carpeta local, no usa la red.
        transcribir = transcriptor_whisper(entorno.get("JARVIS_STT_MODELO") or MODELO_POR_DEFECTO, palabras[0])
    except ImportError:
        raise ErrorVoz(FALTAN_DEPENDENCIAS) from None
    except Exception as e:
        raise ErrorVoz(f"no pude cargar el modelo de voz a texto: {e}") from None
    return OyenteLocal(transcribir, umbral=umbral), HablanteSAPI(), palabras


def preparar(entorno, mostrar=print) -> dict:
    """Comprueba micrófono y modelo y devuelve las piezas de voz para conversar; si algo falta, ErrorVoz."""
    oyente, hablante, palabras = motores(entorno)
    mostrar(f"Voz activada: di «{palabras[0]}» y tu petición. Ctrl+C para salir.")
    return piezas_de_voz(oyente, hablante, palabras, mostrar)
