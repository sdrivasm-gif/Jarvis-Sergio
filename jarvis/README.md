# Jarvis

Asistente personal por texto (y más adelante por voz). Fase 1: un bucle de conversación en la terminal que habla con un modelo (Claude u OpenRouter) y puede usar herramientas.

## Instalar

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Configurar

Copia `.env.example` a `.env` y rellena las variables:

- `LLM_PROVIDER`: opcional; `claude-cli` por defecto (usa tu suscripción vía `claude -p`, sin clave; necesita `claude` instalado y con sesión iniciada). También `claude` u `openrouter`. `JARVIS_PROVIDER` sigue valiendo como alias antiguo.
- `ANTHROPIC_API_KEY` (si usas `claude`) u `OPENROUTER_API_KEY` (si usas `openrouter`). `claude-cli` no pide clave.
- `JARVIS_MODEL`: opcional; si no la pones se usa el modelo por defecto del proveedor (`sonnet` en `claude-cli`).
- `JARVIS_EFFORT`: opcional, solo `claude-cli`; `medium` por defecto (`low`, `medium`, `high`, `xhigh`, `max`).

`claude-cli` no tiene herramientas: Jarvis conversa pero no ejecuta `jarvis/tools/` con ese proveedor.

`.env` contiene tus claves y no se commitea. Nunca pongas claves en el código.

Nota: el id de modelo por defecto de OpenRouter (`MODELO_OPENROUTER_POR_DEFECTO` en `jarvis/llm/openrouter.py`) está sin verificar. Si falla, cámbialo con `JARVIS_MODEL`.

## Ejecutar

```powershell
python -m jarvis
```

Sal con `/salir` o Ctrl+C. `/hoy` da el parte del día.

## Herramientas

- `hora`: da la fecha y hora actuales (sin argumentos).
- `notas`: guarda y consulta notas. Argumentos: `accion` (`crear`, `listar` o `buscar`) y `texto` (contenido o texto a buscar).
- `buscar_archivos`: busca archivos por nombre, sin leer su contenido. Argumentos: `carpeta` y `patron` (admite `*.pdf`).
- `abrir_app`: abre una aplicación del menú Inicio. Argumento: `nombre`. Pide confirmación `[s/N]` antes de abrir nada.
- `buscar_web`: busca en la web. Argumento: `consulta`.
- `clima`: tiempo actual y pronóstico de 3 días (Open-Meteo, sin clave). Argumento opcional `ciudad` (`Lima` o `Lima, Perú`); si no la das usa `JARVIS_CIUDAD` de `.env`, o Piura.
- Google (ver la sección de abajo):
  - `calendario_eventos`: lista los eventos de un día. Argumento opcional `fecha` (`AAAA-MM-DD`, `hoy` o `mañana`; hoy por defecto).
  - `calendario_crear`: crea un evento. Argumentos obligatorios: `titulo`, `inicio` (`AAAA-MM-DD HH:MM`) y `duracion_minutos` (entero, 1 a 1440). Pide `[s/N]`.
  - `calendario_borrar`: borra un evento. Argumento: `id_evento` (el que da `calendario_eventos`). Pide `[s/N]`.
  - `correo_buscar`: busca correos con la sintaxis de Gmail (hasta 5). Argumento: `consulta`.
  - `correo_enviar`: envía un correo a UNA dirección. Argumentos: `para`, `asunto` (una línea) y `cuerpo`. Pide `[s/N]`.
  - `drive_buscar`: busca archivos por parte del nombre (hasta 10). Argumento: `nombre`.
  - `drive_compartir`: comparte un archivo. Argumentos: `id_archivo` (el que da `drive_buscar`), `correo` y `rol` opcional (`lector` por defecto, o `editor`). Pide `[s/N]`.
- Memoria y recordatorios (ver las secciones de abajo):
  - `memoria`: `accion` = `guardar`, `buscar` o `listar`, y `texto`. No pide confirmación.
  - `memoria_borrar`: borra un recuerdo. Argumentos: `id_recuerdo` y `texto` exacto. Pide `[s/N]`.
  - `memoria_borrar_todo`: borra todos los recuerdos (sin argumentos). Pide `[s/N]`.
  - `recordatorios`: `accion` = `crear` o `listar`; para crear, `texto` y `cuando` o `en_minutos`. No pide confirmación.
  - `recordatorio_cancelar`: cancela un recordatorio pendiente. Argumentos: `id_recordatorio` y `texto` exacto. Pide `[s/N]`.
  - `parte_del_dia`: devuelve los datos del día (solo lee). No pide confirmación.

Son 19 herramientas. Piden confirmación `[s/N]` 8: `abrir_app`, `calendario_crear`, `calendario_borrar`, `correo_enviar`, `drive_compartir`, `memoria_borrar`, `memoria_borrar_todo` y `recordatorio_cancelar`.

La confirmación muestra un argumento por línea (los de una línea antes que los multilínea, con los caracteres de control escapados). Si falta un argumento obligatorio, no se pregunta nada y se devuelve un error.

## Google (calendario, correo y Drive)

Sin estas variables, las herramientas de Google devuelven un error claro. Ninguna prueba las usa.

1. En Google Cloud Console crea un proyecto y activa Google Calendar API, Gmail API y Google Drive API.
2. En "Pantalla de consentimiento de OAuth" elige tipo Externo y estado Testing, y añade tu cuenta como usuario de prueba.
3. En Credenciales crea un "ID de cliente de OAuth" de tipo Aplicación web con el URI de redirección `https://developers.google.com/oauthplayground`.
4. En https://developers.google.com/oauthplayground pulsa el engranaje, marca "Use your own OAuth credentials" y pega el ID y el secreto. Autoriza estos scopes: `https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/drive`. Luego pulsa "Exchange authorization code for tokens".
5. Pon en `.env`: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` y `GOOGLE_REFRESH_TOKEN`. Nunca los pegues en el chat ni en el código.

Avisos: con la app en modo Testing, Google caduca el refresh token a los 7 días (hay que repetir el paso 4). El scope `drive` da acceso completo. El contenido de los correos y los nombres de archivos llegan al proveedor del modelo. En esta fase "borrar" solo borra eventos del calendario.

## Datos locales

`JARVIS_DATOS` (opcional) indica la carpeta donde se guardan los datos locales (notas, `memoria.json` y `recordatorios.json`). Por defecto es `datos/` en la raíz del proyecto, y git la ignora. Los archivos se leen del disco en cada operación, así que sobreviven a los reinicios.

## Memoria

Guarda lo que le pidas recordar (preferencias, datos personales no sensibles), hasta 500 caracteres, en una sola línea. Un recuerdo repetido no se duplica. Los últimos 20 recuerdos se añaden al prompt del sistema como datos, no como instrucciones, así que funcionan también con `claude-cli`. Eso significa que viajan al proveedor del modelo en cada turno.

Filtro de secretos: nunca guarda claves privadas, claves de API o tokens conocidos, contraseñas etiquetadas ("contraseña: ...", "pin es ...") ni números de tarjeta (13 a 19 dígitos que pasen Luhn). Si lo detecta, rechaza el texto entero y no lo repite en el mensaje. También se aplica a los recordatorios y a `notas crear`. Tiene falsos positivos (rechaza ante la duda) y no detecta contraseñas sueltas sin etiqueta.

Borrar pide confirmación `[s/N]`: `memoria_borrar` necesita el id y el texto exacto del recuerdo (los da `memoria` con `listar` o `buscar`); si el texto no coincide, no borra nada. `memoria_borrar_todo` vacía la memoria entera.

## Recordatorios

`recordatorios` crea con `cuando` (`AAAA-MM-DD HH:MM`, hora local) o con `en_minutos` (1 a 525600), uno de los dos; rechaza horas pasadas. `listar` muestra los pendientes. `recordatorio_cancelar` pide `[s/N]`, el id y el texto exacto.

Cada recordatorio avisa una sola vez. En la terminal el aviso sale cuando se vuelve a mostrar `tú>` (al enviar algo o pulsar Enter), también al arrancar; no interrumpe mientras estás callado. Si venció con Jarvis cerrado, avisa al abrirlo con su hora original.

## Parte del día

`/hoy` en la terminal pide al modelo un resumen corto, con el tono de Jarvis y sin herramientas (funciona con `claude-cli`), de cuatro secciones: eventos de hoy, correos sin leer (hasta 5), las últimas 5 notas y los recordatorios de hoy. No entra en el historial. La herramienta `parte_del_dia` devuelve los mismos datos para que el modelo los resuma en un turno normal.

Si una fuente falla, por ejemplo Google sin configurar, esa sección sale como "No disponible: ..." y el resto sigue.

Con el proveedor por defecto `claude-cli` el modelo NO puede usar herramientas. Para usarlas pon en `.env`:

- `LLM_PROVIDER=claude` y `ANTHROPIC_API_KEY=...`, o
- `LLM_PROVIDER=openrouter` y `OPENROUTER_API_KEY=...`.

## Voz

Opcional y apagada por defecto: sin ella Jarvis funciona igual, solo con texto.

```powershell
pip install -e ".[voz]"
python -m jarvis --voz
```

También se activa con `JARVIS_VOZ=on` en `.env`. Escucha con faster-whisper (local, la primera vez descarga el modelo `base`, sin clave) y habla con la voz de Windows. El audio no se guarda ni sale del equipo. Si faltan los extras, el micrófono o el modelo, avisa y sigue con texto.

- Di "Jarvis" y la orden: "Jarvis, ¿qué hora es?". Si solo dices "Jarvis", responde "¿Sí, señor?" y la siguiente frase es la orden. Lo que se oye sin la palabra se descarta.
- "salir" o "adiós" cierran; "parte del día" equivale a `/hoy`.
- Las confirmaciones (enviar correo, etc.) se leen en voz alta: solo "sí" o "confirmo" aceptan; cualquier otra cosa o el silencio es NO.
- Ctrl+C corta la voz y cierra Jarvis; durante una confirmación solo la cancela.

Variables opcionales de `.env`:

- `JARVIS_PALABRA_ACTIVACION` (por defecto `jarvis`; admite variantes: `jarvis,yarvis`).
- `JARVIS_STT_MODELO` (`base`, `small`... o una carpeta local).
- `JARVIS_VOZ_UMBRAL` (sensibilidad del micrófono, 400 por defecto; bájalo si no te detecta).

Los WAV de `tests/audio/` salen de `python scripts/generar_audios_prueba.py`.

## Interfaz (HUD)

Una página local con estilo HUD para hablar con Jarvis. Usa solo la biblioteca estándar de Python (sin dependencias nuevas).

```powershell
python -m jarvis --ui
python -m jarvis --ui --voz
```

Con `--voz` (o `JARVIS_VOZ=on`) la página además escucha y habla, como en la sección Voz; si la voz falla, sigue solo con texto.

Variable opcional de `.env`: `JARVIS_UI_PUERTO`, un entero entre 1024 y 65535, o `0` (por defecto) para que se elija un puerto libre en cada arranque. Un valor no válido, o un puerto ocupado, hace que Jarvis avise y termine. Además valen las de Voz y las del proveedor.

Al arrancar se abre una ventana de app con `msedge --app=URL` (1100x720); Edge se busca en el PATH y en `ProgramFiles(x86)`, `ProgramFiles` y `LOCALAPPDATA`. Si no hay Edge o falla, se usa el navegador por defecto. Si no se puede abrir ninguna ventana, la consola muestra la URL completa (lleva el token; no la compartas).

Acceso directo en el escritorio (consola minimizada):

```powershell
.venv\Scripts\python scripts\crear_acceso_directo.py [--carpeta RUTA]
```

Crea `Jarvis.lnk` que ejecuta `python -m jarvis --ui` desde la carpeta del proyecto. Para cerrar Jarvis, cierra su consola o pulsa Ctrl+C en ella.

Qué muestra la página:

- Un círculo animado que cambia según el estado: reposo, escuchando, pensando o hablando.
- Los subtítulos de la conversación (texto plano, sin markdown; se guardan los últimos 200).
- Una entrada de texto para escribir a Jarvis. Mientras está ocupado, rechaza otro mensaje.
- Un panel "Hoy" con eventos, correos sin leer, notas y recordatorios, sin pasar por el modelo. Se carga al abrir, cada 5 minutos y con el botón "Actualizar". El botón "Parte del día" envía `/hoy` (ese sí usa el modelo).
- Los avisos de recordatorios, como subtítulos.
- Las confirmaciones (enviar correo, borrar, etc.) en un cuadro con los botones "Sí, ejecutar" y "No". Con la voz activa, Jarvis solo dice que necesita tu confirmación en pantalla: nunca se confirma hablando.

Seguridad:

- Escucha solo en `127.0.0.1` (no es configurable).
- Cada arranque genera un token aleatorio que va en el fragmento de la URL (`/#token`), así que no llega al servidor, a los logs ni al Referer. La página lo guarda en `sessionStorage`, lo quita de la barra y lo manda en la cabecera `X-Jarvis-Token`.
- El servidor comprueba `Host`, `Origin` y `Sec-Fetch-Site`, exige `application/json` en los POST, limita el cuerpo a 16 KiB y el texto a 4000 caracteres, y envía una CSP estricta. No hay CORS ni logs de peticiones.
- Una confirmación sin respuesta en 60 s, o con la página cerrada, es NO. Solo un clic en "Sí" para esa confirmación cuenta como sí.

Limitaciones:

- Cerrar la ventana no cierra Jarvis: se cierra con la consola o Ctrl+C. Si abres otra ventana con el acceso directo, arranca otra instancia con historial nuevo.
- El token aparece en la línea de comandos de `msedge.exe`, visible para los procesos del mismo usuario.
- Con `--voz`, lo que escribes en la página espera a que termine la escucha en curso (hasta 8 s).
- Sin icono propio. El JS solo tiene comprobaciones estáticas; su comportamiento se prueba a mano.

Decisión de diseño: `docs/decisiones/006-ui-hud-fase-6.md`.

## Probar

```powershell
pytest -q
```

No necesita clave ni red: los tests usan un cliente simulado.

## Estructura

- `jarvis/` : bucle (`bucle.py`), configuración (`config.py`) y punto de entrada (`__main__.py`).
- `jarvis/llm/` : proveedores del modelo (`claude.py`, `openrouter.py`) y un cliente simulado (`falso.py`).
- `jarvis/tools/` : herramientas que el modelo puede llamar, una por archivo.
- `jarvis/voz.py` : voz opcional (escuchar y hablar).
- `jarvis/ui/` : interfaz HUD (`servidor.py`, `sesion.py` y los estáticos `index.html`, `app.js`, `estilo.css`).
- `scripts/crear_acceso_directo.py` : crea el acceso directo de la interfaz en el escritorio.
- `jarvis/integrations/` : clientes de Google (las herramientas siguen en `jarvis/tools/`).
- `tests/` : pruebas con pytest.

## Agregar una herramienta

Crea un solo archivo en `jarvis/tools/` copiando la plantilla `jarvis/tools/hora.py`. No hay que tocar nada más: `jarvis/tools/__init__.py` lo descubre solo (los archivos que empiezan por `_` se ignoran). El archivo define:

- `NOMBRE`: identificador único que verá el modelo.
- `DESCRIPCION`: qué hace, en una frase; el modelo decide con ella cuándo usarla.
- `ESQUEMA`: JSON Schema de los argumentos de `ejecutar`.
- `requiere_confirmacion`: `True` si la acción tiene efectos reales.
- `ejecutar(**args) -> str`: hace el trabajo y devuelve texto para el modelo.

Las acciones con efectos reales (enviar, borrar, comprar, publicar, modificar calendario) deben poner `requiere_confirmacion = True`; así el bucle pide un "s" explícito antes de ejecutarlas.
