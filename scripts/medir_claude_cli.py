"""Mide en segundos una llamada real a claude: antes (json, solo --safe-mode) y después (ClienteClaudeCLI).

Uso: .venv/Scripts/python scripts/medir_claude_cli.py
Hace 2 x REPETICIONES llamadas reales con tu suscripción; no es un test.
"""
import statistics
import subprocess
import time

from jarvis.bucle import SISTEMA
from jarvis.llm.claude_cli import CARPETA_NEUTRA, ClienteClaudeCLI

REPETICIONES = 3
PROMPT = "Responde solo con la palabra: hola"
# Copia del comando que usaba el proveedor antes del cambio (sin streaming y con menos aislamiento).
ANTES = ["claude", "-p", "--output-format", "json", "--model", "sonnet", "--effort", "medium",
         "--system-prompt", SISTEMA, "--tools", "", "--safe-mode"]


def medir_antes() -> tuple[float, float]:
    CARPETA_NEUTRA.mkdir(exist_ok=True)
    t0 = time.perf_counter()
    subprocess.run(ANTES, input=PROMPT, cwd=CARPETA_NEUTRA, capture_output=True, text=True,
                   encoding="utf-8", check=True)
    total = time.perf_counter() - t0
    return total, total  # sin streaming: el primer texto llega con la respuesta completa


def medir_despues() -> tuple[float, float]:
    cliente = ClienteClaudeCLI("sonnet", "medium")  # cliente nuevo: sin --resume, igual que ANTES
    primero = []
    t0 = time.perf_counter()
    cliente.al_texto = lambda _: primero or primero.append(time.perf_counter() - t0)
    cliente.responder([{"rol": "usuario", "texto": PROMPT}], [], SISTEMA)
    return primero[0], time.perf_counter() - t0


if __name__ == "__main__":
    for nombre, medir in (("antes  ", medir_antes), ("después", medir_despues)):
        medidas = [medir() for _ in range(REPETICIONES)]
        for i, (primero, total) in enumerate(medidas, 1):
            print(f"{nombre} #{i}: primer texto {primero:5.2f} s | total {total:5.2f} s")
        print(f"{nombre} media: primer texto {statistics.mean(m[0] for m in medidas):5.2f} s"
              f" | total {statistics.mean(m[1] for m in medidas):5.2f} s")
