"""Clima con Open-Meteo: sin clave y solo con la biblioteca estándar."""
import json
import os
import urllib.parse
import urllib.request

NOMBRE = "clima"
DESCRIPCION = ("Da el tiempo actual y el pronóstico de 3 días de una ciudad (Open-Meteo). "
               "Si no se indica ciudad, usa la del usuario.")
ESQUEMA = {"type": "object",
           "properties": {"ciudad": {"type": "string", "description": "Ciudad, opcionalmente con país: 'Lima' o 'Lima, Perú'. Vacía: la ciudad del usuario."}},
           "required": []}
requiere_confirmacion = False  # solo lee; lo único que sale del equipo es el nombre de la ciudad
CIUDAD_POR_DEFECTO = "Piura"
GEOCODIFICAR = "https://geocoding-api.open-meteo.com/v1/search"
PRONOSTICO = "https://api.open-meteo.com/v1/forecast"
AGENTE = "Mozilla/5.0 (Jarvis)"
TIMEOUT = 10
DIAS = 3
ACTUAL = "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m"
DIARIO = "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
ESTADOS = {0: "despejado", 1: "mayormente despejado", 2: "parcialmente nublado", 3: "nublado",
           45: "niebla", 48: "niebla con escarcha", 51: "llovizna ligera", 53: "llovizna", 55: "llovizna intensa",
           56: "llovizna helada ligera", 57: "llovizna helada intensa", 61: "lluvia ligera", 63: "lluvia",
           65: "lluvia intensa", 66: "lluvia helada ligera", 67: "lluvia helada intensa", 71: "nevada ligera",
           73: "nevada", 75: "nevada intensa", 77: "granos de nieve", 80: "chubascos ligeros", 81: "chubascos",
           82: "chubascos violentos", 85: "chubascos de nieve ligeros", 86: "chubascos de nieve intensos",
           95: "tormenta", 96: "tormenta con granizo ligero", 99: "tormenta con granizo intenso"}


def ciudad_por_defecto() -> str:
    return os.environ.get("JARVIS_CIUDAD", "").strip() or CIUDAD_POR_DEFECTO


def descargar_json(url: str) -> dict:
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(peticion, timeout=TIMEOUT) as respuesta:  # por atributo, por la guardia de los tests
        return json.loads(respuesta.read().decode("utf-8"))


def estado(codigo) -> str:
    return ESTADOS.get(codigo, f"código {codigo}")


def geocodificar(ciudad: str) -> dict | None:
    # ponytail: la pista del país se compara sin quitar tildes ("Peru" no encuentra "Perú"); sin caché.
    nombre, _, pista = ciudad.partition(",")
    pista = pista.strip().casefold()
    url = GEOCODIFICAR + "?" + urllib.parse.urlencode(
        {"name": nombre.strip(), "count": 5, "language": "es", "format": "json"})
    resultados = descargar_json(url).get("results") or []
    if pista:
        for r in resultados:
            if pista in f"{r.get('country', '')} {r.get('admin1', '')}".casefold():
                return r
    return resultados[0] if resultados else None


def ejecutar(ciudad: str = "") -> str:
    ciudad = ciudad.strip() or ciudad_por_defecto()
    if not ciudad.partition(",")[0].strip():
        return "Error: falta la ciudad."
    r = geocodificar(ciudad)
    if r is None:
        return f"No encontré la ciudad '{ciudad}'."
    url = PRONOSTICO + "?" + urllib.parse.urlencode(
        {"latitude": r["latitude"], "longitude": r["longitude"], "current": ACTUAL, "daily": DIARIO,
         "timezone": "auto", "forecast_days": DIAS})
    datos = descargar_json(url)
    partes = [r["name"]]
    if r.get("admin1") and r["admin1"] != r["name"]:
        partes.append(r["admin1"])
    if r.get("country"):
        partes.append(r["country"])
    a, d = datos["current"], datos["daily"]
    lineas = [f"Clima en {', '.join(partes)}: ahora {round(a['temperature_2m'])} °C "
              f"(sensación {round(a['apparent_temperature'])} °C), {estado(a['weather_code'])}, "
              f"humedad {round(a['relative_humidity_2m'])} %, viento {round(a['wind_speed_10m'])} km/h."]
    for i, fecha in enumerate(d["time"]):
        linea = (f"- {fecha}: {estado(d['weather_code'][i])}, "
                 f"{round(d['temperature_2m_min'][i])}–{round(d['temperature_2m_max'][i])} °C")
        p = d["precipitation_probability_max"][i]
        if p is not None:
            linea += f", lluvia {round(p)} %"
        lineas.append(linea)
    return "\n".join(lineas)
