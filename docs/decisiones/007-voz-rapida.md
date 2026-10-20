# 007 — Voz rápida: voces neurales, cola de frases y transcripción sin `av` (fase 7)

Fecha: 2026-10-20 · Autor: pesado · Estado: aceptada

## Contexto
El goal es goals/07-voz-rapida.md. Hay dos problemas:
- La voz SAPI suena lenta y antigua.
- La transcripción falla con `open() got an unexpected keyword argument 'metadata_errors'`.

**Diagnóstico del error de `av`** (evidencia en `.venv`, faster-whisper 1.2.1):
- `faster_whisper/audio.py:46`: `decode_audio` llama a `av.open(input_file, mode="r", metadata_errors="ignore")`.
- `faster_whisper/transcribe.py:875`: `if not isinstance(audio, np.ndarray): audio = decode_audio(...)`.
- `voz.transcriptor_whisper` le pasa un `io.BytesIO` (`wav_en_memoria`), así que **siempre** pasa por `decode_audio`. Con una versión de `av` que ya no acepta ese argumento, falla.

Si se le pasa un `np.ndarray` float32, `decode_audio` no se ejecuta. `faster_whisper/audio.py` sigue haciendo `import av` al importarse, así que `av` sigue instalado (es dependencia de faster-whisper), pero nunca se llama.

**Estado de partida** (mapa del explorador):
- `conversar` solo transmite por streaming si el cliente tiene `al_texto` (hoy solo `ClienteClaudeCLI`). La voz y la UI pasan `fragmento=None`.
- `HablanteSAPI.decir` bloquea y lanza un PowerShell por llamada.
- `OyenteLocal` abre y cierra el micrófono en cada `escuchar`. Todo es secuencial y en un solo hilo, y por eso hoy la voz y la escucha no se pisan.
- `HablanteConEstado` (UI) marca "hablando" mientras `decir` bloquea.

## Decisiones
1. **Transcripción sin `av`.** `voz.pcm_a_float32(pcm) -> np.ndarray` hace `np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0`. Importa numpy dentro de la función, para que importar `jarvis.voz` no cargue numpy. `transcriptor_whisper` le pasa ese arreglo a `transcribe`. Se borran `wav_en_memoria` y su test (código muerto). El audio del usuario sigue sin tocar el disco.
2. **Tres motores** con `JARVIS_VOZ_MOTOR=edge|sapi|elevenlabs` (por defecto `edge`):
   - edge-tts: voces neurales de Microsoft, sin clave, con internet. `JARVIS_VOZ_NOMBRE` (por defecto `es-MX-JorgeNeural`), `JARVIS_VOZ_VELOCIDAD` (`+15%`) y `JARVIS_VOZ_TONO` (`-5Hz`).
   - SAPI: el `HablanteSAPI` de siempre, sin cambios.
   - ElevenLabs: opcional y apagado por defecto.
3. **Reproducción: MCI de Windows (`winmm.mciSendStringW`) vía `ctypes`.** Biblioteca estándar, sin dependencias y sin procesos.
   - Edge y ElevenLabs entregan MP3. Cada frase se escribe en un archivo temporal propio en `%TEMP%\jarvis-voz\` (`tempfile.mkstemp`) y se reproduce con `open "<ruta>" type mpegvideo alias jarvis_voz` → `play` → sondeo de `status … mode` cada 50 ms → `close`.
   - **Todas las órdenes MCI salen del hilo de reproducción.**
   - Para cortar: la función `parar()` que recibe el reproductor pasa a ser verdadera y, en ≤ 50 ms, el mismo hilo manda `stop` y `close`.
   - El archivo se borra justo después de sonar o al descartarlo. Al arrancar se borran los `*.mp3` que hayan quedado de una sesión anterior que se cerró de golpe.
   - La orden MCI solo lleva una ruta que generamos nosotros, entre comillas (se rechaza si contiene `"`). **El texto hablado nunca va en un comando.**
   - Si MCI falla (sin códec, sin salida de audio o fuera de Windows), cuenta como fallo del motor: respaldo SAPI (decisión 8).
4. **Cola de frases (`habla.HablanteCola`)**:
   - Dos hilos daemon, creados la primera vez que se encola: uno sintetiza y otro reproduce.
   - Se comunican con `queue.Queue` (las frases) y `queue.Queue(maxsize=1)` (los audios). Así, mientras suena la frase N, se sintetiza la N+1 (prefetch de una).
   - Edge es asyncio: el hilo de síntesis hace `asyncio.run(wait_for(Communicate(...).save(ruta), 10 s))` por frase, con un bucle de eventos propio en ese hilo.
   - El orden se conserva porque todo pasa por las dos colas: también las frases descartadas o que van al respaldo.
   - Cortar sube un contador de generación: lo encolado antes se descarta sin esperar a nadie.
   - Al cerrar Jarvis no hay `join`: el último `decir` ("Hasta luego.") ya esperó a que la cola se vaciara, y los hilos daemon mueren con el proceso.
5. **Contrato del hablante.** `encolar(frase)` no bloquea; `esperar()` bloquea hasta que suena todo lo encolado; `cortar()` calla y descarta; `decir(texto) = trocear + encolar + esperar`.
   - Con `decir` bloqueante no cambian `confirmar_por_voz`, `"¿Sí, señor?"` ni `HablanteConEstado.decir`.
   - **Invariante:** todo camino público termina en `esperar()` antes de devolver el control a `conversar`. Además, `entrada_por_voz` llama a `hablante.esperar()` justo antes de `oyente.escuchar()` (defensa en profundidad). El micrófono nunca se abre mientras suena Jarvis.
   - `esperar()` espera en trozos de 0,1 s (para que Ctrl+C entre en Windows). Ante cualquier excepción, KeyboardInterrupt incluida, llama a `cortar()` y la relanza. Si un hilo murió, lanza `ErrorVoz` en vez de colgarse.
6. **Troceado: `voz.partir_frases(texto, final=False) -> (frases, resto)`, función pura e incremental.** Quien la usa guarda `resto` y la vuelve a llamar con `resto + trozo`.
   - Corta en `. ! ? …` (con comillas o paréntesis de cierre) **seguidos de espacio**, y en salto de línea. Así no corta en URL, decimales (`3.5`) ni `www.x.com`.
   - No corta tras abreviaturas (`Sr.`, `Dra.`, `p. ej.`…), tras una sola letra ni tras un número (marcadores de lista).
   - Une las frases de menos de 20 caracteres con la siguiente. Una frase de más de 300 caracteres sin cierre se corta en el último espacio.
   - No corta mientras haya un bloque ``` sin cerrar. Con `final=True` sale también el resto.
   - Cada frase se limpia con `limpiar_para_voz` antes de encolarse. El tope `MAX_HABLADO` se aplica al **total** del turno: al pasarlo se encola "El resto está en pantalla." y se calla.
7. **Conexión con `conversar` (un cambio mínimo en `bucle.py`)**:
   - `voz.FragmentoDeVoz(hablante, mostrar)` es el `fragmento` en modo voz, tanto en terminal como en UI.
   - El primer trozo de cada turno (el prefijo `"jarvis> "`) no se dice. Los demás se acumulan para la pantalla y alimentan el troceador.
   - Al terminar el turno, `fin_de_turno()` dice lo que falta, muestra la línea completa con `mostrar` (igual que hoy `salida`) y espera a que termine de sonar. Nunca lanza `Exception`: un error se muestra como "(no pude hablar: …)".
   - **Por qué hay que tocar `bucle.py`:** el `fragmento("\n")` final no se distingue de un delta `"\n"` del modelo. Por eso `conversar` cierra el turno con `cerrar_turno(fragmento)` = `fragmento("\n")` y luego `fragmento.fin_de_turno()` si existe. La firma de `conversar` no cambia y, con funciones normales, el comportamiento es idéntico.
   - **Clientes sin streaming** (ClienteClaude, OpenRouter, Falso): la respuesta llega entera a `salida_por_voz` (sin cambios), que llama a `decir`. `decir` la trocea y la encola, así que el primer audio solo depende de sintetizar la primera frase.
   - Dar `al_texto` a otros clientes queda fuera de alcance (`ponytail:`, decisión de Sergio).
8. **Respaldo dentro de la cola.** Si la síntesis o la reproducción fallan (falta `edge_tts`, sin red, tiempo agotado de 10 s, audio vacío, error HTTP o de MCI), la cola queda "caída" el resto de la sesión, sin reintentos.
   - **Ninguna frase se pierde:** la que falló y las siguientes se juntan y, en `esperar()`, se dicen con SAPI en **un solo** `decir`, desde el hilo principal, así que Ctrl+C mata ese PowerShell.
   - El aviso sale una vez por `mostrar`, con la causa (`ErrorVoz` propio o solo el nombre del tipo de excepción, nunca su texto: los errores de red podrían llevar URL).
   - Si falta `edge_tts` al arrancar, se avisa una vez y se usa SAPI directamente.
   - ElevenLabs también cae a SAPI y no a edge: casi siempre falla por red o por cuota, y una cadena de tres motores es más complicada.
   - Si falla el propio SAPI, `esperar` lanza `ErrorVoz` y `decir_sin_fallar` lo muestra.
9. **`JARVIS_VOZ_MOTOR=sapi`** devuelve una `HablanteCola` sin sintetizador: no crea hilos, junta lo encolado y lo dice con un solo PowerShell por turno. Es exactamente lo de hoy, sin un proceso por frase.
10. **Configuración estricta.** Solo se validan las variables del motor elegido. Un valor inválido es `ErrorVoz` con un mensaje claro y la voz se desactiva, como con `JARVIS_VOZ_UMBRAL`.
    - Motor: uno de los tres, sin distinguir mayúsculas.
    - Velocidad: `^[+-]\d{1,3}%$`. Tono: `^[+-]\d{1,3}Hz$`. Nombre: `^[A-Za-z0-9-]{5,60}$`.
    - ElevenLabs: hacen falta `ELEVENLABS_API_KEY` y `ELEVENLABS_VOICE_ID` (`^[A-Za-z0-9]{10,40}$`); `ELEVENLABS_MODEL_ID` es opcional (por defecto `eleven_flash_v2_5`, el de menor latencia y con español).
    - Los mensajes nombran la variable, **nunca el valor de la clave**.
11. **ElevenLabs por su API REST oficial con `urllib`**, sin SDK ni dependencias.
    - Petición: `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128` con el JSON `{"text", "model_id"}`.
    - La clave va **solo** en la cabecera `xi-api-key`: ni en la URL, ni en los logs, ni en los errores (`raise … from None`).
    - No se toma nada del repositorio GPL AlexandreSajus/JARVIS.
12. **Un módulo nuevo, `jarvis/habla.py`**: configuración, sintetizadores, reproductor, cola y `crear_hablante`. `voz.py` (≈390 líneas) se queda con la escucha, el texto y la conexión con `conversar`, y gana `pcm_a_float32`, `partir_frases` y `FragmentoDeVoz` (≈80 líneas).
    - Dirección única: `habla` importa `jarvis.voz` como módulo (`from jarvis import voz`, y usa `voz.ErrorVoz` al llamar, porque un test recarga `voz`). `voz.motores` importa `habla` dentro de la función, como ya hace con faster-whisper.
13. **Dependencias.** El extra `voz` pasa a `["faster-whisper", "sounddevice", "numpy", "edge-tts"]`.
    - `numpy` se declara porque ahora lo importa nuestro código (ya llega con faster-whisper).
    - `av` no se toca: lo trae faster-whisper y nosotros no lo usamos.
    - Nada nuevo en `dependencies` ni en `dev`. El test de la conversión usa `pytest.importorskip("numpy")`: en este `.venv` corre (numpy 2.5.4), y sin numpy se salta en vez de romper la suite.
14. **`scripts/medir_voz.py`** usa el mismo `crear_hablante` y la misma cola.
    - Mide con `time.perf_counter` desde `decir` hasta la primera llamada a `HablanteCola.al_empezar` (que el reproductor invoca justo después de `play`) y hasta que `decir` vuelve.
    - Imprime el motor, `primer audio: X.XX s` y `total: Y.YY s`. Con SAPI imprime `n/d`.
    - Argumentos: `--motor` y `--frase`. No imprime claves.

## Alternativas descartadas
- **Fijar `av<…` o parchear faster-whisper:** dependería de versiones ajenas. Con el arreglo de numpy el problema desaparece con cualquier `av`.
- **miniaudio** (decodifica MP3 y reproduce desde memoria, sin archivo temporal): es una dependencia nativa más. Queda como plan B si MCI da problemas en el equipo de Sergio.
- **sounddevice + decodificar MP3:** necesitaría `av` (justo lo que se quiere evitar) u otro decodificador.
- **PowerShell persistente con `MediaPlayer`:** hay que hacer IPC por stdin, gestionar el ciclo de vida del proceso y no aporta nada frente a MCI.
- **`winsound`:** solo reproduce WAV y en modo síncrono, y edge-tts solo da MP3.
- **Un único hilo** que sintetiza y reproduce: no puede sintetizar la frase N+1 mientras bloquea reproduciendo la N cuando las frases llegan poco a poco.
- **Un bucle asyncio persistente** (una conexión de websocket reutilizada): ahorraría ≈100–300 ms por frase, pero el prefetch ya oculta ese coste salvo en la primera. Queda como `ponytail:`.
- **Detectar el fin de turno sin tocar `bucle.py`** (vaciar el troceador al siguiente `entrada`, `salida` o `confirmar`): habría que envolver tres piezas en terminal y otras tres en la UI, con más acoplamiento que un gancho de cuatro líneas.
- **Tratar el `"\n"` final como fin de turno:** un delta `"\n"` del modelo bloquearía a mitad del streaming y partiría el subtítulo de la UI.
- **Ir mostrando en la UI los subtítulos a medida que llegan:** `Sesion` no actualiza mensajes. Ver Consecuencias.
- **Respaldo en cadena ElevenLabs → edge → SAPI**, o reintentar edge cada N minutos: más estados y más tests. Hoy basta con reiniciar Jarvis (`ponytail:`).
- **El SDK `elevenlabs`:** añade dependencias para una sola petición POST.
- **Un SAPI por frase en modo `sapi`:** varias pausas de arranque de 0,5–1 s por respuesta. Se mantiene un solo proceso por turno.

## Consecuencias
- **Privacidad:** con edge, el texto que Jarvis dice (respuestas, avisos y confirmaciones, incluido el cuerpo de un correo que se va a enviar) va a los servidores de Microsoft para sintetizarlo; con ElevenLabs, a los suyos. El audio del usuario sigue sin salir del equipo. El MP3 de Jarvis pasa unos segundos por `%TEMP%\jarvis-voz\` y se borra. Para no enviar nada, usar `JARVIS_VOZ_MOTOR=sapi`.
- **Fragilidad de edge-tts:** usa el servicio de lectura en voz alta de Edge, que no es una API pública con garantías. Puede romperse o cambiar, y por eso existe el respaldo SAPI.
- **El streaming real solo existe con `claude-cli`.** Con `claude` u `openrouter` (los que tienen herramientas), Jarvis empieza a hablar cuando llega la respuesta completa, pero solo espera a sintetizar la primera frase, no el texto entero.
- **UI con voz:** el subtítulo completo aparece al terminar la respuesta, mientras la voz ya empezó. El círculo pasa a "hablando" con la primera frase y vuelve al estado anterior al terminar de sonar.
- **Ctrl+C a mitad del streaming:** antes de "Hasta luego." se dicen las frases ya encoladas (normalmente una o dos). Un segundo Ctrl+C corta al momento (`ponytail:`).
- **En respaldo,** el resto del turno se dice con SAPI cuando la respuesta termina, no al momento.
- Hay hilos daemon en el proceso de Jarvis. Los tests los controlan con eventos (`threading.Event`), nunca con `sleep` fijos.
- **Riesgos a verificar a mano** con `scripts/medir_voz.py`:
  - que MCI `mpegvideo` reproduzca desde un hilo que no es el principal;
  - la latencia de `open` (≈50–300 ms);
  - el primer audio de edge (estimado en ≈0,6–1,2 s tras tener la primera frase).
  Si MCI falla, se oye SAPI y aparece el aviso: nunca queda en silencio.
- **Cambios en tests existentes** (son cambios de comportamiento buscados):
  - `piezas_de_voz` y `piezas_ui_voz` ya no devuelven `fragmento=None`;
  - `motores` devuelve una `HablanteCola`;
  - `test_preparar` ve además el aviso de que falta edge-tts;
  - el test del transcriptor espera un arreglo float32;
  - la lambda de `voz.motores` en `test_main` acepta `mostrar`.
