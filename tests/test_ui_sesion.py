import threading
import time
from datetime import datetime
from types import SimpleNamespace

import pytest
from clientes_falsos import ClienteStreamingFalso, HablanteFalso, OyenteFalso, sin_credenciales

from jarvis import bucle, recordatorios, voz
from jarvis.integrations import google
from jarvis.llm import LlamadaHerramienta, Respuesta
from jarvis.llm.falso import ClienteFalso
from jarvis.ui import sesion as ui_sesion

ARGS = {"para": "ana@example.com", "cuerpo": "Hola\nAna"}
TEXTO_CONF = "¿Ejecutar correo_enviar?\n  para: ana@example.com\n  cuerpo: Hola\n    Ana"
CLAVES = {"estado", "ocupado", "voz", "confirmacion", "mensajes", "ultimo"}


def esperar(condicion, tiempo=2.0):
    limite = time.monotonic() + tiempo
    while not condicion():
        if time.monotonic() > limite:
            pytest.fail(f"no se cumplió la condición en {tiempo} s")
        time.sleep(0.01)


def herramienta_enviar(ejecutadas):
    return SimpleNamespace(
        NOMBRE="correo_enviar", DESCRIPCION="x",
        ESQUEMA={"type": "object", "properties": {"para": {"type": "string"}, "cuerpo": {"type": "string"}},
                 "required": ["para", "cuerpo"]},
        requiere_confirmacion=True,
        ejecutar=lambda **a: ejecutadas.append(a) or "enviado",
    )


def en_hilo(f):
    resultado = {}
    hilo = threading.Thread(target=lambda: resultado.setdefault("valor", f()), daemon=True)
    hilo.resultado = resultado
    hilo.start()
    return hilo


def conversando(sesion, cliente, herramientas, piezas, reloj=datetime.now):
    return en_hilo(lambda: bucle.conversar(cliente, herramientas, reloj=reloj, **piezas))


def terminar(sesion, hilo):
    sesion.cerrar()
    hilo.join(2)
    assert not hilo.is_alive()


def mensajes(s, quien=None):
    return [(m["quien"], m["texto"]) for m in s.instantanea()["mensajes"] if quien in (None, m["quien"])]


# 1
def test_anotar_e_instantanea():
    s = ui_sesion.Sesion(token="t")
    assert [s.anotar("sistema", x)["id"] for x in "abc"] == [1, 2, 3]
    inst = s.instantanea(1)
    assert [m["id"] for m in inst["mensajes"]] == [2, 3] and inst["ultimo"] == 3
    assert set(s.instantanea()) == CLAVES
    s = ui_sesion.Sesion()
    for i in range(205):
        s.anotar("jarvis", i)
    todos = s.instantanea()["mensajes"]
    assert len(todos) == 200 and todos[0]["id"] == 6
    with pytest.raises(ValueError):
        s.anotar("otro", "x")


# 2
@pytest.mark.parametrize("linea, esperado", [
    ("jarvis> hola", ("jarvis", "hola")),
    ("jarvis> Recordatorio (2026-10-20 10:05): agua", ("aviso", "Recordatorio (2026-10-20 10:05): agua")),
    ("tú (voz)> qué hora es", ("usuario", "qué hora es")),
    ("Error del proveedor: X", ("sistema", "Error del proveedor: X")),
    ("Hasta luego.", ("sistema", "Hasta luego.")),
])
def test_anotar_linea(linea, esperado):
    s = ui_sesion.Sesion()
    s.anotar_linea(linea)
    assert mensajes(s)[-1] == esperado


# 3
def test_estados():
    s = ui_sesion.Sesion()
    with pytest.raises(ValueError):
        s.poner_estado("nada")
    with s.durante("hablando"):
        assert s.estado == "hablando"
    assert s.estado == "reposo"
    with pytest.raises(RuntimeError):
        with s.durante("hablando"):
            raise RuntimeError("x")
    assert s.estado == "reposo"


# 4
def test_enviar_y_entrada():
    s = ui_sesion.Sesion(espera_entrada=0.01)
    assert s.entrada() == "" and s.ocupado is False and s.estado == "reposo"
    assert s.enviar("  hola ") is True and s.ocupado is True
    assert s.enviar("otra") is False
    assert mensajes(s)[-1] == ("usuario", "hola")
    assert s.entrada() == "hola" and s.estado == "pensando"
    assert s.enviar("x") is False
    assert s.entrada() == "" and s.ocupado is False and s.estado == "reposo"
    assert s.enviar("x") is True


# 5
def test_cerrar():
    s = ui_sesion.Sesion()
    s.cerrar()
    with pytest.raises(EOFError):
        s.entrada()
    assert s.enviar("x") is False
    inicio = time.monotonic()
    assert s.confirmar("correo_enviar", ARGS) is False
    assert time.monotonic() - inicio < 1


# 6
@pytest.mark.parametrize("respuesta, esperado", [(True, True), (False, False), ("sí", False)])
def test_confirmar(respuesta, esperado):
    s = ui_sesion.Sesion()
    hilo = en_hilo(lambda: s.confirmar("correo_enviar", ARGS))
    esperar(lambda: s.instantanea()["confirmacion"] == {"id": 1, "texto": TEXTO_CONF, "segundos": 60})
    assert s.responder(99, True) is False
    assert s.responder(1, respuesta) is True
    assert s.responder(1, True) is False
    hilo.join(2)
    assert not hilo.is_alive()
    assert hilo.resultado["valor"] is esperado
    assert s.instantanea()["confirmacion"] is None
    assert mensajes(s, "sistema")[-1][1] == ("Confirmado: correo_enviar." if esperado else "Cancelado: correo_enviar.")


# 7
def test_confirmar_caduca():
    s = ui_sesion.Sesion(tiempo_confirmacion=0.2)
    hilo = en_hilo(lambda: s.confirmar("correo_enviar", ARGS))
    esperar(lambda: s.instantanea()["confirmacion"] is not None)
    assert s.instantanea()["confirmacion"]["segundos"] == 1
    hilo.join(1.5)
    assert not hilo.is_alive()
    assert hilo.resultado["valor"] is False
    assert mensajes(s)[-1] == ("sistema", "Sin respuesta en 1 s: correo_enviar cancelado.")
    assert s.instantanea()["confirmacion"] is None


# 8
def test_conversar_por_la_pagina():
    s = ui_sesion.Sesion(espera_entrada=0.01)
    cliente = ClienteFalso([Respuesta(texto="Hola, señor.")])
    hilo = conversando(s, cliente, {}, ui_sesion.piezas_ui(s))
    assert s.enviar("hola")
    esperar(lambda: mensajes(s, "jarvis"))
    esperar(lambda: not s.ocupado and s.estado == "reposo")
    terminar(s, hilo)
    assert mensajes(s) == [("usuario", "hola"), ("jarvis", "Hola, señor."), ("sistema", "Hasta luego.")]
    assert cliente.recibidos[0]["mensajes"][-1]["texto"] == "hola"


# 9
@pytest.mark.parametrize("caso", ["si", "no", "caduca"])
def test_confirmacion_en_la_pagina(caso):
    ejecutadas = []
    s = ui_sesion.Sesion(espera_entrada=0.01, tiempo_confirmacion=0.3)
    cliente = ClienteFalso([Respuesta(llamadas=[LlamadaHerramienta("l1", "correo_enviar", ARGS)]),
                            Respuesta(texto="Listo.")])
    hilo = conversando(s, cliente, {"correo_enviar": herramienta_enviar(ejecutadas)}, ui_sesion.piezas_ui(s))
    assert s.enviar("manda el correo")
    esperar(lambda: s.instantanea()["confirmacion"] is not None)
    id_conf = s.instantanea()["confirmacion"]["id"]
    if caso == "si":
        assert s.responder(id_conf, True)
    elif caso == "no":
        assert s.responder(id_conf, False)
    esperar(lambda: ("jarvis", "Listo.") in mensajes(s))
    terminar(s, hilo)
    resultado = cliente.recibidos[1]["mensajes"][-1]["resultado"]
    if caso == "si":
        assert ejecutadas == [ARGS] and resultado == "enviado"
    else:
        assert ejecutadas == [] and resultado == "El usuario canceló la acción."


# 10
def test_recordatorio_aparece_una_vez():
    recordatorios.crear("tomar agua", datetime(2026, 10, 20, 10, 5), datetime(2026, 10, 20, 10, 0))
    s = ui_sesion.Sesion(espera_entrada=0.01)
    hilo = conversando(s, ClienteFalso([]), {}, ui_sesion.piezas_ui(s), reloj=lambda: datetime(2026, 10, 20, 10, 6))
    esperar(lambda: mensajes(s, "aviso"))
    time.sleep(0.2)  # ≥ 10 vueltas más de conversar: el aviso no se repite
    terminar(s, hilo)
    assert [t for _, t in mensajes(s, "aviso")] == ["Recordatorio (2026-10-20 10:05): tomar agua"]


# 11
def test_hoy_por_la_pagina(monkeypatch):
    sin_credenciales(monkeypatch, google)
    s = ui_sesion.Sesion(espera_entrada=0.01)
    cliente = ClienteFalso([Respuesta(texto="Parte listo.")])
    hilo = conversando(s, cliente, {}, ui_sesion.piezas_ui(s))
    assert s.enviar("/hoy")
    esperar(lambda: ("jarvis", "Parte listo.") in mensajes(s))
    terminar(s, hilo)
    assert cliente.recibidos[0]["herramientas"] == []


class OyenteAnotado(OyenteFalso):
    """Anota el estado de la sesión en cada escucha."""

    def __init__(self, sesion, *textos):
        super().__init__(*textos)
        self.sesion, self.estados = sesion, []

    def escuchar(self):
        self.estados.append(self.sesion.estado)
        return super().escuchar()


class HablanteAnotado(HablanteFalso):
    """Anota el estado de la sesión en cada frase."""

    def __init__(self, sesion):
        super().__init__()
        self.sesion, self.estados = sesion, []

    def decir(self, texto):
        self.estados.append(self.sesion.estado)
        super().decir(texto)


# 13
def test_voz_con_pagina():
    s = ui_sesion.Sesion(espera_entrada=0.01)
    oyente, hablante = OyenteAnotado(s, "Jarvis, ¿qué hora es?"), HablanteAnotado(s)
    cliente = ClienteFalso([Respuesta(texto="Son las 10."), Respuesta(texto="Hola.")])
    hilo = conversando(s, cliente, {}, ui_sesion.piezas_ui_voz(s, oyente, hablante, ["jarvis"]))
    esperar(lambda: ("sistema", ui_sesion.VOZ_APAGADA) in mensajes(s))
    assert s.voz is False
    assert ("usuario", "¿qué hora es?") in mensajes(s) and ("jarvis", "Son las 10.") in mensajes(s)
    assert hablante.dichos[0] == "Son las 10."
    assert oyente.estados and set(oyente.estados) == {"escuchando"}
    assert hablante.estados and set(hablante.estados) == {"hablando"}
    assert s.enviar("hola")
    esperar(lambda: ("jarvis", "Hola.") in mensajes(s))
    terminar(s, hilo)


# 14
def test_voz_confirma_en_pantalla():
    s = ui_sesion.Sesion()
    oyente, hablante = OyenteFalso("sí"), HablanteFalso()
    confirmar = ui_sesion.piezas_ui_voz(s, oyente, hablante, ["jarvis"])["confirmar"]
    assert s.voz is True
    hilo = en_hilo(lambda: confirmar("correo_enviar", ARGS))
    esperar(lambda: s.instantanea()["confirmacion"] is not None)
    assert hablante.dichos == [ui_sesion.CONFIRMA_EN_PANTALLA]
    assert oyente.escuchas == 0  # nunca se oye un "sí"
    assert s.responder(1, True) is True
    hilo.join(2)
    assert not hilo.is_alive() and hilo.resultado["valor"] is True


# 15
def test_microfono_roto_no_cierra():
    s = ui_sesion.Sesion(espera_entrada=0.01)
    piezas = ui_sesion.piezas_ui_voz(s, OyenteFalso(RuntimeError("sin micro")), HablanteFalso(), ["jarvis"])
    hilo = conversando(s, ClienteFalso([]), {}, piezas)
    esperar(lambda: ("sistema", ui_sesion.VOZ_APAGADA) in mensajes(s))
    assert ("sistema", "Error del micrófono: sin micro") in mensajes(s)
    time.sleep(0.05)  # unas vueltas más: conversar sigue vivo con texto
    assert hilo.is_alive()
    terminar(s, hilo)


@pytest.mark.parametrize("falla", [None, voz.ErrorVoz("sin audio")])
def test_hablante_con_estado_habla_hasta_que_termina_de_sonar(falla):
    s = ui_sesion.Sesion()
    s.poner_estado("pensando")
    interno = HablanteFalso(falla_esperar=falla)
    h = ui_sesion.HablanteConEstado(interno, s)
    h.encolar("Primera frase.")
    h.encolar("Segunda frase.")
    assert s.estado == "hablando" and interno.encolados == ["Primera frase.", "Segunda frase."]
    if falla:
        with pytest.raises(voz.ErrorVoz):
            h.esperar()
    else:
        h.esperar()
    assert s.estado == "pensando" and interno.esperas == 1
    h.cortar()
    assert interno.cortes == 1 and s.estado == "pensando"


def test_voz_con_pagina_y_streaming():
    s = ui_sesion.Sesion(espera_entrada=0.01)
    hablante = HablanteFalso()
    piezas = ui_sesion.piezas_ui_voz(s, OyenteFalso("Jarvis, ¿qué hora es?"), hablante, ["jarvis"])
    assert isinstance(piezas["fragmento"], voz.FragmentoDeVoz)
    cliente = ClienteStreamingFalso(["Son las diez y cuarto, señor. ", "Que tenga buen día"])
    hilo = conversando(s, cliente, {}, piezas)
    esperar(lambda: ("sistema", ui_sesion.VOZ_APAGADA) in mensajes(s))
    terminar(s, hilo)
    assert ("jarvis", "Son las diez y cuarto, señor. Que tenga buen día") in mensajes(s)
    assert hablante.encolados == ["Son las diez y cuarto, señor.", "Que tenga buen día."]
    assert not any(t.startswith("(no pude hablar") for _, t in mensajes(s))


# 12
def test_piezas_ui():
    s = ui_sesion.Sesion()
    piezas = ui_sesion.piezas_ui(s)
    assert set(piezas) == {"entrada", "salida", "confirmar", "fragmento"} and piezas["fragmento"] is None
    assert piezas["salida"] == s.anotar_linea and piezas["confirmar"] == s.confirmar
