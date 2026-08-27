# Estado de implementación por fases

## Completado

- Fase 1: autenticación, organización editable, equipos, miembros, RBAC, WorkItems,
  comentarios, actividad, notificaciones y experiencia móvil.
- Fase 2: asignaciones, plazos, prioridad, estados, checklists, relaciones, archivos,
  menciones, Mi trabajo, proyectos y resumen ejecutivo.
- Fase 3: workflows configurables, aprobaciones, entregables esperados y entregados,
  SLA, escalamiento y automatizaciones idempotentes.
- Fases 4 y 5: PWA, preferencias y adaptadores de mensajería, webhooks firmados,
  normalización/identidad, cola saliente y conectores externos de sólo lectura.
- Fases 6 a 8: Ask Conciencia de sólo lectura, registro y router de agentes, propuestas
  con aprobación humana e inteligencia de procesos no autónoma.
- Operación: auditoría, outbox transaccional, reintentos/dead-letter, rate limiting,
  logging estructurado, tokens refresh rotativos, health/readiness y Docker Compose.

## Puertas de calidad actuales

- Suite unitaria e integración end-to-end.
- Lint estricto.
- Cadena Alembic reversible desde una base vacía.
- PostgreSQL y almacenamiento persistente en el despliegue local Docker.
- Separación explícita de desarrollo, staging y producción mediante configuración.

## Evolución posterior al primer despliegue

Push real, proveedores productivos de correo/WhatsApp/Telegram, almacenamiento de objetos,
OIDC corporativo, broker distribuido, observabilidad gestionada y búsqueda semántica requieren
credenciales e infraestructura externas. Permanecen detrás de puertos/adaptadores para no
acoplar el núcleo ni simular acceso a producción.
