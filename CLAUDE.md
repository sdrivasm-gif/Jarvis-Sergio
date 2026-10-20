# Proyecto Jarvis

Asistente personal por voz y texto, construido por fases con goals de Claude Code.

## Idioma y lenguaje
- Habla y documenta en español. Los nombres en el código van en inglés o español, pero de forma consistente.
- Lenguaje por defecto: Python 3.11+. Si se decide otro, anótalo en docs/decisiones/.

## Cómo se trabaja (el bucle)
1. Antes de empezar, lee `loop/estado.md` para saber en qué fase estás.
2. Cada goal cierra UNA fase con una condición verificable (ver `goals/`).
3. La sesión principal orquesta y reparte el trabajo entre los subagentes.
4. Antes de dar un goal por cumplido, pega en la conversación la salida literal de las pruebas (la entrega el `verificador`).
5. Al final de cada vuelta actualiza `loop/estado.md` y añade una línea a `loop/bitacora.md`.

## Equipo de subagentes

| Subagente | Modelo y esfuerzo | Skill o plugin | Para qué |
|---|---|---|---|
| `explorador` | Sonnet · bajo | graphify | mapear el código existente, solo lectura |
| `pesado` | Opus 5.5 · alto | superpowers (brainstorming, systematic-debugging) | diseño y decisiones difíciles, escribe en docs/ |
| `constructor` | Opus 5.5 · alto | ponytail + superpowers (test-driven-development) | escribe el código: primero el test, luego el mínimo necesario |
| `conector-llm` | Sonnet · medio | OpenRouter | capa del proveedor del modelo, costo y latencia |
| `ligero` | Sonnet · medio | — | estructura, tests simples, README |
| `verificador` | Sonnet · medio | superpowers (verification-before-completion) | corre pytest y entrega la evidencia literal |
| `revisor` | Opus 5.5 · alto | ponytail (review) | revisa el diff, solo lectura |
| `investigador-apps` | Opus 5.5 · alto | REA | investiga cómo abrir o controlar una app (solo fase 2) |

## Orden de una vuelta
1. `explorador` mapea lo que ya existe (se omite si el repositorio está vacío).
2. `pesado` decide el diseño y deja la especificación en `loop/estado.md`.
3. `conector-llm` o `investigador-apps` solo cuando el trabajo toque el proveedor del modelo o una app externa.
4. `constructor` escribe el código; `ligero` hace lo mecánico.
5. `verificador` corre las pruebas y pega la salida.
6. `revisor` revisa el diff. Si dice CAMBIOS REQUERIDOS, vuelve al paso 4.

## Superpowers: qué se usa y qué no
Este archivo manda sobre cualquier skill de superpowers. Si una skill contradice una regla de aquí, gana CLAUDE.md.

Se usan:
- `brainstorming` y `systematic-debugging` → `pesado`. En un goal no preguntan al usuario: lo que falte se anota en `loop/estado.md` como PREGUNTA PARA EL USUARIO. El diseño va a `docs/decisiones/`.
- `test-driven-development` → `constructor`, junto con ponytail: primero el test que falla, luego el mínimo código que lo pasa.
- `verification-before-completion` → `verificador`: un CUMPLE solo con salida de un comando de esa misma pasada.
- `requesting-code-review` → la sesión principal, al llamar a `revisor`: indicar qué se implementó, qué pedía el goal y qué diff revisar. Sin commits todavía, el diff es `git diff` más `git status`.
- `brainstorming` también con el usuario, antes de lanzar un goal, si la fase aún no tiene diseño claro.

No se usan, porque chocan con este proyecto:
- `finishing-a-development-branch` y `using-git-worktrees`: el usuario hace los commits y trabaja en una sola rama.
- `subagent-driven-development`, `writing-plans` y `executing-plans`: el orden de la vuelta y los subagentes ya están definidos arriba, y esas skills guardan planes en `docs/superpowers/` y piden commits.

## Reglas de código
- Lo mínimo que funcione (ponytail): no agregues abstracciones, dependencias ni funciones que nadie pidió. Cada atajo se marca con un comentario `ponytail:` que diga cómo mejorarlo.
- Agregar una herramienta nueva a Jarvis = crear un solo archivo en `jarvis/tools/`.
- Decisiones importantes: un archivo corto en `docs/decisiones/`.
- Los tests nunca llaman a una API real: usan un cliente simulado.

## Seguridad (no negociable)
- Ninguna clave, token ni contraseña en el código, logs o commits. Todo va en `.env` (que no se commitea y no se lee).
- Toda acción con efectos reales (enviar correo o mensajes, borrar, comprar, publicar, modificar calendario) pide confirmación explícita del usuario antes de ejecutarse.
- Las pruebas usan datos de mentira, nunca cuentas reales.
- Trabaja en una rama y no hagas commit ni push; el usuario revisa el diff y hace el commit.
- REA solo se usa con apps instaladas en este equipo y para entender cómo controlarlas, sin evadir licencias ni protecciones.
