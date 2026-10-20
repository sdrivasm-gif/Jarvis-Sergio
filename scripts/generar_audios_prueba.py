"""Genera los WAV de prueba de tests/audio/ con la biblioteca estándar: mismos bytes en cada ejecución.
Con --con-voz sintetiza además frases con la voz de Windows (SAPI) para las pruebas opcionales con motores reales."""
import base64
import math
import random
import subprocess
import sys
import wave
from array import array
from pathlib import Path

FRECUENCIA = 16000
MUESTRAS_POR_BLOQUE = 480  # 30 ms
CARPETA = Path(__file__).resolve().parents[1] / "tests" / "audio"
FRASES = {"voz_hora": "Jarvis, ¿qué hora es?", "voz_si": "Sí.", "voz_no": "No, cancela."}

SCRIPT = """
$ruta = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String([Console]::In.ReadLine()))
$texto = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String([Console]::In.ReadLine()))
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'es-*' } | Select-Object -First 1
if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }
$s.SetOutputToWaveFile($ruta, [System.Speech.AudioFormat.SpeechAudioFormatInfo]::new(16000, 'Sixteen', 'Mono'))
$s.Speak($texto)
$s.Dispose()
"""


def escribir_wav(ruta: Path, muestras: list[int]) -> Path:
    # ponytail: array("h") usa el orden nativo de bytes (little-endian en x86/ARM Windows).
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FRECUENCIA)
        w.writeframes(array("h", muestras).tobytes())
    return ruta


def silencio(bloques: int) -> list[int]:
    return [0] * (bloques * MUESTRAS_POR_BLOQUE)


def tono(bloques: int, amplitud: int = 8000, hz: int = 440) -> list[int]:
    return [round(amplitud * math.sin(2 * math.pi * hz * n / FRECUENCIA)) for n in range(bloques * MUESTRAS_POR_BLOQUE)]


def ruido(bloques: int, amplitud: int = 100, semilla: int = 5) -> list[int]:
    r = random.Random(semilla)
    return [r.randint(-amplitud, amplitud) for _ in range(bloques * MUESTRAS_POR_BLOQUE)]


def generar(carpeta: Path = CARPETA) -> list[Path]:
    carpeta.mkdir(parents=True, exist_ok=True)
    return [
        escribir_wav(carpeta / "silencio.wav", silencio(33)),
        escribir_wav(carpeta / "tono.wav", silencio(20) + tono(40) + silencio(40)),
        escribir_wav(carpeta / "ruido_bajo.wav", ruido(33)),
        escribir_wav(carpeta / "chasquido.wav", silencio(10) + tono(2) + silencio(21)),
    ]


def generar_con_voz(carpeta: Path = CARPETA) -> list[Path]:
    carpeta.mkdir(parents=True, exist_ok=True)
    codificado = base64.b64encode(SCRIPT.encode("utf-16-le")).decode("ascii")
    rutas = []
    for nombre, frase in FRASES.items():
        ruta = carpeta / f"{nombre}.wav"
        entrada = base64.b64encode(str(ruta).encode("utf-8")) + b"\n" + base64.b64encode(frase.encode("utf-8")) + b"\n"
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", codificado],
            input=entrada,
            check=True,
        )
        ruta.with_suffix(".txt").write_text(frase, encoding="utf-8")
        rutas.append(ruta)
    return rutas


if __name__ == "__main__":
    escritas = generar()
    if "--con-voz" in sys.argv:
        escritas += generar_con_voz()
    for r in escritas:
        print(r)
