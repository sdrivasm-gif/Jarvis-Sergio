"""Bucle de conversación: un turno con herramientas y la conversación en terminal."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jarvis import hoy, memoria, recordatorios
from jarvis.tools import definiciones

# Respaldo si no se puede leer personalidad.md.
SISTEMA = "Eres Jarvis, un asistente personal. Responde en español y de forma breve. Usa las herramientas cuando ayuden."
MAX_ITERACIONES = 5
AFIRMATIVAS = {"s", "si", "sí"}
ARCHIVO_PERSONALIDAD = Path(__file__).parent / "personalidad.md"


def cargar_sistema() -> str:
    # ponytail: se lee en cada turno (barato, y se edita sin reiniciar); si se empaqueta sin modo editable,
    # declarar personalidad.md como package-data.
    try:
        return ARCHIVO_PERSONALIDAD.read_text(encoding="utf-8")  # tal cual, sin strip
    except OSError:
        return SISTEMA


def sistema_completo() -> str:
    # Sin recuerdos, memoria.para_sistema() es "" y el sistema queda igual que personalidad.md.
    return cargar_sistema() + memoria.para_sistema()


def avisar_vencidos(salida, ahora: datetime) -> None:
    # ponytail: el aviso llega la próxima vez que aparece "tú>", no mientras se espera en input(); las fases 5 y 6
    # llaman a recordatorios.vencidos desde su bucle de escucha o desde el servidor.
    try:
        for r in recordatorios.vencidos(ahora):
            salida("jarvis> " + recordatorios.aviso(r))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:  # un registro editado a mano o roto
        # ponytail: un registro roto bloquea los avisos de todos; saltarlo dentro de recordatorios.vencidos.
        salida(f"Error en los recordatorios: {e}")


def legible(valor) -> str:
    # Los caracteres de control (\x1b, \r) o bidi (U+202E) se muestran escapados: si no, podrían
    # reescribir en la terminal lo que el usuario cree estar confirmando.
    return "".join(c if c.isprintable() or c == "\n" else repr(c)[1:-1] for c in str(valor))


def texto_confirmacion(nombre: str, argumentos: dict) -> str:
    # Un argumento por línea y los multilínea sangrados, para leer entero, p. ej., el cuerpo de un correo.
    # Los multilínea van al final (orden estable) para que un cuerpo largo no separe "para" del [s/N].
    lineas = "".join("  {}: {}\n".format(legible(k), legible(v).replace("\n", "\n    "))
                     for k, v in sorted(argumentos.items(), key=lambda kv: "\n" in str(kv[1])))
    return f"¿Ejecutar {legible(nombre)}?\n{lineas}[s/N] "


def confirmar_por_terminal(nombre: str, argumentos: dict) -> bool:
    # ponytail: confirmación solo por terminal; en la fase de voz habrá que inyectar otra función.
    try:
        respuesta = input(texto_confirmacion(nombre, argumentos))
    except (EOFError, KeyboardInterrupt):
        return False
    return respuesta.strip().lower() in AFIRMATIVAS


def ejecutar_llamada(llamada, herramientas, confirmar) -> str:
    modulo = herramientas.get(llamada.nombre)
    if modulo is None:
        return f"Error: herramienta desconocida '{llamada.nombre}'"
    # Nadie confirma un correo sin destinatario: los obligatorios se exigen antes de preguntar.
    # ponytail: los formatos (fecha, correo, id) se validan después de confirmar, dentro de cada herramienta.
    faltan = [k for k in modulo.ESQUEMA.get("required", []) if not str(llamada.argumentos.get(k, "")).strip()]
    if faltan:
        return f"Error: faltan argumentos para {llamada.nombre}: {', '.join(faltan)}."
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
    sistema = sistema_completo()
    for _ in range(max_iteraciones):
        respuesta = cliente.responder(historial, definiciones(herramientas), sistema)
        if not respuesta.texto.strip() and not respuesta.llamadas:
            # Un mensaje de asistente vacío (o solo espacios) lo rechaza la API en el siguiente turno.
            # ponytail: si ya corrieron herramientas con efectos reales, avisar en vez de "prueba de nuevo".
            return hoy.SIN_RESPUESTA
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
              confirmar=confirmar_por_terminal, fragmento=imprimir_fragmento, reloj=datetime.now) -> None:
    historial: list[dict] = []  # ponytail: sin límite; recortar cuando crezca
    emitidos: list[str] = []  # fragmentos ya mostrados en el turno actual
    # sin fragmento (voz) no hay streaming: la respuesta llega entera a salida
    if fragmento is not None and hasattr(cliente, "al_texto"):  # el cliente puede transmitir la respuesta según la genera

        def al_texto(trozo: str) -> None:
            if not emitidos:
                fragmento("jarvis> ")
            emitidos.append(trozo)
            fragmento(trozo)

        cliente.al_texto = al_texto
    try:
        while True:
            avisar_vencidos(salida, reloj())  # también al arrancar: avisa de lo que venció con Jarvis cerrado
            texto = entrada("tú> ").strip()
            if texto == "/salir":
                break
            if not texto:
                continue
            n = len(historial)
            emitidos.clear()
            try:
                if texto == hoy.COMANDO:  # sin herramientas y fuera del historial
                    respuesta = hoy.parte_del_dia(cliente, sistema_completo(), reloj())
                else:
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
