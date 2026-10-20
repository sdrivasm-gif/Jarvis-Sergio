import json
import subprocess
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from jarvis.llm import Respuesta, crear_cliente
from jarvis.llm.claude_cli import ClienteClaudeCLI

RAIZ = Path(__file__).resolve().parent.parent


class Entrada:
    def __init__(self):
        self.escrito = ""

    def write(self, texto):
        self.escrito += texto

    def close(self):
        pass


class ProcesoFalso:
    """Sustituye al proceso de Popen: stdout son líneas ya preparadas."""

    def __init__(self, lineas, codigo=0):
        self.stdin = Entrada()
        self.stdout = iter(lineas)
        self.codigo = codigo
        self.returncode = None

    def wait(self):
        self.returncode = self.codigo
        return self.returncode

    def kill(self):
        pass


class PopenFalso:
    """Sustituye a subprocess.Popen: guarda cada llamada y entrega los procesos en orden."""

    def __init__(self, *procesos):
        self.procesos = list(procesos)
        self.llamadas = []

    def __call__(self, comando, **kwargs):
        self.llamadas.append((comando, kwargs))
        return self.procesos[len(self.llamadas) - 1]


def flujo(*deltas, texto=None, session_id="s1", is_error=False):
    """Líneas de `claude -p --output-format stream-json`: init, deltas, un thinking, resultado."""
    eventos = [{"type": "system", "subtype": "init", "session_id": session_id}]
    eventos += [{"type": "stream_event", "event": {"type": "content_block_delta",
                                                    "delta": {"type": "text_delta", "text": d}}} for d in deltas]
    eventos.append({"type": "stream_event", "event": {"type": "content_block_delta",
                                                       "delta": {"type": "thinking_delta", "thinking": "hmm"}}})
    eventos.append({"type": "result", "is_error": is_error, "session_id": session_id,
                    "result": "".join(deltas) if texto is None else texto})
    return [json.dumps(e) + "\n" for e in eventos]


def msg(texto):
    return [{"rol": "usuario", "texto": texto}]


def valor(comando, flag):
    return comando[comando.index(flag) + 1]


def test_primera_llamada_flags_prompt_y_streaming():
    falso = PopenFalso(ProcesoFalso(flujo("Ho", "la")))
    cliente = ClienteClaudeCLI("sonnet", "medium", abrir=falso)
    fragmentos = []
    cliente.al_texto = fragmentos.append

    respuesta = cliente.responder(msg("hola"), [], "Eres Jarvis")

    assert respuesta == Respuesta(texto="Hola")
    assert fragmentos == ["Ho", "la"]  # solo text_delta, uno por uno
    comando, kwargs = falso.llamadas[0]
    assert comando[:2] == ["claude", "-p"]
    assert valor(comando, "--output-format") == "stream-json"
    assert "--verbose" in comando and "--include-partial-messages" in comando
    assert valor(comando, "--model") == "sonnet"
    assert valor(comando, "--effort") == "medium"
    assert valor(comando, "--system-prompt") == "Eres Jarvis"
    assert valor(comando, "--tools") == ""  # sin herramientas
    # arranque corto: sin CLAUDE.md/hooks (safe-mode), skills, MCP ni ajustes del usuario
    assert "--safe-mode" in comando
    assert "--disable-slash-commands" in comando
    assert "--strict-mcp-config" in comando
    assert valor(comando, "--setting-sources") == ""
    assert "--resume" not in comando
    assert "--bare" not in comando  # --bare exige clave de API
    assert "--no-session-persistence" not in comando  # --resume lo necesita
    assert falso.procesos[0].stdin.escrito == "hola"  # el prompt va por stdin
    assert kwargs["stderr"] == subprocess.STDOUT  # un solo canal: sin riesgo de bloqueo por stderr lleno


def test_sin_al_texto_no_falla():
    falso = PopenFalso(ProcesoFalso(flujo("Hola")))
    assert ClienteClaudeCLI("sonnet", "medium", abrir=falso).responder(msg("hola"), [], "s").texto == "Hola"


def test_corre_en_carpeta_neutra_fuera_del_proyecto():
    falso = PopenFalso(ProcesoFalso(flujo("x")))
    ClienteClaudeCLI("sonnet", "medium", abrir=falso).responder(msg("hola"), [], "s")

    cwd = Path(falso.llamadas[0][1]["cwd"]).resolve()
    assert RAIZ not in (cwd, *cwd.parents)


def test_segunda_llamada_continua_la_sesion_y_manda_solo_el_ultimo_mensaje():
    falso = PopenFalso(ProcesoFalso(flujo("uno", session_id="sesion-42")),
                       ProcesoFalso(flujo("dos", session_id="sesion-42")))
    cliente = ClienteClaudeCLI("sonnet", "medium", abrir=falso)

    cliente.responder(msg("hola"), [], "s")
    historial = msg("hola") + [
        {"rol": "asistente", "texto": "uno", "llamadas": []},
        {"rol": "usuario", "texto": "¿y ahora?"},
    ]
    cliente.responder(historial, [], "s")

    assert valor(falso.llamadas[1][0], "--resume") == "sesion-42"
    assert falso.procesos[1].stdin.escrito == "¿y ahora?"


@pytest.mark.parametrize("fallido", [
    ProcesoFalso(["Error: sesión no encontrada\n"], codigo=1),  # salió sin evento result
    ProcesoFalso(flujo(texto="límite alcanzado", is_error=True)),
    ProcesoFalso([]),
])
def test_errores_del_cli_lanzan_runtimeerror_y_no_guardan_sesion(fallido):
    falso = PopenFalso(fallido, ProcesoFalso(flujo("bien", session_id="s2")))
    cliente = ClienteClaudeCLI("sonnet", "medium", abrir=falso)

    with pytest.raises(RuntimeError):
        cliente.responder(msg("hola"), [], "s")

    cliente.responder(msg("hola"), [], "s")
    assert "--resume" not in falso.llamadas[1][0]


def test_el_error_incluye_la_salida_del_cli():
    falso = PopenFalso(ProcesoFalso(["Error: sesión no encontrada\n"], codigo=1))
    with pytest.raises(RuntimeError, match="sesión no encontrada"):
        ClienteClaudeCLI("sonnet", "medium", abrir=falso).responder(msg("hola"), [], "s")


def test_crear_cliente_claude_cli():
    cliente = crear_cliente(NS(proveedor="claude-cli", modelo="sonnet", esfuerzo="medium", clave=""))
    assert isinstance(cliente, ClienteClaudeCLI)
