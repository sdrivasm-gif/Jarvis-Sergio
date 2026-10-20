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

## Probar

```powershell
pytest -q
```

No necesita clave ni red: los tests usan un cliente simulado.

## Estructura

- `jarvis/` : bucle (`bucle.py`), configuración (`config.py`) y punto de entrada (`__main__.py`).
- `jarvis/llm/` : proveedores del modelo (`claude.py`, `openrouter.py`) y un cliente simulado (`falso.py`).
- `jarvis/tools/` : herramientas que el modelo puede llamar, una por archivo.
- `tests/` : pruebas con pytest.

## Agregar una herramienta

Crea un solo archivo en `jarvis/tools/` copiando la plantilla `jarvis/tools/hora.py`. No hay que tocar nada más: `jarvis/tools/__init__.py` lo descubre solo (los archivos que empiezan por `_` se ignoran). El archivo define:

- `NOMBRE`: identificador único que verá el modelo.
- `DESCRIPCION`: qué hace, en una frase; el modelo decide con ella cuándo usarla.
- `ESQUEMA`: JSON Schema de los argumentos de `ejecutar`.
- `requiere_confirmacion`: `True` si la acción tiene efectos reales.
- `ejecutar(**args) -> str`: hace el trabajo y devuelve texto para el modelo.

Las acciones con efectos reales (enviar, borrar, comprar, publicar, modificar calendario) deben poner `requiere_confirmacion = True`; así el bucle pide un "s" explícito antes de ejecutarlas.
