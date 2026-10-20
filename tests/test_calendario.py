from datetime import date, datetime

from clientes_falsos import CalendarioFalso, PedirFalso, instalar, llamar, no_debe_preguntar, sin_credenciales

from jarvis.integrations import calendario, google
from jarvis.tools import calendario_borrar, calendario_crear, calendario_eventos

EVENTOS = {date(2026, 10, 20): [
    {"id": "ev1", "titulo": "Reunión con Ana", "inicio": "09:00", "fin": "10:00"},
    {"id": "ev2", "titulo": "Cumpleaños de Luis", "inicio": "", "fin": ""},
]}
LISTADO_20 = "Eventos del 2026-10-20:\n- 09:00–10:00 Reunión con Ana (id: ev1)\n- Todo el día: Cumpleaños de Luis (id: ev2)"
SIN_GOOGLE = ("Error: Google no está configurado: faltan GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, "
              "GOOGLE_REFRESH_TOKEN en .env (ver jarvis/README.md).")


def test_eventos_de_un_dia(monkeypatch):
    instalar(monkeypatch, calendario, CalendarioFalso(EVENTOS))
    assert calendario_eventos.ejecutar("2026-10-20") == LISTADO_20


def test_hoy_y_manana(monkeypatch):
    falso = instalar(monkeypatch, calendario, CalendarioFalso(EVENTOS))
    monkeypatch.setattr(calendario_eventos, "hoy", lambda: date(2026, 10, 19))
    assert calendario_eventos.ejecutar() == "No hay eventos el 2026-10-19."
    assert calendario_eventos.ejecutar("hoy") == "No hay eventos el 2026-10-19."
    assert calendario_eventos.ejecutar("mañana") == LISTADO_20
    assert falso.consultas == [date(2026, 10, 19), date(2026, 10, 19), date(2026, 10, 20)]


def test_fecha_invalida(monkeypatch):
    falso = instalar(monkeypatch, calendario, CalendarioFalso(EVENTOS))
    assert calendario_eventos.ejecutar("el martes") == \
        "Error: la fecha 'el martes' no es válida; usa AAAA-MM-DD, 'hoy' o 'mañana'."
    assert falso.creaciones == 0


def test_sin_confirmacion_no_crea_el_evento(monkeypatch):
    falso = instalar(monkeypatch, calendario, CalendarioFalso())
    argumentos = {"titulo": "Dentista", "inicio": "2026-10-21 15:00", "duracion_minutos": 30}
    assert llamar("calendario_crear", calendario_crear, argumentos, lambda n, a: False) == "El usuario canceló la acción."
    assert falso.acciones == []
    assert falso.creaciones == 0
    assert llamar("calendario_crear", calendario_crear, argumentos, lambda n, a: True) == \
        "Evento creado: Dentista, 2026-10-21 15:00–15:30 (id: ev-nuevo)."
    assert falso.acciones == [("crear", "Dentista", datetime(2026, 10, 21, 15, 0), datetime(2026, 10, 21, 15, 30))]


def test_la_confirmacion_siempre_muestra_la_duracion(monkeypatch):
    # Sin la duración, el usuario confirmaría un evento sin saber cuándo acaba.
    falso = instalar(monkeypatch, calendario, CalendarioFalso())
    assert "duracion_minutos" in calendario_crear.ESQUEMA["required"]
    assert llamar("calendario_crear", calendario_crear, {"titulo": "Dentista", "inicio": "2026-10-21 15:00"},
                  no_debe_preguntar) == "Error: faltan argumentos para calendario_crear: duracion_minutos."
    assert falso.creaciones == 0


def test_crear_valida_y_duracion_por_defecto(monkeypatch):
    falso = instalar(monkeypatch, calendario, CalendarioFalso())
    assert calendario_crear.ejecutar("Cita", "mañana a las 3").startswith(
        "Error: inicio debe tener el formato AAAA-MM-DD HH:MM")
    for duracion in (0, 2000):
        assert calendario_crear.ejecutar("Cita", "2026-10-21 15:00", duracion) == \
            "Error: la duración debe ser un número entero de minutos entre 1 y 1440."
    assert calendario_crear.ejecutar("  ", "2026-10-21 15:00") == "Error: falta el título del evento."
    assert falso.acciones == []
    assert calendario_crear.ejecutar("Cita", "2026-10-21T15:00") == \
        "Evento creado: Cita, 2026-10-21 15:00–16:00 (id: ev-nuevo)."


def test_sin_confirmacion_no_borra_el_evento(monkeypatch):
    falso = instalar(monkeypatch, calendario, CalendarioFalso(EVENTOS))
    argumentos = {"id_evento": "ev1"}
    assert llamar("calendario_borrar", calendario_borrar, argumentos, lambda n, a: False) == \
        "El usuario canceló la acción."
    assert falso.acciones == []
    assert falso.creaciones == 0
    assert llamar("calendario_borrar", calendario_borrar, argumentos, lambda n, a: True) == "Evento borrado (id: ev1)."
    assert falso.acciones == [("borrar", "ev1")]


def test_borrar_rechaza_id_raro(monkeypatch):
    falso = instalar(monkeypatch, calendario, CalendarioFalso())
    assert calendario_borrar.ejecutar("../calendars") == "Error: el id de evento '../calendars' no es válido."
    assert falso.acciones == []


def test_banderas():
    assert calendario_eventos.requiere_confirmacion is False
    assert calendario_crear.requiere_confirmacion is True
    assert calendario_borrar.requiere_confirmacion is True


def test_sin_credenciales_error_claro(monkeypatch):
    sin_credenciales(monkeypatch, google)
    assert calendario_eventos.ejecutar("2026-10-20") == SIN_GOOGLE
    argumentos = {"titulo": "Dentista", "inicio": "2026-10-21 15:00", "duracion_minutos": 60}
    assert llamar("calendario_crear", calendario_crear, argumentos, lambda n, a: True) == SIN_GOOGLE


def test_cliente_google_calendario(monkeypatch):
    cliente = calendario.ClienteGoogleCalendario()
    respuesta = {"items": [
        {"id": "a", "summary": "Reunión", "start": {"dateTime": "2026-10-20T09:00:00-05:00"},
         "end": {"dateTime": "2026-10-20T10:00:00-05:00"}},
        {"id": "b", "start": {"date": "2026-10-20"}, "end": {"date": "2026-10-21"}},
    ]}
    pedir = PedirFalso(respuesta, {"id": "nuevo"}, {})
    monkeypatch.setattr(google, "pedir", pedir)

    def local(texto):
        return datetime.fromisoformat(texto).astimezone().strftime("%H:%M")

    assert cliente.eventos_del_dia(date(2026, 10, 20)) == [
        {"id": "a", "titulo": "Reunión", "inicio": local("2026-10-20T09:00:00-05:00"),
         "fin": local("2026-10-20T10:00:00-05:00")},
        {"id": "b", "titulo": "(sin título)", "inicio": "", "fin": ""},
    ]
    metodo, url, params, cuerpo = pedir.llamadas[0]
    assert (metodo, url, cuerpo) == ("GET", calendario.URL, None)
    assert params["timeMin"] == datetime(2026, 10, 20).astimezone().isoformat()
    assert params["timeMax"] == datetime(2026, 10, 21).astimezone().isoformat()
    assert params["singleEvents"] == "true"
    assert params["orderBy"] == "startTime"

    inicio, fin = datetime(2026, 10, 21, 15), datetime(2026, 10, 21, 16)
    assert cliente.crear_evento("X", inicio, fin) == {"id": "nuevo"}
    assert pedir.llamadas[1] == ("POST", calendario.URL, None, {
        "summary": "X", "start": {"dateTime": inicio.astimezone().isoformat()},
        "end": {"dateTime": fin.astimezone().isoformat()}})

    cliente.borrar_evento("a_b-1")
    assert pedir.llamadas[2] == ("DELETE", calendario.URL + "/a_b-1", None, None)
    assert isinstance(calendario.obtener_cliente(), calendario.ClienteGoogleCalendario)
