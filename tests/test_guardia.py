"""La guardia de conftest.py bloquea red, sockets y procesos en todos los tests."""
import http.client
import socket
import subprocess
import urllib.request

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
