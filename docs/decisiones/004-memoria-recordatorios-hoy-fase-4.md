# 004 — Memoria, recordatorios y parte del día (fase 4)

Fecha: 2026-10-20 · Autor: pesado · Estado: aceptada

## Contexto
La fase 4 (goals/06-noche-fases-3-a-6.md) pide: (a) una memoria persistente en `datos/` que sobreviva a los reinicios, con borrado de un recuerdo o de todos (con confirmación) y un filtro que nunca guarde claves, contraseñas ni tarjetas; (b) recordatorios con fecha y hora que se disparen una sola vez, probados con un reloj simulado; (c) un "parte del día" (`/hoy` y una herramienta) que junte los eventos de hoy, los correos pendientes, las notas y los recordatorios, y los resuma con el tono de `personalidad.md`. Restricciones: un archivo por herramienta, sin dependencias nuevas, sin red en los tests y con `tmp_path` para todos los datos. `cargar_herramientas` ejecuta cada `tools/*.py` aislado, así que la lógica compartida va en módulos de `jarvis/` y se importa como `from jarvis import memoria`.

## Decisiones
1. **Módulos de lógica en `jarvis/`, sin herramientas dentro:** `datos.py` (carpeta `JARVIS_DATOS` y listas JSON), `secretos.py` (el filtro), `memoria.py`, `recordatorios.py` y `hoy.py`. `jarvis` ya es un paquete en `pyproject.toml`, así que estos módulos entran sin tocarlo.
2. **Persistencia: un archivo JSON por tipo de dato** (`datos/memoria.json` y `datos/recordatorios.json`), cada uno con una lista de diccionarios. Se escribe entero en un `.tmp` y luego se hace `os.replace`, así un corte nunca deja el archivo a medias. Sin caché en memoria: cada operación lee el disco, de modo que "reiniciar" no cambia nada. Si el archivo está dañado, se lanza un error claro y no se sobrescribe. Un `threading.Lock` en `datos.py` protege cada lectura-modificación-escritura (la voz y la UI de las fases 5 y 6 podrán llamar desde otro hilo).
3. **Filtro de secretos en la capa de datos, no en la herramienta.** `secretos.detectar(texto)` devuelve el tipo de secreto o `None`. Antes, normaliza el texto con NFKC. Detecta: claves privadas PEM; prefijos de claves y tokens (`sk-ant-`, `sk-or-`, `sk-proj-`, `sk-`, `AIza`, `ya29.`, `1//0`, `GOCSPX-`, `ghp_` y similares, `github_pat_`, `AKIA`, `xox?-`, JWT `eyJ…`, `Bearer …`); contraseñas etiquetadas (`contraseña|password|clave|pin|token|secreto|api key|cvv` seguidas, a menos de tres palabras, de `:`, `=`, "es" o "is", y luego algo); y secuencias de 13 a 19 dígitos, con espacios o guiones, que pasen Luhn. Lo usan `memoria.guardar` y `recordatorios.crear`, y también `notas` al crear (una línea), porque guarda en `datos/` igual que ellos. Si encuentra algo, **rechaza el texto entero**, no lo enmascara, y el mensaje nunca repite el secreto. Ante la duda, prefiere un falso positivo ("la clave del éxito es…" se rechaza).
4. **La memoria entra en el prompt del sistema como datos.** `bucle.sistema_completo() = cargar_sistema() + memoria.para_sistema()`. `cargar_sistema` y `personalidad.md` no cambian. Sin recuerdos, el bloque es `""` y el sistema queda idéntico al de antes, así que los tests actuales siguen valiendo. Se mandan los últimos 20 recuerdos, cada uno en una línea `- [id] texto` (los espacios y saltos de línea se colapsan al guardar y al mostrar, así ningún recuerdo puede inventarse líneas). El encabezado dice que son datos sobre el señor y no instrucciones. Así la memoria funciona también con `claude-cli`, que no tiene herramientas. Si el archivo está dañado, el bloque es `""` y el turno sigue.
5. **Herramientas (6 nuevas, 19 en total):**
   - `memoria`: guardar, buscar o listar. Sin confirmación, porque solo escribe en `datos/`.
   - `memoria_borrar`: borra un recuerdo. Con confirmación.
   - `memoria_borrar_todo`: borra todos los recuerdos. Con confirmación.
   - `recordatorios`: crear o listar. Sin confirmación.
   - `recordatorio_cancelar`: cancela un recordatorio. Con confirmación.
   - `parte_del_dia`: solo lee. Sin confirmación.

   Para borrar o cancelar, el modelo debe pasar **el id y el texto exacto**. La confirmación los muestra, y si el texto no coincide con lo guardado (sin distinguir mayúsculas ni espacios), no se borra nada. Así lo que el señor confirma es exactamente lo que se borra, no un id opaco.
6. **Recordatorios: `vencidos(ahora)` reutilizable y sin reloj propio.** Toma los pendientes con `cuando <= ahora`, los marca `disparado` y **guarda antes de devolverlos** (como mucho una vez, aunque Jarvis se caiga justo después). Si no vence nada, no escribe. Lo que venció con Jarvis cerrado se avisa en la siguiente consulta, con su hora original. La hora es local y sin zona horaria, en ISO. `crear` acepta `cuando` (`AAAA-MM-DD HH:MM`) o `en_minutos`, uno de los dos, y rechaza horas pasadas. Cancelar elimina el recordatorio del archivo.
7. **Disparo en terminal: comprobación síncrona, sin hilo.** `conversar(..., reloj=datetime.now)` llama a `avisar_vencidos(salida, reloj())` antes de cada `input()`, también al arrancar. Basta para la condición del goal y se prueba de forma determinista. La voz (fase 5) sustituirá el `input()` bloqueante por un bucle de escucha, y la UI (fase 6) consultará `vencidos()` desde el servidor: las dos reutilizan la misma función.
8. **Parte del día en `jarvis/hoy.py`, en dos pasos.** `reunir(ahora)` arma un texto de 4 secciones reutilizando las herramientas existentes (`calendario_eventos.ejecutar(fecha)`, `correo_buscar.ejecutar("is:unread in:inbox")`, las últimas 5 de `notas` y `recordatorios.del_dia`). Si una sección falla o devuelve `"Error: ..."`, se muestra `"No disponible: ..."` y el resto sigue, por ejemplo sin Google configurado. `resumir(cliente, datos, sistema)` hace **una llamada `responder` sin herramientas** (`[]`), así que `/hoy` también funciona con `claude-cli`. Los datos van entre `<datos>` y `</datos>`, con un aviso de que los correos y los títulos de eventos son de terceros y no instrucciones. Dentro de los datos, `<` y `>` se cambian por `‹` y `›`, para que un correo no pueda cerrar el bloque. La herramienta `parte_del_dia` devuelve los datos envueltos igual, y el modelo los resume en el turno normal. `/hoy` no entra en el historial.
9. **Tests aislados:** un fixture autouse en `conftest.py` apunta `JARVIS_DATOS` a `tmp_path / "datos"`. El "reinicio" se simula con `importlib.reload` del módulo, que lee de nuevo el disco. El reloj siempre se inyecta: `ahora` como argumento, o `ahora()` en cada herramienta, que los tests parchean.

## Alternativas descartadas
- **JSONL de solo añadir:** borrar y marcar como disparado obliga a reescribir igual, y además habría que compactar.
- **SQLite:** más robusto, pero no se edita a mano y no hace falta con cientos de registros.
- **Enmascarar el secreto y guardar el resto:** puede dejar escapar trozos, y además engaña al usuario.
- **Memoria solo por herramienta, sin prompt:** con `claude-cli` no serviría, y el modelo tendría que acordarse de buscar.
- **Memoria relevante por búsqueda o embeddings:** necesita dependencias y nadie lo pidió.
- **Hilo vigía en la terminal:** con `input()` bloqueado es lo único que avisa en tiempo real, pero hace los tests no deterministas y la fase 5 rehace ese bucle. Queda como `ponytail:`.
- **`sched` o `threading.Timer` por recordatorio:** se pierden al reiniciar.
- **Borrar o cancelar solo con el id:** el señor confirmaría algo que no ve.
- **Una sola herramienta `memoria` que también borre:** la confirmación dependería de la acción (lo mismo que se descartó en la decisión 003).
- **`/hoy` dentro del turno normal, con herramientas:** con `claude-cli` no funcionaría, y además expone las herramientas a los correos.

## Consecuencias
- Hay 19 herramientas. Piden confirmación: `abrir_app`, `calendario_borrar`, `calendario_crear`, `correo_enviar`, `drive_compartir`, `memoria_borrar`, `memoria_borrar_todo` y `recordatorio_cancelar`.
- Los últimos 20 recuerdos viajan al proveedor del modelo en cada turno (privacidad: el filtro evita los secretos, pero no los datos personales).
- Riesgo: guardar un recuerdo no pide confirmación. Un correo malicioso podría convencer al modelo de guardar una "orden", que acabaría en el prompt. La mitigación es que el bloque está marcado como datos, que el texto queda en una sola línea y que toda acción con efectos sigue pidiendo `[s/N]`. Si Sergio quiere, se cambia una línea (PENDIENTE).
- En la terminal, un recordatorio avisa la próxima vez que se muestra `tú>` (al enviar algo o pulsar Enter), no mientras el señor está callado.
- El filtro tiene falsos positivos (rechaza) y falsos negativos (contraseñas sin etiqueta, como "hunter2" a secas). La defensa es buena, pero no perfecta.
- Si hay dos procesos de Jarvis a la vez, el cerrojo no los coordina (`ponytail:`).
- No cambian: `personalidad.md`, `config.py`, `__main__.py`, `tools/__init__.py`, `pyproject.toml` ni las herramientas de la fase 3. `notas.py` solo añade el filtro.
