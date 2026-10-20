# Fase 4 — Memoria y proactividad

Requisito: fase 3 cerrada (o saltada si decides no usar voz).

## Goal (pegar en Claude Code)

```text
/goal Jarvis recuerda y avisa: (1) memoria persistente en un archivo local que guarda preferencias y datos que el usuario pide recordar, y los recupera al reiniciar, con tests de persistencia; (2) el usuario puede borrar un recuerdo concreto o toda la memoria, con confirmación; (3) recordatorios con fecha y hora, y un test que simula el paso del tiempo y comprueba que el recordatorio se dispara una sola vez; (4) un resumen diario generado a partir de las notas y los recordatorios del día; (5) la memoria nunca guarda claves, contraseñas ni números de tarjeta, y un test lo comprueba; (6) `pytest -q` termina en 0. Delega al "pesado" el diseño de la memoria, la privacidad y el programador de recordatorios, y al "ligero" los tests de rutina y la documentación. Pide al "verificador" la salida literal de `pytest -q` y al "revisor" que revise el diff. Actualiza loop/estado.md. Detente tras 30 turnos si no se cumple.
```

## Cómo se verifica
- Los tests de persistencia, borrado, recordatorios y filtrado de datos sensibles pasan.
