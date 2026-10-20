# Fase 2 — Herramientas

Requisito: fase 1 cerrada y commiteada (`git log` muestra el commit de la fase 1) y estar en la rama `fase-2`.

## Antes de lanzar

```powershell
cd "$env:USERPROFILE\Documents\jarvis-loop"
git add -A
git commit -m "Fase 1: núcleo de Jarvis"
git switch -c fase-2
claude
```

## Goal (pegar en Claude Code)

```text
/goal Fase 2 del proyecto Jarvis en esta carpeta. Primero confirma que estás en la rama `fase-2` (créala si no existe) y lee CLAUDE.md, loop/estado.md y docs/decisiones/. Estado final: Jarvis tiene estas cinco herramientas, cada una en su propio archivo de jarvis/tools/ siguiendo el contrato de hora.py, y cada una con al menos un test que verifica su salida esperada: (1) hora y fecha, que ya existe y solo se comprueba; (2) crear, listar y buscar notas en un archivo local dentro de una carpeta de datos configurable (JARVIS_DATOS, por defecto `datos/`, agregada a .gitignore); (3) buscar archivos por nombre dentro de una carpeta indicada, solo lectura, con tope de resultados y sin leer el contenido de los archivos ni los .env; (4) abrir una aplicación instalada en Windows por nombre; (5) búsqueda web simple, preferiblemente sin clave de API. La herramienta 4 y cualquier otra con efectos fuera de la carpeta de datos tienen requiere_confirmacion=True, y hay un test que prueba que sin confirmación explícita no se ejecuta la acción real. Ningún test abre una app real, usa la red ni toca carpetas fuera de tmp_path. `pytest -q` termina en 0 sin ninguna clave, el código cumple el estilo ponytail y el revisor responde APROBADO. Orquesta en este orden: "revisor" revisa primero jarvis/llm/claude_cli.py, que se hizo sin revisión en la fase 1, y lo que encuentre se corrige antes de seguir; "explorador" (graphify) mapea el código actual; "pesado" (con brainstorming, sin preguntarme nada) decide cómo se abre una app por nombre en Windows, qué proveedor usa la búsqueda web, el formato de las notas y cómo se prueba cada cosa sin efectos reales, y lo anota en docs/decisiones/ y en loop/estado.md; "ligero" crea las herramientas 2 y 3 con sus tests; "constructor" (Opus 5.5 con ponytail y test-driven-development: primero el test que falla) construye las herramientas 4 y 5 y cualquier ajuste al bucle o a la confirmación; "verificador" (verification-before-completion) pega la salida literal de `pytest -q` ejecutado en esa pasada y la de `python -c "from jarvis.tools import cargar_herramientas; print(sorted(cargar_herramientas()))"`, que debe listar las cinco; "revisor" revisa el diff con ponytail-review, y tú lo llamas indicando qué se implementó, qué pide este goal y el diff (`git diff` y `git status`). No uses "investigador-apps" a menos que "pesado" documente que abrir la app por nombre no es posible sin REA. No uses las skills de superpowers finishing-a-development-branch, using-git-worktrees, subagent-driven-development, writing-plans ni executing-plans; si una skill contradice CLAUDE.md, manda CLAUDE.md. Tras cada vuelta actualiza loop/estado.md y loop/bitacora.md. No hagas commit ni push. Detente tras 40 turnos si no se cumple.
```

## Cómo se verifica
- `pytest -q` termina en 0, con un test por herramienta y sin clave.
- Un test demuestra que sin confirmación no se abre la app.
- La lista de herramientas cargadas tiene las cinco.
- Prueba manual tuya: `python -m jarvis` y pedirle la hora, guardar una nota, buscar un archivo, abrir una app (te debe pedir confirmación) y hacer una búsqueda web.
- El revisor responde APROBADO.
