import json
import os
from types import SimpleNamespace

from jarvis import bucle
from jarvis.llm import LlamadaHerramienta
from jarvis.tools import abrir_app

CALCULADORA = {"Name": "Calculadora", "AppID": "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"}


def apps_falsas(monkeypatch, apps):
    """Sustituye listar_apps y abrir: cuenta los listados y guarda los AppID abiertos."""
    registro = SimpleNamespace(listados=0, abiertas=[])

    def listar():
        registro.listados += 1
        return apps

    monkeypatch.setattr(abrir_app, "listar_apps", listar)
    monkeypatch.setattr(abrir_app, "abrir", registro.abiertas.append)
    return registro


def app(nombre):
    return {"Name": nombre, "AppID": f"{nombre}!App"}


def test_sin_confirmacion_no_abre_la_app(monkeypatch):
    registro = apps_falsas(monkeypatch, [CALCULADORA])
    llamada = LlamadaHerramienta("l1", "abrir_app", {"nombre": "calculadora"})

    assert bucle.ejecutar_llamada(llamada, {"abrir_app": abrir_app}, lambda n, a: False) == \
        "El usuario canceló la acción."
    assert registro.abiertas == []
    assert registro.listados == 0

    assert bucle.ejecutar_llamada(llamada, {"abrir_app": abrir_app}, lambda n, a: True) == "Abrí Calculadora."
    assert registro.abiertas == ["Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"]


def test_requiere_confirmacion():
    assert abrir_app.requiere_confirmacion is True


def test_exacta_gana_a_parcial(monkeypatch):
    registro = apps_falsas(monkeypatch, [app("WordPad"), app("Word")])
    assert abrir_app.ejecutar("word") == "Abrí Word."
    assert registro.abiertas == ["Word!App"]


def test_parcial_unica_la_abre(monkeypatch):
    registro = apps_falsas(monkeypatch, [app("Google Chrome"), app("Calculadora")])
    assert abrir_app.ejecutar("chrome") == "Abrí Google Chrome."
    assert registro.abiertas == ["Google Chrome!App"]


def test_varias_parciales_pregunta_sin_abrir(monkeypatch):
    registro = apps_falsas(monkeypatch, [app("Visual Studio"), app("Visual Studio Code")])
    resultado = abrir_app.ejecutar("visual")
    assert resultado.startswith("Hay varias aplicaciones")
    assert "Visual Studio," in resultado and "Visual Studio Code" in resultado
    assert registro.abiertas == []


def test_sin_tildes_ni_mayusculas(monkeypatch):
    registro = apps_falsas(monkeypatch, [app("Configuración")])
    assert abrir_app.ejecutar("configuracion") == "Abrí Configuración."
    assert registro.abiertas == ["Configuración!App"]


def test_excluye_desinstaladores(monkeypatch):
    registro = apps_falsas(monkeypatch, [app("Zoom Uninstaller")])
    assert abrir_app.ejecutar("zoom") == "No encontré ninguna aplicación instalada llamada 'zoom'."
    assert registro.abiertas == []


def test_nombre_vacio_da_error_sin_listar(monkeypatch):
    registro = apps_falsas(monkeypatch, [CALCULADORA])
    assert abrir_app.ejecutar("  ") == "Error: falta el nombre de la aplicación."
    assert registro.listados == 0


def test_listar_apps_usa_el_comando_fijo_y_entiende_el_bom(monkeypatch):
    llamadas = []

    def run_falso(comando, **kwargs):
        llamadas.append((comando, kwargs))
        return SimpleNamespace(stdout=salida)

    monkeypatch.setattr(abrir_app.subprocess, "run", run_falso)

    salida = ("﻿" + json.dumps({"Name": "Calculadora", "AppID": "X!App"})).encode("utf-8")
    assert abrir_app.listar_apps() == [{"Name": "Calculadora", "AppID": "X!App"}]
    comando, kwargs = llamadas[0]
    assert comando == abrir_app.COMANDO_APPS
    assert not kwargs.get("shell")

    salida = b""
    assert abrir_app.listar_apps() == []


def test_abrir_usa_shell_appsfolder(monkeypatch):
    recibidos = []
    monkeypatch.setattr(os, "startfile", recibidos.append, raising=False)
    abrir_app.abrir("X!App")
    assert recibidos == ["shell:AppsFolder\\X!App"]
