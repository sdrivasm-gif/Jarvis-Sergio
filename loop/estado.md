# Estado del bucle

Fase actual: 1 — cerrada (pendiente de tu revisión y commit)
Último goal cerrado: goals/01-nucleo.md

## Hecho
- Diseño de la fase 1: docs/decisiones/001-nucleo-fase-1.md (pesado).
- Código: jarvis/ (bucle, config, tools/hora.py, llm/ con ClienteClaude, ClienteOpenRouter y ClienteFalso), pyproject.toml, .venv, jarvis/README.md.
- Verificador (última pasada): `pytest -q` → 46 passed, exit 0, también sin claves; sin claves en jarvis/ ni tests/.
- Revisor: 1.ª vuelta CAMBIOS REQUERIDOS (respuesta vacía del modelo, aviso de herramientas ya ejecutadas), corregido; 2.ª vuelta APROBADO. Después se aplicó su recomendación del .strip() (con test).

- Extra (2026-10-20): proveedor `claude-cli` (jarvis/llm/claude_cli.py), ahora el proveedor por defecto. `pytest -q` → 56 passed, exit 0. Sin pasada del `revisor` todavía. Sin herramientas con este proveedor (ponytail: `--tools ""`).

- Extra (2026-10-20): `claude-cli` con streaming y arranque corto. `pytest -q` → 61 passed, exit 0. Pendiente: que el usuario corra `scripts/medir_claude_cli.py` y pase `revisor`.

## Pendiente inmediato
- Tú: revisar el diff (`git diff` y `git status`), probar `python -m jarvis` con clave real en `.env` y hacer el commit.
- Siguiente: goals/02-herramientas.md (reescribirlo con el equipo actual antes de lanzarlo; ver goals/00-reglas-comunes.md).

## Bloqueos / dudas para el usuario
- El ID por defecto de OpenRouter (`anthropic/claude-sonnet-5-5`, en jarvis/llm/openrouter.py) NO está verificado contra la API. Confírmalo con tu clave o fija JARVIS_MODEL.
- Ninguna prueba ha llamado a una API real: `python -m jarvis` con clave real queda como prueba manual tuya.
- Deuda anotada con `ponytail:` para la fase 2 (herramientas con efectos reales): avisar al usuario si el modelo responde vacío tras ejecutar herramientas; los bloques thinking se descartan; el historial crece sin límite; la confirmación solo funciona por terminal (rehacer en la fase de voz).

---

# Especificación fase 1 (para constructor, conector-llm y ligero)

Convención: **todo nombre propio en español** (módulos, funciones, clases, claves de diccionarios). Python 3.11+ (el equipo usa 3.12). Ningún test lee `.env` ni llama a la red. Nadie lee ni toca `.env` ni `.env.example`.

## Estructura de archivos

```
pyproject.toml
jarvis/
  __init__.py            (vacío)
  __main__.py            main(): conecta las piezas
  config.py              Config, ErrorConfig, cargar_config
  bucle.py               SISTEMA, turno, ejecutar_llamada, confirmar_por_terminal, conversar
  README.md              instalar y ejecutar (ligero)
  llm/
    __init__.py          Respuesta, LlamadaHerramienta, Cliente (Protocol), crear_cliente
    claude.py            ClienteClaude + a_formato_anthropic + desde_anthropic
    openrouter.py        ClienteOpenRouter + a_formato_openai + desde_openai
    falso.py             ClienteFalso
  tools/
    __init__.py          CARPETA_TOOLS, cargar_herramientas, definiciones
    hora.py              herramienta de ejemplo y plantilla
tests/
  test_config.py
  test_tools.py
  test_llm.py
  test_bucle.py
```

## pyproject.toml
- `[build-system]` setuptools. `[project]`: name `jarvis`, `requires-python = ">=3.11"`, dependencias `anthropic`, `openai`, `python-dotenv` (sin fijar versiones; `ponytail:` fijarlas cuando haga falta). `[project.optional-dependencies] dev = ["pytest"]`.
- `[tool.setuptools] packages = ["jarvis", "jarvis.llm", "jarvis.tools"]` (explícito, para que no detecte `docs/`, `loop/` ni `goals/`).
- `[tool.pytest.ini_options] testpaths = ["tests"]`, `pythonpath = ["."]`.
- Instalación: `python -m venv .venv` y luego `.venv\Scripts\python -m pip install -e ".[dev]"`.
- Comprobar que `.gitignore` incluye `.venv/` y `.env`, sin abrir `.env`.

## Contratos

### Formato neutro de mensajes (historial)
```python
{"rol": "usuario",     "texto": str}
{"rol": "asistente",   "texto": str, "llamadas": list[LlamadaHerramienta]}
{"rol": "herramienta", "id_llamada": str, "resultado": str}
```
Definición neutra de herramienta: `{"nombre": str, "descripcion": str, "esquema": dict}`.

### jarvis/llm/__init__.py (conector-llm)
```python
@dataclass
class LlamadaHerramienta:
    id: str
    nombre: str
    argumentos: dict

@dataclass
class Respuesta:
    texto: str = ""
    llamadas: list[LlamadaHerramienta] = field(default_factory=list)

class Cliente(Protocol):
    def responder(self, mensajes: list[dict], herramientas: list[dict], sistema: str) -> Respuesta: ...

def crear_cliente(config: Config) -> Cliente  # "claude" -> ClienteClaude, "openrouter" -> ClienteOpenRouter
```

### jarvis/llm/claude.py (conector-llm)
- `ClienteClaude(clave: str, modelo: str, sdk=None)`: si `sdk` es None, crea `anthropic.Anthropic(api_key=clave)`.
- `responder` llama a `sdk.messages.create(model=modelo, max_tokens=MAX_TOKENS, system=sistema, messages=a_formato_anthropic(mensajes), tools=[...])`. Las herramientas se traducen a `{"name", "description", "input_schema"}` y `tools` se omite si la lista está vacía. Usar `MAX_TOKENS = 1024  # ponytail: fijo`.
- `a_formato_anthropic(mensajes) -> list[dict]`:
  - usuario → bloque `{"type":"text","text":...}` con rol `user`.
  - asistente → rol `assistant`, con un bloque `text` si el texto no está vacío y un `{"type":"tool_use","id","name","input"}` por llamada.
  - herramienta → `{"type":"tool_result","tool_use_id","content"}` con rol `user`.
  - **Mensajes `user` consecutivos se fusionan en uno** (varios tool_result seguidos, o tool_result seguido de un texto del usuario).
- `desde_anthropic(resp) -> Respuesta`: concatena los bloques `text` y convierte cada `tool_use` en `LlamadaHerramienta`.

### jarvis/llm/openrouter.py (conector-llm)
- `ClienteOpenRouter(clave: str, modelo: str, sdk=None)`: si `sdk` es None, crea `openai.OpenAI(api_key=clave, base_url="https://openrouter.ai/api/v1")`.
- `responder` llama a `sdk.chat.completions.create(model, max_tokens, messages=a_formato_openai(mensajes, sistema), tools=[{"type":"function","function":{"name","description","parameters"}}])` y omite `tools` si la lista está vacía.
- `a_formato_openai(mensajes, sistema)`:
  - Primero `{"role":"system"}`. usuario → `user`.
  - asistente → `{"role":"assistant","content": texto o None, "tool_calls":[{"id","type":"function","function":{"name","arguments": json.dumps(args)}}]}` (sin `tool_calls` si no hay llamadas).
  - herramienta → `{"role":"tool","tool_call_id","content"}`.
- `desde_openai(resp)`: toma `choices[0].message`, con `content or ""`, y `tool_calls` con `json.loads(arguments)`. Si el JSON no es válido, usa `{}` y lo marca con `ponytail:`.

### jarvis/llm/falso.py (conector-llm)
- `ClienteFalso(respuestas: list[Respuesta])`: `responder` devuelve las respuestas en orden y guarda en `self.recibidos` una copia de los argumentos de cada llamada (`mensajes`, `herramientas`, `sistema`). Si se agotan, lanza `RuntimeError("ClienteFalso sin respuestas")`.

### jarvis/config.py (constructor)
```python
class ErrorConfig(Exception): ...

@dataclass
class Config:
    proveedor: str   # "claude" | "openrouter"
    modelo: str
    clave: str       # nunca se imprime ni se registra en logs

def cargar_config(entorno: Mapping[str, str]) -> Config
```
- `JARVIS_PROVIDER` vale `claude` por defecto. Cualquier valor distinto de `claude` u `openrouter` lanza `ErrorConfig`.
- La clave sale de `ANTHROPIC_API_KEY` o de `OPENROUTER_API_KEY`, según el proveedor. Si falta o está vacía, lanza `ErrorConfig` con un mensaje que nombra la variable y dice que va en `.env`. El valor de la clave nunca aparece en el mensaje.
- `JARVIS_MODEL` tiene estos valores por defecto: `claude-sonnet-5-5` para claude y la constante que fije conector-llm para openrouter.

### jarvis/tools/__init__.py (constructor)
```python
CARPETA_TOOLS: Path  # Path(__file__).parent
def cargar_herramientas(carpeta: Path = CARPETA_TOOLS) -> dict[str, ModuleType]
def definiciones(herramientas: dict[str, ModuleType]) -> list[dict]  # formato neutro
```
- Recorre `carpeta.glob("*.py")` y se salta los que empiezan por `_`. Carga cada uno con `importlib.util.spec_from_file_location`.
- Valida que existan `NOMBRE`, `DESCRIPCION`, `ESQUEMA`, `requiere_confirmacion` y un `ejecutar` invocable. Si falta algo, lanza `ValueError` nombrando el archivo y el atributo. La clave del diccionario es `NOMBRE`.

### Contrato de un archivo de herramienta (jarvis/tools/hora.py como plantilla)
```python
NOMBRE = "hora"
DESCRIPCION = "Devuelve la fecha y hora local actuales."
ESQUEMA = {"type": "object", "properties": {}, "required": []}
requiere_confirmacion = False   # True si la acción tiene efectos reales (enviar, borrar, comprar, publicar, calendario)
def ejecutar(**args) -> str: ...  # devuelve "AAAA-MM-DD HH:MM"
```
Además, un docstring de cabecera que explique el contrato, porque este archivo es la plantilla para las herramientas nuevas.

### jarvis/bucle.py (constructor)
```python
SISTEMA = "Eres Jarvis, un asistente personal. Responde en español y de forma breve. Usa las herramientas cuando ayuden."
MAX_ITERACIONES = 5

def confirmar_por_terminal(nombre: str, argumentos: dict) -> bool   # input "¿Ejecutar {nombre} con {argumentos}? [s/N] "; True solo con s/si/sí
def ejecutar_llamada(llamada, herramientas, confirmar) -> str
def turno(cliente, historial: list[dict], herramientas: dict, texto: str,
          confirmar=confirmar_por_terminal, max_iteraciones: int = MAX_ITERACIONES) -> str
def conversar(cliente, herramientas: dict, entrada=input, salida=print,
              confirmar=confirmar_por_terminal) -> None
```
- `ejecutar_llamada`:
  - Si la herramienta no existe, devuelve `"Error: herramienta desconocida '<nombre>'"`.
  - Si `requiere_confirmacion` es True y `confirmar(...)` devuelve False, devuelve `"El usuario canceló la acción."` **sin ejecutar nada**.
  - Si no, devuelve `str(modulo.ejecutar(**argumentos))`. Si salta una excepción, devuelve `f"Error: {e}"`.
- `turno`:
  1. Añade el mensaje del usuario al historial.
  2. Hasta `max_iteraciones` veces: llama a `cliente.responder(historial, definiciones(herramientas), SISTEMA)` y añade el mensaje del asistente. Si no hay llamadas, devuelve el texto. Si las hay, añade un mensaje `herramienta` por cada llamada.
  3. Si se agota el tope, devuelve `"Me detuve: demasiadas llamadas a herramientas seguidas."`.
- `conversar`:
  - Muestra el prompt `"tú> "`. Termina con `/salir`, `EOFError` o `KeyboardInterrupt`, y despide con `"Hasta luego."`. Las entradas vacías se ignoran.
  - Imprime `"jarvis> " + respuesta`.
  - Si `turno` lanza otra excepción (error del proveedor), imprime `"Error del proveedor: <tipo>: <mensaje>"`, deja el historial como estaba antes del turno (`del historial[n:]`) y sigue.
  - Historial en memoria (`ponytail: sin límite; recortar cuando crezca`).

### jarvis/__main__.py (constructor)
`main() -> int`:
1. `load_dotenv()`.
2. `cargar_config(os.environ)`. Si lanza `ErrorConfig`, imprime el error en stderr y devuelve 1.
3. `crear_cliente`, `cargar_herramientas`, `conversar` y devuelve 0.

Al final, `if __name__ == "__main__": sys.exit(main())`.

## Tests (mínimo 12; ninguno usa red, claves reales ni `.env`)

**tests/test_config.py** (constructor)
1. Con `{"ANTHROPIC_API_KEY": "falsa"}` se obtiene proveedor `claude` y modelo `claude-sonnet-5-5`.
2. Con el diccionario vacío, `ErrorConfig` y un mensaje que contiene `ANTHROPIC_API_KEY` y `.env`.
3. Con `JARVIS_PROVIDER=openrouter` y sin `OPENROUTER_API_KEY`, `ErrorConfig`.
4. Con `JARVIS_PROVIDER=otro`, `ErrorConfig`.
5. `JARVIS_MODEL` sustituye al modelo por defecto.

**tests/test_tools.py** (constructor; ligero puede escribir el 7)
6. `cargar_herramientas()` incluye `"hora"` con el contrato completo y `requiere_confirmacion is False`.
7. `hora.ejecutar()` cumple la regex `^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$`.
8. Un archivo nuevo escrito en `tmp_path` se descubre sin tocar nada más, y `_privado.py` se ignora.
9. A un archivo sin `ejecutar` le corresponde un `ValueError` que nombra el archivo.
10. `definiciones()` devuelve `[{"nombre", "descripcion", "esquema"}]`.

**tests/test_llm.py** (conector-llm)
11. `ClienteFalso` devuelve en orden, registra lo recibido y, cuando se agota, lanza `RuntimeError`.
12. `a_formato_anthropic`: el asistente con llamadas da bloques `tool_use`, y dos resultados seguidos más un texto del usuario quedan en UN solo mensaje `user`.
13. `ClienteClaude` con un `sdk` simulado (SimpleNamespace) pasa `model` y `tools` con `input_schema`, y parsea `text` + `tool_use` a `Respuesta`.
14. `a_formato_openai`: `system` va primero, `arguments` es un string JSON y el rol `tool` lleva `tool_call_id`.
15. `ClienteOpenRouter` con un `sdk` simulado parsea `tool_calls` (los `arguments` JSON pasan a dict).
16. `crear_cliente` devuelve `ClienteClaude` o `ClienteOpenRouter` según `Config` (con clave "falsa"; construir el SDK no llama a la red).

**tests/test_bucle.py** (constructor)
17. Si la respuesta es solo texto, `turno` devuelve ese texto y el historial queda como [usuario, asistente].
18. Uso de herramienta: el falso pide `hora` y luego responde con texto. Se comprueba que el resultado está en el historial y que la 2.ª llamada al cliente lo recibe.
19. Una herramienta con `requiere_confirmacion=True` no se ejecuta si `confirmar` devuelve False (resultado "canceló") y sí se ejecuta si devuelve True.
20. Una herramienta desconocida y una herramienta que lanza una excepción dan como resultado `"Error: ..."`, sin que salte ninguna excepción.
21. Tope: si el falso siempre pide una herramienta, se para tras `max_iteraciones` llamadas y devuelve el mensaje de tope.
22. `conversar` con las entradas `["hola", "/salir"]` hace una sola llamada al cliente y despide. Con una entrada que lanza `EOFError`, sale sin traza.

Para los tests del bucle, las herramientas falsas son `types.SimpleNamespace` con el contrato. No usan la carpeta real.

## Reparto
1. **ligero**: crea `pyproject.toml`, las carpetas, los `__init__.py` vacíos y `.venv`, e instala con `pip install -e ".[dev]"`. Revisa `.gitignore`.
2. **conector-llm**: escribe todo `jarvis/llm/` y `tests/test_llm.py`, con TDD. Fija la constante del modelo por defecto de OpenRouter y se la pasa al constructor.
3. **constructor** (TDD: primero el test que falla): escribe `config.py`, `tools/__init__.py`, `tools/hora.py`, `bucle.py`, `__main__.py`, `test_config.py`, `test_tools.py` y `test_bucle.py`.
4. **ligero**: escribe `jarvis/README.md` (crear el venv, instalar, crear `.env` con las variables JARVIS_PROVIDER, ANTHROPIC_API_KEY u OPENROUTER_API_KEY y JARVIS_MODEL sin valores reales, ejecutar con `python -m jarvis` y `pytest -q`, y cómo agregar una herramienta). No toca el README.md de la raíz.
5. **verificador**: `.venv\Scripts\python -m pytest -q` y además `pytest -q` sin claves en el entorno. Pega la salida literal.

## Criterios de aceptación
- `pytest -q` sale con 0, con 12 tests o más, sin ninguna clave en el entorno.
- Agregar `jarvis/tools/x.py` basta para que el modelo vea la herramienta, sin editar ningún otro archivo.
- Ninguna herramienta con `requiere_confirmacion=True` se ejecuta sin un "s" explícito del usuario.
- Sin claves en el código, los tests ni los mensajes de error. Ninguna dependencia aparte de anthropic, openai, python-dotenv y pytest.
- Los atajos llevan su comentario `ponytail:`.
