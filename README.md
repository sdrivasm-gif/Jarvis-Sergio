# Jarvis — carpeta de trabajo para el bucle

Esta carpeta tiene todo lo necesario para construir un asistente tipo Jarvis por fases con `/goal` y subagentes en Claude Code (terminal).

## Estructura

```
jarvis-loop/
├── CLAUDE.md                  reglas del proyecto (las lee Claude solo)
├── .claude/
│   ├── agents/                subagentes
│   │   ├── explorador.md      Sonnet · bajo · mapea el código (graphify)
│   │   ├── pesado.md          Opus 5.5 · alto · diseño y lo difícil (superpowers)
│   │   ├── conector-llm.md    Sonnet · medio · capa del proveedor del modelo (OpenRouter)
│   │   ├── constructor.md     Opus 5.5 · alto · escribe el código (ponytail + TDD)
│   │   ├── ligero.md          Sonnet · medio · tareas mecánicas
│   │   ├── verificador.md     Sonnet · medio · corre pruebas, solo lectura
│   │   ├── revisor.md         Opus 5.5 · alto · revisa el diff, solo lectura
│   │   └── investigador-apps.md  Opus 5.5 · alto · apps externas con REA (fase 2)
│   └── settings.json          permisos del proyecto
├── agentes/                   copia de los subagentes para llevar a .claude/agents/ (ver LEEME.md)
├── goals/                     un goal listo para pegar por fase
├── loop/                      estado, bitácora y backlog (memoria entre goals)
├── docs/                      plan, plugins y decisiones/
├── jarvis/                    aquí irá el código
└── tests/
```

## Cómo empezar (Windows, cmd)

1. Copia esta carpeta a tu disco, por ejemplo `C:\proyectos\jarvis-loop`.
2. Copia `.env.example` como `.env` y completa tus claves (nunca las subas a git).
3. En la carpeta, ejecuta:
   ```
   git init
   git switch -c fase-1
   claude
   ```
4. Dentro de Claude Code, usa `/tasks` más adelante para comprobar qué modelo y esfuerzo usa cada subagente.
5. Abre `goals/00-reglas-comunes.md`, luego pega el goal de `goals/01-nucleo.md`.
6. Al terminar cada fase: revisa el diff, haz commit y pasa al siguiente goal.

## Requisitos
- Claude Code 2.1.139 o superior (para `/goal`).
- Los subagentes se detectan solos si `.claude/agents/` existía al abrir la sesión.
- Node.js en el PATH si usas el plugin ponytail.
