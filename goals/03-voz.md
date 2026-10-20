# Fase 3 — Voz

Requisito: fase 2 cerrada. Antes de lanzar, decide si la voz será en español y qué motor usarás para voz a texto y texto a voz (anótalo en docs/decisiones/).

## Goal (pegar en Claude Code)

```text
/goal Jarvis acepta entrada por voz y responde hablando, en español: (1) un módulo de voz a texto que transcribe los audios de ejemplo guardados en tests/audio/ con el texto esperado indicado en un archivo junto a cada audio; (2) un módulo de texto a voz que genera un archivo de audio válido a partir de una frase; (3) una palabra de activación configurable por .env; (4) la voz se puede desactivar y Jarvis sigue funcionando solo con texto; (5) `pytest -q` termina en 0. Como el bucle no puede escuchar, la verificación usa solo los audios de ejemplo y archivos generados, nunca el micrófono real. Delega al "ligero" las pruebas, la configuración y la documentación, y al "pesado" el diseño de los módulos de voz y su integración con el bucle. Pide al "verificador" la salida literal de `pytest -q` y al "revisor" que revise el diff. Actualiza loop/estado.md. Detente tras 30 turnos si no se cumple.
```

## Cómo se verifica
- Los tests con audios de ejemplo pasan.
- Prueba manual tuya con micrófono real al final (el bucle no puede hacerla).
