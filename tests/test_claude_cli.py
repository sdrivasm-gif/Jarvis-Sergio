import json
import subprocess
import threading
import time
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from jarvis.llm import Respuesta, crear_cliente
from jarvis.llm import claude_cli
from jarvis.llm.claude_cli import SIN_HERRAMIENTAS, ClienteClaudeCLI

RAIZ = Path(__file__).resolve().parent.parent
COLGADO = "colgado"  # turno en el que claude no contesta hasta que lo maten


class ProcesoFalso:
    """claude persistente simulado: cada línea escrita en stdin libera la salida del turno siguiente.

    Quedarse sin líneas que entregar es morir (EOF en stdout); cerrar stdin lo termina con código 0.
    """

    def __init__(self, *turnos, codigo=1, ignora_eof=False):
        self.turnos = list(turnos)
        self.pendientes = []
        self.escrito = ""
        self.codigo = codigo  # el código con el que sale si muere solo
        self.ignora_eof = ignora_eof
        self.returncode = None
        self.matado = self.cerrado = self.colgado = False
        self.muerto = threading.Event()
        self.stdin = NS(write=self._escribir, flush=lambda: None, close=self._cerrar)
        self.stdout = self._salida()

    def _escribir(self, texto):
        self.escrito += texto
        for _ in range(texto.count("\n")):
            turno = self.turnos.pop(0) if self.turnos else []
            if turno == COLGADO:
                self.colgado = True
            else:
                self.pendientes += turno

    def _cerrar(self):
        self.cerrado = True
        if not self.ignora_eof and self.returncode is None:
            self.returncode = 0

    def _salida(self):
        while True:
            if self.pendientes:
                yield self.pendientes.pop(0)
            elif self.colgado and not self.muerto.is_set():
                self.muerto.wait(5)  # tope por si el reloj nunca dispara: el test falla en vez de colgarse
            else:
                return

    def lineas(self):
        return [json.loads(linea) for linea in self.escrito.splitlines()]

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is None:
            if not self.matado and timeout is not None:
                raise subprocess.TimeoutExpired("claude", timeout)
            self.returncode = self.codigo
        return self.returncode

    def kill(self):
        self.matado = True
        self.muerto.set()


class PopenFalso:
    """Sustituye a subprocess.Popen: guarda cada llamada y entrega los procesos en orden."""

    def __init__(self, *procesos):
        self.procesos = list(procesos)
        self.llamadas = []

    def __call__(self, comando, **kwargs):
        self.llamadas.append((comando, kwargs))
        return self.procesos[len(self.llamadas) - 1]


def flujo(*deltas, texto=None, session_id="s1", is_error=False):
    """Salida de un turno de claude con stream-json: init, deltas, un thinking, un ajeno y el resultado."""
    eventos = [{"type": "system", "subtype": "init", "session_id": session_id}]
    eventos += [{"type": "stream_event", "event": {"type": "content_block_delta",
                                                    "delta": {"type": "text_delta", "text": d}}} for d in deltas]
    eventos.append({"type": "stream_event", "event": {"type": "content_block_delta",
                                                       "delta": {"type": "thinking_delta", "thinking": "hmm"}}})
    eventos.append({"type": "rate_limit_event"})
    eventos.append({"type": "result", "subtype": "success", "is_error": is_error, "session_id": session_id,
                    "result": "".join(deltas) if texto is None else texto})
    return [json.dumps(e) + "\n" for e in eventos]


def msg(texto):
    return [{"rol": "usuario", "texto": texto}]


def valor(comando, flag):
    return comando[comando.index(flag) + 1]


def mensaje_usuario(texto):
    return {"type": "user", "message": {"role": "user", "content": texto}}


def test_varios_turnos_sobre_el_mismo_proceso():
    proceso = ProcesoFalso(flujo("Ho", "la"), flujo("¿Qué ", "tal?"))
    falso = PopenFalso(proceso)
    cliente = ClienteClaudeCLI("sonnet", "medium", abrir=falso)
    fragmentos = []
    cliente.al_texto = fragmentos.append

    assert cliente.responder(msg("hola"), [], "s") == Respuesta(texto="Hola")
    historial = msg("hola") + [{"rol": "asistente", "texto": "Hola", "llamadas": []},
                               {"rol": "usuario", "texto": "¿y ahora?"}]
    assert cliente.responder(historial, [], "s") == Respuesta(texto="¿Qué tal?")

    assert len(falso.llamadas) == 1  # un solo proceso para toda la conversación
    assert proceso.escrito.count("\n") == 2  # una línea JSON por turno, solo con el último mensaje
    assert proceso.lineas() == [mensaje_usuario("hola"), mensaje_usuario("¿y ahora?")]
    assert fragmentos == ["Ho", "la", "¿Qué ", "tal?"]  # solo text_delta, uno por uno
    assert cliente.session_id == "s1"
    assert not proceso.matado and not proceso.cerrado  # sigue vivo esperando el siguiente mensaje


def test_flags_de_arranque():
    falso = PopenFalso(ProcesoFalso(flujo("x")))
    ClienteClaudeCLI("sonnet", "medium", abrir=falso).responder(msg("hola"), [], "Eres Jarvis")

    comando, kwargs = falso.llamadas[0]
    assert comando[:2] == ["claude", "-p"]
    assert valor(comando, "--input-format") == "stream-json"  # un mensaje por línea en stdin
    assert valor(comando, "--output-format") == "stream-json"
    assert "--verbose" in comando and "--include-partial-messages" in comando
    assert valor(comando, "--model") == "sonnet"
    assert valor(comando, "--effort") == "medium"
    assert valor(comando, "--system-prompt") == "Eres Jarvis\n\n" + SIN_HERRAMIENTAS  # para que no finja usarlas
    assert valor(comando, "--tools") == ""  # sin herramientas
    # arranque corto: sin CLAUDE.md/hooks (safe-mode), skills, MCP ni ajustes del usuario
    assert "--safe-mode" in comando
    assert "--disable-slash-commands" in comando
    assert "--strict-mcp-config" in comando
    assert valor(comando, "--setting-sources") == ""
    assert "--resume" not in comando
    assert "--bare" not in comando  # --bare exige clave de API
    assert "--no-session-persistence" not in comando  # --resume lo necesita
    assert kwargs["stdin"] == kwargs["stdout"] == subprocess.PIPE
    assert kwargs["stderr"] == subprocess.STDOUT  # un solo canal: sin riesgo de bloqueo por stderr lleno
    assert kwargs["text"] is True and kwargs["encoding"] == "utf-8"
    cwd = Path(kwargs["cwd"]).resolve()
    assert RAIZ not in (cwd, *cwd.parents)  # fuera del proyecto: no carga el CLAUDE.md de jarvis-loop


def test_sin_al_texto_no_falla():
    falso = PopenFalso(ProcesoFalso(flujo("Hola")))
    assert ClienteClaudeCLI("sonnet", "medium", abrir=falso).responder(msg("hola"), [], "s").texto == "Hola"


def test_precalentar_lanza_sin_escribir_y_responder_lo_reutiliza():
    proceso = ProcesoFalso(flujo("Hola"))
    falso = PopenFalso(proceso)
    cliente = ClienteClaudeCLI("sonnet", "medium", abrir=falso)

    cliente.precalentar("s")
    assert len(falso.llamadas) == 1 and proceso.escrito == ""

    assert cliente.responder(msg("hola"), [], "s").texto == "Hola"
    assert len(falso.llamadas) == 1


def test_precalentar_sin_claude_instalado_no_falla_y_el_error_sale_al_responder():
    def sin_claude(comando, **kwargs):
        raise FileNotFoundError("claude")

    cliente = ClienteClaudeCLI("sonnet", "medium", abrir=sin_claude)
    cliente.precalentar("s")
    with pytest.raises(FileNotFoundError):
        cliente.responder(msg("hola"), [], "s")


def test_otro_sistema_antes_del_primer_turno_relanza_sin_resume():
    viejo = ProcesoFalso()
    falso = PopenFalso(viejo, ProcesoFalso(flujo("uno")))
    cliente = ClienteClaudeCLI("sonnet", "medium", abrir=falso)

    cliente.precalentar("s1")
    assert cliente.responder(msg("hola"), [], "s2").texto == "uno"

    comando = falso.llamadas[1][0]
    assert "--resume" not in comando
    assert valor(comando, "--system-prompt") == "s2\n\n" + SIN_HERRAMIENTAS
    assert viejo.matado


def test_otro_sistema_tras_un_turno_no_relanza():
    # con --resume claude reutilizaría el sistema del primer turno: relanzar no cambiaría nada
    proceso = ProcesoFalso(flujo("uno", session_id="sesion-42"), flujo("dos", session_id="sesion-42"))
    falso = PopenFalso(proceso)
    cliente = ClienteClaudeCLI("sonnet", "medium", abrir=falso)

    cliente.responder(msg("hola"), [], "s1")
    assert cliente.responder(msg("otra"), [], "s2").texto == "dos"
    assert len(falso.llamadas) == 1 and not proceso.matado


def test_el_reloj_del_turno_se_cancela_al_terminar(monkeypatch):
    monkeypatch.setattr(claude_cli, "TIMEOUT", 0.05)
    proceso = ProcesoFalso(flujo("uno"))
    cliente = ClienteClaudeCLI("sonnet", "medium", abrir=PopenFalso(proceso))

    cliente.responder(msg("hola"), [], "s")
    time.sleep(0.1)
    assert not proceso.matado


def test_stdin_roto_da_el_error_del_cli_y_el_siguiente_turno_relanza():
    roto = ProcesoFalso()
    roto.pendientes = ["Error: no autenticado\n"]  # lo que claude dejó en stdout antes de morir

    def escribir(texto):
        raise BrokenPipeError

    roto.stdin.write = escribir
    falso = PopenFalso(roto, ProcesoFalso(flujo("bien")))
    cliente = ClienteClaudeCLI("sonnet", "medium", abrir=falso)

    with pytest.raises(RuntimeError, match="no autenticado"):
        cliente.responder(msg("hola"), [], "s")
    assert cliente.responder(msg("hola"), [], "s").texto == "bien"
    assert len(falso.llamadas) == 2


def test_proceso_muerto_entre_turnos_se_relanza_con_resume():
    muere = ProcesoFalso(flujo("uno", session_id="sesion-42"))
    nuevo = ProcesoFalso(flujo("dos", session_id="sesion-42"))
    falso = PopenFalso(muere, nuevo)
    cliente = ClienteClaudeCLI("sonnet", "medium", abrir=falso)

    cliente.responder(msg("hola"), [], "s")
    muere.returncode = 1  # murió mientras el usuario escribía
    assert cliente.responder(msg("¿sigues?"), [], "s").texto == "dos"

    assert valor(falso.llamadas[1][0], "--resume") == "sesion-42"
    assert nuevo.lineas() == [mensaje_usuario("¿sigues?")]


def test_proceso_que_muere_a_mitad_de_turno_da_error_y_luego_se_relanza():
    muere = ProcesoFalso(flujo("uno", session_id="sesion-42"), ["Error: se cayó\n"], codigo=3)
    falso = PopenFalso(muere, ProcesoFalso(flujo("tres", session_id="sesion-42")))
    cliente = ClienteClaudeCLI("sonnet", "medium", abrir=falso)
    cliente.responder(msg("hola"), [], "s")

    with pytest.raises(RuntimeError, match=r"código 3.*se cayó"):
        cliente.responder(msg("dos"), [], "s")
    assert muere.matado

    assert cliente.responder(msg("dos"), [], "s").texto == "tres"
    assert valor(falso.llamadas[1][0], "--resume") == "sesion-42"


@pytest.mark.parametrize("salida", [["Error: sesión no encontrada\n"], []])
def test_error_en_el_primer_turno_no_guarda_sesion(salida):
    falso = PopenFalso(ProcesoFalso(salida), ProcesoFalso(flujo("bien", session_id="s2")))
    cliente = ClienteClaudeCLI("sonnet", "medium", abrir=falso)

    with pytest.raises(RuntimeError):
        cliente.responder(msg("hola"), [], "s")

    cliente.responder(msg("hola"), [], "s")
    assert "--resume" not in falso.llamadas[1][0]


def test_el_error_incluye_la_salida_del_cli():
    falso = PopenFalso(ProcesoFalso(["Error: sesión no encontrada\n"]))
    with pytest.raises(RuntimeError, match="sesión no encontrada"):
        ClienteClaudeCLI("sonnet", "medium", abrir=falso).responder(msg("hola"), [], "s")


def test_is_error_lanza_sin_guardar_sesion_y_el_proceso_sigue_vivo():
    proceso = ProcesoFalso(flujo(texto="límite alcanzado", is_error=True, session_id="malo"),
                           flujo("bien", session_id="s2"))
    falso = PopenFalso(proceso)
    cliente = ClienteClaudeCLI("sonnet", "medium", abrir=falso)

    with pytest.raises(RuntimeError, match="límite alcanzado"):
        cliente.responder(msg("hola"), [], "s")
    assert cliente.session_id is None and not proceso.matado

    assert cliente.responder(msg("hola"), [], "s").texto == "bien"
    assert len(falso.llamadas) == 1


def test_una_excepcion_a_mitad_del_stream_mata_el_proceso():
    proceso = ProcesoFalso(flujo("Ho", "la"))
    falso = PopenFalso(proceso, ProcesoFalso(flujo("otra")))
    cliente = ClienteClaudeCLI("sonnet", "medium", abrir=falso)
    cliente.al_texto = lambda _: 1 / 0

    with pytest.raises(ZeroDivisionError):
        cliente.responder(msg("hola"), [], "s")
    assert proceso.matado  # quedaría desincronizado: se descarta

    cliente.al_texto = None
    assert cliente.responder(msg("hola"), [], "s").texto == "otra"
    assert len(falso.llamadas) == 2


def test_el_timeout_mata_el_proceso_y_el_siguiente_turno_relanza(monkeypatch):
    colgado = ProcesoFalso(flujo("uno", session_id="sesion-42"), COLGADO)
    falso = PopenFalso(colgado, ProcesoFalso(flujo("tres", session_id="sesion-42")))
    cliente = ClienteClaudeCLI("sonnet", "medium", abrir=falso)
    cliente.responder(msg("hola"), [], "s")
    monkeypatch.setattr(claude_cli, "TIMEOUT", 0.01)  # después del 1.er turno: el reloj es por turno

    with pytest.raises(RuntimeError, match=r"tiempo agotado \(0.01 s\)"):
        cliente.responder(msg("dos"), [], "s")
    assert colgado.matado

    assert cliente.responder(msg("dos"), [], "s").texto == "tres"
    assert valor(falso.llamadas[1][0], "--resume") == "sesion-42"


def test_cerrar_cierra_stdin_y_el_proceso_termina():
    proceso = ProcesoFalso(flujo("x"))
    cliente = ClienteClaudeCLI("sonnet", "medium", abrir=PopenFalso(proceso))
    cliente.responder(msg("hola"), [], "s")

    cliente.cerrar()
    assert proceso.cerrado and proceso.returncode == 0 and not proceso.matado
    cliente.cerrar()  # dos veces no falla


def test_cerrar_sin_proceso_no_falla():
    ClienteClaudeCLI("sonnet", "medium", abrir=PopenFalso()).cerrar()


def test_cerrar_mata_si_no_termina_solo():
    proceso = ProcesoFalso(ignora_eof=True)
    cliente = ClienteClaudeCLI("sonnet", "medium", abrir=PopenFalso(proceso))
    cliente.precalentar("s")

    cliente.cerrar()
    assert proceso.cerrado and proceso.matado


def test_crear_cliente_claude_cli():
    cliente = crear_cliente(NS(proveedor="claude-cli", modelo="sonnet", esfuerzo="medium", clave=""))
    assert isinstance(cliente, ClienteClaudeCLI)
