"""La guardia de conftest.py bloquea red, sockets y procesos en todos los tests."""
import http.client
import socket
import subprocess
import urllib.request
import webbrowser

import pytest

# TEST-NET-1 (RFC 5737) con IP literal: no hay DNS y nunca es un equipo real.
DESTINO = ("192.0.2.1", 80)


def test_bloquea_urlopen():
    with pytest.raises(AssertionError, match="acción real"):
        urllib.request.urlopen("https://example.com")


def test_bloquea_sockets():
    with pytest.raises(AssertionError, match="acción real"):
        socket.create_connection(DESTINO, timeout=1)
    with pytest.raises(AssertionError, match="acción real"):
        with socket.socket() as s:
            s.connect_ex(DESTINO)


def test_bloquea_http_client():
    with pytest.raises(AssertionError, match="acción real"):
        http.client.HTTPSConnection("192.0.2.1", timeout=1).request("GET", "/")


def test_bloquea_procesos():
    with pytest.raises(AssertionError, match="acción real"):
        subprocess.Popen(["whoami"])
    with pytest.raises(AssertionError, match="acción real"):
        subprocess.run(["whoami"])


def test_bloquea_navegador():
    for abrir in (webbrowser.open, webbrowser.open_new, webbrowser.open_new_tab):
        with pytest.raises(AssertionError, match="acción real"):
            abrir("https://example.com")


def _servidor_local():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen()
    return srv


def test_local_bloqueado_sin_fixture():
    srv = _servidor_local()
    try:
        with pytest.raises(AssertionError, match="acción real"):
            socket.create_connection(srv.getsockname(), timeout=1)
    finally:
        srv.close()


def test_red_local_solo_127(red_local):
    srv = _servidor_local()
    try:
        socket.create_connection(srv.getsockname(), timeout=1).close()
    finally:
        srv.close()
    with pytest.raises(AssertionError, match="acción real"):
        socket.create_connection(DESTINO, timeout=1)
    with pytest.raises(AssertionError, match="acción real"):
        http.client.HTTPSConnection("192.0.2.1", timeout=1).request("GET", "/")
    with pytest.raises(AssertionError, match="acción real"):
        with socket.socket() as s:
            s.connect_ex(("127.0.0.1", 1))


def test_sin_microfono_ni_altavoz():
    with pytest.raises(ImportError):
        import sounddevice  # noqa: F401
    with pytest.raises(ImportError):
        import pyaudio  # noqa: F401
