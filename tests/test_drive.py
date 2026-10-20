from clientes_falsos import DriveFalso, PedirFalso, instalar, llamar, sin_credenciales

from jarvis.integrations import drive, google
from jarvis.tools import drive_buscar, drive_compartir

ARCHIVOS = [{"id": "f1", "nombre": "Presupuesto 2026", "tipo": "spreadsheet",
             "enlace": "https://docs.google.com/spreadsheets/d/f1"}]


def test_buscar_formatea(monkeypatch):
    falso = instalar(monkeypatch, drive, DriveFalso(ARCHIVOS))
    assert drive_buscar.ejecutar("presupuesto") == (
        "Encontré 1 archivo(s) en Drive:\n"
        "- Presupuesto 2026 (spreadsheet) — https://docs.google.com/spreadsheets/d/f1 (id: f1)")
    assert falso.consultas == [("presupuesto", 10)]


def test_buscar_sin_resultados_y_vacio(monkeypatch):
    falso = instalar(monkeypatch, drive, DriveFalso())
    assert drive_buscar.ejecutar("nada") == "No encontré archivos en Drive con 'nada'."
    assert drive_buscar.ejecutar(" ") == "Error: falta el nombre a buscar."
    assert falso.creaciones == 1


def test_sin_confirmacion_no_comparte_el_archivo(monkeypatch):
    falso = instalar(monkeypatch, drive, DriveFalso(ARCHIVOS))
    argumentos = {"id_archivo": "f1", "correo": "luis@example.com", "rol": "editor"}
    assert llamar("drive_compartir", drive_compartir, argumentos, lambda n, a: False) == "El usuario canceló la acción."
    assert falso.acciones == []
    assert falso.creaciones == 0
    assert llamar("drive_compartir", drive_compartir, argumentos, lambda n, a: True) == \
        "Compartí el archivo f1 con luis@example.com como editor."
    assert falso.acciones == [("compartir", "f1", "luis@example.com", "writer")]
    drive_compartir.ejecutar("f1", "luis@example.com")
    assert falso.acciones[-1] == ("compartir", "f1", "luis@example.com", "reader")


def test_compartir_valida(monkeypatch):
    falso = instalar(monkeypatch, drive, DriveFalso())
    assert drive_compartir.ejecutar("../x", "luis@example.com") == "Error: el id de archivo '../x' no es válido."
    assert drive_compartir.ejecutar("f1", "luis") == \
        "Error: la dirección 'luis' no es válida; pon un solo correo, como ana@example.com."
    assert drive_compartir.ejecutar("f1", "luis@example.com", "dueño") == \
        "Error: rol 'dueño' no válido; usa lector o editor."
    assert falso.acciones == []


def test_banderas():
    assert drive_buscar.requiere_confirmacion is False
    assert drive_compartir.requiere_confirmacion is True


def test_sin_credenciales_error_claro(monkeypatch):
    sin_credenciales(monkeypatch, google)
    assert drive_buscar.ejecutar("x") == (
        "Error: Google no está configurado: faltan GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, "
        "GOOGLE_REFRESH_TOKEN en .env (ver jarvis/README.md).")


def test_cliente_google_drive(monkeypatch):
    cliente = drive.ClienteGoogleDrive()
    respuesta = {"files": [
        {"id": "f1", "name": "P", "mimeType": "application/vnd.google-apps.spreadsheet", "webViewLink": "L"},
        {"id": "f2", "name": "Q", "mimeType": "application/pdf"},
    ]}
    pedir = PedirFalso(respuesta, {})
    monkeypatch.setattr(google, "pedir", pedir)
    archivos = cliente.buscar("o'brien", 10)
    assert pedir.llamadas[0] == ("GET", drive.URL, {"q": "name contains 'o\\'brien' and trashed = false",
                                                    "pageSize": 10, "fields": drive.CAMPOS}, None)
    assert [a["tipo"] for a in archivos] == ["spreadsheet", "application/pdf"]
    assert archivos[0] == {"id": "f1", "nombre": "P", "tipo": "spreadsheet", "enlace": "L"}
    assert archivos[1]["enlace"] == ""

    cliente.compartir("f1", "luis@example.com", "writer")
    assert pedir.llamadas[1] == ("POST", drive.URL + "/f1/permissions", {"sendNotificationEmail": "true"},
                                 {"type": "user", "role": "writer", "emailAddress": "luis@example.com"})
    assert drive.escapar("a\\b'c") == "a\\\\b\\'c"
    assert isinstance(drive.obtener_cliente(), drive.ClienteGoogleDrive)
