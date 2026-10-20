# Reglas comunes de todos los goals

Cómo usar: abre `claude` dentro de esta carpeta, lee estas reglas y pega el goal de la fase que toca.

## Estructura de un buen goal
1. Estado final medible, numerado.
2. El comando exacto que lo demuestra (por ejemplo `pytest -q` termina en 0).
3. El orden en que se orquestan los subagentes (ver el equipo en CLAUDE.md).
4. Un tope de turnos (`Detente tras N turnos si no se cumple`).

## Por qué importa
El evaluador del goal solo juzga lo que aparece en la conversación. No ejecuta comandos ni lee archivos por su cuenta. Por eso cada goal pide pegar la salida real de las pruebas, y para eso existe el subagente `verificador`.

## Equipo actualizado
Los goals 02 a 05 se escribieron con el equipo anterior (ligero, pesado, verificador, revisor). Con el equipo actual, el código lo escribe `constructor` y el diseño lo decide `pesado`. Antes de lanzar cada fase, pídele a Claude que reescriba su goal con el equipo de CLAUDE.md, o pídeselo a quien lo redactó. La fase 2 es la única que usa `investigador-apps` (REA).

## Antes de lanzar un goal
- Estás en una rama de git (`git switch -c fase-N`).
- Modo de permisos: usa auto mode si quieres que corra sin preguntar cada herramienta.
- Revisa `loop/estado.md` para confirmar la fase.

## Después de cada goal
- Lee el diff tú mismo (`git diff`) antes de aceptar.
- Haz el commit manualmente. Nada de push automático.

## Comandos útiles
- `/goal` — ver el estado del goal activo
- `/goal clear` — cancelarlo
- `/tasks` — ver qué subagentes corren y con qué modelo y esfuerzo
- `claude -p "/goal ..."` — correrlo sin interfaz
