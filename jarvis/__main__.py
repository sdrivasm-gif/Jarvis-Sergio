"""Punto de entrada: python -m jarvis. Solo conecta las piezas."""
import os
import sys

from dotenv import load_dotenv

from jarvis import voz
from jarvis.bucle import conversar
from jarvis.config import ErrorConfig, cargar_config
from jarvis.llm import crear_cliente
from jarvis.tools import cargar_herramientas


def main(argv: list[str] | None = None) -> int:
    # ponytail: los argumentos desconocidos se ignoran (la fase 6 añade --ui); usar argparse cuando haya más.
    argv = sys.argv[1:] if argv is None else argv
    load_dotenv()
    try:
        config = cargar_config(os.environ)
    except ErrorConfig as e:
        print(e, file=sys.stderr)
        return 1
    if config.proveedor == "claude-cli":
        print("Aviso: el proveedor claude-cli no usa herramientas; para usarlas pon LLM_PROVIDER=claude "
              "u openrouter en .env.", file=sys.stderr)
    piezas = {}  # sin voz, conversar recibe exactamente (cliente, herramientas), como antes
    if voz.activada(argv, os.environ):
        try:
            piezas = voz.preparar(os.environ)
        except voz.ErrorVoz as e:
            print(f"Voz desactivada: {e} Sigo solo con texto.", file=sys.stderr)
    conversar(crear_cliente(config), cargar_herramientas(), **piezas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
