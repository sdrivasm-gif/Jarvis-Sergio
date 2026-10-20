"""Servidor local de la interfaz HUD: solo 127.0.0.1, token por sesión, sin CORS ni logs."""
from __future__ import annotations

import hmac
import json
import os
import shutil
import socketserver
import subprocess
import sys
import threading
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from jarvis import hoy, voz
from jarvis.bucle import conversar
from jarvis.ui.sesion import Sesion, piezas_ui, piezas_ui_voz

# ponytail: cerrar la ventana no detiene Jarvis (se cierra con la consola o Ctrl+C); apagarse si la página deja
#   de consultar, con cuidado de que Edge frena los temporizadores de las ventanas minimizadas.
# ponytail: el token aparece en la línea de comandos de msedge.exe (visible para los procesos del usuario);
#   pasarlo por otra vía si eso deja de ser aceptable.
# ponytail: sin icono propio; añadir un favicon y el icono del acceso directo.
HOST = "127.0.0.1"
PUERTO_POR_DEFECTO = 0            # 0 = un puerto libre en cada arranque
MAX_CUERPO = 16_384
MAX_TEXTO = 4000
TIEMPO_SOCKET = 15                # s por conexión (una conexión lenta no retiene un hilo para siempre)
CARPETA = Path(__file__).parent
CABECERA_TOKEN = "X-Jarvis-Token"
ESTATICOS = {"/": ("index.html", "text/html; charset=utf-8"),
             "/app.js": ("app.js", "text/javascript; charset=utf-8"),
             "/estilo.css": ("estilo.css", "text/css; charset=utf-8")}
RUTAS_API = {"/api/estado": "GET", "/api/hoy": "GET", "/api/mensaje": "POST", "/api/confirmar": "POST"}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
CABECERAS_SEGURIDAD = {"Content-Security-Policy": CSP, "X-Content-Type-Options": "nosniff",
                       "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store",
                       "Cross-Origin-Opener-Policy": "same-origin", "Cross-Origin-Resource-Policy": "same-origin"}
ARGS_VENTANA = ("--window-size=1100,720",)


class ErrorUI(Exception):
    """Configuración de la UI no válida (puerto)."""


class ErrorHTTP(Exception):
    def __init__(self, codigo: int, mensaje: str):
        super().__init__(mensaje)
        self.codigo = codigo


@dataclass
class RespuestaHTTP:
    codigo: int
    cabeceras: dict[str, str]
    cuerpo: bytes


def respuesta_json(codigo: int, datos) -> RespuestaHTTP:
    return RespuestaHTTP(codigo, {**CABECERAS_SEGURIDAD, "Content-Type": "application/json; charset=utf-8"},
                         json.dumps(datos, ensure_ascii=False).encode("utf-8"))


def error(codigo: int, mensaje: str) -> RespuestaHTTP:
    return respuesta_json(codigo, {"error": mensaje})


def _digitos(valor: str) -> bool:
    return valor.isascii() and valor.isdigit()  # isdigit solo no basta: "١٢" también son dígitos


def puerto_de(entorno) -> int:
    valor = (entorno.get("JARVIS_UI_PUERTO") or "").strip()
    if not valor:
        return PUERTO_POR_DEFECTO
    if _digitos(valor) and (int(valor) == 0 or 1024 <= int(valor) <= 65535):
        return int(valor)
    raise ErrorUI(f"JARVIS_UI_PUERTO='{valor}' no es válido; usa 0 (libre) o un entero entre 1024 y 65535.")


def longitud(cabeceras) -> int:
    if cabeceras.get("Transfer-Encoding") is not None or cabeceras.get("Content-Length") is None:
        raise ErrorHTTP(411, "se necesita Content-Length")
    valor = cabeceras.get("Content-Length").strip()
    if not _digitos(valor):
        raise ErrorHTTP(400, "Content-Length no válido")
    # Primero la longitud del texto: int() de más de 4300 dígitos lanza ValueError.
    if len(valor) > len(str(MAX_CUERPO)) or int(valor) > MAX_CUERPO:
        raise ErrorHTTP(413, f"cuerpo de más de {MAX_CUERPO} bytes")
    return int(valor)


def comprobar_api(sesion, metodo: str, cabeceras, puerto: int) -> None:
    origen = cabeceras.get("Origin")
    # Un formulario o fetch de otra web siempre manda Origin en POST; sin él, no se acepta.
    if (origen is None and metodo == "POST") or (origen is not None and origen != f"http://{HOST}:{puerto}"):
        raise ErrorHTTP(403, "origen no permitido")
    sitio = cabeceras.get("Sec-Fetch-Site")
    if sitio is not None and sitio != "same-origin":
        raise ErrorHTTP(403, "origen no permitido")
    recibido = (cabeceras.get(CABECERA_TOKEN) or "").encode("utf-8", errors="replace")
    if not hmac.compare_digest(recibido, sesion.token.encode("utf-8")):
        raise ErrorHTTP(403, "token no válido")


def leer_json(cabeceras, cuerpo: bytes) -> dict:
    # Content-Type obligatorio: un formulario de otra web no puede mandar application/json sin preflight.
    if (cabeceras.get("Content-Type") or "").split(";")[0].strip().lower() != "application/json":
        raise ErrorHTTP(415, "se espera application/json")
    if len(cuerpo) > MAX_CUERPO:
        raise ErrorHTTP(413, f"cuerpo de más de {MAX_CUERPO} bytes")
    try:
        datos = json.loads(cuerpo.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise ErrorHTTP(400, "JSON no válido") from None
    if not isinstance(datos, dict):
        raise ErrorHTTP(400, "JSON no válido")
    return datos


def _api(sesion, ruta: str, consulta: str, cabeceras, cuerpo: bytes, reloj) -> RespuestaHTTP:
    if ruta == "/api/estado":
        desde = parse_qs(consulta).get("desde", ["0"])[0]
        if not (_digitos(desde) and len(desde) <= 12):
            raise ErrorHTTP(400, "desde no válido")
        return respuesta_json(200, sesion.instantanea(int(desde)))
    if ruta == "/api/hoy":
        ahora = reloj()
        return respuesta_json(200, {"titulo": hoy.encabezado(ahora),
                                    "secciones": [{"titulo": t, "texto": c} for t, c in hoy.secciones(ahora)]})
    datos = leer_json(cabeceras, cuerpo)
    if ruta == "/api/mensaje":
        texto = datos.get("texto")
        if not isinstance(texto, str) or not texto.strip() or len(texto) > MAX_TEXTO:
            raise ErrorHTTP(400, f"texto vacío o de más de {MAX_TEXTO} caracteres")
        if not sesion.enviar(texto):
            raise ErrorHTTP(409, "Jarvis está ocupado")
        return respuesta_json(202, {"ok": True})
    # /api/confirmar: solo un booleano JSON cuenta (type, no isinstance: True no vale como id ni 1 como sí).
    id_confirmacion, si = datos.get("id"), datos.get("si")
    if type(id_confirmacion) is not int or type(si) is not bool:
        raise ErrorHTTP(400, 'se espera {"id": entero, "si": true|false}')
    if not sesion.responder(id_confirmacion, si):
        raise ErrorHTTP(409, "no hay esa confirmación pendiente")
    return respuesta_json(200, {"ok": True})


def atender(sesion, metodo: str, objetivo: str, cabeceras, cuerpo: bytes, puerto: int,
            reloj=datetime.now) -> RespuestaHTTP:
    """Una petición, sin sockets. Todas las comprobaciones van antes de cualquier efecto sobre la sesión."""
    try:
        if cabeceras.get("Host") != f"{HOST}:{puerto}":  # corta el DNS rebinding
            raise ErrorHTTP(403, "host no permitido")
        partes = urlsplit(objetivo)
        ruta = partes.path
        if ruta in ESTATICOS:
            if metodo != "GET":
                raise ErrorHTTP(405, "método no permitido")
            nombre, tipo = ESTATICOS[ruta]
            return RespuestaHTTP(200, {**CABECERAS_SEGURIDAD, "Content-Type": tipo}, (CARPETA / nombre).read_bytes())
        if ruta not in RUTAS_API:
            raise ErrorHTTP(404, "no existe")
        comprobar_api(sesion, metodo, cabeceras, puerto)
        if metodo != RUTAS_API[ruta]:
            raise ErrorHTTP(405, "método no permitido")
        return _api(sesion, ruta, partes.query, cabeceras, cuerpo, reloj)
    except ErrorHTTP as e:
        return error(e.codigo, str(e))


class Manejador(BaseHTTPRequestHandler):
    server_version = "Jarvis"
    sys_version = ""
    timeout = TIEMPO_SOCKET

    def log_message(self, formato, *args):
        pass  # sin logs: ni rutas ni cabeceras salen por consola

    def do_GET(self):
        self._responder(b"")

    def do_POST(self):
        try:
            n = longitud(self.headers)
        except ErrorHTTP as e:
            self._enviar(error(e.codigo, str(e)))  # sin leer el cuerpo
            return
        self._responder(self.rfile.read(n))

    def _responder(self, cuerpo: bytes) -> None:
        try:
            r = atender(self.server.sesion, self.command, self.path, self.headers, cuerpo, self.server.server_address[1])
        except Exception:
            r = error(500, "error interno")  # sin traza
        self._enviar(r)

    def _enviar(self, r: RespuestaHTTP) -> None:
        self.send_response(r.codigo)
        for nombre, valor in r.cabeceras.items():
            self.send_header(nombre, valor)
        self.send_header("Content-Length", str(len(r.cuerpo)))
        self.end_headers()
        self.wfile.write(r.cuerpo)


class ServidorUI(ThreadingHTTPServer):
    allow_reuse_address = False  # en Windows, SO_REUSEADDR dejaría a otro proceso quedarse con el puerto
    daemon_threads = True

    def __init__(self, sesion, puerto: int):
        self.sesion = sesion
        super().__init__((HOST, puerto), Manejador)

    def server_bind(self):
        # Sin el socket.getfqdn de HTTPServer.server_bind: una búsqueda DNS inversa que no hace falta.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = HOST, self.server_address[1]

    def handle_error(self, request, client_address):
        e = sys.exc_info()[1]
        if not isinstance(e, (ConnectionError, TimeoutError)):
            print(f"(UI) error atendiendo una petición: {type(e).__name__}", file=sys.stderr)  # nunca la traza


def crear_servidor(sesion, puerto: int = PUERTO_POR_DEFECTO) -> ServidorUI:
    return ServidorUI(sesion, puerto)


def buscar_edge(entorno=None, which=shutil.which) -> str | None:
    entorno = os.environ if entorno is None else entorno
    if ruta := which("msedge"):
        return ruta
    for variable in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        if variable in entorno:
            ruta = Path(entorno[variable], "Microsoft", "Edge", "Application", "msedge.exe")
            if ruta.is_file():
                return str(ruta)
    return None


def abrir_ventana(url: str, buscar=None, abrir=None, navegador=None) -> bool:
    ruta = (buscar or buscar_edge)()
    if ruta:
        try:
            (abrir or subprocess.Popen)([ruta, f"--app={url}", *ARGS_VENTANA],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except OSError:
            pass
    try:
        return bool((navegador or webbrowser.open)(url))
    except webbrowser.Error:  # solo este: la guardia de los tests no queda tapada
        return False


def lanzar(cliente, herramientas: dict, entorno, con_voz: bool = False, mostrar=print) -> int:
    """python -m jarvis --ui: servidor en un hilo, ventana y conversar en el hilo principal hasta /salir o Ctrl+C."""
    # conversar, crear_servidor y abrir_ventana se buscan en este módulo al llamar: los tests los sustituyen.
    try:
        puerto = puerto_de(entorno)
    except ErrorUI as e:
        print(e, file=sys.stderr)
        return 1
    sesion = Sesion()
    piezas = piezas_ui(sesion)
    if con_voz:
        try:
            oyente, hablante, palabras = voz.motores(entorno)
            piezas = piezas_ui_voz(sesion, oyente, hablante, palabras)
            aviso = f"Voz activada: di «{palabras[0]}» y tu petición."
            mostrar(aviso)
            sesion.anotar("sistema", aviso)
        except voz.ErrorVoz as e:
            print(f"Voz desactivada: {e} Sigo solo con texto.", file=sys.stderr)
    try:
        servidor = crear_servidor(sesion, puerto)
    except OSError as e:
        print(f"No pude abrir el puerto {puerto}: {e}. Prueba con JARVIS_UI_PUERTO=0.", file=sys.stderr)
        return 1
    threading.Thread(target=servidor.serve_forever, name="jarvis-ui", daemon=True).start()
    base = f"http://{HOST}:{servidor.server_address[1]}/"
    url = base + "#" + sesion.token
    mostrar(f"Jarvis UI en {base} — cierra esta consola o pulsa Ctrl+C para salir.")  # sin el token
    if not abrir_ventana(url):
        mostrar("No pude abrir una ventana. Abre esta dirección en el navegador "
                f"(lleva el token de esta sesión; no la compartas): {url}")
    try:
        conversar(cliente, herramientas, **piezas)
    finally:
        servidor.shutdown()
        servidor.server_close()
    return 0
