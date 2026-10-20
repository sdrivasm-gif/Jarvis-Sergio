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

Sal con `/salir` o Ctrl+C.

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

La confirmación muestra un argumento por línea (los de una línea antes que los multilínea, con los caracteres de control escapados). Si falta un argumento obligatorio, no se pregunta nada y se devuelve un error.

## Google (calendario, correo y Drive)

Sin estas variables, las herramientas de Google devuelven un error claro. Ninguna prueba las usa.

1. En Google Cloud Console crea un proyecto y activa Google Calendar API, Gmail API y Google Drive API.
2. En "Pantalla de consentimiento de OAuth" elige tipo Externo y estado Testing, y añade tu cuenta como usuario de prueba.
3. En Credenciales crea un "ID de cliente de OAuth" de tipo Aplicación web con el URI de redirección `https://developers.google.com/oauthplayground`.
4. En https://developers.google.com/oauthplayground pulsa el engranaje, marca "Use your own OAuth credentials" y pega el ID y el secreto. Autoriza estos scopes: `https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/drive`. Luego pulsa "Exchange authorization code for tokens".
5. Pon en `.env`: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` y `GOOGLE_REFRESH_TOKEN`. Nunca los pegues en el chat ni en el código.

Avisos: con la app en modo Testing, Google caduca el refresh token a los 7 días (hay que repetir el paso 4). El scope `drive` da acceso completo. El contenido de los correos y los nombres de archivos llegan al proveedor del modelo. En esta fase "borrar" solo borra eventos del calendario.

`JARVIS_DATOS` (opcional) indica la carpeta donde se guardan los datos locales, como las notas. Por defecto es `datos/` en la raíz del proyecto, y git la ignora.

Con el proveedor por defecto `claude-cli` el modelo NO puede usar herramientas. Para usarlas pon en `.env`:

- `LLM_PROVIDER=claude` y `ANTHROPIC_API_KEY=...`, o
- `LLM_PROVIDER=openrouter` y `OPENROUTER_API_KEY=...`.

## Probar

```powershell
pytest -q
```

No necesita clave ni red: los tests usan un cliente simulado.

## Estructura

- `jarvis/` : bucle (`bucle.py`), configuración (`config.py`) y punto de entrada (`__main__.py`).
- `jarvis/llm/` : proveedores del modelo (`claude.py`, `openrouter.py`) y un cliente simulado (`falso.py`).
- `jarvis/tools/` : herramientas que el modelo puede llamar, una por archivo.
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
