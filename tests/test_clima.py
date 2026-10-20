import json
import urllib.request

import pytest

from jarvis.tools import clima

GEO_LIMA = {"results": [{"name": "Lima", "latitude": -12.04318, "longitude": -77.02824,
                         "country": "Perú", "admin1": "Lima"}]}
PRONOSTICO_FALSO = {
    "current": {"temperature_2m": 18.6, "apparent_temperature": 17.2, "relative_humidity_2m": 83,
                "weather_code": 3, "wind_speed_10m": 11.4},
    "daily": {"time": ["2026-10-20", "2026-10-21", "2026-10-22"], "weather_code": [3, 61, 42],
              "temperature_2m_min": [15.8, 16.1, 15.0], "temperature_2m_max": [21.3, 20.6, 22.0],
              "precipitation_probability_max": [10, 80, None]},
}


@pytest.fixture
def descargas(monkeypatch):
    """Parchea descargar_json: devuelve las respuestas en orden y guarda las URLs pedidas."""
    def instalar(*respuestas):
        urls = []
        pendientes = list(respuestas)
        monkeypatch.setattr(clima, "descargar_json", lambda url: (urls.append(url), pendientes.pop(0))[1])
        return urls

    return instalar


def test_clima_de_una_ciudad(descargas):
    urls = descargas(GEO_LIMA, PRONOSTICO_FALSO)
    assert clima.ejecutar("Lima") == (
        "Clima en Lima, Perú: ahora 19 °C (sensación 17 °C), nublado, humedad 83 %, viento 11 km/h.\n"
        "- 2026-10-20: nublado, 16–21 °C, lluvia 10 %\n"
        "- 2026-10-21: lluvia ligera, 16–21 °C, lluvia 80 %\n"
        "- 2026-10-22: código 42, 15–22 °C")
    assert urls[0].startswith(clima.GEOCODIFICAR + "?")
    assert "name=Lima" in urls[0] and "language=es" in urls[0]
    assert urls[1].startswith(clima.PRONOSTICO + "?")
    for trozo in ("latitude=-12.04318", "longitude=-77.02824", "timezone=auto", "forecast_days=3"):
        assert trozo in urls[1]


def test_ciudad_por_defecto(descargas, monkeypatch):
    monkeypatch.setenv("JARVIS_CIUDAD", "Lima")
    urls = descargas(GEO_LIMA, PRONOSTICO_FALSO)
    clima.ejecutar()
    assert "name=Lima" in urls[0]
    for valor in (None, "  "):
        if valor is None:
            monkeypatch.delenv("JARVIS_CIUDAD")
        else:
            monkeypatch.setenv("JARVIS_CIUDAD", valor)
        urls = descargas({})
        clima.ejecutar()
        assert "name=Piura" in urls[0]


def test_pais_elige_resultado(descargas):
    geo = {"results": [{"name": "Piura", "latitude": 1.0, "longitude": 1.0, "country": "España"},
                       {"name": "Piura", "latitude": -5.19449, "longitude": -80.63282,
                        "country": "Perú", "admin1": "Piura"}]}
    urls = descargas(geo, PRONOSTICO_FALSO)
    salida = clima.ejecutar("Piura, perú")
    assert "name=Piura" in urls[0] and "per" not in urls[0]
    assert "latitude=-5.19449" in urls[1]
    assert salida.startswith("Clima en Piura, Perú:")


def test_ciudad_no_encontrada(descargas):
    urls = descargas({})
    assert clima.ejecutar("Atlantis") == "No encontré la ciudad 'Atlantis'."
    assert len(urls) == 1
    urls = descargas()
    assert clima.ejecutar(" , Perú") == "Error: falta la ciudad."
    assert urls == []


def test_descargar_json(monkeypatch):
    recibidos = []

    class RespuestaFalsa:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"a": 1}).encode("utf-8")

    def urlopen_falso(peticion, timeout=None):
        recibidos.append((peticion, timeout))
        return RespuestaFalsa()

    monkeypatch.setattr(urllib.request, "urlopen", urlopen_falso)
    assert clima.descargar_json("https://x.example/a") == {"a": 1}
    peticion, timeout = recibidos[0]
    assert peticion.get_header("User-agent") == clima.AGENTE
    assert timeout == 10


def test_no_requiere_confirmacion():
    assert clima.requiere_confirmacion is False
