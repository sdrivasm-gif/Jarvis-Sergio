"""Acceso mínimo a las APIs REST de Google: urllib y un refresh token de OAuth en .env. Sin logs."""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

VARIABLES = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN")
URL_TOKEN = "https://oauth2.googleapis.com/token"
TIMEOUT = 15
MARGEN = 60  # segundos: el token se renueva un poco antes de que caduque
ID_VALIDO = re.compile(r"[A-Za-z0-9_-]{1,1024}")  # se usa con fullmatch
# fullmatch; una sola dirección, sin espacios, separadores ni caracteres de control (C0, DEL y C1).
CORREO_VALIDO = re.compile(r"[^@\s,;<>\"'\x00-\x1f\x7f-\x9f]+@[^@\s,;<>\"'\x00-\x1f\x7f-\x9f]+\.[^@\s,;<>\"'\x00-\x1f\x7f-\x9f]+")
# ponytail: sin reintentos ni paginación, y un único token en memoria por proceso.
_token: dict = {}  # {"valor": str, "vence": float de time.monotonic()}; solo en memoria


class ErrorIntegracion(Exception):
    """Error esperable de una integración; su texto se puede mostrar (sin tokens ni secretos)."""


def credenciales() -> dict[str, str]:
    valores = {v: os.environ.get(v, "").strip() for v in VARIABLES}
    faltan = [v for v in VARIABLES if not valores[v]]
    if faltan:
        raise ErrorIntegracion(f"Google no está configurado: faltan {', '.join(faltan)} en .env (ver jarvis/README.md).")
    return valores


def mensaje_de_error(error: urllib.error.HTTPError) -> str:
    # Solo el texto de error de Google: nunca la petición, las cabeceras ni las credenciales.
    texto = ""
    try:
        datos = json.loads(error.read() or b"{}")
        detalle = datos.get("error")
        if isinstance(detalle, dict):
            texto = detalle.get("message", "")
        elif isinstance(detalle, str):
            texto = datos.get("error_description") or detalle
    except Exception:
        pass
    return str(texto or error.reason)[:200]


def abrir_json(peticion: urllib.request.Request) -> dict:
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT) as respuesta:  # por atributo, por la guardia de los tests
            datos = respuesta.read()
    except urllib.error.HTTPError as e:  # antes que URLError, que es su clase base
        raise ErrorIntegracion(f"Google respondió {e.code}: {mensaje_de_error(e)}") from None
    except urllib.error.URLError as e:
        raise ErrorIntegracion(f"No pude conectar con Google: {e.reason}") from None
    return json.loads(datos) if datos.strip() else {}


def obtener_token() -> str:
    if _token.get("valor") and time.monotonic() < _token["vence"]:
        return _token["valor"]
    c = credenciales()
    datos = urllib.parse.urlencode({
        "client_id": c["GOOGLE_CLIENT_ID"],
        "client_secret": c["GOOGLE_CLIENT_SECRET"],
        "refresh_token": c["GOOGLE_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    respuesta = abrir_json(urllib.request.Request(
        URL_TOKEN, data=datos, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"}))
    if not respuesta.get("access_token"):
        raise ErrorIntegracion("Google no devolvió un token de acceso.")
    _token.update(valor=respuesta["access_token"],
                  vence=time.monotonic() + int(respuesta.get("expires_in", 3600)) - MARGEN)
    return _token["valor"]


def pedir(metodo: str, url: str, params: dict | None = None, cuerpo: dict | None = None) -> dict:
    cabeceras = {"Authorization": f"Bearer {obtener_token()}"}  # primero: sin credenciales no se toca la red
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    data = None
    if cuerpo is not None:
        data = json.dumps(cuerpo).encode("utf-8")
        cabeceras["Content-Type"] = "application/json"
    return abrir_json(urllib.request.Request(url, data=data, method=metodo, headers=cabeceras))
