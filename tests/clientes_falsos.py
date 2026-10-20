"""Clientes simulados (calendario, correo, Drive, voz y modelo): anotan cada acción y nunca salen a la red."""
import copy

from jarvis import bucle
from jarvis.llm import LlamadaHerramienta, Respuesta


class CalendarioFalso:
    def __init__(self, eventos: dict | None = None):
        self.eventos = eventos or {}  # {date: [evento]}
        self.consultas, self.acciones, self.creaciones = [], [], 0

    def eventos_del_dia(self, dia):
        self.consultas.append(dia)
        return list(self.eventos.get(dia, []))

    def crear_evento(self, titulo, inicio, fin):
        self.acciones.append(("crear", titulo, inicio, fin))
        return {"id": "ev-nuevo"}

    def borrar_evento(self, id_evento):
        self.acciones.append(("borrar", id_evento))


class CorreoFalso:
    def __init__(self, mensajes=()):
        self.mensajes = list(mensajes)
        self.consultas, self.acciones, self.creaciones = [], [], 0

    def buscar(self, consulta, maximo):
        self.consultas.append((consulta, maximo))
        return self.mensajes[:maximo]

    def enviar(self, para, asunto, cuerpo):
        self.acciones.append(("enviar", para, asunto, cuerpo))
        return "msg-nuevo"


class DriveFalso:
    def __init__(self, archivos=()):
        self.archivos = list(archivos)
        self.consultas, self.acciones, self.creaciones = [], [], 0

    def buscar(self, nombre, maximo):
        self.consultas.append((nombre, maximo))
        return self.archivos[:maximo]

    def compartir(self, id_archivo, correo, rol):
        self.acciones.append(("compartir", id_archivo, correo, rol))


def instalar(monkeypatch, modulo, falso):
    """modulo.obtener_cliente() devuelve `falso` y suma 1 a falso.creaciones cada vez. Devuelve falso."""
    def obtener_cliente():
        falso.creaciones += 1
        return falso

    monkeypatch.setattr(modulo, "obtener_cliente", obtener_cliente)
    return falso


class PedirFalso:
    """Sustituye google.pedir: guarda (metodo, url, params, cuerpo) y devuelve las respuestas en orden."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def __call__(self, metodo, url, params=None, cuerpo=None):
        self.llamadas.append((metodo, url, params, cuerpo))
        return self.respuestas.pop(0)


def sin_credenciales(monkeypatch, google):
    for v in google.VARIABLES:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(google, "_token", {})


def llamar(nombre, modulo, argumentos, confirmar):
    """Ejecuta la herramienta real por el bucle, como lo haría el modelo."""
    return bucle.ejecutar_llamada(LlamadaHerramienta("l1", nombre, argumentos), {nombre: modulo}, confirmar)


def no_debe_preguntar(nombre, argumentos):
    raise AssertionError("no debía pedir confirmación")


def entradas(*textos):
    """Simula input(): devuelve cada texto y luego lanza EOFError."""
    pendientes = list(textos)

    def entrada(prompt=""):
        if not pendientes:
            raise EOFError
        valor = pendientes.pop(0)
        if isinstance(valor, BaseException):
            raise valor
        return valor

    return entrada


class OyenteFalso:
    """Oyente simulado: devuelve cada texto (None = silencio); si es una excepción, la lanza; agotado → EOFError."""

    def __init__(self, *textos):
        self.pendientes = list(textos)
        self.escuchas = 0

    def escuchar(self):
        self.escuchas += 1
        if not self.pendientes:
            raise EOFError
        valor = self.pendientes.pop(0)
        if isinstance(valor, BaseException):
            raise valor
        return valor


class HablanteFalso:
    """Hablante simulado: anota lo que diría (nunca suena); con `falla` (en decir) o `falla_esperar`, la lanza.
    Con `registro` (lista compartida, p. ej. con un oyente) anota el orden: ("encolar", f), ("esperar",), ("decir", t)."""

    def __init__(self, falla: BaseException | None = None, falla_esperar: BaseException | None = None,
                 registro: list | None = None):
        self.falla, self.falla_esperar = falla, falla_esperar
        self.registro = registro if registro is not None else []
        self.dichos, self.encolados = [], []
        self.esperas = self.cortes = 0

    def decir(self, texto):
        self.registro.append(("decir", texto))
        if self.falla:
            raise self.falla
        self.dichos.append(texto)

    def encolar(self, frase):
        self.registro.append(("encolar", frase))
        self.encolados.append(frase)

    def esperar(self):
        self.registro.append(("esperar",))
        self.esperas += 1
        if self.falla_esperar:
            raise self.falla_esperar

    def cortar(self):
        self.cortes += 1


class ClienteStreamingFalso:
    """Cliente que transmite: por cada fragmento i llama a al_emitir(i) y luego a al_texto; devuelve el texto entero."""

    def __init__(self, fragmentos, al_emitir=lambda i: None):
        self.fragmentos, self.al_emitir = list(fragmentos), al_emitir
        self.al_texto = None
        self.recibidos = []

    def responder(self, mensajes, herramientas, sistema):
        self.recibidos.append(copy.deepcopy({"mensajes": mensajes, "herramientas": herramientas, "sistema": sistema}))
        for i, f in enumerate(self.fragmentos):
            self.al_emitir(i)
            if self.al_texto:
                self.al_texto(f)
        return Respuesta(texto="".join(self.fragmentos))
