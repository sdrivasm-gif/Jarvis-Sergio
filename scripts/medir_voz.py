"""Mide la voz: segundos hasta el primer audio y total. Uso: python scripts/medir_voz.py [--motor edge|sapi|elevenlabs] [--frase TEXTO]"""
import argparse
import os
import sys
import time

from dotenv import load_dotenv

from jarvis import habla, voz

FRASE_EJEMPLO = ("Buenos días, señor. Hoy tiene tres reuniones y una tarea pendiente. "
                 "El clima es soleado, con veinticuatro grados. ¿Quiere que le lea el primer correo?")


def medir(hablante, frase: str, reloj=time.perf_counter) -> tuple[float | None, float]:
    """(segundos hasta que empieza a sonar el primer audio o None si el motor no lo informa, segundos totales)."""
    marcas = []
    anterior = hablante.al_empezar
    hablante.al_empezar = lambda: marcas.append(reloj())  # la cola lo llama justo después de "play"
    inicio = reloj()
    try:
        hablante.decir(frase)
    finally:
        hablante.al_empezar = anterior
    return (marcas[0] - inicio if marcas else None), reloj() - inicio


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Mide cuánto tarda Jarvis en empezar a hablar y en terminar.")
    p.add_argument("--motor", choices=habla.MOTORES, help="por defecto, el de JARVIS_VOZ_MOTOR (o edge)")
    p.add_argument("--frase", default=FRASE_EJEMPLO, help="texto que se dice")
    args = p.parse_args(argv)
    load_dotenv()
    entorno = dict(os.environ)
    if args.motor:
        entorno["JARVIS_VOZ_MOTOR"] = args.motor
    try:
        hablante = habla.crear_hablante(entorno, print)
    except voz.ErrorVoz as e:
        print(f"No se pudo preparar la voz: {e}", file=sys.stderr)  # los mensajes nunca llevan una clave
        return 1
    primero, total = medir(hablante, args.frase)
    print(f"motor: {hablante.nombre}")
    print(f"primer audio: {primero:.2f} s" if primero is not None
          else "primer audio: n/d (la voz de Windows no lo informa)")
    print(f"total: {total:.2f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
