# Goal — claude-cli persistente (respuestas más rápidas)

Hoy cada mensaje lanza un proceso nuevo `claude -p` con `--resume`, y ese arranque es lo que más tarda. Este goal mantiene un solo proceso vivo durante toda la conversación. Es chico a propósito: no usa Opus de diseño ni explorador, para gastar poca cuota.

## Antes de lanzar

```powershell
cd "$env:USERPROFILE\Documents\jarvis-loop"
git status --short
git push -u origin voz-rapida
git push origin --tags
git switch -c claude-cli-rapido
claude
```

## Goal (pegar en Claude Code)

```text
/goal Hacer más rápido el proveedor claude-cli de Jarvis, en esta carpeta. Primero confirma que estás en la rama `claude-cli-rapido` (créala si no existe) y lee CLAUDE.md, loop/estado.md y jarvis/llm/claude_cli.py. Hoy cada mensaje lanza un proceso nuevo `claude -p` con --resume, y ese arranque es lo que lo hace lento. Estado final: (1) ClienteClaudeCLI mantiene UN solo proceso de claude vivo durante toda la conversación, usando --input-format stream-json con --output-format stream-json y escribiendo cada mensaje del usuario como una línea JSON en su stdin; verifica los flags y el formato exactos con `claude --help` y la documentación oficial antes de implementar; (2) el proceso se lanza al arrancar Jarvis (precalentado) y se cierra al salir, también con Ctrl+C y cuando algo falle; (3) si el proceso muere o se queda sin responder, el siguiente mensaje lo relanza con --resume del session_id y no se pierde la conversación; (4) se mantienen el streaming de fragmentos de texto, el tiempo límite por turno, las opciones de arranque corto actuales (--safe-mode, --strict-mcp-config, --setting-sources "", --tools "") y el system prompt; (5) los tests usan un proceso simulado, nunca llaman a claude de verdad, y cubren varios turnos sobre el mismo proceso, proceso muerto que se relanza, tiempo agotado y cierre limpio; (6) scripts/medir_claude_cli.py mide también el modo persistente (primer mensaje y siguientes) para que lo ejecute yo; (7) `pytest -q` termina en 0 sin claves ni red. Para ahorrar cuota usa solo "constructor" (ponytail y test-driven-development), "verificador" (verification-before-completion, pega `pytest -q` ejecutado en esa pasada) y "revisor" (ponytail-review, una sola pasada sobre el diff); no uses "explorador", "pesado" ni "investigador-apps". No uses las skills de superpowers finishing-a-development-branch, using-git-worktrees, subagent-driven-development, writing-plans ni executing-plans; si una skill contradice CLAUDE.md, manda CLAUDE.md salvo la excepción de commit. EXCEPCIÓN solo para este goal: al cerrar, la sesión principal hace un commit local `claude-cli persistente` con la etiqueta `v0.8-cli-rapido`; nunca push. Actualiza loop/bitacora.md y solo las líneas de estado actual de loop/estado.md, sin copiar historial. Detente tras 30 turnos si no se cumple.
```

## Al terminar
- `.\.venv\Scripts\python.exe scripts\medir_claude_cli.py` para ver los tiempos del modo persistente.
- `.\.venv\Scripts\python.exe -m jarvis --ui --voz` y comprobar que el primer mensaje y los siguientes responden rápido.
