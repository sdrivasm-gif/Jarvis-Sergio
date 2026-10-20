from pathlib import Path
from types import SimpleNamespace

import pytest
from clientes_falsos import no_debe_preguntar

from jarvis import bucle
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


def entradas(*textos):
    """Simula input(): devuelve cada texto y luego lanza EOFError."""
    pendientes = list(textos)

    def entrada(prompt=""):
        if not pendientes:
            raise EOFError
        valor = pendientes.pop(0)
        if isinstance(valor, BaseException):
            raise valor
        return valor

    return entrada


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
