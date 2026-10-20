# Fase 2 — Herramientas

Requisito: fase 1 cerrada en loop/estado.md.

## Goal (pegar en Claude Code)

```text
/goal Jarvis tiene estas herramientas, cada una en su propio archivo dentro de jarvis/tools/ y con al menos un test que verifica su salida esperada: (1) hora y fecha; (2) crear, listar y buscar notas guardadas en un archivo local; (3) buscar archivos por nombre en una carpeta indicada; (4) abrir una aplicación por nombre (en las pruebas se simula, no se abre nada real); (5) búsqueda web simple. Ninguna herramienta con efectos reales se ejecuta sin confirmación explícita del usuario, y hay un test que lo prueba. `pytest -q` termina en 0. Delega al "ligero" las herramientas simples (1, 2, 3) y sus tests, y al "pesado" la herramienta 4, la de búsqueda web y el mecanismo de confirmación. Pide al "verificador" la salida literal de `pytest -q` y al "revisor" que revise el diff. Actualiza loop/estado.md. Detente tras 30 turnos si no se cumple.
```

## Cómo se verifica
- Un test por herramienta, y todos pasan.
- Un test demuestra que sin confirmación no se ejecuta la acción real.
- El revisor responde APROBADO.
