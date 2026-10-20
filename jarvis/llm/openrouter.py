"""Cliente de OpenRouter (API compatible con OpenAI)."""
from __future__ import annotations

import json

from jarvis.llm import LlamadaHerramienta, Respuesta

# ponytail: NO verificado contra el catálogo de OpenRouter (sin red/clave en esta fase);
# confirmar el id con la skill openrouter-models y actualizar aquí.
MODELO_OPENROUTER_POR_DEFECTO = "anthropic/claude-sonnet-5-5"
MAX_TOKENS = 16000  # ponytail: fijo e incluye el pensamiento del modelo; hacerlo configurable si las respuestas se cortan


def a_formato_openai(mensajes: list[dict], sistema: str) -> list[dict]:
    salida: list[dict] = [{"role": "system", "content": sistema}]
    for m in mensajes:
        if m["rol"] == "asistente":
            msg = {"role": "assistant", "content": m["texto"] or None}
            if m.get("llamadas"):
                msg["tool_calls"] = [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.nombre, "arguments": json.dumps(c.argumentos)},
                    }
                    for c in m["llamadas"]
                ]
            salida.append(msg)
        elif m["rol"] == "herramienta":
            salida.append({"role": "tool", "tool_call_id": m["id_llamada"], "content": m["resultado"]})
        else:
            salida.append({"role": "user", "content": m["texto"]})
    return salida


def desde_openai(resp) -> Respuesta:
    msg = resp.choices[0].message
    llamadas = []
    for c in msg.tool_calls or []:
        try:
            args = json.loads(c.function.arguments)
        except json.JSONDecodeError:
            args = {}  # ponytail: JSON inválido se descarta en silencio; avisar al modelo del error
        llamadas.append(LlamadaHerramienta(c.id, c.function.name, args))
    return Respuesta(msg.content or "", llamadas)


class ClienteOpenRouter:
    def __init__(self, clave: str, modelo: str, sdk=None):
        if sdk is None:
            import openai

            sdk = openai.OpenAI(api_key=clave, base_url="https://openrouter.ai/api/v1")
        self._sdk = sdk
        self._modelo = modelo

    def responder(self, mensajes: list[dict], herramientas: list[dict], sistema: str) -> Respuesta:
        args = dict(
            model=self._modelo,
            max_tokens=MAX_TOKENS,
            messages=a_formato_openai(mensajes, sistema),
        )
        if herramientas:
            args["tools"] = [
                {
                    "type": "function",
                    "function": {"name": h["nombre"], "description": h["descripcion"], "parameters": h["esquema"]},
                }
                for h in herramientas
            ]
        return desde_openai(self._sdk.chat.completions.create(**args))
