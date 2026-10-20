"""Cliente de Claude directo (SDK de Anthropic)."""
from __future__ import annotations

from jarvis.llm import LlamadaHerramienta, Respuesta

MAX_TOKENS = 16000  # ponytail: fijo e incluye el pensamiento del modelo; hacerlo configurable si las respuestas se cortan; por encima de ~21000 el SDK exige streaming


def a_formato_anthropic(mensajes: list[dict]) -> list[dict]:
    salida: list[dict] = []
    for m in mensajes:
        if m["rol"] == "asistente":
            rol = "assistant"
            bloques = [{"type": "text", "text": m["texto"]}] if m["texto"].strip() else []
            bloques += [
                {"type": "tool_use", "id": c.id, "name": c.nombre, "input": c.argumentos}
                for c in m.get("llamadas", [])
            ]
        elif m["rol"] == "herramienta":
            rol = "user"
            bloques = [{"type": "tool_result", "tool_use_id": m["id_llamada"], "content": m["resultado"]}]
        else:
            rol = "user"
            bloques = [{"type": "text", "text": m["texto"]}]
        # La API exige roles alternos: los user consecutivos se fusionan.
        if salida and salida[-1]["role"] == rol == "user":
            salida[-1]["content"] += bloques
        else:
            salida.append({"role": rol, "content": bloques})
    return salida


def desde_anthropic(resp) -> Respuesta:
    # ponytail: se descartan los bloques thinking; devolverlos sin cambios si las cadenas de herramientas razonan mal
    texto = "".join(b.text for b in resp.content if b.type == "text")
    llamadas = [
        LlamadaHerramienta(b.id, b.name, b.input) for b in resp.content if b.type == "tool_use"
    ]
    return Respuesta(texto, llamadas)


class ClienteClaude:
    def __init__(self, clave: str, modelo: str, sdk=None):
        if sdk is None:
            import anthropic

            sdk = anthropic.Anthropic(api_key=clave)
        self._sdk = sdk
        self._modelo = modelo

    def responder(self, mensajes: list[dict], herramientas: list[dict], sistema: str) -> Respuesta:
        args = dict(
            model=self._modelo,
            max_tokens=MAX_TOKENS,
            system=sistema,
            messages=a_formato_anthropic(mensajes),
        )
        if herramientas:
            args["tools"] = [
                {"name": h["nombre"], "description": h["descripcion"], "input_schema": h["esquema"]}
                for h in herramientas
            ]
        return desde_anthropic(self._sdk.messages.create(**args))
