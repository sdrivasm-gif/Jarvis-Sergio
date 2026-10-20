# Estado del bucle

Fase actual: 2 — cerrada (pendiente de tu revisión y commit; goal: goals/02-herramientas.md, rama `fase-2`)
Último goal cerrado: goals/01-nucleo.md (commit b20ba9e)

## Hecho
- Fase 1 cerrada y commiteada: núcleo (bucle, config, tools/hora.py, llm/ con ClienteClaude, ClienteOpenRouter, ClienteClaudeCLI y ClienteFalso). Diseño: docs/decisiones/001-nucleo-fase-1.md.
- Fase 2: revisor revisó jarvis/llm/claude_cli.py (correcciones en el working tree: `M jarvis/llm/claude_cli.py`, `M tests/test_claude_cli.py`).
- Fase 2: explorador mapeó el código. pesado decidió el diseño: docs/decisiones/002-herramientas-fase-2.md (abajo, la especificación).

- Fase 2 (cierre): revisor de claude_cli.py → CAMBIOS REQUERIDOS (proceso `claude` huérfano si falla el stream; timeout sin nombre), corregido por constructor con tests. Herramientas 2 y 3 (ligero), 4 y 5, personalidad (`cargar_sistema`), aviso/sufijo de claude-cli y conftest con guardia (constructor), README (ligero). Revisor del diff → APROBADO; se aplicaron sus ajustes (guardia también sobre `subprocess.run`, `es_env` más amplio, `uddg` vacío, retoques de tests/doc).
- Verificador (última pasada): `pytest -q` sin claves → 100 passed, exit 0; herramientas → `['abrir_app', 'buscar_archivos', 'buscar_web', 'hora', 'notas']`; personalidad.md sin cambios; sin `shell=True`; `datos/` en .gitignore y no creada; sin claves.

## Pendiente inmediato
- Tú: revisar el diff (`git diff` y `git status`), hacer la prueba manual de abajo y el commit. `goals/06-noche-fases-3-a-6.md` apareció sin seguimiento durante la sesión y no es de esta vuelta.
- Siguiente: goals/03-voz.md (reescribirlo con el equipo actual antes de lanzarlo).

## Bloqueos / dudas para el usuario
- **PREGUNTA PARA EL USUARIO (claude-cli y herramientas):** con el proveedor por defecto (`claude-cli`) las cinco herramientas existen, pero el modelo no puede usarlas. En esta fase solo se avisa al arrancar y se le dice al modelo que no las tiene (decisión 002, punto 7). Para tu prueba manual de la fase 2, pon `LLM_PROVIDER=claude` (con ANTHROPIC_API_KEY) u `openrouter` (con OPENROUTER_API_KEY) en `.env`. ¿Quieres un goal propio para dar herramientas a claude-cli, o prefieres cambiar el proveedor por defecto?
- **Para revisar (decisión de pesado, cambiar es una línea):** `buscar_web` no pide confirmación, porque solo lee y no tiene efectos, pero la consulta sale a DuckDuckGo. Si prefieres que pida confirmación en cada búsqueda, es `requiere_confirmacion = True` en jarvis/tools/buscar_web.py y ajustar su test.
- Prueba manual solo tuya: que `Get-StartApps` y `os.startfile("shell:AppsFolder\\...")` abran tus apps, que DuckDuckGo responda sin captcha y que la personalidad (varias líneas) llegue entera a `claude -p`. Si algo falla, las alternativas están en la decisión 002, en Consecuencias.
- Siguen de la fase 1: el ID por defecto de OpenRouter (`anthropic/claude-sonnet-5-5`) no está verificado; ninguna prueba llamó a una API real; hay deuda `ponytail:` (respuesta vacía tras herramientas, historial sin límite, confirmación solo por terminal).

---

# Especificación fase 2 (para ligero y constructor)

Fuente: docs/decisiones/002-herramientas-fase-2.md. Convención: nombres en español, `# ponytail: <límite>; <cómo mejorarlo>` en cada atajo, Python 3.11+, sin dependencias nuevas (solo la biblioteca estándar). TDD: primero el test que falla. Ningún test abre una app, usa la red, lee `.env` ni escribe fuera de `tmp_path`. **Ningún módulo de herramienta tiene efectos al importarse** (nada de PowerShell, red ni mkdir a nivel de módulo): `cargar_herramientas()` los importa todos.

Las herramientas siguen el contrato de `jarvis/tools/hora.py` (NOMBRE, DESCRIPCION, ESQUEMA, requiere_confirmacion, ejecutar(**args) -> str). `ejecutar` solo acepta los argumentos del ESQUEMA (nada inyectable por el modelo). Los errores esperables se devuelven como texto `"Error: ..."`. Los inesperados (OSError, timeout) pueden lanzar excepción, porque `bucle.ejecutar_llamada` ya los convierte en `"Error: <e>"`.

En los tests, cada módulo se importa normal (`from jarvis.tools import notas`) y se parchea con `monkeypatch.setattr(modulo, ...)`.

## Archivos

| Archivo | Quién | Qué |
|---|---|---|
| `.gitignore` | ligero | añadir la línea `datos/` |
| `jarvis/tools/notas.py` + `tests/test_notas.py` | ligero | herramienta 2 |
| `jarvis/tools/buscar_archivos.py` + `tests/test_buscar_archivos.py` | ligero | herramienta 3 |
| `jarvis/README.md` | ligero | sección corta: las 5 herramientas, `JARVIS_DATOS`, que `abrir_app` pide confirmación y que con `claude-cli` no hay herramientas |
| `tests/conftest.py` | constructor | guardia autouse sin efectos reales |
| `jarvis/tools/abrir_app.py` + `tests/test_abrir_app.py` | constructor | herramienta 4 |
| `jarvis/tools/buscar_web.py` + `tests/test_buscar_web.py` | constructor | herramienta 5 |
| `jarvis/bucle.py` + `tests/test_bucle.py` | constructor | personalidad |
| `jarvis/llm/claude_cli.py` + `tests/test_claude_cli.py` | constructor | sufijo "sin herramientas" |
| `jarvis/__main__.py` + `tests/test_main.py` | constructor | aviso al arrancar |
| `tests/test_tools.py` | constructor (al final) | las cinco y sus banderas |

No se tocan: `jarvis/personalidad.md` (ni su texto ni sus espacios), `jarvis/config.py`, `jarvis/tools/__init__.py`, `jarvis/tools/hora.py`, `scripts/medir_claude_cli.py`, `.env*`.

## Herramienta 2 — jarvis/tools/notas.py (ligero)

```python
NOMBRE = "notas"
DESCRIPCION = ("Guarda, lista o busca notas del usuario en un archivo local. "
               "accion='crear' con texto, 'listar', o 'buscar' con texto.")
ESQUEMA = {
    "type": "object",
    "properties": {
        "accion": {"type": "string", "enum": ["crear", "listar", "buscar"]},
        "texto": {"type": "string", "description": "Contenido de la nota (crear) o texto a buscar (buscar)."},
    },
    "required": ["accion"],
}
requiere_confirmacion = False  # solo escribe dentro de la carpeta de datos
CARPETA_DATOS_POR_DEFECTO = Path(__file__).resolve().parents[2] / "datos"
ARCHIVO = "notas.txt"
MAX_NOTAS = 20

def carpeta_datos() -> Path      # Path(os.environ["JARVIS_DATOS"]) si existe y no está vacía; si no, CARPETA_DATOS_POR_DEFECTO. Se lee en cada llamada.
def ejecutar(accion: str, texto: str = "") -> str
```
- Archivo `carpeta_datos() / ARCHIVO`, en UTF-8, una nota por línea: `f"{datetime.now():%Y-%m-%d %H:%M} | {' '.join(texto.split())}\n"` (los saltos de línea y los espacios repetidos quedan en un solo espacio). `crear` hace `mkdir(parents=True, exist_ok=True)` y añade la línea al final (modo `"a"`).
- Salidas exactas:
  - crear OK → `"Nota guardada."`
  - crear con texto vacío o solo espacios → `"Error: la nota está vacía."` (no crea el archivo)
  - listar sin archivo o sin líneas → `"No hay notas."`
  - listar → las últimas `MAX_NOTAS` líneas, sin el `\n` final, unidas por `"\n"`
  - buscar con texto vacío → `"Error: falta el texto a buscar."`
  - buscar → las últimas `MAX_NOTAS` líneas que contienen el texto (comparando con `casefold()`), unidas por `"\n"`. Si no hay ninguna → `f"No hay notas que contengan '{texto}'."`
  - otra acción → `f"Error: acción desconocida '{accion}'; usa crear, listar o buscar."`
- `ponytail:` listar y buscar sin paginar (solo las últimas 20); sin borrar ni editar notas.

**tests/test_notas.py** (todos con `monkeypatch.setenv("JARVIS_DATOS", str(tmp_path / "datos"))`, una carpeta que aún no existe):
1. crear → `"Nota guardada."`; `notas.txt` existe y su línea cumple `^\d{4}-\d{2}-\d{2} \d{2}:\d{2} \| comprar pan$`.
2. crear con `"línea uno\nlínea dos"` guarda una sola línea con `"línea uno línea dos"`.
3. crear `"   "` → `"Error: la nota está vacía."` y no hay archivo.
4. listar sin notas → `"No hay notas."`; tras crear dos, listar devuelve 2 líneas en orden de creación.
5. listar con 25 notas devuelve exactamente 20 líneas, las últimas.
6. buscar `"PAN"` encuentra `"comprar pan"` y no `"llamar a Ana"`; buscar `"xyz"` → `"No hay notas que contengan 'xyz'."`; buscar `""` → `"Error: falta el texto a buscar."`
7. acción `"borrar"` → empieza por `"Error: acción desconocida 'borrar'"`.
8. Sin `JARVIS_DATOS` (`monkeypatch.delenv(..., raising=False)`): `carpeta_datos() == <raíz del repo>/"datos"`, con la raíz calculada como `Path(__file__).resolve().parents[1]` desde tests/. No escribe nada.
9. `notas.requiere_confirmacion is False`.

## Herramienta 3 — jarvis/tools/buscar_archivos.py (ligero)

```python
NOMBRE = "buscar_archivos"
DESCRIPCION = ("Busca archivos por su nombre dentro de una carpeta y sus subcarpetas. Solo devuelve rutas: "
               "no lee el contenido. Admite comodines como *.pdf.")
ESQUEMA = {
    "type": "object",
    "properties": {
        "carpeta": {"type": "string", "description": "Carpeta donde buscar, p. ej. C:\\Users\\rivas\\Documents o ~/Documents."},
        "patron": {"type": "string", "description": "Parte del nombre o comodín (*.pdf); no distingue mayúsculas."},
    },
    "required": ["carpeta", "patron"],
}
requiere_confirmacion = False  # solo lista nombres; no lee ni cambia nada
MAX_RESULTADOS = 50
MAX_PROFUNDIDAD = 5

def es_env(nombre: str) -> bool  # nombre.casefold() == ".env" o empieza por ".env."
def ejecutar(carpeta: str, patron: str) -> str
```
- `base = Path(carpeta).expanduser()`. Recorre `os.walk(base)` (sin seguir enlaces, que es lo que hace por defecto). **Nunca abre ni lee ningún archivo.**
- En cada nivel poda las carpetas: `dirs[:] = [d for d in dirs if not d.startswith(".")]`. Si la profundidad de la carpeta actual (número de partes relativas a `base`) es `>= MAX_PROFUNDIDAD`, hace `dirs.clear()`. Así se ven archivos hasta en `base/a/b/c/d/e/` y no en `base/a/b/c/d/e/f/`.
- Coincidencia: `p = patron.casefold()`. Si no contiene `*`, `?` ni `[`, `p = f"*{p}*"`. Luego `fnmatch.fnmatchcase(nombre.casefold(), p)`. Solo archivos, no carpetas. `es_env(nombre)` → nunca se lista.
- Para al reunir `MAX_RESULTADOS + 1`. Muestra los primeros `MAX_RESULTADOS`, ordenados (`sorted`), como `str(Path(raiz) / nombre)`.
- Salidas exactas:
  - patrón vacío o solo espacios → `"Error: falta el patrón de búsqueda."`
  - `not base.is_dir()` → `f"Error: la carpeta '{carpeta}' no existe."`
  - sin coincidencias → `f"No encontré archivos que coincidan con '{patron}' en '{carpeta}'."`
  - con coincidencias → `f"Encontré {n} archivo(s):"` + `"\n"` + una ruta por línea. Si se cortó por el tope, `n` = 50 y se añade una última línea `"(hay más; acota la búsqueda)"`.
- `ponytail:` sin tope de tiempo ni de carpetas visitadas; si buscar en C:\ tarda, añadir uno.

**tests/test_buscar_archivos.py** (todo en `tmp_path`):
1. Encuentra `informe.pdf` y `sub/Informe-2.PDF` con el patrón `"informe"`, y también con `"*.pdf"`. La salida empieza por `"Encontré 2 archivo(s):"` y contiene las dos rutas completas.
2. **No lee contenidos:** `notas.txt` con el contenido `"informe"` no aparece al buscar `"informe"`.
3. **Sin .env:** `.env`, `.ENV`, `.env.local` y `sub/.env.example` no aparecen al buscar `"env"` ni `"*"`, y `config.env.txt` sí.
4. Carpeta oculta: `.git/informe.txt` no aparece.
5. Profundidad: `a/b/c/d/e/x.txt` aparece; `a/b/c/d/e/f/x.txt` no.
6. Tope: 60 archivos `f{i}.txt` → la salida tiene la cabecera `"Encontré 50 archivo(s):"`, 50 rutas y la línea final `"(hay más; acota la búsqueda)"`.
7. Carpeta inexistente → `"Error: la carpeta '...' no existe."`; patrón `""` → `"Error: falta el patrón de búsqueda."`; sin coincidencias → `"No encontré archivos que coincidan con 'zzz' en '...'."`
8. `buscar_archivos.requiere_confirmacion is False`.

## tests/conftest.py (constructor, primero)

Hay un fixture `autouse` llamado `sin_efectos_reales(monkeypatch)` que sustituye `os.startfile` (con `raising=False`) y `urllib.request.urlopen` por una función que lanza `AssertionError("un test intentó una acción real (app o red)")`. Los tests que comprueban los envoltorios reales los vuelven a parchear con un grabador.

## Herramienta 4 — jarvis/tools/abrir_app.py (constructor)

```python
NOMBRE = "abrir_app"
DESCRIPCION = ("Abre una aplicación instalada en este equipo Windows por su nombre, tal como aparece "
               "en el menú Inicio (p. ej. 'Calculadora', 'Spotify'). Requiere confirmación del usuario.")
ESQUEMA = {
    "type": "object",
    "properties": {"nombre": {"type": "string", "description": "Nombre de la aplicación en el menú Inicio."}},
    "required": ["nombre"],
}
requiere_confirmacion = True  # abre un programa: efecto real fuera de la carpeta de datos
COMANDO_APPS = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                "[Console]::OutputEncoding = [Text.Encoding]::UTF8; Get-StartApps | ConvertTo-Json -Compress"]
TIMEOUT_APPS = 15
MAX_CANDIDATOS = 5
EXCLUIDAS = ("uninstall", "desinstal")

def listar_apps() -> list[dict]   # [{"Name": str, "AppID": str}, ...]
def abrir(app_id: str) -> None    # os.startfile("shell:AppsFolder\\" + app_id)
def normalizar(texto: str) -> str # casefold + sin tildes (unicodedata NFKD, quitando combining) + strip
def ejecutar(nombre: str) -> str
```
- `listar_apps`: `subprocess.run(COMANDO_APPS, capture_output=True, timeout=TIMEOUT_APPS, check=True)`. La salida se decodifica con `"utf-8-sig"` (PowerShell puede poner BOM). Si está vacía → `[]`. Si es un objeto suelto → `[objeto]`. **Prohibido** `shell=True` y meter `nombre` en el comando.
- `abrir`: llama a `os.startfile` por atributo, nunca con `from os import startfile`, para que la guardia de conftest funcione.
- `ejecutar`:
  1. `buscado = normalizar(nombre)`. Si queda vacío → `"Error: falta el nombre de la aplicación."` (sin listar).
  2. `apps = [a for a in listar_apps() if not any(x in normalizar(a["Name"]) for x in EXCLUIDAS)]`.
  3. Exactas: `normalizar(Name) == buscado`. Si hay alguna, abre la primera.
  4. Si no, parciales: `buscado in normalizar(Name)`. Con 1 la abre. Con más de 1 → `f"Hay varias aplicaciones que coinciden con '{nombre}': {', '.join(primeros MAX_CANDIDATOS Name)}. ¿Cuál abro?"` sin abrir nada.
  5. Sin coincidencias → `f"No encontré ninguna aplicación instalada llamada '{nombre}'."`
  6. Al abrir → `abrir(app["AppID"])` y devuelve `f"Abrí {app['Name']}."`
- `ponytail:` PowerShell en cada llamada (1–2 s; cachear la lista); el usuario confirma el nombre pedido, no el AppID resuelto; no abre desinstaladores.

**tests/test_abrir_app.py**: el helper `apps_falsas(monkeypatch, apps)` parchea `abrir_app.listar_apps` (que cuenta las llamadas) y `abrir_app.abrir` (que guarda cada `app_id` en una lista `abiertas`).
1. **`test_sin_confirmacion_no_abre_la_app`** (el test que pide el goal): `bucle.ejecutar_llamada(LlamadaHerramienta("l1", "abrir_app", {"nombre": "calculadora"}), {"abrir_app": abrir_app}, lambda n, a: False)` → `"El usuario canceló la acción."`, con `abiertas == []` y `listar_apps` sin llamar. Con `lambda n, a: True` → `"Abrí Calculadora."` y `abiertas == ["Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"]`.
2. `abrir_app.requiere_confirmacion is True`.
3. Exacta gana a parcial: las apps `"Word"` y `"WordPad"`; con `"word"` se abre Word.
4. Parcial única: `"chrome"` → abre `"Google Chrome"`.
5. Varias parciales: con `"visual"` frente a `"Visual Studio"` y `"Visual Studio Code"` → empieza por `"Hay varias aplicaciones"`, nombra las dos y `abiertas == []`.
6. Sin tildes ni mayúsculas: `"configuracion"` abre `"Configuración"`.
7. Desinstaladores excluidos: `"Zoom Uninstaller"` como única coincidencia de `"zoom"` → `"No encontré ninguna aplicación instalada llamada 'zoom'."`
8. Nombre `"  "` → `"Error: falta el nombre de la aplicación."`
9. `listar_apps` real con `abrir_app.subprocess.run` parcheado: comprueba que el comando recibido `== abrir_app.COMANDO_APPS`, que no lleva `shell=True` y que la salida con BOM (`'\ufeff{"Name":"Calculadora","AppID":"X!App"}'` en bytes UTF-8) da una lista de 1. Con `b""` da `[]`.
10. `abrir` real con `os.startfile` parcheado por un grabador → recibe `"shell:AppsFolder\\X!App"`.

## Herramienta 5 — jarvis/tools/buscar_web.py (constructor)

```python
NOMBRE = "buscar_web"
DESCRIPCION = ("Busca en la web (DuckDuckGo) y devuelve hasta 5 resultados con título, resumen y enlace. "
               "No incluyas datos personales en la consulta.")
ESQUEMA = {
    "type": "object",
    "properties": {"consulta": {"type": "string", "description": "Qué buscar."}},
    "required": ["consulta"],
}
requiere_confirmacion = False  # solo lee; no cambia nada fuera de la carpeta de datos (ver decisión 002, punto 2)
URL = "https://html.duckduckgo.com/html/"
AGENTE = "Mozilla/5.0 (Jarvis)"
TIMEOUT = 10
MAX_RESULTADOS = 5

def descargar(url: str) -> str                    # urllib.request.urlopen(Request(url, headers={"User-Agent": AGENTE}), timeout=TIMEOUT); .read().decode("utf-8", "replace")
def extraer_resultados(html: str) -> list[dict]  # [{"titulo", "url", "resumen"}] en orden de aparición
def ejecutar(consulta: str) -> str
```
- `descargar` llama a `urllib.request.urlopen` por atributo (por la guardia de conftest).
- `ejecutar`:
  - consulta vacía o solo espacios → `"Error: falta la consulta."`
  - URL = `URL + "?" + urllib.parse.urlencode({"q": consulta})`
  - toma los primeros `MAX_RESULTADOS` de `extraer_resultados(descargar(url))`
  - sin resultados → `f"Sin resultados para '{consulta}'."`
  - con resultados → una línea por resultado, unidas por `"\n"`: `f"{i}. {titulo} — {resumen} ({url})"`, o `f"{i}. {titulo} ({url})"` si el resumen está vacío.
- `extraer_resultados`:
  - Cada `<a ...class="result__a"...>TÍTULO</a>` es un resultado. Hay que sacar `href` de la etiqueta sin depender del orden de los atributos.
  - El resumen es el primer `class="result__snippet"...>...</a>` entre ese resultado y el siguiente; si no hay, `""`.
  - Título y resumen: quitar etiquetas (`re.sub(r"<[^>]+>", "", s)`), aplicar `html.unescape` y colapsar espacios.
  - URL: `html.unescape(href)`. Si lleva `uddg=`, se toma `parse_qs(urlparse(href).query)["uddg"][0]`. Si empieza por `//`, se le antepone `https:`.
  - Se descartan los resultados cuya URL contiene `duckduckgo.com/y.js` (anuncios).
- `ponytail:` parseo con regex del HTML de DuckDuckGo; si cambia o sale un captcha, el resultado es "Sin resultados" (distinguir el bloqueo).

**tests/test_buscar_web.py** (con un HTML de mentira en una constante del test, imitando DuckDuckGo: un anuncio con `href="https://duckduckgo.com/y.js?ad=1"`, un resultado con `href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fes.wikipedia.org%2Fwiki%2FLima&amp;rut=abc"`, título `"Lima - <b>Wikipedia</b>"` y resumen `"Lima es la <b>capital</b> del Perú &amp; ..."`, un resultado sin resumen y 5 más):
1. `extraer_resultados`: descarta el anuncio; el primero es `{"titulo": "Lima - Wikipedia", "url": "https://es.wikipedia.org/wiki/Lima", "resumen": "Lima es la capital del Perú & ..."}`; el que no tiene resumen da `"resumen": ""`.
2. `ejecutar("clima en Lima")` con `buscar_web.descargar` parcheado: la URL recibida es `"https://html.duckduckgo.com/html/?q=clima+en+Lima"`, la salida tiene exactamente 5 líneas y la primera es `"1. Lima - Wikipedia — Lima es la capital del Perú & ... (https://es.wikipedia.org/wiki/Lima)"`.
3. HTML sin resultados → `"Sin resultados para 'nada'."`; consulta `" "` → `"Error: falta la consulta."` sin llamar a `descargar`.
4. `descargar` real con `urllib.request.urlopen` parcheado por un falso (un context manager con `.read()`): comprueba la URL del Request, la cabecera User-Agent `== AGENTE` y `timeout == 10`.
5. `buscar_web.requiere_confirmacion is False`.

## Personalidad — jarvis/bucle.py (constructor)

```python
SISTEMA = "..."  # se queda igual: ahora es el respaldo
ARCHIVO_PERSONALIDAD = Path(__file__).parent / "personalidad.md"

def cargar_sistema() -> str:
    # lee ARCHIVO_PERSONALIDAD (global del módulo, consultada en cada llamada) con encoding="utf-8", tal cual, sin strip;
    # si hay OSError, devuelve SISTEMA
```
- `turno` hace `sistema = cargar_sistema()` una vez, antes del bucle de iteraciones, y pasa `sistema` a `cliente.responder` en lugar de `SISTEMA`. Las firmas no cambian.
- `ponytail:` la personalidad se lee en cada turno (es barato, y así se puede editar sin reiniciar); si algún día se empaqueta sin modo editable, declarar `personalidad.md` como package-data.

**tests/test_bucle.py**:
- Línea 55: `assert cliente.recibidos[0]["sistema"] == cargar_sistema()` (y añadir `cargar_sistema` al import).
- Nuevo `test_sistema_viene_de_personalidad_md`: con `ClienteFalso`, `turno(...)`; el `sistema` recibido `== (Path(jarvis.bucle.__file__).parent / "personalidad.md").read_text(encoding="utf-8")` y contiene `"Eres Jarvis, el asistente personal de Sergio"`.
- Nuevo `test_sin_personalidad_usa_el_respaldo(monkeypatch, tmp_path)`: `monkeypatch.setattr(bucle, "ARCHIVO_PERSONALIDAD", tmp_path / "no_existe.md")` y luego `turno(...)` → `sistema == SISTEMA`.

## claude-cli sin herramientas (constructor)

- `jarvis/llm/claude_cli.py`: añadir la constante `SIN_HERRAMIENTAS = "En esta sesión no tienes herramientas: no puedes consultar la hora, notas, archivos, aplicaciones ni la web. Si te piden algo así, dilo en una frase y no finjas haberlo hecho."` y pasar `"--system-prompt", sistema + "\n\n" + SIN_HERRAMIENTAS`. Actualizar el comentario `ponytail:` existente: dar herramientas a claude-cli es un goal aparte.
- `tests/test_claude_cli.py:110`: pasa a `valor(comando, "--system-prompt") == "Eres Jarvis\n\n" + SIN_HERRAMIENTAS`.
- `jarvis/__main__.py`: después de `cargar_config`, `if config.proveedor == "claude-cli": print("Aviso: el proveedor claude-cli no usa herramientas; para usarlas pon LLM_PROVIDER=claude u openrouter en .env.", file=sys.stderr)`.
- `tests/test_main.py`: nuevo `test_claude_cli_avisa_que_no_hay_herramientas`, con `LLM_PROVIDER=claude-cli` y `load_dotenv`, `crear_cliente` y `conversar` parcheados como no-op → `main() == 0`; stderr contiene `"claude-cli"` y `"herramientas"`.

## tests/test_tools.py (constructor, al final)
- `test_cinco_herramientas_y_confirmaciones`: `sorted(cargar_herramientas()) == ["abrir_app", "buscar_archivos", "buscar_web", "hora", "notas"]`, y `{n: m.requiere_confirmacion for n, m in ...}` da True solo para `abrir_app`.

## Orden
1. ligero: `.gitignore` y las herramientas 2 y 3 con sus tests. A la vez, el constructor hace `conftest.py`, abrir_app, buscar_web, personalidad, claude-cli y main (no se pisan archivos).
2. constructor: `test_tools.py` (las cinco), una vez existan todas.
3. ligero: README.
4. verificador: `.venv\Scripts\python -m pytest -q` (sin claves en el entorno) y `.venv\Scripts\python -c "from jarvis.tools import cargar_herramientas; print(sorted(cargar_herramientas()))"`. Pega la salida literal.
5. revisor: `git diff` y `git status`, contrastando con goals/02-herramientas.md y la decisión 002.

## Criterios de aceptación
- `pytest -q` sale con 0 sin ninguna clave, con al menos un test por herramienta (hora ya los tiene).
- La lista de herramientas impresa es `['abrir_app', 'buscar_archivos', 'buscar_web', 'hora', 'notas']`.
- `abrir_app.requiere_confirmacion is True` y `test_sin_confirmacion_no_abre_la_app` pasa (sin confirmación ni se lista ni se abre).
- Ningún test llega a `os.startfile`, `urllib.request.urlopen` ni PowerShell reales. Nada se escribe fuera de `tmp_path`.
- `buscar_archivos` nunca abre archivos y nunca lista `.env` ni `.env.*`. `notas` no acepta rutas del modelo.
- Ni `shell=True` ni texto del modelo dentro de un comando.
- `jarvis/personalidad.md` sin cambios (`git diff` no lo muestra). Sin dependencias nuevas. Cada atajo lleva su `ponytail:`.

---

# Fase 1 (resumen; detalle en docs/decisiones/001-nucleo-fase-1.md y en el commit b20ba9e)

Contratos vigentes que la fase 2 usa:
- **Herramienta**: módulo en `jarvis/tools/` con `NOMBRE`, `DESCRIPCION`, `ESQUEMA` (JSON Schema), `requiere_confirmacion`, `ejecutar(**args) -> str`. `cargar_herramientas(carpeta=CARPETA_TOOLS)` descubre los `*.py` que no empiezan por `_` y valida el contrato (si falta algo, `ValueError`). `definiciones()` devuelve `[{"nombre", "descripcion", "esquema"}]`.
- **Bucle**: `ejecutar_llamada(llamada, herramientas, confirmar)`. Si la herramienta es desconocida → `"Error: herramienta desconocida '<n>'"`. Si `requiere_confirmacion` y `confirmar` devuelve False → `"El usuario canceló la acción."` sin ejecutar. Si salta una excepción → `"Error: <e>"`. `turno(...)` hace como máximo 5 iteraciones; `conversar(...)` maneja terminal, streaming (`al_texto`) y errores del proveedor. `confirmar_por_terminal` solo acepta s/si/sí.
- **Proveedor**: `Cliente.responder(mensajes, herramientas, sistema) -> Respuesta(texto, llamadas)`. `crear_cliente(config)` → claude-cli (por defecto, sin clave ni herramientas), claude u openrouter. Historial en formato neutro (`rol`: usuario, asistente, herramienta). `ClienteFalso(respuestas)` guarda lo recibido en `.recibidos`.
- **Config**: `cargar_config(entorno)` lee `LLM_PROVIDER` (alias `JARVIS_PROVIDER`), `JARVIS_MODEL`, `JARVIS_EFFORT` y las claves `ANTHROPIC_API_KEY` u `OPENROUTER_API_KEY` según el proveedor. `load_dotenv()` solo se llama en `__main__.main()`.
