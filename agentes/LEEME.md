# Mover los subagentes a .claude

Claude Code lee los subagentes desde `.claude\agents\`. Esa carpeta no se puede escribir de forma remota, así que los archivos están aquí.

## En PowerShell

```powershell
cd "$env:USERPROFILE\Documents\jarvis-loop"
Copy-Item agentes\*.md .claude\agents\ -Exclude LEEME.md -Force
dir .claude\agents
```

Deben aparecer 8 archivos: constructor, conector-llm, explorador, investigador-apps, ligero, pesado, revisor, verificador.

Los 4 archivos antiguos que copiaste a `C:\Users\rivas\.claude\agents` quedan desactualizados. Como los del proyecto tienen prioridad no estorban, pero puedes borrarlos para evitar confusiones.

Después reinicia `claude` en la carpeta del proyecto.

## Comprobar que las skills existen

Pega esto en Claude Code:

```text
Lista las skills disponibles con su nombre exacto y dime si existen estas diez: ponytail:ponytail, ponytail:ponytail-review, graphify, openrouter:openrouter-analytics, reverse-engineer-anything, superpowers:brainstorming, superpowers:systematic-debugging, superpowers:test-driven-development, superpowers:verification-before-completion y superpowers:requesting-code-review. Si alguna tiene otro nombre, dime cuál es.
```

Si alguna tiene otro nombre, corrígelo en el campo `skills:` del archivo del subagente. Claude Code omite sin avisar una skill que no encuentra.
