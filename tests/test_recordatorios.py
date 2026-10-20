import importlib
import json
from datetime import date, datetime

import pytest
from clientes_falsos import llamar

from jarvis import recordatorios
from jarvis.tools import recordatorio_cancelar
from jarvis.tools import recordatorios as h_recordatorios


def D(h, m, s=0, dia=20):
    return datetime(2026, 10, dia, h, m, s)


AGUA = {"id": 1, "texto": "tomar agua", "cuando": "2026-10-20T10:05:00", "creado": "2026-10-20T10:00:00",
        "estado": "pendiente"}


@pytest.fixture
def archivo(tmp_path):
    return tmp_path / "datos" / "recordatorios.json"


def agua():
    return recordatorios.crear("tomar agua", D(10, 5), D(10, 0))


def test_crear_y_sobrevive_reinicio(archivo):
    assert recordatorios.crear("  tomar\nagua ", D(10, 5), D(10, 0)) == AGUA
    assert json.loads(archivo.read_text("utf-8")) == [AGUA]
    importlib.reload(recordatorios)
    assert recordatorios.pendientes() == [AGUA]


def test_se_dispara_una_sola_vez_con_reloj_simulado():
    agua()
    tiempos = (D(10, 0), D(10, 4, 59), D(10, 5), D(10, 5), D(10, 6), D(10, 5, dia=21))
    assert [len(recordatorios.vencidos(t)) for t in tiempos] == [0, 0, 1, 0, 0, 0]
    (r,) = recordatorios.cargar()
    assert r["estado"] == "disparado" and r["disparado"] == "2026-10-20T10:05:00"
    assert recordatorios.pendientes() == []


def test_reinicio_entre_medias_no_repite_ni_pierde():
    agua()
    importlib.reload(recordatorios)
    assert recordatorios.vencidos(D(10, 4)) == []
    importlib.reload(recordatorios)
    assert len(recordatorios.vencidos(D(10, 30))) == 1  # venció "con Jarvis cerrado": avisa tarde, pero avisa
    importlib.reload(recordatorios)
    assert recordatorios.vencidos(D(10, 31)) == []
    assert recordatorios.vencidos(D(11, 0)) == []


def test_sin_vencidos_no_escribe(tmp_path, archivo):
    assert recordatorios.vencidos(D(10, 0)) == []
    assert not (tmp_path / "datos").exists()
    agua()
    antes = archivo.read_bytes()
    assert recordatorios.vencidos(D(10, 1)) == []
    assert archivo.read_bytes() == antes


def test_varios_en_orden():
    recordatorios.crear("b", D(10, 7), D(10, 0))
    recordatorios.crear("a", D(10, 6), D(10, 0))
    assert [r["id"] for r in recordatorios.vencidos(D(10, 10))] == [2, 1]


def test_crear_valida(archivo):
    casos = [(("  ", D(10, 5)), "falta el texto del recordatorio."),
             (("x", D(9, 0)), "esa hora ya pasó (2026-10-20 09:00)."),
             (("x", D(10, 0)), "esa hora ya pasó (2026-10-20 10:00)."),
             (("x" * 301, D(10, 5)), "el recordatorio es demasiado largo (máximo 300 caracteres).")]
    for (texto, cuando), mensaje in casos:
        with pytest.raises(ValueError) as e:
            recordatorios.crear(texto, cuando, D(10, 0))
        assert str(e.value) == mensaje
    with pytest.raises(ValueError) as e:
        recordatorios.crear("cambiar la contraseña: hunter2", D(10, 5), D(10, 0))
    assert str(e.value).startswith("no lo guardo porque parece contener una contraseña")
    assert "hunter2" not in str(e.value)
    assert not archivo.exists()


def test_cancelar():
    agua()
    with pytest.raises(ValueError, match="^el recordatorio 1 no dice eso; dice: 'tomar agua'. No cancelé nada.$"):
        recordatorios.cancelar(1, "otra")
    with pytest.raises(ValueError, match="^no hay ningún recordatorio pendiente con id 7.$"):
        recordatorios.cancelar(7, "x")
    assert recordatorios.cancelar(1, "Tomar  Agua") == AGUA
    assert recordatorios.pendientes() == []
    assert recordatorios.vencidos(D(11, 0)) == []
    recordatorios.crear("estirar", D(10, 10), D(10, 0))  # id 1 otra vez: el cancelado salió del archivo
    recordatorios.vencidos(D(10, 10))
    with pytest.raises(ValueError, match="^no hay ningún recordatorio pendiente con id 1.$"):
        recordatorios.cancelar(1, "estirar")


def test_del_dia():
    agua()
    recordatorios.vencidos(D(10, 5))
    recordatorios.crear("mañana", D(9, 0, dia=21), D(10, 0))
    recordatorios.crear("cena", D(17, 0), D(10, 0))
    assert [r["texto"] for r in recordatorios.del_dia(date(2026, 10, 20))] == ["tomar agua", "cena"]


def test_aviso():
    assert recordatorios.aviso(agua()) == "Recordatorio (2026-10-20 10:05): tomar agua"


def test_archivo_danado(archivo):
    archivo.parent.mkdir(parents=True)
    archivo.write_text("{roto", encoding="utf-8")
    with pytest.raises(ValueError, match="el archivo de datos recordatorios.json está dañado; revísalo o bórralo."):
        recordatorios.vencidos(D(10, 0))
    assert archivo.read_text(encoding="utf-8") == "{roto"


@pytest.fixture
def reloj(monkeypatch):
    monkeypatch.setattr(h_recordatorios, "ahora", lambda: D(10, 0, 30))


def crear_dos():
    h_recordatorios.ejecutar("crear", "tomar agua", cuando="2026-10-20 17:00")
    h_recordatorios.ejecutar("crear", "estirar", en_minutos=10)


def test_herramienta_crear(reloj):
    assert h_recordatorios.ejecutar("crear", "tomar agua", cuando="2026-10-20 17:00") == (
        "Recordatorio creado (id 1) para el 2026-10-20 17:00: tomar agua")
    assert h_recordatorios.ejecutar("crear", "estirar", en_minutos=10) == (
        "Recordatorio creado (id 2) para el 2026-10-20 10:10: estirar")
    assert recordatorios.cargar()[1]["cuando"] == "2026-10-20T10:10:30"
    assert h_recordatorios.ejecutar("crear", "cenar", cuando="2026-10-20T18:00") == (
        "Recordatorio creado (id 3) para el 2026-10-20 18:00: cenar")


def test_herramienta_crear_valida(reloj):
    uno_de_dos = "Error: indica cuándo con cuando ('AAAA-MM-DD HH:MM') o con en_minutos, solo uno de los dos."
    assert h_recordatorios.ejecutar("crear", "x") == uno_de_dos
    assert h_recordatorios.ejecutar("crear", "x", cuando="2026-10-20 17:00", en_minutos=5) == uno_de_dos
    assert h_recordatorios.ejecutar("crear", "x", cuando="mañana a las 5") == (
        "Error: cuando debe tener el formato AAAA-MM-DD HH:MM (recibí 'mañana a las 5').")
    for n in (0, "diez", 525601):
        assert h_recordatorios.ejecutar("crear", "x", en_minutos=n) == (
            "Error: en_minutos debe ser un número entero entre 1 y 525600."), n
    assert h_recordatorios.ejecutar("crear", "x", cuando="2026-10-20 09:00") == (
        "Error: esa hora ya pasó (2026-10-20 09:00).")
    assert h_recordatorios.ejecutar("crear", "", cuando="2026-10-20 17:00") == "Error: falta el texto del recordatorio."
    assert recordatorios.pendientes() == []


def test_herramienta_listar(reloj):
    assert h_recordatorios.ejecutar("listar") == "No hay recordatorios pendientes."
    crear_dos()
    assert h_recordatorios.ejecutar("listar") == (
        "Recordatorios pendientes:\n- [2] 2026-10-20 10:10 — estirar\n- [1] 2026-10-20 17:00 — tomar agua")
    assert h_recordatorios.ejecutar("borrar").startswith("Error: acción desconocida 'borrar'")


def test_sin_confirmacion_no_cancela_el_recordatorio(reloj):
    h_recordatorios.ejecutar("crear", "tomar agua", cuando="2026-10-20 17:00")
    argumentos = {"id_recordatorio": 1, "texto": "tomar agua"}
    assert llamar("recordatorio_cancelar", recordatorio_cancelar, argumentos, lambda n, a: False) == (
        "El usuario canceló la acción.")
    assert len(recordatorios.pendientes()) == 1
    assert llamar("recordatorio_cancelar", recordatorio_cancelar, argumentos, lambda n, a: True) == (
        "Recordatorio cancelado (id 1): tomar agua (2026-10-20 17:00).")
    assert recordatorios.pendientes() == []


def test_cancelar_valida(reloj):
    h_recordatorios.ejecutar("crear", "tomar agua", cuando="2026-10-20 17:00")
    assert recordatorio_cancelar.ejecutar("uno", "x") == "Error: el id 'uno' no es válido."
    assert recordatorio_cancelar.ejecutar(1, "otra") == (
        "Error: el recordatorio 1 no dice eso; dice: 'tomar agua'. No cancelé nada.")
    assert len(recordatorios.pendientes()) == 1


def test_banderas():
    assert h_recordatorios.requiere_confirmacion is False
    assert recordatorio_cancelar.requiere_confirmacion is True


def test_herramienta_cuando_none_con_en_minutos(reloj):
    # Algunos modelos mandan los opcionales como null.
    assert h_recordatorios.ejecutar("crear", "estirar", cuando=None, en_minutos=10) == (
        "Recordatorio creado (id 1) para el 2026-10-20 10:10: estirar")
