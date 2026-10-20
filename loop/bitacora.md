# Bitácora

Una línea por turno importante: fecha — fase — qué se hizo — resultado de las pruebas.

2026-10-19 — Fase 1 — Núcleo completo: bucle en terminal, registro de herramientas (hora.py), config, jarvis/llm/ (Claude, OpenRouter, ClienteFalso), jarvis/README.md. Revisor: 1.ª vuelta CAMBIOS REQUERIDOS (respuesta vacía, aviso de herramientas ya ejecutadas), 2.ª APROBADO; se aplicó además el .strip() recomendado — `pytest -q`: 46 passed, exit 0, también sin claves.

2026-10-20 — Fase 1 (extra) — Proveedor claude-cli (jarvis/llm/claude_cli.py): usa la suscripción vía `claude -p --output-format json --safe-mode --tools ""`, continúa con --resume, corre desde una carpeta neutra; es el proveedor por defecto (LLM_PROVIDER, alias JARVIS_PROVIDER; JARVIS_MODEL=sonnet, JARVIS_EFFORT=medium). Sin revisor todavía — `pytest -q`: 56 passed, exit 0.
2026-10-20 — Fase 1 (extra) — claude-cli más rápido: streaming (stream-json + text_delta → bucle imprime fragmentos) y arranque corto (--safe-mode + --disable-slash-commands + --strict-mcp-config + --setting-sources ""; medido: 524 907 → 654 tokens de contexto). Script de medición: scripts/medir_claude_cli.py (lo corre el usuario). Sin revisor todavía — `pytest -q`: 61 passed, exit 0.
