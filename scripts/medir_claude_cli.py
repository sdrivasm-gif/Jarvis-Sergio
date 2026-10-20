"""Mide en segundos llamadas reales a claude: antes (json, solo --safe-mode), después (un proceso por mensaje)
y persistente (un solo ClienteClaudeCLI precalentado: el 1.er mensaje y los siguientes sobre el mismo proceso).

Uso: .venv/Scripts/python scripts/medir_claude_cli.py
Hace 3 x REPETICIONES + 1 llamadas reales con tu suscripción (REPETICIONES antes, REPETICIONES después,
y en persistente el 1.º más REPETICIONES siguientes); no es un test.
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


def medir_mensaje(cliente: ClienteClaudeCLI) -> tuple[float, float]:
    primero = []
    t0 = time.perf_counter()
    cliente.al_texto = lambda _: primero or primero.append(time.perf_counter() - t0)
    cliente.responder([{"rol": "usuario", "texto": PROMPT}], [], SISTEMA)
    return primero[0], time.perf_counter() - t0


def medir_despues() -> tuple[float, float]:
    cliente = ClienteClaudeCLI("sonnet", "medium")  # cliente nuevo y sin precalentar: lanza claude al responder
    try:
        return medir_mensaje(cliente)
    finally:
        cliente.cerrar()


def imprimir(nombre: str, medidas: list[tuple[float, float]]) -> None:
    for i, (primero, total) in enumerate(medidas, 1):
        print(f"{nombre} #{i}: primer texto {primero:5.2f} s | total {total:5.2f} s")
    print(f"{nombre} (media): primer texto {statistics.mean(m[0] for m in medidas):5.2f} s"
          f" | total {statistics.mean(m[1] for m in medidas):5.2f} s")


def medir_persistente(cliente: ClienteClaudeCLI, espera: float = 3) -> None:
    try:
        cliente.precalentar(SISTEMA)  # como al arrancar Jarvis
        # ponytail: espera fija que simula al usuario tecleando mientras claude arranca; si el 1.º sale lento,
        # subirla o esperar a su evento system/init.
        time.sleep(espera)
        primero, total = medir_mensaje(cliente)
        print(f"persistente 1.º: primer texto {primero:5.2f} s | total {total:5.2f} s")
        imprimir("persistente siguientes", [medir_mensaje(cliente) for _ in range(REPETICIONES)])
    finally:
        cliente.cerrar()


if __name__ == "__main__":
    for nombre, medir in (("antes  ", medir_antes), ("después", medir_despues)):
        imprimir(nombre, [medir() for _ in range(REPETICIONES)])
    medir_persistente(ClienteClaudeCLI("sonnet", "medium"))
