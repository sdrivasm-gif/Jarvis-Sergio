"""Punto de entrada: python -m jarvis. Solo conecta las piezas."""
import os
import sys

from dotenv import load_dotenv

from jarvis.bucle import conversar
from jarvis.config import ErrorConfig, cargar_config
from jarvis.llm import crear_cliente
from jarvis.tools import cargar_herramientas


def main() -> int:
    load_dotenv()
    try:
        config = cargar_config(os.environ)
    except ErrorConfig as e:
        print(e, file=sys.stderr)
        return 1
    if config.proveedor == "claude-cli":
        print("Aviso: el proveedor claude-cli no usa herramientas; para usarlas pon LLM_PROVIDER=claude "
              "u openrouter en .env.", file=sys.stderr)
    conversar(crear_cliente(config), cargar_herramientas())
    return 0


if __name__ == "__main__":
    sys.exit(main())
