# Fase 5 — Integraciones (calendario, correo, Drive)

Requisito: fases 1 a 4 cerradas. Esta fase toca cuentas reales, así que es la más delicada.

## Reglas especiales
- Las pruebas usan solo datos de mentira (clientes simulados), nunca tus cuentas reales.
- Leer es libre; enviar, crear, borrar o compartir exige confirmación explícita en cada acción.
- Las credenciales las pones tú en .env; el bucle no las lee ni las pide.

## Goal (pegar en Claude Code)

```text
/goal Jarvis se conecta a calendario, correo y Drive a través de una capa de integración con clientes simulados para las pruebas: (1) cada integración vive en su propio archivo en jarvis/integrations/ y tiene un cliente simulado en tests/; (2) las acciones de solo lectura (listar eventos, buscar correos, buscar archivos) funcionan con el cliente simulado; (3) las acciones con efectos (crear evento, enviar correo, compartir archivo, borrar) exigen confirmación explícita y hay un test por acción que prueba que sin confirmación no se ejecuta; (4) ningún token ni credencial aparece en el código ni en los logs, y un test busca patrones de claves en el repositorio; (5) `pytest -q` termina en 0. Delega al "pesado" el diseño de la capa de integración y de la confirmación, y al "ligero" los clientes simulados, los tests y la documentación. Pide al "verificador" la salida literal de `pytest -q` y al "revisor" una revisión de seguridad del diff. Actualiza loop/estado.md. Detente tras 35 turnos si no se cumple.
```

## Cómo se verifica
- Todos los tests pasan con clientes simulados.
- Pruebas reales con tus cuentas las haces tú, a mano, al final.
