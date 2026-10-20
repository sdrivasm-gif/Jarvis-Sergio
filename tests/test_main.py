import sys

import pytest

import jarvis.__main__ as principal
from jarvis import voz


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
