import re

import pytest

from jarvis.tools import cargar_herramientas, definiciones

PLANTILLA = '''
NOMBRE = "{nombre}"
DESCRIPCION = "Herramienta de prueba."
ESQUEMA = {{"type": "object", "properties": {{}}, "required": []}}
requiere_confirmacion = False
def ejecutar(**args):
    return "ok"
'''


def test_carga_hora_con_contrato_completo():
    hora = cargar_herramientas()["hora"]
    assert hora.NOMBRE == "hora"
    assert isinstance(hora.DESCRIPCION, str) and hora.DESCRIPCION
    assert hora.ESQUEMA["type"] == "object"
    assert hora.requiere_confirmacion is False
    assert callable(hora.ejecutar)


def test_hora_devuelve_fecha_y_hora():
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", cargar_herramientas()["hora"].ejecutar())


def test_descubre_archivo_nuevo_e_ignora_privados(tmp_path):
    (tmp_path / "eco.py").write_text(PLANTILLA.format(nombre="eco"), encoding="utf-8")
    (tmp_path / "_privado.py").write_text(PLANTILLA.format(nombre="privado"), encoding="utf-8")
    herramientas = cargar_herramientas(tmp_path)
    assert list(herramientas) == ["eco"]
    assert herramientas["eco"].ejecutar() == "ok"


def test_sin_ejecutar_da_value_error_con_el_archivo(tmp_path):
    codigo = PLANTILLA.format(nombre="rota").split("def ejecutar")[0]
    (tmp_path / "rota.py").write_text(codigo, encoding="utf-8")
    with pytest.raises(ValueError, match=r"rota\.py.*ejecutar"):
        cargar_herramientas(tmp_path)


def test_ejecutar_no_invocable_da_value_error(tmp_path):
    codigo = PLANTILLA.format(nombre="rota").split("def ejecutar")[0] + "ejecutar = 3\n"
    (tmp_path / "rota.py").write_text(codigo, encoding="utf-8")
    with pytest.raises(ValueError, match=r"rota\.py.*ejecutar"):
        cargar_herramientas(tmp_path)


def test_sin_requiere_confirmacion_da_value_error(tmp_path):
    codigo = PLANTILLA.format(nombre="rota").replace("requiere_confirmacion = False\n", "")
    (tmp_path / "rota.py").write_text(codigo, encoding="utf-8")
    with pytest.raises(ValueError, match=r"rota\.py.*requiere_confirmacion"):
        cargar_herramientas(tmp_path)


def test_definiciones_formato_neutro(tmp_path):
    (tmp_path / "eco.py").write_text(PLANTILLA.format(nombre="eco"), encoding="utf-8")
    assert definiciones(cargar_herramientas(tmp_path)) == [{
        "nombre": "eco",
        "descripcion": "Herramienta de prueba.",
        "esquema": {"type": "object", "properties": {}, "required": []},
    }]
