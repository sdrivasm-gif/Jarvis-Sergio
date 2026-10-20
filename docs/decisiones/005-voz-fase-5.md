# 005 — Voz: voz a texto, texto a voz y palabra de activación (fase 5)

Fecha: 2026-10-20 · Autor: pesado · Estado: aceptada

## Contexto
La fase 5 (goals/06-noche-fases-3-a-6.md) pide voz a texto (STT) y texto a voz (TTS) en español, con motores locales y sin clave. También pide una palabra de activación configurable en `.env` y que la voz se pueda desactivar, de modo que Jarvis siga funcionando solo con texto. Los tests usan motores simulados y audios de ejemplo en `tests/audio/`. Las pruebas con motores reales son opcionales y se saltan si faltan. Ningún test puede usar el micrófono, el altavoz ni la red.

Entorno: Windows 11 y Python 3.12 (`.venv`). Hoy no hay ninguna dependencia de audio instalada. `bucle.conversar` ya acepta `entrada`, `salida`, `confirmar` y `fragmento` inyectables.

## Decisiones
1. **STT: faster-whisper, modelo `base` (≈145 MB), en CPU con int8.** Se carga perezosamente: el import va dentro de una función y el modelo se carga al arrancar en modo voz. El audio se le pasa como un WAV **en memoria** (`io.BytesIO`), así que nunca toca el disco. Se usa `language="es"`, `vad_filter=True` (descarta lo que no es voz y reduce las alucinaciones), `beam_size=1` y `initial_prompt` con la palabra de activación, para que escriba "Jarvis" bien. `JARVIS_STT_MODELO` acepta un nombre (`base`, `small`…; la primera vez se descarga una sola vez de Hugging Face, sin clave) o una carpeta local.
2. **TTS: la voz de Windows (SAPI, `System.Speech`) mediante `powershell.exe`, sin dependencias.** Hay un proceso por frase, y el texto le llega por stdin **en base64**, así que no hay forma de inyectar comandos. El script es constante y va con `-EncodedCommand`. Elige la primera voz `es-MX` instalada y, si no hay, cualquier `es-*`. Al estar en un proceso aparte, hablar se interrumpe matando ese proceso (Ctrl+C). Se usa `powershell.exe` 5.1 porque `pwsh` 7 no trae `System.Speech`.
3. **Micrófono: `sounddevice` con `RawInputStream`** a 16 kHz, mono, int16, en bloques de 30 ms. Se lee en bytes, sin numpy en nuestro código, y una lectura corta deja que Ctrl+C responda. **El flujo se abre en cada escucha y se cierra al terminar.** Así, mientras Jarvis habla, nadie graba, y al volver a escuchar no queda audio viejo con su propia voz.
4. **Detección de la frase por energía, con la biblioteca estándar** (`recortar_frase`, una función pura). Empieza tras 3 bloques seguidos con RMS ≥ `JARVIS_VOZ_UMBRAL` (400 por defecto) e incluye 300 ms previos. Termina tras 0,75 s de silencio o a los 15 s. Si en 8 s no hay voz, devuelve `None`. Se prueba de forma determinista con los WAV de `tests/audio/`.
5. **Integración sin duplicar el bucle:** `voz.piezas_de_voz(oyente, hablante, palabras)` devuelve `entrada`, `salida`, `confirmar` y `fragmento=None` para pasarlos a la `conversar` de siempre. El único cambio en `bucle.py` es que, con `fragmento=None`, no se activa el streaming, y así la respuesta llega entera a `salida`, que la muestra y la dice. Los avisos de recordatorios ya pasan por `salida`, así que también se dicen en voz alta. Como `entrada` devuelve `""` tras cada silencio de 8 s, `conversar` vuelve a llamar a `avisar_vencidos`: los recordatorios suenan casi en tiempo real sin hilos.
6. **Palabra de activación:** `JARVIS_PALABRA_ACTIVACION` (por defecto `jarvis`; admite variantes separadas por comas, por ejemplo `jarvis,yarvis`). Se compara por palabras completas, sin tildes ni mayúsculas. **La orden es lo que se dice después de la palabra.** Si solo se dice la palabra, Jarvis responde "¿Sí, señor?" y la siguiente frase es la orden. Lo que se oye sin la palabra se transcribe en local y se descarta: no se muestra ni se envía. "salir" o "adiós" equivalen a `/salir`, y "parte del día" a `/hoy`.
7. **Confirmar por voz falla a NO.** Se muestra la confirmación en pantalla y se lee en voz alta. La versión hablada sale de los mismos argumentos que `texto_confirmacion`, ya pasados por `legible`, y no se recorta ni se le quitan URLs: se oye lo que se confirma. Después se escucha una vez. Solo es un sí si, quitando la palabra de activación, **todas** las palabras son "sí" o "confirmo". El silencio, "sí, pero no", "claro", "yes", un error del micrófono o de la voz y Ctrl+C dan siempre `False`.
8. **Limpieza del texto hablado (`limpiar_para_voz`):** quita el markdown (títulos, viñetas, énfasis, tablas y código), cambia las URL por "enlace" y elimina los emojis y los caracteres de control. Corta a 1200 caracteres con "… El resto está en pantalla.". La pantalla muestra siempre el texto original.
9. **Activación:** con `python -m jarvis --voz` o `JARVIS_VOZ=on` en `.env`. Por defecto está apagada, y sin voz el comportamiento es idéntico al de hoy. Si faltan los extras, el micrófono o el modelo, se avisa por stderr y **sigue solo con texto**.
10. **Dependencias opcionales:** `[project.optional-dependencies] voz = ["faster-whisper", "sounddevice"]`. Ningún módulo de Jarvis las importa al cargarse.
11. **Tests:** usan `OyenteFalso` y `HablanteFalso`, más cuatro WAV deterministas (silencio, tono, ruido bajo y chasquido) que genera `scripts/generar_audios_prueba.py` y que se commitean. La guardia de `conftest.py` pone `sounddevice` y `pyaudio` a `None` en `sys.modules`, y los procesos ya estaban bloqueados. `tests/test_voz_real.py` solo corre si están faster-whisper y una carpeta local de modelo en `JARVIS_STT_MODELO`.

## Alternativas descartadas
- **STT con vosk** (modelo `small-es` de ≈39 MB, streaming y gramáticas): era la opción más ligera y simple, pero su vocabulario es fijo y "jarvis" no es una palabra española, con riesgo real de que nunca reconozca la palabra de activación. Además entiende peor el dictado libre. Queda como plan B si `base` va lento en la CPU de Sergio.
- **whisper.cpp:** en Windows exige binarios precompilados y un proceso por frase con un WAV temporal en disco (choca con "el audio no se guarda"), o bindings con ruedas inciertas.
- **Reconocimiento de voz de Windows (`System.Speech.Recognition`):** está obsoleto en Windows 11, necesita el reconocedor de español instalado y dicta mal.
- **pyttsx3:** usa las mismas voces SAPI, pero añade comtypes/pywin32, tiene cuelgues conocidos de `runAndWait` en bucles y no se interrumpe bien desde otro hilo. Sobre PowerShell solo gana latencia.
- **Piper:** es neural, suena mucho mejor y es local, pero exige `piper-tts` y onnxruntime, una voz de ≈60 MB y reproducir el audio nosotros. Es la mejora natural: basta otra clase `Hablante` (`ponytail:`).
- **PyAudio:** valdría igual (también trae PortAudio), pero su API es más verbosa.
- **`conversar_por_voz` aparte:** duplicaría el historial, los errores, `/hoy` y los avisos.
- **Hablar por fragmentos en streaming:** depende del `"\n"` que cierra la línea y corta las frases a medias.
- **Hilo de escucha permanente e interrumpir al hablar el usuario (barge-in):** sin cancelación de eco, el micrófono oye a Jarvis y se interrumpe solo. Queda como `ponytail:`, para usarlo con auriculares.
- **Pedir el sí dos veces o aceptar "claro"/"vale":** más ambigüedad; ante la duda, NO.

## Consecuencias
- Sin `--voz` ni `JARVIS_VOZ=on` no cambia nada, y la suite actual sigue igual. `config.py`, las herramientas y los proveedores no cambian.
- Latencia estimada, sin medir: transcribir con `base` en CPU tarda ≈0,5–2 s por frase y PowerShell tarda ≈0,5–1 s en empezar a hablar. Mientras transcribe no se escucha.
- La voz SAPI suena robótica. Las voces "naturales" de Windows 11 no están disponibles en `System.Speech`.
- Puede que Whisper escriba mal "Jarvis" (por ejemplo "Harvis") si se pronuncia a la española: se añaden variantes en `.env`. Con ruido puede alucinar texto, pero sin la palabra de activación se descarta, y en una confirmación nunca da un sí salvo que sea exactamente "sí".
- Privacidad: el audio nunca se guarda ni sale del equipo. Solo la orden transcrita, tras la palabra de activación, va al proveedor del modelo, igual que si se tecleara.
- Riesgo a verificar a mano: que `powershell.exe -EncodedCommand` lea el texto por stdin con `[Console]::In`. Si no suena, el plan B es meter el base64 dentro del script codificado y recortar a ≈6000 caracteres.
- La fase 6 (UI) reutiliza `Oyente` y `Hablante`: puede envolverlos para saber cuándo Jarvis escucha y cuándo habla.
