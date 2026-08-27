# Arquitectura

## Decisión

LINTEAM comienza como monolito modular. Cada módulo mantiene sus reglas y sus
puertos; una extracción futura no exige convertir hoy cada operación en una
llamada de red.

```text
HTTP / jobs / webhooks
        ↓
presentation (adaptadores de entrada)
        ↓
application (casos de uso, puertos, transacciones)
        ↓
domain (entidades, value objects, reglas, eventos)
        ↑
infrastructure (PostgreSQL, colas, archivos, proveedores)
```

La regla de dependencias apunta hacia adentro. `domain` no importa FastAPI,
ORM, mensajería ni SDK externos. `application` depende de abstracciones; el
arranque ensambla implementaciones concretas.

## Módulos

`identity`, `organization`, `work`, `workflow`, `projects`, `approvals`,
`notifications`, `files`, `audit`, `automation`, `integrations`, `agents`,
`search` y `analytics`. La base implementada cubre `organization` y `work`; los
demás se agregan por fases sin un paquete global de “servicios” compartidos.

## Principios operativos

- `organization_id` es obligatorio en toda entidad de negocio y filtro de
  repositorio. Las referencias cruzadas se validan dentro del tenant.
- UUID es la identidad interna; `human_readable_id` es sólo una referencia de
  usuario y tiene unicidad por organización.
- Los cambios de negocio ocurren mediante casos de uso y producen eventos.
- Una transacción persiste agregado, auditoría y outbox de forma atómica.
- Eventos del outbox alimentan notificaciones, búsquedas y analítica de forma
  asíncrona e idempotente.
- Integraciones y agentes acceden por puertos con permisos y alcance explícitos,
  nunca directamente a tablas.

## Estructura del código

```text
app/
  domain/          # modelo puro y reglas
  application/     # casos de uso, DTO y puertos
  infrastructure/  # adaptadores reemplazables
  presentation/    # HTTP y contratos externos
  bootstrap.py     # composición
```

## Transacciones y eventos

En PostgreSQL cada comando utilizará una unidad de trabajo. El evento de
dominio se guarda en `outbox_event` en la misma transacción. Un worker lo
publica y registra intentos; consumidores usan una clave idempotente. Los
eventos de actividad son visibles para usuarios y los de auditoría son
inmutables y de acceso restringido.

## Decisiones pospuestas

No se introducen microservicios, Kafka, Elasticsearch ni Kubernetes sin carga
que los justifique. PostgreSQL puede resolver inicialmente búsqueda, colas
pequeñas y JSONB; Redis sólo se añadirá para una necesidad medida.

