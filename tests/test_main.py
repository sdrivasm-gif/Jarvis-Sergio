import http.client
import json
import re
import sys
from types import SimpleNamespace

import pytest
from clientes_falsos import HablanteFalso, OyenteFalso

import jarvis.__main__ as principal
from jarvis import voz
from jarvis.ui import servidor as ui
from jarvis.ui.sesion import Sesion

URL_UI = re.compile(r"http://127\.0\.0\.1:(\d+)/#([A-Za-z0-9_-]{43})")


def test_main_sin_clave_devuelve_1_sin_tocar_la_red(monkeypatch, capsys):
    for variable in ("JARVIS_PROVIDER", "JARVIS_MODEL", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "claude")  # el proveedor por defecto (claude-cli) no pide clave
    monkeypatch.setattr(principal, "load_dotenv", lambda: None)  # no se lee el .env real

    def prohibido(*args, **kwargs):
        raise AssertionError("no debía crear el cliente ni conversar")

    monkeypatch.setattr(principal, "crear_cliente", prohibido)
    monkeypatch.setattr(principal, "conversar", prohibido)

    assert principal.main() == 1
    salida = capsys.readouterr()
    assert "ANTHROPIC_API_KEY" in salida.err
    assert salida.out == ""


def test_claude_cli_avisa_que_no_hay_herramientas(monkeypatch, capsys):
    monkeypatch.delenv("JARVIS_PROVIDER", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "claude-cli")
    monkeypatch.setattr(principal, "load_dotenv", lambda: None)  # no se lee el .env real
    monkeypatch.setattr(principal, "crear_cliente", lambda config: None)
    monkeypatch.setattr(principal, "conversar", lambda cliente, herramientas: None)

    assert principal.main() == 0
    err = capsys.readouterr().err
    assert "claude-cli" in err and "herramientas" in err


@pytest.fixture
def capturado(monkeypatch):
    """main() sin .env, con claude-cli y sin cliente ni herramientas reales; guarda (args, kwargs) de conversar."""
    monkeypatch.delenv("JARVIS_PROVIDER", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "claude-cli")
    monkeypatch.setattr(principal, "load_dotenv", lambda: None)
    monkeypatch.setattr(principal, "crear_cliente", lambda config: "cliente")
    monkeypatch.setattr(principal, "cargar_herramientas", lambda: {})
    llamadas = []
    monkeypatch.setattr(principal, "conversar", lambda *args, **kwargs: llamadas.append((args, kwargs)))
    return llamadas


def test_sin_voz_no_prepara_la_voz(monkeypatch, capturado):
    def prohibido(*args, **kwargs):
        raise AssertionError("no debía preparar la voz")

    monkeypatch.setattr(voz, "preparar", prohibido)
    assert principal.main([]) == 0
    assert capturado == [(("cliente", {}), {})]


def test_voz_sin_dependencias_sigue_con_texto(monkeypatch, capsys, capturado):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)  # la guardia ya anula sounddevice
    assert principal.main(["--voz"]) == 0
    assert capturado == [(("cliente", {}), {})]
    err = capsys.readouterr().err
    assert "Voz desactivada: " in err and 'pip install -e ".[voz]"' in err and "Sigo solo con texto." in err


def test_voz_activa_pasa_las_piezas(monkeypatch, capturado):
    monkeypatch.setattr(voz, "preparar", lambda entorno: {"fragmento": None, "marca": 1})
    assert principal.main(["--voz"]) == 0
    monkeypatch.setenv("JARVIS_VOZ", "on")
    assert principal.main([]) == 0
    monkeypatch.setenv("JARVIS_VOZ", "off")
    assert principal.main([]) == 0
    assert [kwargs for _, kwargs in capturado] == [{"fragmento": None, "marca": 1}, {"fragmento": None, "marca": 1}, {}]


@pytest.fixture
def ui_simulada(monkeypatch, capturado):
    """--ui sin ventana ni conversación real: el servidor real se crea en 127.0.0.1 y se cierra."""
    u = SimpleNamespace(abiertas=[], llamadas=[], creados=[], abre=True)

    def abrir_ventana(url):
        u.abiertas.append(url)
        return u.abre

    crear_real = ui.crear_servidor

    def crear_servidor(sesion, puerto=0):
        u.creados.append(crear_real(sesion, puerto))
        return u.creados[-1]

    monkeypatch.setattr(ui, "abrir_ventana", abrir_ventana)
    monkeypatch.setattr(ui, "conversar", lambda *args, **kwargs: u.llamadas.append((args, kwargs)))
    monkeypatch.setattr(ui, "crear_servidor", crear_servidor)
    monkeypatch.delenv("JARVIS_UI_PUERTO", raising=False)
    return u


def test_ui_arranca_imprime_la_url_y_se_detiene(ui_simulada, capturado, capsys):
    assert principal.main(["--ui"]) == 0
    assert capturado == []  # no conversa por la terminal
    [(args, kwargs)] = ui_simulada.llamadas
    assert args == ("cliente", {})
    assert set(kwargs) == {"entrada", "salida", "confirmar", "fragmento"} and kwargs["fragmento"] is None
    puerto, token = URL_UI.fullmatch(ui_simulada.abiertas[0]).groups()
    salida = capsys.readouterr()
    assert f"Jarvis UI en http://127.0.0.1:{puerto}/" in salida.out
    assert token not in salida.out + salida.err
    assert ui_simulada.creados[0].socket.fileno() == -1  # el servidor quedó cerrado


def test_ui_sin_ventana_muestra_la_url(ui_simulada, capsys):
    ui_simulada.abre = False
    assert principal.main(["--ui"]) == 0
    assert ui_simulada.abiertas[0] in capsys.readouterr().out


def test_ui_puerto_invalido(ui_simulada, monkeypatch, capsys):
    monkeypatch.setenv("JARVIS_UI_PUERTO", "80")
    assert principal.main(["--ui"]) == 1
    assert "JARVIS_UI_PUERTO='80' no es válido" in capsys.readouterr().err
    assert ui_simulada.abiertas == ui_simulada.creados == []


def test_ui_puerto_ocupado(ui_simulada, monkeypatch, capsys):
    def ocupado(sesion, puerto=0):
        raise OSError("en uso")

    monkeypatch.setattr(ui, "crear_servidor", ocupado)
    assert principal.main(["--ui"]) == 1
    assert "No pude abrir el puerto 0: en uso. Prueba con JARVIS_UI_PUERTO=0." in capsys.readouterr().err
    assert ui_simulada.abiertas == ui_simulada.llamadas == []


def test_ui_con_voz_sin_dependencias(ui_simulada, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)  # la guardia ya anula sounddevice
    assert principal.main(["--ui", "--voz"]) == 0
    assert "Voz desactivada: " in capsys.readouterr().err
    [(_, kwargs)] = ui_simulada.llamadas
    assert kwargs["salida"].__func__ is Sesion.anotar_linea


def test_ui_con_voz_usa_motores(ui_simulada, monkeypatch, capsys):
    mostrados = []

    def motores(entorno, mostrar=print):
        mostrados.append(mostrar)
        return OyenteFalso(), HablanteFalso(), ["jarvis"]

    monkeypatch.setattr(voz, "motores", motores)
    assert principal.main(["--ui", "--voz"]) == 0
    assert "Voz activada: di «jarvis»" in capsys.readouterr().out
    [(_, kwargs)] = ui_simulada.llamadas
    assert getattr(kwargs["salida"], "__func__", None) is not Sesion.anotar_linea  # es la salida de voz
    assert isinstance(kwargs["fragmento"], voz.FragmentoDeVoz)
    assert mostrados[0].__func__ is Sesion.anotar_linea  # los avisos de la voz salen en la página


def test_ui_extremo_a_extremo(ui_simulada, red_local, monkeypatch):
    respuestas = []

    def conversar(*args, **kwargs):
        puerto, token = URL_UI.fullmatch(ui_simulada.abiertas[0]).groups()
        c = http.client.HTTPConnection("127.0.0.1", int(puerto), timeout=5)
        try:
            c.request("GET", "/api/estado", headers={"X-Jarvis-Token": token})
            r = c.getresponse()
            respuestas.append((r.status, json.loads(r.read())))
        finally:
            c.close()

    monkeypatch.setattr(ui, "conversar", conversar)
    assert principal.main(["--ui"]) == 0
    [(estado, datos)] = respuestas
    assert estado == 200 and datos["estado"] == "reposo"


def test_sin_ui_no_lanza(capturado, monkeypatch):
    def prohibido(*args, **kwargs):
        raise AssertionError("no debía lanzar la UI")

    monkeypatch.setattr(ui, "lanzar", prohibido)
    assert principal.main([]) == 0
    assert capturado == [(("cliente", {}), {})]
