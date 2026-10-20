# 001 — Núcleo de la fase 1

Fecha: 2026-10-19 · Autor: pesado · Estado: aceptada

## Contexto
La fase 1 (goals/01-nucleo.md) pide un bucle de conversación en terminal con historial, un registro de herramientas donde cada herramienta nueva sea un solo archivo, configuración por `.env`, el proveedor del modelo aislado en `jarvis/llm/` con un cliente simulado, y al menos 10 tests que pasen sin clave. Estilo ponytail: lo mínimo que funcione.

## Decisiones
1. **Nombres en español** para todo el código propio (módulos, funciones, clases, claves de los diccionarios). El contrato de herramientas ya va en español (`NOMBRE`, `DESCRIPCION`, `ESQUEMA`, `requiere_confirmacion`, `ejecutar`), así que el resto lo sigue: `ClienteClaude`, `ClienteOpenRouter`, `ClienteFalso`, `crear_cliente`, `cargar_config`. Lo que viene de los SDK (`messages.create`, `tool_use`...) queda como está.
2. **Bucle**: `python -m jarvis` → `jarvis/__main__.py` solo conecta las piezas; la lógica vive en `jarvis/bucle.py` (`turno` y `conversar`), que se prueba con `ClienteFalso` y una entrada guionizada. El historial es una lista en memoria con un **formato neutro propio** (dicts con `rol`). Cada cliente lo traduce al formato de su API. Hay un tope de 5 iteraciones de herramientas por turno. Se sale con `/salir`, Ctrl+C o EOF.
3. **Herramientas**: `jarvis/tools/__init__.py` descubre todos los `*.py` de la carpeta que no empiecen por `_` y valida el contrato al cargarlos. Si una herramienta tiene `requiere_confirmacion = True`, el bucle pregunta `[s/N]` antes de ejecutarla, y cualquier respuesta que no sea sí la cancela. Si una herramienta falla, el modelo recibe el error como texto y el bucle no se cae.
4. **Config**: `python-dotenv` se llama solo en `__main__.main()`. `cargar_config(entorno)` recibe un diccionario, así que los tests nunca leen `.env` ni dependen de variables reales. Si falta la clave del proveedor elegido, lanza `ErrorConfig` con un mensaje claro.
5. **Proveedor**: un Protocol `Cliente` con un único método, `responder(mensajes, herramientas, sistema) -> Respuesta`. `ClienteClaude` usa el SDK `anthropic`. `ClienteOpenRouter` usa el SDK `openai` con `base_url` de OpenRouter, porque es menos código que `httpx` a mano y ya trae reintentos. Los dos aceptan un `sdk` inyectado para probarlos sin red. La traducción de formatos va en funciones puras que se pueden probar.
6. **Empaquetado**: un solo `pyproject.toml` (dependencias, extra `dev` con pytest y `pythonpath = ["."]` para que `pytest -q` funcione desde la raíz). Paquetes declarados a mano para que setuptools no se confunda con `docs/`, `loop/` ni `goals/`. Entorno virtual en `.venv`.

## Alternativas descartadas
- **Usar el formato de Anthropic como historial interno**: es menos código, pero el proveedor se cuela en el bucle y OpenRouter tendría que traducir desde Anthropic. Con el formato neutro, cada cliente traduce lo suyo.
- **Registro con decorador o clases base**: es más abstracción y no ahorra archivos. Con módulos y constantes basta.
- **Leer `.env` a mano**: python-dotenv es una línea y resuelve comillas y comentarios.
- **`requirements.txt` + `pytest.ini`**: son dos archivos en lugar de uno.
- **httpx para OpenRouter**: habría que escribir a mano el parseo, los errores y los reintentos.

## Consecuencias
- Agregar una herramienta = crear `jarvis/tools/<nombre>.py` con el contrato. No se toca nada más.
- Cambiar de proveedor = `JARVIS_PROVIDER` en `.env`.
- Deuda marcada con `ponytail:`: historial sin límite, sin streaming, `max_tokens` fijo, confirmación solo por terminal (en la fase de voz habrá que cambiarla).
