"""Punto de entrada: python -m jarvis. Solo conecta las piezas."""
import os
import sys

from dotenv import load_dotenv

from jarvis import voz
from jarvis.bucle import conversar, sistema_completo
from jarvis.config import ErrorConfig, cargar_config
from jarvis.llm import crear_cliente
from jarvis.tools import cargar_herramientas
from jarvis.ui import servidor as ui


def main(argv: list[str] | None = None) -> int:
    # ponytail: solo se reconocen --ui y --voz; el resto se ignora. Usar argparse cuando haya más.
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
    cliente = crear_cliente(config)
    if hasattr(cliente, "precalentar"):  # claude-cli: su proceso arranca mientras se prepara lo demás
        cliente.precalentar(sistema_completo())  # el mismo sistema que usa cada turno
    try:
        if "--ui" in argv:  # la página local; con --voz también escucha y habla
            return ui.lanzar(cliente, cargar_herramientas(), os.environ, con_voz=voz.activada(argv, os.environ))
        piezas = {}  # sin voz, conversar recibe exactamente (cliente, herramientas), como antes
        if voz.activada(argv, os.environ):
            try:
                piezas = voz.preparar(os.environ)
            except voz.ErrorVoz as e:
                print(f"Voz desactivada: {e} Sigo solo con texto.", file=sys.stderr)
        conversar(cliente, cargar_herramientas(), **piezas)
        return 0
    finally:  # también con Ctrl+C o un error: no deja claude vivo
        if hasattr(cliente, "cerrar"):
            cliente.cerrar()


if __name__ == "__main__":
    sys.exit(main())
