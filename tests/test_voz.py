import base64
import importlib
import io
import math
import subprocess
import sys
import types
import wave
from array import array
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from clientes_falsos import HablanteFalso, OyenteFalso

from jarvis import bucle, recordatorios, voz
from jarvis.llm import LlamadaHerramienta, Respuesta
from jarvis.llm.falso import ClienteFalso

AUDIO = Path(__file__).parent / "audio"


# 1
def test_importar_no_carga_motores(monkeypatch):
    for modulo in ("faster_whisper", "sounddevice", "numpy"):
        monkeypatch.setitem(sys.modules, modulo, None)
    importlib.reload(voz)


# 2
def test_normalizar():
    assert voz.normalizar("¡Sí, CONFIRMO!") == "si confirmo"
    assert voz.normalizar("Parte del Día") == "parte del dia"


# 3
def test_palabras_activacion():
    assert voz.palabras_activacion({}) == ["jarvis"]
    assert voz.palabras_activacion({"JARVIS_PALABRA_ACTIVACION": " Jarvis , yarvis ,, "}) == ["Jarvis", "yarvis"]
    assert voz.palabras_activacion({"JARVIS_PALABRA_ACTIVACION": " , "}) == ["jarvis"]


@pytest.mark.parametrize("argv, entorno, esperado", [
    ([], {}, False),
    (["--voz"], {}, True),
    ([], {"JARVIS_VOZ": "ON"}, True),
    ([], {"JARVIS_VOZ": "sí"}, True),
    ([], {"JARVIS_VOZ": "off"}, False),
    (["--voz"], {"JARVIS_VOZ": "off"}, True),
    (["-q"], {}, False),
])
def test_activada(argv, entorno, esperado):
    assert voz.activada(argv, entorno) is esperado


# 4
def test_umbral():
    assert voz.umbral_de({}) == 400
    assert voz.umbral_de({"JARVIS_VOZ_UMBRAL": "  "}) == 400
    assert voz.umbral_de({"JARVIS_VOZ_UMBRAL": "800"}) == 800
    for valor in ("0", "40000", "alto"):
        with pytest.raises(voz.ErrorVoz) as e:
            voz.umbral_de({"JARVIS_VOZ_UMBRAL": valor})
        assert str(e.value) == f"JARVIS_VOZ_UMBRAL='{valor}' no es válido; usa un entero entre 1 y 32767."


# 5
@pytest.mark.parametrize("texto, palabras, esperado", [
    ("Jarvis, ¿qué hora es?", ["jarvis"], "¿qué hora es?"),
    ("oye JARVIS qué tal", ["jarvis"], "qué tal"),
    ("Jarvis.", ["jarvis"], ""),
    ("¿Qué hora es, Jarvis?", ["jarvis"], ""),
    ("hola a todos", ["jarvis"], None),
    ("jarvisito ven", ["jarvis"], None),
    ("Yarvis, apaga", ["jarvis", "yarvis"], "apaga"),
    ("hola, oye Jarvis: pon música", ["oye jarvis"], "pon música"),
    ("Jarvis ven", ["Járvis"], "ven"),
    (None, ["jarvis"], None),
    ("", ["jarvis"], None),
])
def test_quitar_palabra(texto, palabras, esperado):
    assert voz.quitar_palabra(texto, palabras) == esperado


# 6
@pytest.mark.parametrize("texto", ["sí", "Sí.", "¡Sí, confirmo!", "Jarvis, sí", "sí, sí", "confirmo", "SI"])
def test_es_afirmativa_si(texto):
    assert voz.es_afirmativa(texto, ["jarvis"]) is True


@pytest.mark.parametrize("texto", [None, "", "   ", "no", "sí, pero no", "no, sí", "si quieres", "claro", "vale",
                                   "yes", "s", "jarvis", "sí, a las cinco", "Sí. Bueno, no."])
def test_es_afirmativa_no(texto):
    assert voz.es_afirmativa(texto, ["jarvis"]) is False


# 7
def test_limpiar_para_voz():
    assert voz.limpiar_para_voz("Son las **10:00**. Fuente: https://example.com/hora.") == "Son las 10:00. Fuente: enlace."
    assert voz.limpiar_para_voz(
        "# Agenda\n\n- Reunión con *Ana* a las 9\n- Ver [el informe](https://example.com/i)\n\n"
        "| hora | qué |\n|---|---|\n| 9:00 | café ☕ |"
    ) == "Agenda. Reunión con Ana a las 9. Ver el informe. hora, qué. 9:00, café."
    assert voz.limpiar_para_voz("Usa esto:\n```python\nprint('hola')\n```\nY listo") == "Usa esto: (código omitido). Y listo."
    assert voz.limpiar_para_voz("¿Qué tal, señor? ¡Bien!") == "¿Qué tal, señor? ¡Bien!"
    assert voz.limpiar_para_voz("") == ""
    assert voz.limpiar_para_voz("---") == ""
    assert voz.limpiar_para_voz("**") == ""
    assert voz.limpiar_para_voz("id_recuerdo: 3") == "id recuerdo: 3."
    sucio = voz.limpiar_para_voz("Hola\x1b[31m rojo‮")
    assert "\x1b" not in sucio and "‮" not in sucio
    largo = voz.limpiar_para_voz("palabra " * 400)
    assert largo.endswith(voz.CORTE) and len(largo) <= voz.MAX_HABLADO + len(voz.CORTE)


# 8
def test_texto_confirmacion_hablado():
    assert voz.texto_confirmacion_hablado("correo_enviar", {"para": "ana@example.com", "cuerpo": "Hola\nAna"}) == (
        "¿Ejecutar correo enviar? para: ana@example.com. cuerpo: Hola Ana. "
        "Di sí para confirmar; cualquier otra respuesta cancela.")
    assert voz.texto_confirmacion_hablado("memoria_borrar_todo", {}) == (
        "¿Ejecutar memoria borrar todo? Di sí para confirmar; cualquier otra respuesta cancela.")
    hablado = voz.texto_confirmacion_hablado("correo_enviar", {"para": "ana@example.com\x1b[2K"})
    assert "\\x1b" in hablado and "\x1b" not in hablado


# 9
def test_bloques_de_wav(tmp_path):
    tono = list(voz.bloques_de_wav(AUDIO / "tono.wav"))
    assert len(tono) == 100 and all(len(b) == 960 for b in tono)
    assert len(list(voz.bloques_de_wav(AUDIO / "silencio.wav"))) == 33
    with wave.open(str(tmp_path / "ocho.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(bytes(960))
    with pytest.raises(ValueError, match="el audio debe ser WAV mono de 16 bits a 16000 Hz: ocho.wav"):
        list(voz.bloques_de_wav(tmp_path / "ocho.wav"))


# 10
def test_rms():
    assert voz.rms(b"") == 0.0
    assert voz.rms(array("h", [3, -4] * 240).tobytes()) == pytest.approx(math.sqrt(12.5))
    assert voz.rms(next(voz.bloques_de_wav(AUDIO / "silencio.wav"))) == 0.0
    assert voz.rms(list(voz.bloques_de_wav(AUDIO / "tono.wav"))[30]) > 5000


def _frase(nombre, **opciones):
    return voz.recortar_frase(voz.bloques_de_wav(AUDIO / nombre), **opciones)


# 11
def test_recortar_frase_con_audios():
    pcm = _frase("tono.wav")
    assert len(pcm) == 72 * 960
    assert pcm[:7 * 960] == bytes(7 * 960)  # 7 bloques de silencio previo
    assert voz.rms(pcm[7 * 960:8 * 960]) > 5000
    for nombre in ("silencio.wav", "ruido_bajo.wav", "chasquido.wav"):
        assert _frase(nombre) is None, nombre
    assert len(_frase("tono.wav", maximo=20)) == 20 * 960
    assert len(_frase("tono.wav", silencio_fin=1000)) == 87 * 960  # el audio acaba a mitad de la frase


def test_recortar_frase_deja_de_esperar():
    leidos = []

    def contados():
        for b in voz.bloques_de_wav(AUDIO / "silencio.wav"):
            leidos.append(b)
            yield b

    assert voz.recortar_frase(contados(), espera=10) is None
    assert len(leidos) == 10


class Transcribir:
    def __init__(self, texto="  Jarvis, ¿qué hora es? "):
        self.texto, self.longitudes = texto, []

    def __call__(self, pcm):
        self.longitudes.append(len(pcm))
        return self.texto


# 12
def test_oyente_local_con_audios():
    transcribir = Transcribir()
    oyente = voz.OyenteLocal(transcribir, fuente=lambda: voz.bloques_de_wav(AUDIO / "tono.wav"))
    assert oyente.escuchar() == "Jarvis, ¿qué hora es?"
    assert transcribir.longitudes == [72 * 960]

    transcribir = Transcribir()
    assert voz.OyenteLocal(transcribir, fuente=lambda: voz.bloques_de_wav(AUDIO / "silencio.wav")).escuchar() is None
    assert transcribir.longitudes == []

    vacio = voz.OyenteLocal(Transcribir("  "), fuente=lambda: voz.bloques_de_wav(AUDIO / "tono.wav"))
    assert vacio.escuchar() is None


# 13
def test_cierra_el_microfono_tras_cada_escucha():
    estado = {"cerrado": False}

    def fuente():
        try:
            yield from voz.bloques_de_wav(AUDIO / "tono.wav")
        finally:
            estado["cerrado"] = True

    voz.OyenteLocal(Transcribir(), fuente=fuente).escuchar()
    assert estado["cerrado"] is True


# 14
def test_wav_en_memoria():
    with wave.open(voz.wav_en_memoria(b"\x00\x00" * 480)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (1, 2, 16000, 480)


# 15
def test_transcriptor_whisper_con_modulo_falso(monkeypatch):
    visto = {}

    class WhisperModel:
        def __init__(self, *args, **kwargs):
            visto["modelo"] = (args, kwargs)

        def transcribe(self, audio, **kw):
            visto["audio"], visto["kw"] = audio.read(), kw
            return ([SimpleNamespace(text=" Jarvis,"), SimpleNamespace(text="  "),
                     SimpleNamespace(text=" ¿qué hora es? ")], None)

    falso = types.ModuleType("faster_whisper")
    falso.WhisperModel = WhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", falso)

    t = voz.transcriptor_whisper("base", "jarvis")
    assert t(b"\x00\x00" * 480) == "Jarvis, ¿qué hora es?"
    assert visto["modelo"] == (("base",), {"device": "cpu", "compute_type": "int8"})
    assert visto["kw"] == {"language": "es", "beam_size": 1, "vad_filter": True,
                           "condition_on_previous_text": False, "initial_prompt": "Jarvis."}
    assert visto["audio"].startswith(b"RIFF")


class StdinFalso(io.BytesIO):
    def close(self):
        self.escrito = self.getvalue()
        super().close()


class ProcesoFalso:
    def __init__(self, codigo=0, termina=True):
        self.stdin, self.codigo, self.termina = StdinFalso(), codigo, termina
        self.returncode, self.matado = None, False

    def poll(self):
        if self.termina:
            self.returncode = self.codigo
        return self.returncode

    def kill(self):
        self.matado = True
        self.returncode = -9


class AbrirFalso:
    def __init__(self, proceso=None):
        self.proceso = proceso or ProcesoFalso()
        self.llamadas = []

    def __call__(self, *args, **kwargs):
        self.llamadas.append((args, kwargs))
        return self.proceso


# 16
def test_hablante_sapi_sin_inyeccion():
    abrir = AbrirFalso()
    voz.HablanteSAPI(abrir).decir("Hola, señor. ¿Qué tal?")
    (args, kwargs), = abrir.llamadas
    assert args[0] == voz.COMANDO_SAPI and voz.COMANDO_SAPI[0] == "powershell.exe"
    assert base64.b64decode(voz.COMANDO_SAPI[-1]).decode("utf-16-le") == voz.SCRIPT_SAPI
    assert "System.Speech" in voz.SCRIPT_SAPI and "es-MX" in voz.SCRIPT_SAPI
    assert not any("señor" in parte for parte in voz.COMANDO_SAPI)
    assert kwargs["stdin"] == subprocess.PIPE and "shell" not in kwargs
    assert abrir.proceso.stdin.escrito == base64.b64encode("Hola, señor. ¿Qué tal?".encode("utf-8"))

    vacio = AbrirFalso()
    voz.HablanteSAPI(vacio).decir("   ")
    assert vacio.llamadas == []


# 17
def test_hablante_sapi_errores(monkeypatch):
    with pytest.raises(voz.ErrorVoz, match="código 1"):
        voz.HablanteSAPI(AbrirFalso(ProcesoFalso(codigo=1))).decir("hola")

    colgado = ProcesoFalso(termina=False)

    def ctrl_c(segundos):
        raise KeyboardInterrupt

    monkeypatch.setattr(voz.time, "sleep", ctrl_c)
    with pytest.raises(KeyboardInterrupt):
        voz.HablanteSAPI(AbrirFalso(colgado)).decir("hola")
    assert colgado.matado is True


def test_hablante_sapi_sin_abrir_lo_para_la_guardia():
    with pytest.raises(AssertionError, match="acción real"):
        voz.HablanteSAPI().decir("hola")


ARGS = {"para": "ana@example.com", "cuerpo": "Hola\nAna"}
HABLADO = ("¿Ejecutar correo enviar? para: ana@example.com. cuerpo: Hola Ana. "
           "Di sí para confirmar; cualquier otra respuesta cancela.")
PANTALLA = "¿Ejecutar correo_enviar?\n  para: ana@example.com\n  cuerpo: Hola\n    Ana\n[responde «sí» por voz]"


def herramienta_enviar(ejecutadas):
    return SimpleNamespace(
        NOMBRE="correo_enviar", DESCRIPCION="x",
        ESQUEMA={"type": "object", "properties": {"para": {"type": "string"}, "cuerpo": {"type": "string"}},
                 "required": ["para", "cuerpo"]},
        requiere_confirmacion=True,
        ejecutar=lambda **a: ejecutadas.append(a) or "enviado",
    )


# 18
def test_salida_por_voz():
    vistos, hablante = [], HablanteFalso()
    salida = voz.salida_por_voz(hablante, vistos.append)
    salida("jarvis> Son las **10:00**.")
    assert vistos == ["jarvis> Son las **10:00**."]
    assert hablante.dichos == ["Son las 10:00."]

    salida("---")
    assert vistos[-1] == "---" and hablante.dichos == ["Son las 10:00."]

    vistos = []
    voz.salida_por_voz(HablanteFalso(falla=voz.ErrorVoz("sin voz")), vistos.append)("jarvis> hola")
    assert vistos == ["jarvis> hola", "(no pude hablar: sin voz)"]


# 19
@pytest.mark.parametrize("oido, ejecuta", [
    ("sí", True), ("Sí, confirmo.", True), ("Jarvis, sí", True),
    (None, False), ("no", False), ("sí, pero no", False), ("claro", False),
    (RuntimeError("micro"), False), (EOFError(), False), (KeyboardInterrupt(), False),
])
def test_confirmar_por_voz(oido, ejecuta):
    vistos, ejecutadas, hablante = [], [], HablanteFalso()
    confirmar = voz.confirmar_por_voz(OyenteFalso(oido), hablante, ["jarvis"], vistos.append)
    r = bucle.ejecutar_llamada(LlamadaHerramienta("l1", "correo_enviar", ARGS),
                               {"correo_enviar": herramienta_enviar(ejecutadas)}, confirmar)
    if ejecuta:
        assert r == "enviado" and ejecutadas == [ARGS]
    else:
        assert r == "El usuario canceló la acción." and ejecutadas == []
    assert hablante.dichos == [HABLADO]
    assert vistos[0] == PANTALLA
    if oido == "sí":
        assert vistos[1] == "tú (voz)> sí"
    if oido is None:
        assert vistos[1] == "tú (voz)> (silencio)"


# 20
def test_confirmar_sin_poder_hablar_no_escucha_y_cancela():
    oyente = OyenteFalso("sí")
    confirmar = voz.confirmar_por_voz(oyente, HablanteFalso(falla=voz.ErrorVoz("x")), ["jarvis"], [].append)
    assert confirmar("correo_enviar", ARGS) is False
    assert oyente.escuchas == 0  # nunca se oye un sí que no fue preguntado


# 21
def test_conversar_por_voz_completo():
    vistos, hablante = [], HablanteFalso()
    oyente = OyenteFalso("hola a todos", "Jarvis, ¿qué hora es?", None, "jarvis", "dime un chiste", "Jarvis, salir")
    cliente = ClienteFalso([Respuesta(texto="Son las **10:00**. Fuente: https://example.com/hora."),
                            Respuesta(texto="Un chiste.")])
    bucle.conversar(cliente, {}, reloj=lambda: datetime(2026, 10, 20, 9, 0),
                    **voz.piezas_de_voz(oyente, hablante, ["jarvis"], vistos.append))
    assert vistos == ["tú (voz)> ¿qué hora es?", "jarvis> Son las **10:00**. Fuente: https://example.com/hora.",
                      "tú (voz)> jarvis", "jarvis> ¿Sí, señor?", "tú (voz)> dime un chiste", "jarvis> Un chiste.",
                      "tú (voz)> salir", "Hasta luego."]
    assert hablante.dichos == ["Son las 10:00. Fuente: enlace.", "¿Sí, señor?", "Un chiste.", "Hasta luego."]
    # "hola a todos" no salió del equipo
    assert [r["mensajes"][-1]["texto"] for r in cliente.recibidos] == ["¿qué hora es?", "dime un chiste"]


# 22
def test_por_voz_sin_si_no_se_envia():
    vistos, ejecutadas, hablante = [], [], HablanteFalso()
    cliente = ClienteFalso([Respuesta(llamadas=[LlamadaHerramienta("l1", "correo_enviar", ARGS)]),
                            Respuesta(texto="Cancelado, señor.")])
    bucle.conversar(cliente, {"correo_enviar": herramienta_enviar(ejecutadas)},
                    reloj=lambda: datetime(2026, 10, 20, 9, 0),
                    **voz.piezas_de_voz(OyenteFalso("Jarvis, manda el correo a Ana", "no"), hablante, ["jarvis"],
                                        vistos.append))
    assert ejecutadas == []
    assert cliente.recibidos[1]["mensajes"][-1]["resultado"] == "El usuario canceló la acción."
    assert hablante.dichos == [HABLADO, "Cancelado, señor.", "Hasta luego."]


# 23
def test_recordatorio_vencido_se_dice_en_voz_alta():
    recordatorios.crear("tomar agua", datetime(2026, 10, 20, 10, 5), datetime(2026, 10, 20, 10, 0))
    hablante = HablanteFalso()
    bucle.conversar(ClienteFalso([]), {}, reloj=lambda: datetime(2026, 10, 20, 10, 6),
                    **voz.piezas_de_voz(OyenteFalso(None), hablante, ["jarvis"], [].append))
    assert hablante.dichos == ["Recordatorio (2026-10-20 10:05): tomar agua.", "Hasta luego."]


# 24
def test_microfono_roto_se_despide():
    vistos, hablante = [], HablanteFalso()
    bucle.conversar(ClienteFalso([]), {}, reloj=lambda: datetime(2026, 10, 20, 9, 0),
                    **voz.piezas_de_voz(OyenteFalso(RuntimeError("sin micro")), hablante, ["jarvis"], vistos.append))
    assert "Error del micrófono: sin micro" in vistos
    assert hablante.dichos[-1] == "Hasta luego."


def _motores_falsos(monkeypatch, query_devices=lambda kind: {}, modelo_falla=None):
    sd = types.ModuleType("sounddevice")  # sin RawInputStream: si preparar abriera el micrófono, fallaría
    sd.query_devices = query_devices
    monkeypatch.setitem(sys.modules, "sounddevice", sd)

    class WhisperModel:
        def __init__(self, *args, **kwargs):
            if modelo_falla:
                raise modelo_falla

    fw = types.ModuleType("faster_whisper")
    fw.WhisperModel = WhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fw)


# 25
def test_preparar(monkeypatch):
    _motores_falsos(monkeypatch)
    vistos = []
    piezas = voz.preparar({}, vistos.append)
    assert set(piezas) == {"entrada", "salida", "confirmar", "fragmento"} and piezas["fragmento"] is None
    assert vistos == ["Voz activada: di «jarvis» y tu petición. Ctrl+C para salir."]


def _error_de_preparar(entorno=None):
    with pytest.raises(voz.ErrorVoz) as e:
        voz.preparar(entorno or {}, [].append)
    return str(e.value)


def test_preparar_errores(monkeypatch):
    monkeypatch.setitem(sys.modules, "sounddevice", None)  # como la guardia: sin los extras
    assert _error_de_preparar() == voz.FALTAN_DEPENDENCIAS

    def no_hay(kind):
        raise ValueError("no hay")

    _motores_falsos(monkeypatch, query_devices=no_hay)
    assert _error_de_preparar() == "no encuentro un micrófono: no hay"

    _motores_falsos(monkeypatch, modelo_falla=RuntimeError("falta model.bin"))
    assert _error_de_preparar() == "no pude cargar el modelo de voz a texto: falta model.bin"

    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    assert _error_de_preparar() == voz.FALTAN_DEPENDENCIAS

    _motores_falsos(monkeypatch)
    assert _error_de_preparar({"JARVIS_VOZ_UMBRAL": "x"}) == (
        "JARVIS_VOZ_UMBRAL='x' no es válido; usa un entero entre 1 y 32767.")
