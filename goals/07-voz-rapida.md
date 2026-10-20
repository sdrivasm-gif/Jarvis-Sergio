# Goal — Voz rápida y natural

Reemplaza la voz de Windows (SAPI) por voces neurales y hace que Jarvis hable antes de terminar su respuesta. También corrige el error de transcripción de `av`.

## Antes de lanzar

```powershell
cd "$env:USERPROFILE\Documents\jarvis-loop"
git status --short
git push -u origin fase-3
git push origin --tags
git switch -c voz-rapida
claude
```

## Goal (pegar en Claude Code)

```text
/goal Voz rápida y natural para Jarvis, en esta carpeta. Primero confirma que estás en la rama `voz-rapida` (créala si no existe), lee CLAUDE.md, loop/estado.md, docs/decisiones/005-voz-fase-5.md y jarvis/voz.py. Problemas: la voz de Windows (SAPI) suena lenta y antigua, y la transcripción falla con `open() got an unexpected keyword argument 'metadata_errors'` porque faster-whisper 1.2.1 llama a av.open(metadata_errors=...) y av 19 ya no lo acepta. Estado final: (1) la transcripción no depende de `av`: se pasa a faster-whisper un arreglo numpy float32 normalizado en vez de un WAV en memoria, con un test de la conversión que no carga el modelo; (2) un motor de voz nuevo con edge-tts (voces neurales de Microsoft, sin clave, necesita internet), voz masculina en español configurable con JARVIS_VOZ_NOMBRE (por defecto es-MX-JorgeNeural), JARVIS_VOZ_VELOCIDAD (por defecto +15%) y JARVIS_VOZ_TONO (por defecto -5Hz); (3) selección con JARVIS_VOZ_MOTOR=edge|sapi|elevenlabs, por defecto edge; si edge falla (sin internet o error) vuelve solo a SAPI y lo avisa una vez; (4) motor ElevenLabs opcional, apagado por defecto, con ELEVENLABS_API_KEY y ELEVENLABS_VOICE_ID en .env, usando solo su SDK o API oficial; no copies código del repositorio AlexandreSajus/JARVIS, que es GPL-3.0; (5) Jarvis empieza a hablar antes de que termine la respuesta: parte el texto en frases a medida que llega en streaming y reproduce cada frase mientras se sintetiza la siguiente, sin lanzar un proceso nuevo por frase y sin que la voz se pise con la escucha del micrófono; (6) un script scripts/medir_voz.py que imprime el tiempo hasta el primer audio y el total para una frase de ejemplo, que ejecutaré yo; (7) las confirmaciones por voz y la palabra de activación siguen funcionando; (8) `pytest -q` termina en 0 sin claves, sin red y sin audio real: todos los motores se prueban con simulados. Orquesta: "explorador" (graphify) mapea voz.py y la interfaz; "pesado" (brainstorming, sin preguntarme) decide cómo reproducir el audio, la cola de frases y el manejo de errores, y lo anota en docs/decisiones/007-voz-rapida.md y loop/estado.md; "constructor" (ponytail y test-driven-development) implementa; "ligero" actualiza jarvis/README.md y, si puede, .env.example (si no, lo anota como PENDIENTE PARA SERGIO); "verificador" (verification-before-completion) pega `pytest -q` ejecutado en esa pasada; "revisor" revisa el diff con ponytail-review, con revisión de seguridad: sin claves en logs y el texto que se sintetiza nunca va dentro de un comando de shell. No uses "investigador-apps" ni las skills de superpowers finishing-a-development-branch, using-git-worktrees, subagent-driven-development, writing-plans ni executing-plans; si una skill contradice CLAUDE.md, manda CLAUDE.md salvo la excepción de commit. EXCEPCIÓN solo para este goal: al cerrar, la sesión principal hace un commit local `Voz rápida` con la etiqueta `v0.7-voz`; nunca push. Actualiza loop/estado.md y loop/bitacora.md. Detente tras 60 turnos si no se cumple.
```

## Al terminar
- `.\.venv\Scripts\python.exe -m pip install -e ".[voz]"` por si hay dependencias nuevas.
- `.\.venv\Scripts\python.exe scripts\medir_voz.py` para ver los tiempos.
- `.\.venv\Scripts\python.exe -m jarvis --ui --voz` y probar "Jarvis, ¿qué hora es?".
- Si quieres la voz de ElevenLabs: crea una cuenta, copia tu clave y el ID de la voz en `.env`, y pon `JARVIS_VOZ_MOTOR=elevenlabs`.
