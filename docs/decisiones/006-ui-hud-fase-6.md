# 006 — Interfaz local con estilo HUD (fase 6)

Fecha: 2026-10-20 · Autor: pesado · Estado: aceptada

## Contexto
La fase 6 (goals/06-noche-fases-3-a-6.md) pide una página local con estilo HUD, que se abre con `python -m jarvis --ui` y la sirve un servidor mínimo en Python. Se abre como ventana de app con `msedge --app=URL` y, si no hay Edge, en el navegador. También pide un script que cree un acceso directo en el escritorio. La página tiene:
- un círculo animado que cambia al escuchar y al hablar;
- subtítulos;
- una entrada de texto;
- un panel con los pendientes del día.

Además pide tests del servidor, un smoke test de arranque y nada de dependencias pesadas de frontend.

El servidor ejecuta herramientas con efectos reales (con confirmación), así que cualquier web abierta en el navegador del usuario es un atacante posible: CSRF y DNS rebinding contra `127.0.0.1`. `bucle.conversar` ya acepta `entrada`, `salida`, `confirmar` y `fragmento` inyectables (decisión 005), y `recordatorios.vencidos(ahora)` y `hoy.reunir(ahora)` ya se pueden reutilizar.

## Decisiones
1. **Solo biblioteca estándar.** `http.server.ThreadingHTTPServer` con un manejador propio, sin `SimpleHTTPRequestHandler` (no se sirve ninguna carpeta). El frontend son tres archivos escritos a mano, `jarvis/ui/index.html`, `app.js` y `estilo.css`, sin CDN ni fuentes externas. Van en tres archivos (y no en uno) para que la CSP pueda prohibir todo script y estilo en línea.
2. **La UI es otra forma de alimentar `conversar`, no un bucle nuevo.** `conversar` corre en el hilo principal con las piezas de una `Sesion` (`jarvis/ui/sesion.py`):
   - `entrada` espera en una cola el texto que llega de la página y, si en 1 s no llega nada, devuelve `""`. Así `conversar` revisa los recordatorios cada segundo.
   - `salida` añade un subtítulo.
   - `confirmar` muestra Sí/No en la página y espera.
   - `fragmento=None`.

   El historial, `/hoy`, los errores del proveedor y los avisos de recordatorios son los de siempre. Como hay **un solo consumidor**, solo hay un turno a la vez. `POST /api/mensaje` responde 409 mientras Jarvis está ocupado. `bucle.py` no cambia.
3. **Estado por polling** cada 500 ms con `GET /api/estado?desde=N`, que devuelve el estado, los subtítulos nuevos y la confirmación pendiente. Se descartó SSE: deja conexiones largas abiertas, complica el apagado y los tests, y con dos peticiones por segundo en local no se gana nada.
4. **Confirmación en la página, y falla a NO.** `Sesion.confirmar` publica `{"id", "texto", "segundos"}` con el texto de `bucle.texto_confirmacion`, que ya escapa los caracteres de control y bidi. Después espera, en trozos de 0,5 s para que Ctrl+C entre en Windows, a `POST /api/confirmar {"id", "si"}`. Pasados 60 s sin respuesta, si la página se cierra o si se cierra Jarvis, la respuesta es NO. Solo `si: true` (un booleano JSON) para el id pendiente cuenta como sí, y una segunda respuesta se ignora. En la página el foco empieza en "No" y Escape equivale a "No".
5. **Panel del día sin modelo.** `GET /api/hoy` devuelve las cuatro secciones de `hoy` en crudo: eventos, correos sin leer, notas y recordatorios. Para eso `hoy.reunir` se divide en `encabezado` + `secciones`, y su salida no cambia. Sin Google, la sección dice "No disponible: …", como en `/hoy`. El panel se carga al abrir la página, cada 5 minutos y con un botón. El botón "Parte del día" envía `/hoy` como un mensaje más, y ese parte sí usa el modelo.
6. **Recordatorios:** los avisa `conversar` como siempre (`avisar_vencidos` antes de cada `entrada`, es decir, cada segundo). Llegan como subtítulo de tipo `aviso`. `vencidos` los marca al leerlos, así que cada uno aparece una sola vez.
7. **Voz con la UI (`--ui --voz`), un diseño mínimo:**
   - `voz.motores(entorno)` sale de `preparar` y devuelve `(oyente, hablante, palabras)`.
   - La UI los envuelve en `OyenteConEstado` y `HablanteConEstado`, que ponen el estado `escuchando` o `hablando` mientras duran y después dejan el anterior.
   - `entrada` mira primero la cola de la página y, si está vacía, escucha (hasta 8 s).
   - `salida` es `voz.salida_por_voz`.
   - **La confirmación es siempre con los botones de la página.** Jarvis dice "Necesito tu confirmación en la pantalla." Un clic es más seguro que el reconocimiento de voz, y quien usa `--ui` está delante de la pantalla.
   - Si el micrófono falla, la voz se apaga y Jarvis sigue con texto, sin cerrarse.

   Sin voz, el servidor solo usa `reposo` y `pensando`. La página simula `escuchando` mientras escribes y `hablando` mientras aparece el subtítulo de Jarvis, de forma solo visual.
8. **Seguridad:**
   - **Red:** escucha solo en `127.0.0.1`, una constante que no se puede configurar. `allow_reuse_address = False`, porque en Windows `SO_REUSEADDR` dejaría a otro proceso quedarse con el puerto. El puerto se configura con `JARVIS_UI_PUERTO`; por defecto es `0` (libre).
   - **Token de sesión:** se genera con `secrets.token_urlsafe(32)` en cada arranque y viaja en el **fragmento** de la URL (`/#token`). El fragmento no llega al servidor, a los logs ni al Referer. El JS lo guarda en `sessionStorage`, lo quita de la barra con `history.replaceState` y lo envía en la cabecera `X-Jarvis-Token`. Se compara con `hmac.compare_digest`.
   - **Peticiones aceptadas:**
     - En **todas** las rutas, `Host` debe ser exactamente `127.0.0.1:<puerto>`, lo que corta el DNS rebinding.
     - En `/api/*`:
       - el token es obligatorio;
       - si viene `Origin`, debe ser `http://127.0.0.1:<puerto>`, y en POST es obligatorio;
       - si viene `Sec-Fetch-Site`, debe ser `same-origin`.
     - POST exige `Content-Type: application/json`, porque un formulario de otra web no puede enviarlo sin preflight. No hay CORS ni `OPTIONS`.
     - El cuerpo debe tener `Content-Length` y ≤ 16 KiB; si no, 411/413 sin leerlo. El texto, ≤ 4000 caracteres. El socket tiene un timeout de 15 s.
   - **Cabeceras:** CSP `default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'`, más `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` y `Cache-Control: no-store`.
   - **En la página:** el JS solo usa `textContent`: nada de `innerHTML`, `eval` ni manejadores en línea. Los correos y eventos son datos externos.
   - **Lo que nunca se imprime:** `log_message` está silenciado. El token no se imprime, salvo que no se pueda abrir ninguna ventana: entonces se muestra la URL completa, con un aviso.
9. **Ventana:** se busca `msedge.exe` con `shutil.which` y en `ProgramFiles(x86)`, `ProgramFiles` y `LOCALAPPDATA`. Se abre con `Popen([edge, "--app=URL", "--window-size=1100,720"])`, como lista y sin `shell`. Si no se encuentra Edge o falla, se usa `webbrowser.open(URL)`.
10. **Acceso directo:** `scripts/crear_acceso_directo.py` llama a `powershell.exe -EncodedCommand` con un script **constante** que usa `WScript.Shell.CreateShortcut`. Las rutas le llegan por variables de entorno (`JARVIS_LNK_*`), así que no hay comillas que escapar ni nada que inyectar. Crea `Jarvis.lnk` en el escritorio real (`[Environment]::GetFolderPath('Desktop')`, que respeta OneDrive), o en `--carpeta`. El acceso directo apunta al `python.exe` del venv con `-m jarvis --ui`, la carpeta del proyecto como carpeta de trabajo y la consola minimizada. Al cerrar la consola se cierra Jarvis.
11. **Tests sin efectos:**
    - La mayoría prueban funciones puras: `servidor.atender(sesion, metodo, ruta, cabeceras, cuerpo, puerto, reloj) -> RespuestaHTTP` y la `Sesion` con `conversar` y `ClienteFalso` en un hilo.
    - Unos pocos usan un servidor real en `127.0.0.1:0` con el fixture explícito `red_local`. Este fixture deja conectar **solo** a `127.0.0.1` y guarda el `connect` original en `conftest.py` al importarse. El resto de tests sigue con la guardia intacta.
    - La guardia también bloquea `webbrowser.open*`.
    - El acceso directo se prueba con un `ejecutar` falso y `tmp_path`.
    - El smoke test llama a `main(["--ui"])` con `conversar` y `abrir_ventana` simulados.

## Alternativas descartadas
- **SSE o WebSocket:** más código (hilos largos y apagado) y nada que ganar en local.
- **Un servidor que ejecuta `turno` en un hilo por petición, con cerrojo propio:** duplica en la UI el historial, `/hoy`, los errores y los avisos que ya resuelve `conversar`.
- **Token en la query (`?t=`):** queda en el historial, en los logs de acceso y en el Referer. Una cookie `SameSite=Strict` también valdría, pero exige más cabeceras y no aporta nada frente al fragmento más la cabecera.
- **Un solo `index.html` con script y estilo en línea:** obligaría a `'unsafe-inline'` o a nonces por respuesta.
- **Confirmar por voz con `--ui --voz`:** queda como pregunta para Sergio. Hoy manda la página.
- **`Jarvis.cmd` en el escritorio** en lugar de un `.lnk`: es más simple de probar, pero no es un acceso directo de verdad (sin icono ni ventana minimizada).
- **Un puerto fijo por defecto:** puede chocar con otro programa. Como el token cambia en cada arranque, un marcador no serviría igual.
- **Apagarse al cerrar la ventana**, por falta de polling: Edge frena los temporizadores de las ventanas minimizadas y apagaría Jarvis sin querer. Queda como `ponytail:`.
- **Pintar el markdown de las respuestas:** exige construir el DOM a mano o `innerHTML`. Se muestra el texto plano (`ponytail:`).

## Consecuencias
- Sin `--ui` nada cambia. `bucle.py`, `config.py`, las herramientas, los proveedores y `personalidad.md` no se tocan. `voz.py` solo gana `motores` (y `preparar` lo usa), y `hoy.py` se divide sin cambiar su salida.
- El token aparece en la línea de comandos de `msedge.exe`, visible para los procesos del mismo usuario. Se acepta: esos procesos ya pueden hacer lo mismo que el usuario.
- Con `--voz`, lo que se escribe en la página espera a que termine la escucha en curso (≤ 8 s) (`ponytail:` cortar la escucha cuando llega texto).
- Cerrar la ventana no cierra Jarvis: se cierra con la consola o con Ctrl+C. Al reabrir con el acceso directo arranca otra instancia, con historial nuevo.
- El JS no tiene tests automáticos de comportamiento, solo comprobaciones estáticas (ids, nada de `innerHTML` ni de URLs externas). Su comportamiento lo comprueba Sergio a mano.
- `recordatorios.json` se lee una vez por segundo mientras la UI está abierta. Es barato y, sin vencidos, no se escribe.
