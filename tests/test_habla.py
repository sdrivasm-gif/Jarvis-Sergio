import asyncio
import json
import sys
import threading
import time
import types
import urllib.error
from pathlib import Path

import pytest
from clientes_falsos import HablanteFalso

from jarvis import habla, voz

CLAVE = "clave-de-mentira-123"
ID_VOZ = "VozDeMentira0123"


def esperar(condicion, tiempo=2.0):
    limite = time.monotonic() + tiempo
    while not condicion():
        assert time.monotonic() < limite, "la condición no se cumplió a tiempo"
        time.sleep(0.01)


class Sintetizador:
    """Escribe tmp_path/<n>.mp3 con la frase dentro; con `falla_en`, lanza `error` para esa frase."""

    def __init__(self, carpeta, falla_en=None, error=None):
        self.carpeta, self.falla_en, self.error = carpeta, falla_en, error
        self.frases = []

    def __call__(self, frase):
        if frase == self.falla_en:
            self.frases.append(frase)
            raise self.error
        ruta = self.carpeta / f"{len(self.frases) + 1}.mp3"
        ruta.write_text(frase, encoding="utf-8")
        self.frases.append(frase)
        return ruta


class Reproductor:
    """Lee la frase del archivo; si no está liberado, suena hasta que se libera o hasta que parar() es verdadero."""

    def __init__(self, liberado=True, falla=None):
        self.liberar, self.falla = threading.Event(), falla
        if liberado:
            self.liberar.set()
        self.sonando, self.sonadas, self.paradas = [], [], []

    def __call__(self, ruta, parar, al_empezar):
        frase = ruta.read_text(encoding="utf-8")
        if self.falla:
            raise self.falla
        al_empezar()
        self.sonando.append(frase)
        while not self.liberar.wait(0.01):
            if parar():
                self.paradas.append(frase)
                return
        self.sonadas.append(frase)


def _cola(tmp_path, sint=None, rep=None, respaldo=None):
    vistos = []
    cola = habla.HablanteCola(respaldo or HablanteFalso(), sint or Sintetizador(tmp_path), rep or Reproductor(),
                              vistos.append, "edge")
    return cola, vistos


def _mp3(tmp_path):
    return sorted(p.name for p in tmp_path.glob("*.mp3"))


# --- HablanteCola ---

def test_cola_orden(tmp_path):  # 1
    rep, respaldo = Reproductor(), HablanteFalso()
    cola, vistos = _cola(tmp_path, rep=rep, respaldo=respaldo)
    cola.decir("Primera frase de prueba. Segunda frase de prueba.")
    assert rep.sonadas == ["Primera frase de prueba.", "Segunda frase de prueba."]
    assert _mp3(tmp_path) == [] and respaldo.dichos == [] and vistos == []
    assert sorted(h.name for h in cola._hilos) == ["jarvis-reproduccion", "jarvis-sintesis"]
    assert all(h.daemon for h in cola._hilos)


def test_cola_prepara_la_siguiente_mientras_suena(tmp_path):  # 2
    sint, rep = Sintetizador(tmp_path), Reproductor(liberado=False)
    cola, _ = _cola(tmp_path, sint, rep)
    cola.encolar("frase uno")
    cola.encolar("frase dos")
    esperar(lambda: rep.sonando == ["frase uno"])
    esperar(lambda: sint.frases == ["frase uno", "frase dos"])
    assert rep.sonadas == []
    rep.liberar.set()
    cola.esperar()
    assert rep.sonadas == ["frase uno", "frase dos"]


def test_cola_esperar_bloquea_hasta_que_suena(tmp_path):  # 3
    rep = Reproductor(liberado=False)
    cola, _ = _cola(tmp_path, rep=rep)
    cola.encolar("frase uno")
    terminado = threading.Event()
    threading.Thread(target=lambda: (cola.esperar(), terminado.set()), daemon=True).start()
    esperar(lambda: rep.sonando == ["frase uno"])
    assert not terminado.wait(0.05)
    rep.liberar.set()
    assert terminado.wait(2.0)


def test_cola_respaldo_si_falla_la_sintesis(tmp_path):  # 4
    sint = Sintetizador(tmp_path, falla_en="frase 2", error=voz.ErrorVoz("sin red"))
    rep, respaldo = Reproductor(liberado=False), HablanteFalso()
    cola, vistos = _cola(tmp_path, sint, rep, respaldo)
    cola.encolar("frase 1")
    esperar(lambda: rep.sonando == ["frase 1"])  # ya sonando: la caída no la descarta
    cola.encolar("frase 2")
    cola.encolar("frase 3")
    esperar(lambda: sint.frases == ["frase 1", "frase 2"])
    rep.liberar.set()
    cola.esperar()
    aviso = habla.AVISO_RESPALDO.format(nombre="edge", causa="sin red")
    assert rep.sonadas == ["frase 1"] and respaldo.dichos == ["frase 2 frase 3"] and vistos == [aviso]
    assert sint.frases == ["frase 1", "frase 2"]

    cola.decir("Otra frase más de prueba. Y una segunda de prueba.")
    assert sint.frases == ["frase 1", "frase 2"]
    assert respaldo.dichos[-1] == "Otra frase más de prueba. Y una segunda de prueba."
    assert vistos == [aviso] and _mp3(tmp_path) == []


def test_cola_respaldo_si_falla_la_reproduccion(tmp_path):  # 5
    respaldo = HablanteFalso()
    cola, vistos = _cola(tmp_path, rep=Reproductor(falla=voz.ErrorVoz("sin códec")), respaldo=respaldo)
    cola.encolar("frase 1")
    cola.esperar()
    assert respaldo.dichos == ["frase 1"]
    assert vistos == [habla.AVISO_RESPALDO.format(nombre="edge", causa="sin códec")]
    assert _mp3(tmp_path) == []


def test_cola_cortar(tmp_path):  # 6
    sint, rep, respaldo = Sintetizador(tmp_path), Reproductor(liberado=False), HablanteFalso()
    cola, vistos = _cola(tmp_path, sint, rep, respaldo)
    cola.encolar("frase 1")
    cola.encolar("frase 2")
    esperar(lambda: rep.sonando == ["frase 1"] and sint.frases == ["frase 1", "frase 2"])
    cola.cortar()
    esperar(lambda: rep.paradas == ["frase 1"])
    esperar(lambda: _mp3(tmp_path) == [])
    cola.esperar()  # no queda nada pendiente
    assert rep.sonando == ["frase 1"]
    rep.liberar.set()
    cola.decir("Después del corte, señor.")
    assert rep.sonadas == ["Después del corte, señor."] and respaldo.dichos == [] and vistos == []


def test_cola_ctrl_c_corta_y_relanza(tmp_path):  # 7
    cola = habla.HablanteCola(HablanteFalso(falla=KeyboardInterrupt()))
    cola.encolar("frase")
    with pytest.raises(KeyboardInterrupt):
        cola.esperar()
    assert cola._gen == 1


def test_cola_error_del_respaldo_sube(tmp_path):  # 8
    respaldo = HablanteFalso(falla=voz.ErrorVoz("sin SAPI"))
    cola = habla.HablanteCola(respaldo)
    cola.encolar("frase")
    with pytest.raises(voz.ErrorVoz, match="sin SAPI"):
        cola.esperar()
    respaldo.falla = None
    cola.decir("Ahora sí funciona, señor.")
    assert respaldo.dichos == ["Ahora sí funciona, señor."]


def test_cola_al_empezar(tmp_path):  # 9
    rep = Reproductor()
    cola, _ = _cola(tmp_path, rep=rep)
    marcas = []
    cola.al_empezar = lambda: marcas.append(list(rep.sonando))
    cola.decir("Una frase cualquiera de prueba.")
    assert marcas == [[]]  # antes de sonar, una sola vez


def test_cola_solo_sapi(tmp_path):  # 10
    respaldo = HablanteFalso()
    cola = habla.HablanteCola(respaldo)
    cola.decir("Primera frase de prueba. Segunda frase de prueba.")
    cola.decir("   ")
    assert respaldo.dichos == ["Primera frase de prueba. Segunda frase de prueba."]
    assert cola._hilos == []


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")  # el hilo muere a propósito
def test_cola_con_un_hilo_muerto_no_se_cuelga(tmp_path):
    respaldo = HablanteFalso()
    cola, _ = _cola(tmp_path, rep=Reproductor(falla=SystemExit()), respaldo=respaldo)  # SystemExit mata el hilo
    cola.encolar("frase 1")
    cola.esperar()
    assert respaldo.dichos == ["frase 1"]
    esperar(lambda: not cola._hilos[1].is_alive())
    cola.encolar("frase 2")
    with pytest.raises(voz.ErrorVoz, match="la cola de voz se detuvo."):
        cola.esperar()


def test_cola_aviso_solo_con_el_tipo_de_error(tmp_path):  # 11
    sint = Sintetizador(tmp_path, falla_en="frase 1", error=RuntimeError("https://example.com/?secreto=1"))
    respaldo = HablanteFalso()
    cola, vistos = _cola(tmp_path, sint, respaldo=respaldo)
    cola.encolar("frase 1")
    cola.esperar()
    assert vistos == [habla.AVISO_RESPALDO.format(nombre="edge", causa="RuntimeError")]
    assert respaldo.dichos == ["frase 1"]


def _error(funcion, entorno) -> str:
    with pytest.raises(voz.ErrorVoz) as e:
        funcion(entorno)
    return str(e.value)


# --- configuración ---

def test_valores_por_defecto():
    assert habla.motor_de({}) == "edge"
    assert habla.motor_de({"JARVIS_VOZ_MOTOR": "  "}) == "edge"
    assert habla.voz_edge_de({}) == ("es-MX-JorgeNeural", "+15%", "-5Hz")


def test_motor():
    assert habla.motor_de({"JARVIS_VOZ_MOTOR": " SAPI "}) == "sapi"
    assert habla.motor_de({"JARVIS_VOZ_MOTOR": "ElevenLabs"}) == "elevenlabs"
    assert _error(habla.motor_de, {"JARVIS_VOZ_MOTOR": "piper"}) == (
        "JARVIS_VOZ_MOTOR='piper' no es válido; usa edge, sapi o elevenlabs.")


def test_voz_edge():
    assert habla.voz_edge_de({"JARVIS_VOZ_NOMBRE": "es-ES-AlvaroNeural", "JARVIS_VOZ_VELOCIDAD": "-10%",
                              "JARVIS_VOZ_TONO": "+0Hz"}) == ("es-ES-AlvaroNeural", "-10%", "+0Hz")
    for v in ("15%", "+15", "rápido"):
        assert _error(habla.voz_edge_de, {"JARVIS_VOZ_VELOCIDAD": v}) == (
            f"JARVIS_VOZ_VELOCIDAD='{v}' no es válido; usa un porcentaje con signo, por ejemplo +15% o -10%.")
    for v in ("-5", "5Hz"):
        assert _error(habla.voz_edge_de, {"JARVIS_VOZ_TONO": v}) == (
            f"JARVIS_VOZ_TONO='{v}' no es válido; usa hercios con signo, por ejemplo -5Hz o +0Hz.")
    for v in ("es-MX-Jorge'Neural", "es-MX-<Jorge>"):
        assert _error(habla.voz_edge_de, {"JARVIS_VOZ_NOMBRE": v}) == (
            f"JARVIS_VOZ_NOMBRE='{v}' no es válido; usa un nombre de voz como es-MX-JorgeNeural.")


def test_voz_edge_escapa_caracteres_de_control():
    mensaje = _error(habla.voz_edge_de, {"JARVIS_VOZ_TONO": "\x1b[2K"})
    assert "\x1b" not in mensaje and "\\x1b" in mensaje


def test_elevenlabs():
    assert habla.elevenlabs_de({"ELEVENLABS_API_KEY": CLAVE, "ELEVENLABS_VOICE_ID": ID_VOZ}) == (
        CLAVE, ID_VOZ, "eleven_flash_v2_5")
    assert habla.elevenlabs_de({"ELEVENLABS_API_KEY": CLAVE, "ELEVENLABS_VOICE_ID": f" {ID_VOZ} ",
                                "ELEVENLABS_MODEL_ID": " eleven_multilingual_v2 "}) == (
        CLAVE, ID_VOZ, "eleven_multilingual_v2")
    mensajes = [
        _error(habla.elevenlabs_de, {"ELEVENLABS_VOICE_ID": ID_VOZ}),
        _error(habla.elevenlabs_de, {"ELEVENLABS_API_KEY": CLAVE}),
        _error(habla.elevenlabs_de, {"ELEVENLABS_API_KEY": CLAVE, "ELEVENLABS_VOICE_ID": "../x"}),
    ]
    assert mensajes == ["Falta ELEVENLABS_API_KEY en .env (JARVIS_VOZ_MOTOR=elevenlabs).",
                        "Falta ELEVENLABS_VOICE_ID en .env (JARVIS_VOZ_MOTOR=elevenlabs).",
                        "ELEVENLABS_VOICE_ID no es válido; copia el ID de la voz (solo letras y números)."]
    assert not any(CLAVE in m for m in mensajes)


# --- archivos temporales y sintetizadores ---

def test_archivo_temporal(tmp_path):
    ruta = habla.archivo_temporal(tmp_path / "a" / "b")
    assert ruta.parent == tmp_path / "a" / "b" and ruta.suffix == ".mp3" and ruta.read_bytes() == b""
    habla.borrar(ruta)
    habla.borrar(ruta)  # ya no está: no falla
    habla.borrar(None)
    assert not ruta.exists()


def _comunicar(contenido=b"mp3", demora=0.0):
    llamadas = []

    class Comunicado:
        async def save(self, ruta):
            if demora:
                await asyncio.sleep(demora)
            Path(ruta).write_bytes(contenido)

    def comunicar(texto, **kw):
        llamadas.append((texto, kw))
        return Comunicado()

    comunicar.llamadas = llamadas
    return comunicar


def _edge(carpeta, comunicar):
    return habla.SintetizadorEdge("es-MX-JorgeNeural", "+15%", "-5Hz", carpeta, comunicar)


def test_sintetizador_edge(tmp_path, red_local):  # asyncio.run abre un socketpair en 127.0.0.1
    comunicar = _comunicar()
    ruta = _edge(tmp_path, comunicar)("Hola, señor.")
    assert ruta.parent == tmp_path and ruta.suffix == ".mp3" and ruta.read_bytes() == b"mp3"
    assert comunicar.llamadas == [("Hola, señor.", {"voice": "es-MX-JorgeNeural", "rate": "+15%", "pitch": "-5Hz"})]


def test_sintetizador_edge_sin_audio(tmp_path, red_local):
    with pytest.raises(voz.ErrorVoz, match="edge-tts no devolvió audio."):
        _edge(tmp_path, _comunicar(b""))("Hola, señor.")
    assert _mp3(tmp_path) == []


def test_sintetizador_edge_tiempo_agotado(tmp_path, monkeypatch, red_local):
    monkeypatch.setattr(habla, "TIEMPO_SINTESIS", 0.05)
    with pytest.raises(TimeoutError):
        _edge(tmp_path, _comunicar(demora=1.0))("Hola, señor.")
    assert _mp3(tmp_path) == []


def test_sintetizador_edge_sin_edge_tts(tmp_path):
    with pytest.raises(ImportError):  # la guardia anula edge_tts
        _edge(tmp_path, None)("Hola, señor.")


class Respuesta:
    def __init__(self, datos):
        self.datos = datos

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self.datos


class Pedir:
    def __init__(self, resultado):
        self.resultado, self.llamadas = resultado, []

    def __call__(self, req, timeout=None):
        self.llamadas.append((req, timeout))
        if isinstance(self.resultado, BaseException):
            raise self.resultado
        return Respuesta(self.resultado)


def _once(carpeta, pedir):
    return habla.SintetizadorElevenLabs(CLAVE, ID_VOZ, "eleven_flash_v2_5", carpeta, pedir)


def test_sintetizador_elevenlabs(tmp_path):
    pedir = Pedir(b"mp3")
    ruta = _once(tmp_path, pedir)("Hola, señor.")
    assert ruta.parent == tmp_path and ruta.read_bytes() == b"mp3"
    (req, timeout), = pedir.llamadas
    assert req.full_url == f"https://api.elevenlabs.io/v1/text-to-speech/{ID_VOZ}?output_format=mp3_44100_128"
    assert req.get_method() == "POST" and timeout == habla.TIEMPO_SINTESIS
    assert req.get_header("Xi-api-key") == CLAVE and CLAVE not in req.full_url
    assert json.loads(req.data) == {"text": "Hola, señor.", "model_id": "eleven_flash_v2_5"}
    assert CLAVE not in req.data.decode("utf-8")


@pytest.mark.parametrize("error, mensaje", [
    (urllib.error.HTTPError("https://api.elevenlabs.io/x", 401, "Unauthorized", {}, None), "ElevenLabs respondió 401."),
    (urllib.error.URLError(f"fallo con {CLAVE}"), "sin conexión con ElevenLabs (URLError)."),
    (TimeoutError("timed out"), "sin conexión con ElevenLabs (TimeoutError)."),
    (b"", "ElevenLabs no devolvió audio."),
])
def test_sintetizador_elevenlabs_errores(tmp_path, error, mensaje):
    with pytest.raises(voz.ErrorVoz) as e:
        _once(tmp_path, Pedir(error))("Hola, señor.")
    assert str(e.value) == mensaje and e.value.__cause__ is None
    assert e.value.__context__ is None or e.value.__suppress_context__
    assert _mp3(tmp_path) == []


def test_sintetizador_elevenlabs_sin_pedir_lo_para_la_guardia(tmp_path):
    with pytest.raises(AssertionError, match="acción real"):
        _once(tmp_path, None)("Hola, señor.")


# --- reproductor ---

class Mci:
    """Anota las órdenes; responde a "status" con `estados` (y luego "stopped"); con `falla`, lanza en esa orden."""

    def __init__(self, estados=("playing", "playing"), falla=None):
        self.estados, self.falla, self.ordenes = list(estados), falla, []

    def __call__(self, orden):
        self.ordenes.append(orden)
        if self.falla and orden.startswith(self.falla):
            raise voz.ErrorVoz("el reproductor de Windows falló: x")
        if orden.startswith("status"):
            return self.estados.pop(0) if self.estados else "stopped"
        return ""


@pytest.fixture
def sondeo_rapido(monkeypatch):
    monkeypatch.setattr(habla, "SONDEO_MCI", 0)


def test_reproductor_mci(tmp_path, sondeo_rapido):
    mci, empezado = Mci(), []
    ruta = tmp_path / "1.mp3"
    habla.ReproductorMCI(mci)(ruta, lambda: False, lambda: empezado.append(1))
    assert mci.ordenes == [f'open "{ruta}" type mpegvideo alias jarvis_voz', "play jarvis_voz"] + [
        "status jarvis_voz mode"] * 3 + ["close jarvis_voz"]
    assert empezado == [1]


def test_reproductor_mci_parar(tmp_path, sondeo_rapido):
    mci = Mci(estados=["playing"] * 100)
    habla.ReproductorMCI(mci)(tmp_path / "1.mp3", lambda: True, lambda: None)
    assert mci.ordenes[1:] == ["play jarvis_voz", "status jarvis_voz mode", "stop jarvis_voz", "close jarvis_voz"]


def test_reproductor_mci_errores(tmp_path, sondeo_rapido):
    mci = Mci(falla="play")
    with pytest.raises(voz.ErrorVoz, match="reproductor"):
        habla.ReproductorMCI(mci)(tmp_path / "1.mp3", lambda: False, lambda: None)
    assert mci.ordenes[-1] == "close jarvis_voz"

    mci = Mci()
    with pytest.raises(voz.ErrorVoz, match="ruta de audio no válida."):
        habla.ReproductorMCI(mci)(tmp_path / 'a" b.mp3', lambda: False, lambda: None)
    assert mci.ordenes == []

    with pytest.raises(AssertionError, match="acción real"):
        habla.ReproductorMCI()(tmp_path / "1.mp3", lambda: False, lambda: None)


def test_el_texto_nunca_va_en_una_orden_mci(tmp_path, sondeo_rapido):
    mci = Mci(estados=[])
    cola = habla.HablanteCola(HablanteFalso(), Sintetizador(tmp_path), habla.ReproductorMCI(mci), [].append, "edge")
    cola.decir('Hola, señor" alias x. Cierre todo & salga ya.')
    assert any(o.startswith("open") for o in mci.ordenes)
    assert not any("señor" in o or "salga" in o for o in mci.ordenes)


# --- crear_hablante ---

def _crear(entorno, carpeta):
    vistos = []
    return habla.crear_hablante(entorno, vistos.append, carpeta), vistos


def test_crear_hablante_sapi(tmp_path):
    h, vistos = _crear({"JARVIS_VOZ_MOTOR": "sapi"}, tmp_path)
    assert isinstance(h, habla.HablanteCola) and h.sintetizar is None and h._hilos == []
    assert isinstance(h.respaldo, voz.HablanteSAPI) and h.nombre == "sapi" and vistos == []


def test_crear_hablante_edge_sin_edge_tts(tmp_path):
    h, vistos = _crear({}, tmp_path)  # la guardia anula edge_tts
    assert h.sintetizar is None and isinstance(h.respaldo, voz.HablanteSAPI)
    assert vistos == [habla.SIN_EDGE]


def test_crear_hablante_valida_antes_de_importar(tmp_path):
    with pytest.raises(voz.ErrorVoz, match="JARVIS_VOZ_VELOCIDAD"):
        _crear({"JARVIS_VOZ_VELOCIDAD": "rápido"}, tmp_path)
    with pytest.raises(voz.ErrorVoz, match="ELEVENLABS_API_KEY"):
        _crear({"JARVIS_VOZ_MOTOR": "elevenlabs"}, tmp_path)


def test_crear_hablante_edge(tmp_path, monkeypatch):
    falso = types.ModuleType("edge_tts")
    falso.Communicate = lambda *a, **k: None
    monkeypatch.setitem(sys.modules, "edge_tts", falso)
    monkeypatch.setattr(habla, "CARPETA_AUDIO", tmp_path)  # la carpeta por defecto se resuelve al llamar
    (tmp_path / "viejo.mp3").write_bytes(b"mp3")
    (tmp_path / "otro.txt").write_text("x")
    vistos = []
    h = habla.crear_hablante({}, vistos.append)
    s = h.sintetizar
    assert isinstance(s, habla.SintetizadorEdge) and isinstance(h.reproducir, habla.ReproductorMCI)
    assert (s.nombre, s.velocidad, s.tono, s.carpeta, s.comunicar) == (
        "es-MX-JorgeNeural", "+15%", "-5Hz", tmp_path, falso.Communicate)
    assert h.nombre == "edge (es-MX-JorgeNeural)" and isinstance(h.respaldo, voz.HablanteSAPI) and vistos == []
    assert _mp3(tmp_path) == [] and (tmp_path / "otro.txt").exists()


def test_crear_hablante_elevenlabs(tmp_path):
    h, vistos = _crear({"JARVIS_VOZ_MOTOR": "elevenlabs", "ELEVENLABS_API_KEY": CLAVE, "ELEVENLABS_VOICE_ID": ID_VOZ},
                       tmp_path / "no-existe")
    s = h.sintetizar
    assert isinstance(s, habla.SintetizadorElevenLabs) and s.carpeta == tmp_path / "no-existe"
    assert (s.id_voz, s.modelo, h.nombre) == (ID_VOZ, "eleven_flash_v2_5", "elevenlabs") and vistos == []
