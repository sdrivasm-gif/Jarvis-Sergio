import io
import json
import urllib.error
import urllib.request
from urllib.parse import parse_qs

import pytest
from clientes_falsos import sin_credenciales

from jarvis.integrations import google

FALTAN_TODAS = ("Google no está configurado: faltan GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, "
                "GOOGLE_REFRESH_TOKEN en .env (ver jarvis/README.md).")


@pytest.fixture
def credenciales_falsas(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id-falso")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secreto-falso")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "refresco-falso")
    monkeypatch.setattr(google, "_token", {})


class RespuestaFalsa:
    def __init__(self, cuerpo: bytes):
        self.cuerpo = cuerpo

    def read(self):
        return self.cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def urlopen_falso(monkeypatch, *respuestas):
    """Parchea urlopen: guarda (peticion, timeout) y devuelve las respuestas en orden (o lanza las excepciones)."""
    llamadas = []
    pendientes = list(respuestas)

    def falso(peticion, timeout=None):
        llamadas.append((peticion, timeout))
        r = pendientes.pop(0)
        if isinstance(r, BaseException):
            raise r
        return RespuestaFalsa(r if isinstance(r, bytes) else json.dumps(r).encode())

    monkeypatch.setattr(urllib.request, "urlopen", falso)
    return llamadas


def test_sin_variables_no_toca_la_red(monkeypatch):
    sin_credenciales(monkeypatch, google)  # urlopen sin parchear: si llegara a la red, la guardia daría AssertionError
    with pytest.raises(google.ErrorIntegracion) as error:
        google.pedir("GET", "https://api.example/x")
    assert str(error.value) == FALTAN_TODAS


def test_solo_nombra_las_que_faltan(credenciales_falsas, monkeypatch):
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "   ")
    with pytest.raises(google.ErrorIntegracion) as error:
        google.pedir("GET", "https://api.example/x")
    assert "faltan GOOGLE_REFRESH_TOKEN en" in str(error.value)
    assert "CLIENT_ID" not in str(error.value)


def test_pide_token_y_lo_reutiliza(credenciales_falsas, monkeypatch):
    llamadas = urlopen_falso(monkeypatch, {"access_token": "tok-falso", "expires_in": 3600}, {"n": 1}, {"n": 2})
    assert google.pedir("GET", "https://api.example/x") == {"n": 1}
    assert google.pedir("GET", "https://api.example/y") == {"n": 2}
    assert len(llamadas) == 3
    token = llamadas[0][0]
    assert token.full_url == google.URL_TOKEN
    assert token.get_method() == "POST"
    datos = parse_qs(token.data.decode())
    assert datos["grant_type"] == ["refresh_token"]
    assert datos["refresh_token"] == ["refresco-falso"]
    assert datos["client_id"] == ["id-falso"]
    assert all(p.get_header("Authorization") == "Bearer tok-falso" for p, _ in llamadas[1:])
    assert all(t == 15 for _, t in llamadas)


def test_token_guardado_y_caducado(credenciales_falsas, monkeypatch):
    monkeypatch.setattr(google, "_token", {"valor": "tok-guardado", "vence": float("inf")})
    llamadas = urlopen_falso(monkeypatch, {"ok": 1})
    google.pedir("GET", "https://api.example/x")
    assert len(llamadas) == 1
    assert llamadas[0][0].get_header("Authorization") == "Bearer tok-guardado"

    monkeypatch.setattr(google, "_token", {"valor": "viejo", "vence": 0})
    llamadas = urlopen_falso(monkeypatch, {"access_token": "tok-falso"}, {"ok": 1})
    google.pedir("GET", "https://api.example/x")
    assert len(llamadas) == 2


def test_params_y_cuerpo(credenciales_falsas, monkeypatch):
    monkeypatch.setattr(google, "_token", {"valor": "tok-falso", "vence": float("inf")})
    llamadas = urlopen_falso(monkeypatch, b"")
    resultado = google.pedir("POST", "https://api.example/x", params={"a": "1", "h": ["From", "Subject"]},
                             cuerpo={"k": "v"})
    assert resultado == {}
    peticion = llamadas[0][0]
    assert peticion.full_url == "https://api.example/x?a=1&h=From&h=Subject"
    assert peticion.data == b'{"k": "v"}'
    assert peticion.get_header("Content-type") == "application/json"


def test_error_http_sin_secretos(credenciales_falsas, monkeypatch):
    cuerpo = b'{"error": "invalid_grant", "error_description": "Token has been expired or revoked."}'
    urlopen_falso(monkeypatch, urllib.error.HTTPError(google.URL_TOKEN, 400, "Bad Request", {}, io.BytesIO(cuerpo)))
    with pytest.raises(google.ErrorIntegracion) as error:
        google.pedir("GET", "https://api.example/x")
    assert str(error.value) == "Google respondió 400: Token has been expired or revoked."
    assert "secreto-falso" not in str(error.value) and "refresco-falso" not in str(error.value)

    monkeypatch.setattr(google, "_token", {"valor": "tok-falso", "vence": float("inf")})
    cuerpo = b'{"error": {"code": 403, "message": "Insufficient Permission"}}'
    urlopen_falso(monkeypatch, urllib.error.HTTPError("https://api.example/x", 403, "Forbidden", {},
                                                      io.BytesIO(cuerpo)))
    with pytest.raises(google.ErrorIntegracion) as error:
        google.pedir("GET", "https://api.example/x")
    assert str(error.value) == "Google respondió 403: Insufficient Permission"


def test_sin_conexion(credenciales_falsas, monkeypatch):
    urlopen_falso(monkeypatch, urllib.error.URLError("sin red"))
    with pytest.raises(google.ErrorIntegracion) as error:
        google.pedir("GET", "https://api.example/x")
    assert str(error.value) == "No pude conectar con Google: sin red"


def test_validadores():
    assert google.ID_VALIDO.fullmatch("abc_123-X")
    for raro in ("../x", "a/b", ""):
        assert not google.ID_VALIDO.fullmatch(raro)
    assert google.CORREO_VALIDO.fullmatch("ana@example.com")
    for raro in ("ana", "ana@example.com, luis@example.com", "ana@example.com\nBcc: x@example.com",
                 "ana\x1b[1A@example.com", "ana@exa\x00mple.com", "ana@example.com\x7f", "ana@example.co\x85m"):
        assert not google.CORREO_VALIDO.fullmatch(raro)
