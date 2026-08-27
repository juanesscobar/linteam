# Modelo de datos

## Núcleo normalizado

- `organization` → `business_unit` → `department` → `team`.
- `user` representa identidad global; `membership` vincula usuario,
  organización, posición, supervisor y estructura organizacional.
- `role`, `permission`, `role_permission`, `membership_role` implementan RBAC.
- `work_item_type`, `work_item`, `assignment`, `work_item_relation`, `tag`,
  `work_item_tag`, `custom_field_definition` y `custom_field_value`.
- `comment`, `attachment`, `checklist`, `checklist_item`, `deliverable`.
- `workflow`, `workflow_state`, `workflow_transition` y `sla`.
- `approval_request` y `approval_decision`.
- `notification`, `notification_preference`, `activity_event`, `audit_event`.
- `automation`, `automation_run`, `integration`,
  `external_entity_reference`, `project`.
- `agent`, `agent_capability`, `agent_permission`, `agent_run`,
  `agent_action_proposal`, `agent_approval`.

## Reglas

Todas las tablas de negocio llevan `organization_id`, timestamps UTC y, cuando
corresponde, `archived_at`. Las claves foráneas compuestas o validaciones de
aplicación impiden referencias entre organizaciones. El borrado de trabajo,
auditoría y aprobaciones es lógico; `audit_event` no expone update/delete.

`work_item.type_id` referencia un tipo configurable. El estado referencia un
estado del workflow asignado; no es un enum de base de datos. Prioridad e
impacto sí comienzan como vocabularios estables, con posibilidad de catálogo.
Campos personalizados se validan contra su definición y se indexan sólo cuando
el uso lo requiera.

## Índices esenciales

- `(organization_id, human_readable_id)` único.
- WorkItems por `(organization_id, status, due_at)`, creador, asignado y fecha.
- Membresías por organización/usuario y estructura.
- Eventos por organización, entidad y fecha.
- Referencias externas por integración/tipo/id externo, únicas.
- Outbox por estado y próximo intento.

No se guardan archivos binarios en PostgreSQL: `attachment` conserva metadatos,
checksum y una clave opaca del almacenamiento de objetos.

