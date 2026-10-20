import importlib
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from clientes_falsos import entradas, no_debe_preguntar

from jarvis import bucle, memoria, recordatorios
from jarvis.bucle import (
    SISTEMA,
    cargar_sistema,
    confirmar_por_terminal,
    conversar,
    ejecutar_llamada,
    texto_confirmacion,
    turno,
)
from jarvis.llm import LlamadaHerramienta, Respuesta
from jarvis.llm.claude import a_formato_anthropic
from jarvis.llm.falso import ClienteFalso


def herramienta(nombre, ejecutar, requiere_confirmacion=False, requeridos=()):
    return SimpleNamespace(
        NOMBRE=nombre,
        DESCRIPCION=f"Herramienta {nombre}.",
        ESQUEMA={"type": "object", "properties": {k: {"type": "string"} for k in requeridos},
                 "required": list(requeridos)},
        requiere_confirmacion=requiere_confirmacion,
        ejecutar=ejecutar,
    )


def pide(nombre, id_llamada="l1", **argumentos):
    return Respuesta(llamadas=[LlamadaHerramienta(id_llamada, nombre, argumentos)])


# 17
def test_turno_solo_texto():
    cliente = ClienteFalso([Respuesta(texto="Hola, soy Jarvis.")])
    historial = []
    assert turno(cliente, historial, {}, "hola") == "Hola, soy Jarvis."
    assert historial == [
        {"rol": "usuario", "texto": "hola"},
        {"rol": "asistente", "texto": "Hola, soy Jarvis.", "llamadas": []},
    ]
    assert cliente.recibidos[0]["sistema"] == cargar_sistema()


def test_sistema_viene_de_personalidad_md():
    cliente = ClienteFalso([Respuesta(texto="ok")])
    turno(cliente, [], {}, "hola")
    sistema = cliente.recibidos[0]["sistema"]
    assert sistema == (Path(bucle.__file__).parent / "personalidad.md").read_text(encoding="utf-8")
    assert "Eres Jarvis, el asistente personal de Sergio" in sistema


def test_sin_personalidad_usa_el_respaldo(monkeypatch, tmp_path):
    monkeypatch.setattr(bucle, "ARCHIVO_PERSONALIDAD", tmp_path / "no_existe.md")
    cliente = ClienteFalso([Respuesta(texto="ok")])
    turno(cliente, [], {}, "hola")
    assert cliente.recibidos[0]["sistema"] == SISTEMA


# 18
def test_turno_usa_herramienta_y_pasa_el_resultado():
    herramientas = {"hora": herramienta("hora", lambda: "2026-10-19 10:00")}
    cliente = ClienteFalso([pide("hora", "l1"), Respuesta(texto="Son las 10.")])
    historial = []
    assert turno(cliente, historial, herramientas, "¿qué hora es?") == "Son las 10."
    resultado = {"rol": "herramienta", "id_llamada": "l1", "resultado": "2026-10-19 10:00"}
    assert resultado in historial
    assert cliente.recibidos[1]["mensajes"][-1] == resultado
    assert cliente.recibidos[0]["herramientas"] == [{
        "nombre": "hora",
        "descripcion": "Herramienta hora.",
        "esquema": {"type": "object", "properties": {}, "required": []},
    }]


# 19
def test_confirmacion_negada_no_ejecuta_y_afirmada_si():
    ejecutadas = []
    borrar = herramienta("borrar", lambda **a: ejecutadas.append(a) or "borrado", requiere_confirmacion=True)
    llamada = LlamadaHerramienta("l1", "borrar", {"ruta": "x"})
    vistos = []

    def negar(nombre, argumentos):
        vistos.append((nombre, argumentos))
        return False

    resultado = ejecutar_llamada(llamada, {"borrar": borrar}, negar)
    assert "canceló" in resultado
    assert ejecutadas == []
    assert vistos == [("borrar", {"ruta": "x"})]

    assert ejecutar_llamada(llamada, {"borrar": borrar}, lambda n, a: True) == "borrado"
    assert ejecutadas == [{"ruta": "x"}]


def test_sin_confirmacion_requerida_no_pregunta():
    hora = herramienta("hora", lambda: "ahora")
    assert ejecutar_llamada(LlamadaHerramienta("l1", "hora", {}), {"hora": hora}, no_debe_preguntar) == "ahora"


@pytest.mark.parametrize("respuesta, esperado", [
    ("s", True), ("si", True), ("sí", True), (" S ", True), ("SÍ", True),
    ("", False), ("n", False), ("no", False), ("yes", False), ("sii", False),
])
def test_confirmar_por_terminal(monkeypatch, respuesta, esperado):
    preguntas = []
    monkeypatch.setattr("builtins.input", lambda prompt: preguntas.append(prompt) or respuesta)
    assert confirmar_por_terminal("borrar", {"ruta": "x"}) is esperado
    assert preguntas == ["¿Ejecutar borrar?\n  ruta: x\n[s/N] "]


def test_texto_confirmacion_legible():
    assert texto_confirmacion("correo_enviar", {"para": "ana@example.com", "cuerpo": "Hola\nAna"}) == \
        "¿Ejecutar correo_enviar?\n  para: ana@example.com\n  cuerpo: Hola\n    Ana\n[s/N] "
    assert texto_confirmacion("hora", {}) == "¿Ejecutar hora?\n[s/N] "


def test_texto_confirmacion_deja_los_multilinea_al_final():
    # Un cuerpo largo no debe separar "para" del [s/N].
    texto = texto_confirmacion("correo_enviar", {"cuerpo": "a\nb", "para": "x@y.com"})
    assert texto.index("  para:") < texto.index("  cuerpo:")


def test_texto_confirmacion_escapa_caracteres_de_control():
    # Un \x1b[1A o un \r podrían reescribir en la terminal lo que el usuario confirma; U+202E invierte el texto.
    texto = texto_confirmacion("correo_enviar", {"cuerpo": "a\x1b[1Ab\rc", "para": "x‮@example.com"})
    assert "\x1b" not in texto and "\r" not in texto and "‮" not in texto
    assert "  cuerpo: a\\x1b[1Ab\\rc\n" in texto
    assert "  para: x\\u202e@example.com\n" in texto


def test_faltan_argumentos_no_pide_confirmacion_ni_ejecuta():
    ejecutadas = []
    enviar = herramienta("enviar", lambda **a: ejecutadas.append(a) or "enviado",
                         requiere_confirmacion=True, requeridos=("para", "asunto"))

    def llamar(argumentos, confirmar=no_debe_preguntar):
        return ejecutar_llamada(LlamadaHerramienta("l1", "enviar", argumentos), {"enviar": enviar}, confirmar)

    assert llamar({}) == "Error: faltan argumentos para enviar: para, asunto."
    assert llamar({"para": "  ", "asunto": "x"}) == "Error: faltan argumentos para enviar: para."
    assert ejecutadas == []
    assert llamar({"para": "ana@example.com", "asunto": "x"}, lambda n, a: True) == "enviado"


def test_confirmar_por_terminal_con_eof_cancela(monkeypatch):
    def sin_entrada(prompt):
        raise EOFError

    monkeypatch.setattr("builtins.input", sin_entrada)
    assert confirmar_por_terminal("borrar", {}) is False


# 20
def test_herramienta_desconocida_y_excepcion_dan_error():
    def falla():
        raise OSError("disco lleno")

    herramientas = {"falla": herramienta("falla", falla)}
    assert ejecutar_llamada(LlamadaHerramienta("l1", "nada", {}), herramientas, None) == \
        "Error: herramienta desconocida 'nada'"
    assert ejecutar_llamada(LlamadaHerramienta("l2", "falla", {}), herramientas, None) == "Error: disco lleno"


def test_argumentos_invalidos_dan_error():
    hora = herramienta("hora", lambda: "ahora")
    resultado = ejecutar_llamada(LlamadaHerramienta("l1", "hora", {"inventado": 1}), {"hora": hora}, None)
    assert resultado.startswith("Error: ")


# 21
def test_tope_de_iteraciones():
    herramientas = {"hora": herramienta("hora", lambda: "ahora")}
    cliente = ClienteFalso([pide("hora", f"l{i}") for i in range(10)])
    resultado = turno(cliente, [], herramientas, "bucle", max_iteraciones=3)
    assert resultado == "Me detuve: demasiadas llamadas a herramientas seguidas."
    assert len(cliente.recibidos) == 3


# 22
def test_conversar_responde_y_sale_con_salir():
    cliente = ClienteFalso([Respuesta(texto="Hola.")])
    impreso = []
    conversar(cliente, {}, entrada=entradas("", "hola", "/salir"), salida=impreso.append)
    assert len(cliente.recibidos) == 1
    assert impreso == ["jarvis> Hola.", "Hasta luego."]


@pytest.mark.parametrize("corte", [EOFError(), KeyboardInterrupt()])
def test_conversar_sale_sin_traza_con_eof_o_ctrl_c(corte):
    impreso = []
    conversar(ClienteFalso([]), {}, entrada=entradas(corte), salida=impreso.append)
    assert impreso == ["Hasta luego."]


def test_conversar_error_del_proveedor_restaura_historial():
    class ClienteQueFallaUnaVez:
        def __init__(self):
            self.recibidos = []

        def responder(self, mensajes, herramientas, sistema):
            self.recibidos.append(list(mensajes))
            if len(self.recibidos) == 1:
                raise ConnectionError("sin red")
            return Respuesta(texto="ok")

    cliente = ClienteQueFallaUnaVez()
    impreso = []
    conversar(cliente, {}, entrada=entradas("uno", "dos"), salida=impreso.append)
    assert impreso == ["Error del proveedor: ConnectionError: sin red", "jarvis> ok", "Hasta luego."]
    assert cliente.recibidos[1] == [{"rol": "usuario", "texto": "dos"}]


def test_respuesta_vacia_no_rompe_el_historial():
    cliente = ClienteFalso([Respuesta(), Respuesta(texto="ok")])
    historial = []
    assert turno(cliente, historial, {}, "uno") == "(sin respuesta del modelo; prueba de nuevo)"
    assert turno(cliente, historial, {}, "dos") == "ok"
    assert all(m["content"] != [] for m in a_formato_anthropic(historial))


def test_respuesta_solo_espacios_no_rompe_el_historial():
    cliente = ClienteFalso([Respuesta(texto="\n\n"), Respuesta(texto="ok")])
    historial = []
    assert turno(cliente, historial, {}, "uno") == "(sin respuesta del modelo; prueba de nuevo)"
    assert turno(cliente, historial, {}, "dos") == "ok"
    assert all(b["text"].strip() for m in a_formato_anthropic(historial) for b in m["content"] if b["type"] == "text")


def test_conversar_avisa_si_el_turno_fallido_ya_ejecuto_herramientas():
    herramientas = {"hora": herramienta("hora", lambda: "ahora")}
    # ClienteFalso lanza RuntimeError en la 2.ª llamada al quedarse sin respuestas.
    cliente = ClienteFalso([pide("hora")])
    impreso = []
    conversar(cliente, herramientas, entrada=entradas("hora"), salida=impreso.append)
    assert impreso[0].startswith("Error del proveedor: RuntimeError")
    assert "ya se ejecutaron 1" in impreso[1]


class ClienteQueTransmite:
    """Como ClienteClaudeCLI: si `al_texto` existe, el bucle lo rellena y recibe los fragmentos."""

    def __init__(self, fragmentos, falla=False):
        self.al_texto = None
        self.fragmentos = fragmentos
        self.falla = falla

    def responder(self, mensajes, herramientas, sistema):
        for fragmento in self.fragmentos:
            self.al_texto(fragmento)
        if self.falla:
            raise ConnectionError("se cortó")
        return Respuesta(texto="".join(self.fragmentos))


def test_conversar_muestra_los_fragmentos_sin_repetir_la_respuesta():
    impreso, fragmentos = [], []
    conversar(ClienteQueTransmite(["Ho", "la"]), {}, entrada=entradas("hola", "/salir"),
              salida=impreso.append, fragmento=fragmentos.append)
    assert fragmentos == ["jarvis> ", "Ho", "la", "\n"]
    assert impreso == ["Hasta luego."]


def test_conversar_cierra_la_linea_si_el_streaming_se_corta():
    impreso, fragmentos = [], []
    conversar(ClienteQueTransmite(["Ho"], falla=True), {}, entrada=entradas("hola", "/salir"),
              salida=impreso.append, fragmento=fragmentos.append)
    assert fragmentos == ["jarvis> ", "Ho", "\n"]
    assert impreso == ["Error del proveedor: ConnectionError: se cortó", "Hasta luego."]


def test_conversar_imprime_la_respuesta_si_el_cliente_transmite_pero_no_envio_nada():
    impreso, fragmentos = [], []
    conversar(ClienteQueTransmite([]), {}, entrada=entradas("hola", "/salir"),
              salida=impreso.append, fragmento=fragmentos.append)
    assert fragmentos == []
    assert impreso == ["jarvis> (sin respuesta del modelo; prueba de nuevo)", "Hasta luego."]


def test_sistema_completo_sin_recuerdos_es_la_personalidad():
    assert bucle.sistema_completo() == cargar_sistema()


def test_turno_lleva_los_recuerdos_al_sistema():
    memoria.guardar("prefiere el café", datetime(2026, 10, 20, 9, 0))
    cliente = ClienteFalso([Respuesta(texto="ok")])
    turno(cliente, [], {}, "hola")
    assert cliente.recibidos[0]["sistema"] == cargar_sistema() + "\n\n" + memoria.ENCABEZADO + "\n- [1] prefiere el café"


def crear_agua():
    recordatorios.crear("tomar agua", datetime(2026, 10, 20, 10, 5), datetime(2026, 10, 20, 10, 0))


def test_conversar_avisa_un_recordatorio_una_sola_vez():
    crear_agua()
    tiempos = iter([datetime(2026, 10, 20, 10, 0), datetime(2026, 10, 20, 10, 6), datetime(2026, 10, 20, 10, 7)])
    impreso = []
    conversar(ClienteFalso([Respuesta(texto="ok"), Respuesta(texto="ok")]), {}, entrada=entradas("hola", "otra"),
              salida=impreso.append, reloj=lambda: next(tiempos))
    assert impreso == ["jarvis> ok", "jarvis> Recordatorio (2026-10-20 10:05): tomar agua", "jarvis> ok", "Hasta luego."]


def test_conversar_avisa_al_arrancar_y_no_repite_tras_reiniciar():
    crear_agua()
    for esperado in (["jarvis> Recordatorio (2026-10-20 10:05): tomar agua", "Hasta luego."], ["Hasta luego."]):
        impreso = []
        conversar(ClienteFalso([]), {}, entrada=entradas(), salida=impreso.append,
                  reloj=lambda: datetime(2026, 10, 20, 12, 0))
        assert impreso == esperado
        importlib.reload(recordatorios)


def test_conversar_recordatorios_danados_no_rompen(tmp_path):
    archivo = tmp_path / "datos" / "recordatorios.json"
    archivo.parent.mkdir(parents=True)
    archivo.write_text("{roto", encoding="utf-8")
    impreso = []
    conversar(ClienteFalso([Respuesta(texto="ok")]), {}, entrada=entradas("hola"), salida=impreso.append)
    e = "Error en los recordatorios: el archivo de datos recordatorios.json está dañado; revísalo o bórralo."
    assert impreso == [e, "jarvis> ok", e, "Hasta luego."]


def escribir_recordatorios(tmp_path, registros):
    archivo = tmp_path / "datos" / "recordatorios.json"
    archivo.parent.mkdir(parents=True)
    archivo.write_text(json.dumps(registros), encoding="utf-8")


def test_recordatorio_sin_estado_no_tumba_la_conversacion(tmp_path):
    escribir_recordatorios(tmp_path, [{"id": 1, "texto": "x", "cuando": "2026-10-20T10:05:00"}])
    impreso = []
    conversar(ClienteFalso([Respuesta(texto="ok")]), {}, entrada=entradas("hola"), salida=impreso.append)
    assert impreso[0].startswith("Error en los recordatorios: ")
    assert impreso[1:] == ["jarvis> ok", impreso[0], "Hasta luego."]


def test_recordatorio_con_cuando_null_no_tumba_el_aviso(tmp_path):
    escribir_recordatorios(tmp_path, [{"id": 1, "texto": "x", "cuando": None, "estado": "pendiente"}])
    impreso = []
    bucle.avisar_vencidos(impreso.append, datetime(2026, 10, 20, 12, 0))
    assert len(impreso) == 1 and impreso[0].startswith("Error en los recordatorios: ")


def test_sin_fragmento_no_transmite():
    class ClienteQueTransmite:
        al_texto = None

        def responder(self, mensajes, herramientas, sistema):
            assert self.al_texto is None  # con fragmento=None (voz) no se engancha el streaming
            return Respuesta(texto="hola")

    cliente, impreso = ClienteQueTransmite(), []
    conversar(cliente, {}, entrada=entradas("hola"), salida=impreso.append, fragmento=None)
    assert impreso == ["jarvis> hola", "Hasta luego."]
    assert cliente.al_texto is None
