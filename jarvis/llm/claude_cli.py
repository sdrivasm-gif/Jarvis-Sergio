"""Proveedor que usa la suscripción de Claude vía `claude -p`, sin clave de API.

Un solo proceso de claude vive toda la conversación: cada mensaje es una línea JSON en su stdin
(--input-format stream-json) y el turno termina con el evento `result`.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import threading
from pathlib import Path

from jarvis.llm import Respuesta

# Fuera del proyecto, para que claude no cargue el CLAUDE.md ni los subagentes de jarvis-loop.
# Fija porque --resume busca la sesión por carpeta.
CARPETA_NEUTRA = Path(tempfile.gettempdir()) / "jarvis-claude-cli"
TIMEOUT = 120  # por turno; ponytail: fijo, hacerlo configurable si alguna respuesta tarda más
ESPERA_CIERRE = 3  # s que se deja a claude para salir solo tras cerrar su stdin
# Va tras la personalidad: esta pide usar herramientas y, sin la frase, el modelo podría fingir que las usó.
SIN_HERRAMIENTAS = ("En esta sesión no tienes herramientas: no puedes consultar la hora, el clima, notas, archivos, "
                    "aplicaciones, la web, el calendario, el correo ni Drive, ni guardar recuerdos ni crear "
                    "recordatorios. Si te piden algo así, dilo en una frase y no finjas haberlo hecho.")


class ClienteClaudeCLI:
    def __init__(self, modelo: str, esfuerzo: str, abrir=subprocess.Popen):
        self.modelo = modelo
        self.esfuerzo = esfuerzo
        self.abrir = abrir
        self.session_id: str | None = None  # el historial lo guarda claude; aquí solo su id
        self.al_texto = None  # función(fragmento) que recibe cada text_delta según llega
        self.proceso = None
        self.sistema: str | None = None  # con el que se lanzó el proceso vivo

    def _lanzar(self, sistema: str) -> None:
        # Arranque corto: --safe-mode (sin CLAUDE.md ni hooks), --disable-slash-commands (sin skills),
        # --strict-mcp-config (sin MCP) y --setting-sources "" (sin ajustes del usuario).
        # No se usa --bare (exige clave de API) ni --no-session-persistence (--resume lo necesita).
        comando = ["claude", "-p", "--input-format", "stream-json",
                   "--output-format", "stream-json", "--verbose", "--include-partial-messages",
                   "--model", self.modelo, "--effort", self.esfuerzo,
                   "--system-prompt", sistema + "\n\n" + SIN_HERRAMIENTAS, "--tools", "",
                   "--safe-mode", "--disable-slash-commands", "--strict-mcp-config", "--setting-sources", ""]
        if self.session_id:  # proceso relanzado: retoma la conversación
            comando += ["--resume", self.session_id]
        CARPETA_NEUTRA.mkdir(exist_ok=True)
        # stderr va al mismo canal que stdout: así no puede llenarse y bloquear la lectura.
        self.proceso = self.abrir(comando, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, encoding="utf-8", cwd=CARPETA_NEUTRA)
        self.sistema = sistema

    def _descartar(self) -> None:
        proceso, self.proceso = self.proceso, None
        proceso.kill()  # si ya terminó no hace nada
        proceso.wait()

    def precalentar(self, sistema: str) -> None:
        """Lanza claude antes del primer mensaje, para no esperar su arranque al responder."""
        try:
            self._lanzar(sistema)
        except OSError:
            pass  # p. ej. claude no instalado: el error sale en el primer responder, como antes

    def cerrar(self) -> None:
        """Cierra el proceso: claude sale solo al ver su stdin cerrado; si no, se mata."""
        proceso, self.proceso = self.proceso, None
        if proceso is None:
            return
        try:
            proceso.stdin.close()
            proceso.wait(timeout=ESPERA_CIERRE)
        except (OSError, subprocess.TimeoutExpired):
            proceso.kill()
            proceso.wait()

    def responder(self, mensajes: list[dict], herramientas: list[dict], sistema: str) -> Respuesta:
        # ponytail: sin herramientas (--tools ""), así que `herramientas` se ignora y nunca hay llamadas;
        # el modelo lo sabe por SIN_HERRAMIENTAS. Dar herramientas a claude-cli es un goal aparte.
        # claude ya tiene el historial: solo se manda el último mensaje del usuario.
        texto = next(m["texto"] for m in reversed(mensajes) if m["rol"] == "usuario")
        # ponytail: con --system-prompt-snapshot on (lo predeterminado) claude reutiliza en --resume el sistema del
        # primer turno, así que solo se relanza por un sistema nuevo si aún no hubo turno; pasar
        # --system-prompt-snapshot off si hace falta que cambie a mitad de conversación (rompe la caché).
        otro_sistema = sistema != self.sistema and self.session_id is None
        if self.proceso is not None and (self.proceso.poll() is not None or otro_sistema):
            self._descartar()  # murió entre turnos o cambió el sistema antes del 1.er turno: se relanza
        if self.proceso is None:
            self._lanzar(sistema)
        proceso = self.proceso
        # Se marca antes de kill: reloj.finished se fija después y el hilo principal podría mirarlo antes.
        # Matar desbloquea la lectura de stdout con EOF.
        agotado = threading.Event()
        reloj = threading.Timer(TIMEOUT, lambda: (agotado.set(), proceso.kill()))
        resultado, ajenas = None, []
        try:
            reloj.start()
            try:
                proceso.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": texto}}) + "\n")
                proceso.stdin.flush()
            except OSError:
                pass  # murió justo ahora: stdout llega a EOF y el error sale abajo con su código
            for linea in proceso.stdout:
                try:
                    evento = json.loads(linea)
                except json.JSONDecodeError:
                    ajenas.append(linea)  # lo que claude escriba fuera del flujo, para el mensaje de error
                    continue
                if evento.get("type") == "result":
                    resultado = evento
                    break  # fin del turno; el proceso sigue vivo esperando la siguiente línea
                if evento.get("type") == "stream_event":
                    delta = evento["event"].get("delta") or {}
                    if delta.get("type") == "text_delta" and self.al_texto:
                        self.al_texto(delta["text"])
        except BaseException:
            self._descartar()  # cortado a mitad de turno quedaría desincronizado (también con Ctrl+C)
            raise
        finally:
            reloj.cancel()
        if resultado is None:
            self._descartar()  # el siguiente responder lo relanza con --resume
            causa = f"tiempo agotado ({TIMEOUT} s)" if agotado.is_set() else f"código {proceso.returncode}"
            raise RuntimeError(f"claude -p salió por {causa} sin resultado: {''.join(ajenas).strip()[:300]}")
        if resultado.get("is_error"):
            # El proceso sigue vivo y sincronizado: el siguiente mensaje lo reutiliza.
            raise RuntimeError(f"claude -p falló: {resultado.get('result')}")
        self.session_id = resultado["session_id"]  # solo tras un éxito
        return Respuesta(texto=resultado["result"])
