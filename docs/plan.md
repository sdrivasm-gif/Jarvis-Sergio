# Plan por fases

| Fase | Qué se construye | Cómo se verifica | Goal |
|---|---|---|---|
| 1. Núcleo | Bucle texto → Claude → respuesta, registro de herramientas, configuración | pytest en 0, arranque de prueba | goals/01-nucleo.md |
| 2. Herramientas | Hora, notas, buscar archivos, abrir apps, búsqueda web | Un test por herramienta, confirmación probada | goals/02-herramientas.md |
| 3. Voz | Activación, voz a texto, texto a voz | Audios de ejemplo | goals/03-voz.md |
| 4. Memoria | Memoria persistente, recordatorios, resumen diario | Tests de persistencia y tiempo simulado | goals/04-memoria-proactividad.md |
| 5. Integraciones | Calendario, correo, Drive | Clientes simulados, confirmación obligatoria | goals/05-integraciones.md |

Cada fase parte de la anterior. No se lanza un goal hasta que loop/estado.md indique la fase anterior como cerrada.

## Decisiones abiertas (responder antes de la fase indicada)
- Lenguaje (por defecto Python) — antes de la fase 1
- Proveedor del modelo: API de Claude directa u OpenRouter — antes de la fase 1
- Motor de voz a texto y texto a voz, y si será en español — antes de la fase 3
