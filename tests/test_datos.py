import re
from pathlib import Path

import pytest

from jarvis import datos


def test_fixture_aisla_la_carpeta(tmp_path):
    assert datos.carpeta() == tmp_path / "datos"
    assert not datos.carpeta().exists()


def test_sin_variable_usa_la_del_repo(monkeypatch):
    monkeypatch.delenv("JARVIS_DATOS")
    assert datos.carpeta() == Path(__file__).resolve().parents[1] / "datos"


def test_leer_sin_archivo():
    assert datos.leer_lista("x.json") == []
    assert not datos.carpeta().exists()


def test_ida_y_vuelta():
    lista = [{"texto": "café ñ", "id": 1}]
    datos.escribir_lista("x.json", lista)
    assert datos.leer_lista("x.json") == lista
    assert "café" in (datos.carpeta() / "x.json").read_text(encoding="utf-8")
    assert not (datos.carpeta() / "x.json.tmp").exists()


@pytest.mark.parametrize("contenido", ["{no es json", '{"a": 1}', "[1, 2]"])
def test_archivo_danado(contenido):
    datos.carpeta().mkdir(parents=True)
    ruta = datos.carpeta() / "x.json"
    ruta.write_text(contenido, encoding="utf-8")
    with pytest.raises(ValueError, match=re.escape("el archivo de datos x.json está dañado; revísalo o bórralo.")):
        datos.leer_lista("x.json")
    assert ruta.read_text(encoding="utf-8") == contenido
