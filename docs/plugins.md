# Plugins del usuario y a quién se asignan

## Identificados
| Plugin | Qué es | Subagente | Skill |
|---|---|---|---|
| ponytail | Plugin que hace que el agente escriba el mínimo código que funcione y marque los atajos con un comentario `ponytail:`. Necesita Node.js en el PATH. | `constructor` y `revisor` | `ponytail:ponytail` y `ponytail:ponytail-review` |
| graphify | Construye un grafo de conocimiento del código en `graphify-out/` (graph.html, GRAPH_REPORT.md, graph.json) para consultar cómo se conecta todo. Paquete `graphifyy`. | `explorador` | `graphify` |
| OpenRouter | Skills oficiales de OpenRouter para Claude Code: SDK, analítica de uso, generaciones. | `conector-llm` | `openrouter:openrouter-analytics` |
| REA | Reverse Engineer Anything: servidor MCP `rea` y skill para investigar aplicaciones sin su código fuente. | `investigador-apps` | `reverse-engineer-anything` |
| superpowers | Conjunto de skills de método (diseñar, probar primero, depurar, verificar, pedir revisión). | `pesado`, `constructor`, `verificador` y la sesión principal | `superpowers:brainstorming`, `superpowers:systematic-debugging`, `superpowers:test-driven-development`, `superpowers:verification-before-completion`, `superpowers:requesting-code-review` |

## Sin skill de plugin
`ligero`, `explorador` y `conector-llm` solo usan lo suyo (tareas mecánicas, graphify, analítica de OpenRouter). `revisor` e `investigador-apps` no cargan skills de superpowers porque ya tienen la suya.

## Superpowers: lo que se deja fuera
`finishing-a-development-branch`, `using-git-worktrees`, `subagent-driven-development`, `writing-plans` y `executing-plans` no se asignan a nadie: chocan con "el usuario hace el commit" y con el orden de la vuelta de CLAUDE.md. `requesting-code-review` no va dentro de `revisor`: sirve a quien pide la revisión, que es la sesión principal. El detalle está en CLAUDE.md.

## Verificaciones pendientes
1. Los nombres exactos de las skills (columna de arriba) son los esperados, pero si alguna no existe con ese nombre Claude Code la omite sin avisar. Comprueba con el prompt de `agentes/LEEME.md`. En superpowers el prefijo `superpowers:` es lo que más puede variar.
2. El servidor MCP `rea` no conectó en una sesión anterior (se agotó el tiempo a los 30 s). Solo importa en la fase 2; arréglalo antes de usar `investigador-apps`.
3. graphify requiere tener instalado su comando (`graphify`) y registrado en Claude Code (`graphify install`).
4. OpenRouter solo se usa si eliges ese proveedor en `.env`; sus guías de SDK son para TypeScript, así que para Python solo aporta la analítica.
