"""Bucle de conversación: un turno con herramientas y la conversación en terminal."""
from __future__ import annotations

from jarvis.tools import definiciones

SISTEMA = "Eres Jarvis, un asistente personal. Responde en español y de forma breve. Usa las herramientas cuando ayuden."
MAX_ITERACIONES = 5
AFIRMATIVAS = {"s", "si", "sí"}


def confirmar_por_terminal(nombre: str, argumentos: dict) -> bool:
    # ponytail: confirmación solo por terminal; en la fase de voz habrá que inyectar otra función.
    try:
        respuesta = input(f"¿Ejecutar {nombre} con {argumentos}? [s/N] ")
    except (EOFError, KeyboardInterrupt):
        return False
    return respuesta.strip().lower() in AFIRMATIVAS


def ejecutar_llamada(llamada, herramientas, confirmar) -> str:
    modulo = herramientas.get(llamada.nombre)
    if modulo is None:
        return f"Error: herramienta desconocida '{llamada.nombre}'"
    # Acciones con efectos reales: sin un sí explícito no se ejecuta nada.
    if modulo.requiere_confirmacion and not confirmar(llamada.nombre, llamada.argumentos):
        return "El usuario canceló la acción."
    try:
        return str(modulo.ejecutar(**llamada.argumentos))
    except Exception as e:
        return f"Error: {e}"


def turno(cliente, historial: list[dict], herramientas: dict, texto: str,
          confirmar=confirmar_por_terminal, max_iteraciones: int = MAX_ITERACIONES) -> str:
    historial.append({"rol": "usuario", "texto": texto})
    for _ in range(max_iteraciones):
        respuesta = cliente.responder(historial, definiciones(herramientas), SISTEMA)
        if not respuesta.texto.strip() and not respuesta.llamadas:
            # Un mensaje de asistente vacío (o solo espacios) lo rechaza la API en el siguiente turno.
            # ponytail: si ya corrieron herramientas con efectos reales, avisar en vez de "prueba de nuevo".
            return "(sin respuesta del modelo; prueba de nuevo)"
        historial.append({"rol": "asistente", "texto": respuesta.texto, "llamadas": respuesta.llamadas})
        if not respuesta.llamadas:
            return respuesta.texto
        for llamada in respuesta.llamadas:
            historial.append({
                "rol": "herramienta",
                "id_llamada": llamada.id,
                "resultado": ejecutar_llamada(llamada, herramientas, confirmar),
            })
    return "Me detuve: demasiadas llamadas a herramientas seguidas."


def imprimir_fragmento(texto: str) -> None:
    print(texto, end="", flush=True)


def conversar(cliente, herramientas: dict, entrada=input, salida=print,
              confirmar=confirmar_por_terminal, fragmento=imprimir_fragmento) -> None:
    historial: list[dict] = []  # ponytail: sin límite; recortar cuando crezca
    emitidos: list[str] = []  # fragmentos ya mostrados en el turno actual
    if hasattr(cliente, "al_texto"):  # el cliente puede transmitir la respuesta según la genera

        def al_texto(trozo: str) -> None:
            if not emitidos:
                fragmento("jarvis> ")
            emitidos.append(trozo)
            fragmento(trozo)

        cliente.al_texto = al_texto
    try:
        while True:
            texto = entrada("tú> ").strip()
            if texto == "/salir":
                break
            if not texto:
                continue
            n = len(historial)
            emitidos.clear()
            try:
                respuesta = turno(cliente, historial, herramientas, texto, confirmar)
                if emitidos:
                    fragmento("\n")  # la respuesta ya se mostró; solo se cierra la línea
                else:
                    salida("jarvis> " + respuesta)
            except Exception as e:
                ejecutadas = sum(m["rol"] == "herramienta" for m in historial[n:])
                del historial[n:]  # el turno fallido no queda a medias en el historial
                if emitidos:
                    fragmento("\n")  # el streaming se cortó a medias: cerrar la línea antes del error
                salida(f"Error del proveedor: {type(e).__name__}: {e}")
                if ejecutadas:
                    salida(f"Ojo: en este turno ya se ejecutaron {ejecutadas} herramienta(s).")
    except (EOFError, KeyboardInterrupt):  # también cubre Ctrl+C mientras responde el modelo
        pass
    salida("Hasta luego.")
