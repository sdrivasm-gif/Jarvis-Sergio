import http.client
import inspect
import json
import threading
import time
from datetime import datetime

import pytest
from clientes_falsos import CorreoFalso, instalar, sin_credenciales

from jarvis.integrations import correo, google
from jarvis.ui import servidor
from jarvis.ui.sesion import Sesion

TOKEN = "t" * 43
PUERTO = 8765
ORIGEN = "http://127.0.0.1:8765"
AHORA = datetime(2026, 10, 20, 8, 0)
SIN_GOOGLE = ("No disponible: Google no está configurado: faltan GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, "
              "GOOGLE_REFRESH_TOKEN en .env (ver jarvis/README.md).")
ARGS = {"para": "ana@example.com", "cuerpo": "Hola\nAna"}
TEXTO_CONF = "¿Ejecutar correo_enviar?\n  para: ana@example.com\n  cuerpo: Hola\n    Ana"
CAB = {"Host": "127.0.0.1:8765", "X-Jarvis-Token": TOKEN}
POST_CAB = {**CAB, "Origin": ORIGEN, "Content-Type": "application/json"}
URL = "http://127.0.0.1:8765/#" + TOKEN
TITULOS = ["Eventos de hoy", "Correos sin leer", "Notas recientes", "Recordatorios de hoy"]


def esperar(condicion, tiempo=2.0):
    limite = time.monotonic() + tiempo
    while not condicion():
        if time.monotonic() > limite:
            pytest.fail(f"no se cumplió la condición en {tiempo} s")
        time.sleep(0.01)


def sesion():
    return Sesion(token=TOKEN)


def pedir(s, metodo, ruta, cabeceras=CAB, cuerpo=b""):
    r = servidor.atender(s, metodo, ruta, cabeceras, cuerpo, PUERTO, lambda: AHORA)
    assert servidor.CABECERAS_SEGURIDAD.items() <= r.cabeceras.items()
    assert "Access-Control-Allow-Origin" not in r.cabeceras
    assert TOKEN.encode() not in r.cuerpo
    assert all(TOKEN not in v for v in r.cabeceras.values())
    return r


def datos(r):
    return json.loads(r.cuerpo.decode("utf-8"))


def post(s, ruta, objeto, cabeceras=POST_CAB):
    return pedir(s, "POST", ruta, cabeceras, json.dumps(objeto).encode())


# 1
def test_estaticos():
    s = sesion()
    for ruta, (nombre, tipo) in [*servidor.ESTATICOS.items(), ("/?x=1", servidor.ESTATICOS["/"])]:
        for cab in (CAB, {"Host": "127.0.0.1:8765"}):
            r = pedir(s, "GET", ruta, cab)
            assert r.codigo == 200 and r.cabeceras["Content-Type"] == tipo
            assert r.cuerpo == (servidor.CARPETA / nombre).read_bytes()
    assert servidor.ESTATICOS["/"][1] == "text/html; charset=utf-8"


# 2
@pytest.mark.parametrize("ruta", ["/index.html", "/../jarvis/bucle.py", "/sesion.py", "/api", "/api/nada",
                                  "//etc/passwd", "/app.js/.."])
def test_rutas_desconocidas(ruta):
    r = pedir(sesion(), "GET", ruta)
    assert r.codigo == 404 and datos(r) == {"error": "no existe"}


# 3
def test_metodos():
    s = sesion()
    for metodo, ruta in [("POST", "/"), ("GET", "/api/mensaje"), ("POST", "/api/estado")]:
        r = pedir(s, metodo, ruta, POST_CAB if metodo == "POST" else CAB, b"{}")
        assert r.codigo == 405 and datos(r) == {"error": "método no permitido"}


# 4
@pytest.mark.parametrize("host", [None, "evil.example.com", "localhost:8765", "127.0.0.1", "127.0.0.1:9999",
                                  "127.0.0.1:8765.evil.example.com"])
@pytest.mark.parametrize("ruta", ["/", "/api/estado"])
def test_host_no_permitido(host, ruta):
    cab = {k: v for k, v in CAB.items() if k != "Host"}
    if host is not None:
        cab["Host"] = host
    r = pedir(sesion(), "GET", ruta, cab)
    assert r.codigo == 403 and datos(r) == {"error": "host no permitido"}


# 5
@pytest.mark.parametrize("token", [None, "", "t" * 42, "T" * 43, "ñ" * 43])
def test_token(token):
    cab = {"Host": CAB["Host"]} if token is None else {**CAB, "X-Jarvis-Token": token}
    r = pedir(sesion(), "GET", "/api/estado", cab)
    assert r.codigo == 403 and datos(r) == {"error": "token no válido"}
    assert pedir(sesion(), "GET", "/api/estado").codigo == 200


# 6
def test_origen():
    s = sesion()
    for origen in ("http://evil.example.com", "null", "http://localhost:8765", "https://127.0.0.1:8765"):
        r = pedir(s, "GET", "/api/estado", {**CAB, "Origin": origen})
        assert r.codigo == 403 and datos(r) == {"error": "origen no permitido"}
    assert pedir(s, "GET", "/api/estado").codigo == 200
    assert pedir(s, "GET", "/api/estado", {**CAB, "Origin": ORIGEN}).codigo == 200
    sin_origen = {k: v for k, v in POST_CAB.items() if k != "Origin"}
    r = post(s, "/api/mensaje", {"texto": "hola"}, sin_origen)
    assert r.codigo == 403 and datos(r) == {"error": "origen no permitido"} and s.ocupado is False
    for sitio in ("cross-site", "same-site", "none"):
        r = pedir(s, "GET", "/api/estado", {**CAB, "Sec-Fetch-Site": sitio})
        assert r.codigo == 403 and datos(r) == {"error": "origen no permitido"}
    assert pedir(s, "GET", "/api/estado", {**CAB, "Sec-Fetch-Site": "same-origin"}).codigo == 200


# 7
def test_mensaje():
    s = sesion()
    r = post(s, "/api/mensaje", {"texto": "hola"})
    assert r.codigo == 202 and datos(r) == {"ok": True}
    ultimo = s.instantanea()["mensajes"][-1]
    assert (ultimo["quien"], ultimo["texto"]) == ("usuario", "hola") and s.ocupado is True
    r = post(s, "/api/mensaje", {"texto": "otra"})
    assert r.codigo == 409 and datos(r) == {"error": "Jarvis está ocupado"}

    r = post(sesion(), "/api/mensaje", {"texto": "hola"}, {**POST_CAB, "Content-Type": "text/plain"})
    assert r.codigo == 415 and datos(r) == {"error": "se espera application/json"}
    r = post(sesion(), "/api/mensaje", {"texto": "hola"}, {**POST_CAB, "Content-Type": "application/json; charset=utf-8"})
    assert r.codigo == 202

    for cuerpo in (b"no json", b"[1]", b'{"texto": 5}', b'{"texto": "  "}', json.dumps({"texto": "x" * 4001}).encode(),
                   b"\xff", b"[" * 5000 + b"]" * 5000):
        s = sesion()
        r = pedir(s, "POST", "/api/mensaje", POST_CAB, cuerpo)
        assert r.codigo == 400 and "error" in datos(r) and s.ocupado is False
    r = pedir(sesion(), "POST", "/api/mensaje", POST_CAB, b" " * (servidor.MAX_CUERPO + 1))
    assert r.codigo == 413


# 8
def test_confirmar_por_http():
    s = sesion()
    resultado = []
    hilo = threading.Thread(target=lambda: resultado.append(s.confirmar("correo_enviar", ARGS)), daemon=True)
    hilo.start()
    esperar(lambda: s.instantanea()["confirmacion"] is not None)
    assert datos(pedir(s, "GET", "/api/estado"))["confirmacion"] == {"id": 1, "texto": TEXTO_CONF, "segundos": 60}
    for cuerpo in ({"id": 1, "si": "true"}, {"id": True, "si": True}):
        r = post(s, "/api/confirmar", cuerpo)
        assert r.codigo == 400 and datos(r) == {"error": 'se espera {"id": entero, "si": true|false}'}
    r = post(s, "/api/confirmar", {"id": 2, "si": True})
    assert r.codigo == 409 and datos(r) == {"error": "no hay esa confirmación pendiente"}
    r = post(s, "/api/confirmar", {"id": 1, "si": True})
    assert r.codigo == 200 and datos(r) == {"ok": True}
    hilo.join(2)
    assert not hilo.is_alive() and resultado == [True]
    assert post(s, "/api/confirmar", {"id": 1, "si": True}).codigo == 409


# 9
def test_estado_desde():
    s = sesion()
    for x in "abc":
        s.anotar("sistema", x)
    d = datos(pedir(s, "GET", "/api/estado?desde=1"))
    assert [m["id"] for m in d["mensajes"]] == [2, 3] and d["ultimo"] == 3
    assert set(d) == {"estado", "ocupado", "voz", "confirmacion", "mensajes", "ultimo"}
    for desde in ("abc", "-1", "1e3"):
        r = pedir(s, "GET", "/api/estado?desde=" + desde)
        assert r.codigo == 400 and datos(r) == {"error": "desde no válido"}


# 10
def test_hoy_sin_google(monkeypatch):
    sin_credenciales(monkeypatch, google)
    r = pedir(sesion(), "GET", "/api/hoy")
    d = datos(r)
    assert r.codigo == 200 and d["titulo"] == "Parte del martes 2026-10-20, a las 08:00."
    assert [x["titulo"] for x in d["secciones"]] == TITULOS
    assert d["secciones"][0]["texto"] == SIN_GOOGLE and d["secciones"][2]["texto"] == "No hay notas."


# 11
def test_hoy_devuelve_texto_externo_tal_cual(monkeypatch):
    sin_credenciales(monkeypatch, google)
    asunto = "<img src=x onerror=alert(1)>"
    instalar(monkeypatch, correo, CorreoFalso([{"id": "m1", "de": "Ana <ana@example.com>", "asunto": asunto,
                                                "fecha": "Mon, 19 Oct 2026 09:30:00 -0500", "resumen": "x"}]))
    r = pedir(sesion(), "GET", "/api/hoy")
    assert asunto in datos(r)["secciones"][1]["texto"]
    assert asunto.encode() in r.cuerpo  # el servidor no escapa: la página usa textContent


# 12
@pytest.mark.parametrize("cabeceras, codigo", [
    ({}, 411), ({"Content-Length": "abc"}, 400), ({"Content-Length": "-1"}, 400), ({"Content-Length": "١٢"}, 400),
    ({"Content-Length": str(servidor.MAX_CUERPO + 1)}, 413),
    ({"Content-Length": "0" * 5000}, 413),  # int() de más de 4300 dígitos daría ValueError
    ({"Content-Length": "10", "Transfer-Encoding": "chunked"}, 411),
])
def test_longitud(cabeceras, codigo):
    with pytest.raises(servidor.ErrorHTTP) as e:
        servidor.longitud(cabeceras)
    assert e.value.codigo == codigo


def test_longitud_valida():
    assert servidor.longitud({"Content-Length": "16"}) == 16


# 13
def test_puerto_de():
    assert servidor.puerto_de({}) == servidor.puerto_de({"JARVIS_UI_PUERTO": " "}) == 0
    assert servidor.puerto_de({"JARVIS_UI_PUERTO": "0"}) == 0
    assert servidor.puerto_de({"JARVIS_UI_PUERTO": "8765"}) == 8765
    for valor in ("80", "70000", "abc", "-1"):
        with pytest.raises(servidor.ErrorUI) as e:
            servidor.puerto_de({"JARVIS_UI_PUERTO": valor})
        assert str(e.value) == f"JARVIS_UI_PUERTO='{valor}' no es válido; usa 0 (libre) o un entero entre 1024 y 65535."


# 14
def test_csp():
    for parte in ("default-src 'none'", "script-src 'self'", "frame-ancestors 'none'", "form-action 'none'"):
        assert parte in servidor.CSP
    assert "unsafe" not in servidor.CSP and "*" not in servidor.CSP


# 15
def test_buscar_edge(tmp_path):
    assert servidor.buscar_edge({}, which=lambda n: "C:/x/msedge.exe") == "C:/x/msedge.exe"
    edge = tmp_path / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    edge.parent.mkdir(parents=True)
    edge.write_bytes(b"")
    assert servidor.buscar_edge({"ProgramFiles(x86)": str(tmp_path)}, which=lambda n: None) == str(edge)
    assert servidor.buscar_edge({}, which=lambda n: None) is None


# 16
def test_abrir_ventana():
    abiertos, navegados = [], []

    def abrir(*args, **kwargs):
        abiertos.append((args, kwargs))

    def navegador(url):
        navegados.append(url)
        return True

    assert servidor.abrir_ventana(URL, buscar=lambda: "msedge.exe", abrir=abrir, navegador=navegador) is True
    args, kwargs = abiertos[0]
    assert args[0] == ["msedge.exe", "--app=" + URL, "--window-size=1100,720"]
    assert "shell" not in kwargs and navegados == []

    def roto(*args, **kwargs):
        raise OSError("no arranca")

    assert servidor.abrir_ventana(URL, buscar=lambda: "msedge.exe", abrir=roto, navegador=navegador) is True
    assert navegados == [URL]
    assert servidor.abrir_ventana(URL, buscar=lambda: None, abrir=roto, navegador=navegador) is True
    assert servidor.abrir_ventana(URL, buscar=lambda: None, navegador=lambda url: False) is False
    with pytest.raises(AssertionError, match="acción real"):  # sin abrir inyectado, la guardia para el Popen
        servidor.abrir_ventana(URL, buscar=lambda: "msedge.exe", navegador=navegador)
    with pytest.raises(AssertionError, match="acción real"):  # y sin navegador, el webbrowser.open
        servidor.abrir_ventana(URL, buscar=lambda: None)


# 17
def test_solo_escucha_en_127():
    srv = servidor.crear_servidor(Sesion(token=TOKEN), 0)
    try:
        assert srv.server_address[0] == "127.0.0.1"
        assert servidor.ServidorUI.allow_reuse_address is False
        assert list(inspect.signature(servidor.crear_servidor).parameters) == ["sesion", "puerto"]
    finally:
        srv.server_close()


def test_handle_error_sin_traza(capsys):
    srv = servidor.crear_servidor(Sesion(token=TOKEN), 0)
    try:
        for e in (ValueError("secreto " + TOKEN), ConnectionResetError("x")):
            try:
                raise e
            except Exception:
                srv.handle_error(None, ("127.0.0.1", 1))
    finally:
        srv.server_close()
    salida = capsys.readouterr()
    assert salida.out == "" and salida.err == "(UI) error atendiendo una petición: ValueError\n"


# 18
@pytest.fixture
def en_marcha():
    srv = servidor.crear_servidor(Sesion(token=TOKEN), 0)
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    yield srv.server_address[1]
    srv.shutdown()
    srv.server_close()
    hilo.join(2)
    assert not hilo.is_alive()


def test_peticiones_reales(red_local, en_marcha, capsys):
    puerto = en_marcha

    def conexion():
        return http.client.HTTPConnection("127.0.0.1", puerto, timeout=5)

    c = conexion()
    c.request("GET", "/")
    r = c.getresponse()
    r.read()
    assert r.status == 200 and r.getheader("Content-Security-Policy") == servidor.CSP
    assert r.getheader("Access-Control-Allow-Origin") is None
    c.close()

    c = conexion()
    c.request("GET", "/api/estado", headers={"X-Jarvis-Token": TOKEN})
    r = c.getresponse()
    assert r.status == 200 and json.loads(r.read())["estado"] == "reposo"
    c.close()

    c = conexion()
    c.request("GET", "/api/estado", headers={"Host": f"localhost:{puerto}", "X-Jarvis-Token": TOKEN})
    r = c.getresponse()
    r.read()
    assert r.status == 403
    c.close()

    c = conexion()
    c.putrequest("POST", "/api/mensaje")
    c.putheader("Content-Length", "999999")
    c.endheaders()
    inicio = time.monotonic()
    r = c.getresponse()
    r.read()
    assert r.status == 413 and time.monotonic() - inicio < 5
    c.close()

    salida = capsys.readouterr()
    assert salida.out == "" and salida.err == ""
