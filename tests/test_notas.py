import re
from pathlib import Path

import pytest

from jarvis.tools import notas


@pytest.fixture
def datos(tmp_path, monkeypatch):
    carpeta = tmp_path / "datos"
    monkeypatch.setenv("JARVIS_DATOS", str(carpeta))
    return carpeta


def test_crear_guarda_linea_con_fecha(datos):
    assert notas.ejecutar("crear", "comprar pan") == "Nota guardada."
    lineas = (datos / "notas.txt").read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 1
    assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2} \| comprar pan$", lineas[0])


def test_crear_multilinea_queda_en_una_linea(datos):
    notas.ejecutar("crear", "línea uno\nlínea dos")
    lineas = (datos / "notas.txt").read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 1
    assert lineas[0].endswith("| línea uno línea dos")


def test_crear_vacia_da_error_y_no_crea_archivo(datos):
    assert notas.ejecutar("crear", "   ") == "Error: la nota está vacía."
    assert not (datos / "notas.txt").exists()


def test_listar_sin_notas_y_con_dos(datos):
    assert notas.ejecutar("listar") == "No hay notas."
    notas.ejecutar("crear", "primera")
    notas.ejecutar("crear", "segunda")
    lineas = notas.ejecutar("listar").split("\n")
    assert len(lineas) == 2
    assert lineas[0].endswith("| primera") and lineas[1].endswith("| segunda")


def test_listar_devuelve_solo_las_ultimas_20(datos):
    for i in range(25):
        notas.ejecutar("crear", f"nota {i}")
    lineas = notas.ejecutar("listar").split("\n")
    assert len(lineas) == 20
    assert lineas[0].endswith("| nota 5") and lineas[-1].endswith("| nota 24")


def test_buscar(datos):
    notas.ejecutar("crear", "comprar pan")
    notas.ejecutar("crear", "llamar a Ana")
    salida = notas.ejecutar("buscar", "PAN")
    assert "comprar pan" in salida and "llamar a Ana" not in salida
    assert notas.ejecutar("buscar", "xyz") == "No hay notas que contengan 'xyz'."
    assert notas.ejecutar("buscar", "") == "Error: falta el texto a buscar."


def test_accion_desconocida(datos):
    assert notas.ejecutar("borrar").startswith("Error: acción desconocida 'borrar'")


def test_carpeta_por_defecto_sin_variable(monkeypatch):
    monkeypatch.delenv("JARVIS_DATOS", raising=False)
    raiz = Path(__file__).resolve().parents[1]
    assert notas.carpeta_datos() == raiz / "datos"


def test_no_pide_confirmacion():
    assert notas.requiere_confirmacion is False
