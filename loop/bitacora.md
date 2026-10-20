# Bitácora

Una línea por turno importante: fecha — fase — qué se hizo — resultado de las pruebas.

2026-10-19 — Fase 1 — Núcleo completo: bucle en terminal, registro de herramientas (hora.py), config, jarvis/llm/ (Claude, OpenRouter, ClienteFalso), jarvis/README.md. Revisor: 1.ª vuelta CAMBIOS REQUERIDOS (respuesta vacía, aviso de herramientas ya ejecutadas), 2.ª APROBADO; se aplicó además el .strip() recomendado — `pytest -q`: 46 passed, exit 0, también sin claves.

2026-10-20 — Fase 1 (extra) — Proveedor claude-cli (jarvis/llm/claude_cli.py): usa la suscripción vía `claude -p --output-format json --safe-mode --tools ""`, continúa con --resume, corre desde una carpeta neutra; es el proveedor por defecto (LLM_PROVIDER, alias JARVIS_PROVIDER; JARVIS_MODEL=sonnet, JARVIS_EFFORT=medium). Sin revisor todavía — `pytest -q`: 56 passed, exit 0.
2026-10-20 — Fase 1 (extra) — claude-cli más rápido: streaming (stream-json + text_delta → bucle imprime fragmentos) y arranque corto (--safe-mode + --disable-slash-commands + --strict-mcp-config + --setting-sources ""; medido: 524 907 → 654 tokens de contexto). Script de medición: scripts/medir_claude_cli.py (lo corre el usuario). Sin revisor todavía — `pytest -q`: 61 passed, exit 0.
2026-10-20 — Fase 2 — Herramientas notas, buscar_archivos, abrir_app (con confirmación) y buscar_web (DuckDuckGo, sin clave), personalidad cargada desde jarvis/personalidad.md con respaldo, aviso de claude-cli sin herramientas; correcciones de claude_cli.py (kill en finally, timeout nombrado). Revisor: claude_cli.py CAMBIOS REQUERIDOS → corregido; diff de la fase APROBADO (+ajustes menores aplicados). Decisión: docs/decisiones/002-herramientas-fase-2.md — `pytest -q`: 100 passed, exit 0, sin claves.
