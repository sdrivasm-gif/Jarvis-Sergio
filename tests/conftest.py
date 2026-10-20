import http.client
import os
import socket
import subprocess
import sys
import urllib.request
import webbrowser

import pytest

# Guardados al importar, antes de que la guardia los sustituya: solo los usa el fixture red_local.
_CONECTAR_REAL = socket.socket.connect
_HTTP_CONECTAR_REAL = http.client.HTTPConnection.connect


def _prohibido(*args, **kwargs):
    raise AssertionError("un test intentó una acción real (app, proceso o red)")


@pytest.fixture(autouse=True)
def sin_efectos_reales(monkeypatch):
    """Red de seguridad: ningún test abre apps reales, lanza procesos ni sale a la red."""
    # ponytail: la resolución DNS (getaddrinfo) no se bloquea, y ClienteClaudeCLI(abrir=subprocess.Popen)
    # liga Popen al importarse, así que se salta la guardia (los tests siempre inyectan `abrir`).
    monkeypatch.setattr(os, "startfile", _prohibido, raising=False)  # raising=False: startfile solo existe en Windows
    monkeypatch.setattr(urllib.request, "urlopen", _prohibido)
    monkeypatch.setattr(subprocess, "run", _prohibido)
    monkeypatch.setattr(subprocess, "Popen", _prohibido)
    monkeypatch.setattr(socket.socket, "connect", _prohibido)
    monkeypatch.setattr(socket.socket, "connect_ex", _prohibido)
    monkeypatch.setattr(http.client.HTTPConnection, "connect", _prohibido)  # HTTPSConnection lo hereda vía super()
    # Ningún test abre el micrófono ni el altavoz: importar estos módulos da ImportError.
    monkeypatch.setitem(sys.modules, "sounddevice", None)
    monkeypatch.setitem(sys.modules, "pyaudio", None)
    monkeypatch.delenv("JARVIS_VOZ", raising=False)  # la voz solo se activa si el test lo pide
    for nombre in ("open", "open_new", "open_new_tab"):  # ningún test abre el navegador
        monkeypatch.setattr(webbrowser, nombre, _prohibido)


@pytest.fixture
def red_local(monkeypatch):
    """Solo para los tests del servidor de la UI: deja conectar a 127.0.0.1; cualquier otro destino sigue prohibido."""
    def conectar(sock, direccion, *args, **kwargs):
        if not (isinstance(direccion, tuple) and direccion[:1] == ("127.0.0.1",)):
            _prohibido()
        return _CONECTAR_REAL(sock, direccion, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", conectar)
    monkeypatch.setattr(http.client.HTTPConnection, "connect", _HTTP_CONECTAR_REAL)  # conecta vía socket.connect (filtrado)


@pytest.fixture(autouse=True)
def datos_en_tmp(tmp_path, monkeypatch):
    """Ningún test lee ni escribe la carpeta datos/ real: JARVIS_DATOS apunta a tmp_path/datos."""
    monkeypatch.setenv("JARVIS_DATOS", str(tmp_path / "datos"))
