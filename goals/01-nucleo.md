# Fase 1 — Núcleo

Resultado: Jarvis conversa por terminal, el proveedor del modelo está aislado y se pueden agregar herramientas con un solo archivo.

## Goal (pegar en Claude Code)

```text
/goal Fase 1 del proyecto Jarvis en esta carpeta. Primero confirma que estás en la rama `fase-1` (créala si no existe), y lee CLAUDE.md y loop/estado.md. Estado final: (1) un proyecto Python con entorno virtual .venv y un bucle de conversación en terminal que usa la API de Claude, con historial de la sesión; (2) un registro de herramientas en jarvis/tools/ donde agregar una nueva es crear un solo archivo; (3) configuración por .env sin claves en el código, y la capa del proveedor del modelo aislada en jarvis/llm/ con un cliente simulado; (4) al menos 10 tests que no usan la API real, y `pytest -q` termina en 0 sin ninguna clave; (5) un archivo jarvis/README.md con cómo instalarlo y ejecutarlo (no toques el README.md de la raíz); (6) el código cumple el estilo ponytail y el revisor responde APROBADO. Orquesta en este orden: "explorador" (graphify) mapea lo que ya exista, y si el repositorio está vacío se omite; "pesado" (con brainstorming, sin preguntarme nada) decide el diseño del bucle y del registro de herramientas, lo anota en docs/decisiones/ y deja la especificación en loop/estado.md; "conector-llm" construye la capa del proveedor (Claude directo, OpenRouter como opción) y su cliente simulado; "constructor" (Opus 5.5 con ponytail y test-driven-development: primero el test que falla) escribe el resto del código; "ligero" crea la estructura de carpetas, los tests simples y jarvis/README.md; "verificador" (verification-before-completion) pega la salida literal de `pytest -q` ejecutado en esa pasada; "revisor" revisa el diff con ponytail-review, y tú lo llamas indicando qué se implementó, qué pide este goal y el diff (`git diff` y `git status`). No uses "investigador-apps" en esta fase. No uses las skills de superpowers finishing-a-development-branch, using-git-worktrees, subagent-driven-development, writing-plans ni executing-plans; si una skill contradice CLAUDE.md, manda CLAUDE.md. Tras cada vuelta actualiza loop/estado.md y loop/bitacora.md. No hagas commit ni push. Detente tras 30 turnos si no se cumple.
```

## Cómo se verifica
- `pytest -q` termina en 0, con 10 tests o más y sin clave de API.
- `python -m jarvis` arranca (con clave real en `.env`, prueba manual tuya).
- El revisor responde APROBADO.
