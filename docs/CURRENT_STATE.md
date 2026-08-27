# Estado actual

## Inventario inicial

Al iniciar el trabajo el repositorio contenía solamente `master-prompt.md`.
No existían aplicación, stack, autenticación, esquema, pruebas ni componentes
reutilizables. Por tanto, no hay sistemas productivos enlazados ni datos que
migrar.

## Alcance de esta base

- Monolito modular en Python 3.12 y FastAPI.
- Núcleo de dominio independiente del framework.
- Casos de uso de organización y WorkItem con aislamiento por organización.
- Puertos de persistencia e implementaciones en memoria para ejecución/pruebas.
- API v1, manejo uniforme de errores, request ID y health check.
- Pruebas del dominio, aislamiento multi-tenant y API.

La persistencia en memoria es deliberadamente temporal: permite validar el
diseño sin fingir durabilidad. PostgreSQL, migraciones, autenticación real y
outbox se incorporan antes de un despliegue compartido.

## Riesgos iniciales

1. No desplegar la implementación en memoria en producción.
2. No conectar cafetería/crédito hasta disponer de sandbox o acceso read-only.
3. No habilitar webhooks sin firma, idempotencia y cola de reintentos.
4. No exponer operaciones sin sustituir la identidad de desarrollo por OIDC.
5. Corregir y validar la codificación del listado inicial de personas antes de
   importarlo; el prompt contiene nombres con mojibake.

