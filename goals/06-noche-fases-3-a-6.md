# Goal de la noche — fases 3 a 6 en una sola corrida

Reemplaza a los goals 03, 04 y 05 antiguos. Orden: 3 Conocimiento e integraciones, 4 Memoria y parte del día, 5 Voz, 6 Interfaz.

## Antes de dormir

1. La fase 2 debe estar terminada, revisada por ti y commiteada:
   ```powershell
   cd "$env:USERPROFILE\Documents\jarvis-loop"
   git status --short
   git add -A
   git commit -m "Fase 2: herramientas y personalidad"
   git tag v0.2-fase-2
   git push
   git push origin --tags
   git switch -c fase-3
   ```
2. El computador no debe dormirse: conéctalo al cargador y en Configuración > Sistema > Energía pon "Suspender: Nunca" mientras dure la corrida.
3. Abre `claude` en la carpeta del proyecto, con auto mode activado, y pega el goal.

## Goal (pegar en Claude Code)

```text
/goal Fases 3 a 6 del proyecto Jarvis en esta carpeta, en orden y sin preguntarme nada porque estaré durmiendo. Primero confirma que estás en la rama `fase-3` (créala si no existe), lee CLAUDE.md, loop/estado.md y docs/decisiones/, y comprueba que la fase 2 figura cerrada en loop/estado.md; si no, ciérrala antes. REGLAS: una fase se cierra solo cuando `pytest -q` termina en 0 sin claves ni red (el verificador pega la salida literal ejecutada en esa pasada) y el revisor responde APROBADO. Si el revisor pide cambios, corrige y repite; tras 3 vueltas sin APROBADO anota la fase como BLOQUEADA en loop/estado.md y sigue con la siguiente que no dependa de ella. Lo que necesite una decisión mía, una clave o una cuenta real se anota como PENDIENTE PARA SERGIO y se sigue con lo demás. Ningún test usa red, micrófono, cuentas reales ni carpetas fuera de tmp_path. Toda acción con efectos reales exige confirmación explícita y tiene su test. Ninguna clave en código, logs ni memoria. EXCEPCIÓN solo para este goal: al cerrar cada fase la sesión principal (no los subagentes) hace un commit local `Fase N: resumen` con la etiqueta `v0.N-faseN`; nunca push. Si un commit se bloquea, sigue sin él y anótalo. FASE 3: (a) Jarvis resuelve dudas generales con el modelo y tiene herramientas de clima (Open-Meteo, sin clave, ciudad por defecto Piura configurable en .env) y de búsqueda web si no existe; (b) jarvis/integrations/ con calendario, correo y Drive, cada uno en su archivo con cliente simulado en tests/, lectura libre (eventos de hoy, buscar correos, buscar archivos) y crear, enviar, compartir o borrar con requiere_confirmacion y un test por acción; (c) un test busca patrones de claves en el repositorio. FASE 4: (a) memoria persistente en datos/ que sobrevive reinicios, con borrado de un recuerdo o de todo con confirmación y un filtro que nunca guarda claves, contraseñas ni tarjetas (test); (b) recordatorios con fecha y hora, con test de reloj simulado que prueba que se disparan una sola vez; (c) "parte del día": comando /hoy y herramienta que juntan eventos de hoy, correos pendientes, notas y recordatorios y los resumen con el tono de jarvis/personalidad.md, probados con datos de mentira. FASE 5: voz a texto y texto a voz en español con motores locales sin clave elegidos por "pesado" y anotados en docs/decisiones/, palabra de activación configurable en .env, voz desactivable (Jarvis sigue solo con texto), tests con motores simulados y audios de ejemplo en tests/audio/; las pruebas con motores reales son opcionales y se saltan si faltan. FASE 6: página local con estilo HUD (`python -m jarvis --ui`, servidor mínimo en Python) que se abre como ventana de app con `msedge --app=URL` y, si no existe Edge, en el navegador, más un script que crea un acceso directo de escritorio: círculo animado que cambia al escuchar y al hablar, subtítulos, entrada de texto y panel con los pendientes del día; con tests del servidor y un smoke test de arranque, sin dependencias pesadas de frontend. EQUIPO por fase: "explorador" (graphify) mapea; "pesado" (brainstorming, sin preguntarme) diseña y anota en docs/decisiones/ y loop/estado.md; "conector-llm" solo si toca el proveedor; "constructor" (ponytail y test-driven-development) escribe el código; "ligero" hace tests simples, configuración y documentación; "verificador" (verification-before-completion) pega `pytest -q`; "revisor" revisa el diff con ponytail-review, con revisión de seguridad extra en la fase 3. No uses "investigador-apps" ni las skills de superpowers finishing-a-development-branch, using-git-worktrees, subagent-driven-development, writing-plans ni executing-plans; si una skill contradice CLAUDE.md, manda CLAUDE.md salvo la excepción de commits. Tras cada fase actualiza loop/estado.md, loop/bitacora.md y jarvis/README.md. ESTADO FINAL: las fases 3 a 6 figuran cerradas o BLOQUEADAS en loop/estado.md, la última salida literal de `pytest -q` termina en 0, y loop/estado.md resume qué quedó listo, qué es PENDIENTE PARA SERGIO y cómo probar cada cosa a mano. Detente tras 160 turnos si no se cumple.
```

## Al despertar
- Lee `loop/estado.md`: ahí está qué quedó cerrado, bloqueado y pendiente.
- `git log --oneline` y `git tag` muestran un punto de retorno por fase. Para volver a uno: `git switch --detach v0.3-fase3`.
- Revisa el diff y sube todo: `git push -u origin fase-3` y `git push origin --tags`.
- Pruebas manuales tuyas: `python -m jarvis` (clima, /hoy), voz con micrófono real y `python -m jarvis --ui`.
