"""Comprobaciones estáticas de la página HUD (el comportamiento del JS lo prueba Sergio a mano)."""
import re
from pathlib import Path

CARPETA = Path(__file__).parents[1] / "jarvis" / "ui"
HTML = (CARPETA / "index.html").read_text(encoding="utf-8")
JS = (CARPETA / "app.js").read_text(encoding="utf-8")
CSS = (CARPETA / "estilo.css").read_text(encoding="utf-8")

IDS = ["nucleo", "estado", "subtitulos", "formulario", "texto", "enviar", "nota", "panel", "titulo-hoy",
       "secciones", "actualizar", "parte", "confirmacion", "confirmacion-texto", "confirmacion-cuenta",
       "si", "no", "aviso-conexion"]
PROHIBIDO_JS = ["innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function",
                "localStorage", "javascript:", 'setTimeout("', "setTimeout('", 'setInterval("', "setInterval('"]


def test_ids():
    for i in IDS:
        assert f'id="{i}"' in HTML, i
        assert f'"{i}"' in JS, i


def test_index_sin_codigo_en_linea():
    for etiqueta in re.findall(r"<script[^>]*>", HTML):
        assert 'src="/app.js"' in etiqueta
    assert "<style" not in HTML and "style=" not in HTML
    assert not re.search(r"\son[a-z]+\s*=", HTML)
    assert 'href="/estilo.css"' in HTML and 'lang="es"' in HTML and '<meta charset="utf-8">' in HTML


def test_sin_recursos_externos():
    for texto in (HTML, JS, CSS):
        for malo in ("http://", "https://", '="//', "@import", "url(", "@font-face"):
            assert malo not in texto, malo
    permitidos = {"/api/estado?desde=", "/api/mensaje", "/api/confirmar", "/api/hoy", "/hoy"}  # "/hoy": el botón Parte del día
    assert set(re.findall(r"[\"'`](/[^\"'`]*)[\"'`]", JS)) <= permitidos


def test_js_sin_html_dinamico():
    for malo in PROHIBIDO_JS:
        assert malo not in JS, malo
    for bueno in ("textContent", "X-Jarvis-Token", "sessionStorage", "replaceState"):
        assert bueno in JS, bueno


def test_estados():
    for e in ("reposo", "escuchando", "pensando", "hablando"):
        assert f'"{e}"' in JS, e
    for clase in (".reposo", ".escuchando", ".pensando", ".hablando", ".desconectado", "prefers-reduced-motion"):
        assert clase in CSS, clase
