"""Proveedor que usa la suscripción de Claude vía `claude -p`, sin clave de API."""
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
TIMEOUT = 120  # ponytail: fijo; hacerlo configurable si alguna respuesta tarda más
# Va tras la personalidad: esta pide usar herramientas y, sin la frase, el modelo podría fingir que las usó.
SIN_HERRAMIENTAS = ("En esta sesión no tienes herramientas: no puedes consultar la hora, el clima, notas, archivos, "
                    "aplicaciones, la web, el calendario, el correo ni Drive. "
                    "Si te piden algo así, dilo en una frase y no finjas haberlo hecho.")


class ClienteClaudeCLI:
    def __init__(self, modelo: str, esfuerzo: str, abrir=subprocess.Popen):
        self.modelo = modelo
        self.esfuerzo = esfuerzo
        self.abrir = abrir
        self.session_id: str | None = None  # el historial lo guarda claude; aquí solo su id
        self.al_texto = None  # función(fragmento) que recibe cada text_delta según llega

    def responder(self, mensajes: list[dict], herramientas: list[dict], sistema: str) -> Respuesta:
        # ponytail: sin herramientas (--tools ""), así que `herramientas` se ignora y nunca hay llamadas;
        # el modelo lo sabe por SIN_HERRAMIENTAS. Dar herramientas a claude-cli es un goal aparte.
        # Con --resume claude ya tiene el historial: solo se manda el último mensaje del usuario.
        texto = next(m["texto"] for m in reversed(mensajes) if m["rol"] == "usuario")
        # Arranque corto: --safe-mode (sin CLAUDE.md ni hooks), --disable-slash-commands (sin skills),
        # --strict-mcp-config (sin MCP) y --setting-sources "" (sin ajustes del usuario).
        # No se usa --bare (exige clave de API) ni --no-session-persistence (--resume lo necesita).
        comando = ["claude", "-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
                   "--model", self.modelo, "--effort", self.esfuerzo,
                   "--system-prompt", sistema + "\n\n" + SIN_HERRAMIENTAS, "--tools", "",
                   "--safe-mode", "--disable-slash-commands", "--strict-mcp-config", "--setting-sources", ""]
        if self.session_id:
            comando += ["--resume", self.session_id]
        CARPETA_NEUTRA.mkdir(exist_ok=True)
        # stderr va al mismo canal que stdout: así no puede llenarse y bloquear la lectura.
        proceso = self.abrir(comando, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", cwd=CARPETA_NEUTRA)
        # Se marca antes de kill: reloj.finished se fija después y el hilo principal podría mirarlo antes.
        agotado = threading.Event()
        reloj = threading.Timer(TIMEOUT, lambda: (agotado.set(), proceso.kill()))
        reloj.start()
        try:
            proceso.stdin.write(texto)
            proceso.stdin.close()
            resultado, ajenas = None, []
            for linea in proceso.stdout:
                try:
                    evento = json.loads(linea)
                except json.JSONDecodeError:
                    ajenas.append(linea)  # lo que claude escriba fuera del flujo, para el mensaje de error
                    continue
                if evento.get("type") == "result":
                    resultado = evento
                elif evento.get("type") == "stream_event":
                    delta = evento["event"].get("delta") or {}
                    if delta.get("type") == "text_delta" and self.al_texto:
                        self.al_texto(delta["text"])
            proceso.wait()
        finally:
            reloj.cancel()
            proceso.kill()  # si algo falló a mitad del stream claude seguiría vivo; si ya terminó no hace nada
            proceso.wait()
        if resultado is None:
            causa = f"tiempo agotado ({TIMEOUT} s)" if agotado.is_set() else f"código {proceso.returncode}"
            raise RuntimeError(f"claude -p salió por {causa} sin resultado: {''.join(ajenas).strip()[:300]}")
        if resultado.get("is_error"):
            raise RuntimeError(f"claude -p falló: {resultado.get('result')}")
        self.session_id = resultado["session_id"]  # solo tras un éxito
        return Respuesta(texto=resultado["result"])
