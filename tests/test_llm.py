import json
from types import SimpleNamespace as NS

import pytest

from jarvis.llm import LlamadaHerramienta, Respuesta, crear_cliente
from jarvis.llm.claude import ClienteClaude, a_formato_anthropic
from jarvis.llm.falso import ClienteFalso
from jarvis.llm.openrouter import (
    MODELO_OPENROUTER_POR_DEFECTO,
    ClienteOpenRouter,
    a_formato_openai,
)

HERRAMIENTA = {"nombre": "hora", "descripcion": "Hora local.", "esquema": {"type": "object"}}
HISTORIAL = [
    {"rol": "usuario", "texto": "hola"},
    {"rol": "asistente", "texto": "", "llamadas": [LlamadaHerramienta("t1", "hora", {"a": 1})]},
    {"rol": "herramienta", "id_llamada": "t1", "resultado": "10:00"},
    {"rol": "herramienta", "id_llamada": "t2", "resultado": "11:00"},
    {"rol": "usuario", "texto": "gracias"},
]


def test_falso_en_orden_registra_y_se_agota():
    r1, r2 = Respuesta(texto="a"), Respuesta(texto="b")
    f = ClienteFalso([r1, r2])
    msgs = [{"rol": "usuario", "texto": "x"}]
    assert f.responder(msgs, [], "sis") is r1
    msgs.append({"rol": "usuario", "texto": "y"})  # la copia guardada no cambia
    assert f.recibidos[0]["mensajes"] == [{"rol": "usuario", "texto": "x"}]
    assert f.recibidos[0]["sistema"] == "sis"
    assert f.responder(msgs, [], "sis") is r2
    with pytest.raises(RuntimeError, match="ClienteFalso sin respuestas"):
        f.responder(msgs, [], "sis")


def test_a_formato_anthropic_tool_use_y_fusion_de_user():
    out = a_formato_anthropic(HISTORIAL)
    assert [m["role"] for m in out] == ["user", "assistant", "user"]
    assert out[1]["content"] == [
        {"type": "tool_use", "id": "t1", "name": "hora", "input": {"a": 1}}
    ]
    assert out[2]["content"] == [
        {"type": "tool_result", "tool_use_id": "t1", "content": "10:00"},
        {"type": "tool_result", "tool_use_id": "t2", "content": "11:00"},
        {"type": "text", "text": "gracias"},
    ]


def test_cliente_claude_con_sdk_simulado():
    llamadas = []
    resp = NS(content=[
        NS(type="text", text="Son "),
        NS(type="text", text="las 10"),
        NS(type="tool_use", id="t9", name="hora", input={"z": 2}),
    ])
    sdk = NS(messages=NS(create=lambda **kw: llamadas.append(kw) or resp))
    r = ClienteClaude("falsa", "m1", sdk=sdk).responder(HISTORIAL[:1], [HERRAMIENTA], "sis")
    kw = llamadas[0]
    assert kw["model"] == "m1" and kw["system"] == "sis"
    assert kw["tools"] == [{"name": "hora", "description": "Hora local.", "input_schema": {"type": "object"}}]
    assert r == Respuesta("Son las 10", [LlamadaHerramienta("t9", "hora", {"z": 2})])
    ClienteClaude("falsa", "m1", sdk=sdk).responder(HISTORIAL[:1], [], "sis")
    assert "tools" not in llamadas[1]


def test_a_formato_openai():
    out = a_formato_openai(HISTORIAL, "sis")
    assert out[0] == {"role": "system", "content": "sis"}
    asistente = out[2]
    assert asistente["content"] is None
    assert asistente["tool_calls"][0]["function"]["arguments"] == json.dumps({"a": 1})
    assert out[3] == {"role": "tool", "tool_call_id": "t1", "content": "10:00"}


def test_cliente_openrouter_con_sdk_simulado():
    llamadas = []
    msg = NS(content=None, tool_calls=[
        NS(id="c1", function=NS(name="hora", arguments='{"z": 2}')),
        NS(id="c2", function=NS(name="hora", arguments="no es json")),
    ])
    resp = NS(choices=[NS(message=msg)])
    sdk = NS(chat=NS(completions=NS(create=lambda **kw: llamadas.append(kw) or resp)))
    r = ClienteOpenRouter("falsa", "m1", sdk=sdk).responder(HISTORIAL[:1], [HERRAMIENTA], "sis")
    assert r.texto == ""
    assert r.llamadas == [
        LlamadaHerramienta("c1", "hora", {"z": 2}),
        LlamadaHerramienta("c2", "hora", {}),
    ]
    assert llamadas[0]["tools"][0]["function"]["parameters"] == {"type": "object"}
    ClienteOpenRouter("falsa", "m1", sdk=sdk).responder(HISTORIAL[:1], [], "sis")
    assert "tools" not in llamadas[1]


@pytest.mark.parametrize("argumentos", ["null", "[]", '"texto"', "3"])
def test_openrouter_argumentos_que_no_son_objeto_dan_dict_vacio(argumentos):
    msg = NS(content=None, tool_calls=[NS(id="c1", function=NS(name="hora", arguments=argumentos))])
    sdk = NS(chat=NS(completions=NS(create=lambda **kw: NS(choices=[NS(message=msg)]))))
    r = ClienteOpenRouter("falsa", "m1", sdk=sdk).responder(HISTORIAL[:1], [], "sis")
    assert r.llamadas == [LlamadaHerramienta("c1", "hora", {})]


def test_crear_cliente_segun_config():
    c = crear_cliente(NS(proveedor="claude", modelo="m", clave="falsa"))
    assert isinstance(c, ClienteClaude)
    o = crear_cliente(NS(proveedor="openrouter", modelo=MODELO_OPENROUTER_POR_DEFECTO, clave="falsa"))
    assert isinstance(o, ClienteOpenRouter)
    with pytest.raises(ValueError):
        crear_cliente(NS(proveedor="otro", modelo="m", clave="falsa"))
