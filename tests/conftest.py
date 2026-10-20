import http.client
import os
import socket
import subprocess
import urllib.request

import pytest


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


@pytest.fixture(autouse=True)
def datos_en_tmp(tmp_path, monkeypatch):
    """Ningún test lee ni escribe la carpeta datos/ real: JARVIS_DATOS apunta a tmp_path/datos."""
    monkeypatch.setenv("JARVIS_DATOS", str(tmp_path / "datos"))
