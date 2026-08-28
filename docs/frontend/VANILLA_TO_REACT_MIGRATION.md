# Migración Vanilla JS → React + TypeScript

## Auditoría

El frontend anterior tenía un único `index.html` con `#auth` y `#shell`, un `app.js` que mezclaba autenticación, router hash, llamadas HTTP, modales, dashboard y pipeline, y una pantalla TV independiente en `display.html`/`display.js`. El setup administrativo estaba anidado en el login y la expiración solo alternaba visibilidad.

## Mapeo

| Frontend anterior | Módulo React |
| --- | --- |
| `#auth`, `login-form` | `AuthPage`, `PublicRoute` |
| formulario bootstrap | `AuthPage setup`, `/setup` |
| `#shell`, sidebar y topbar | `AppLayout` |
| `renderHome` | `Dashboard` |
| `renderMyWork` / `workRows` | `MyWork` / `WorkList` |
| `renderPipeline` y drag/drop | `Pipeline`, `PipelineColumn`, `WorkCard`, dnd-kit |
| `renderInbox` | `Placeholder` preparado para `Inbox` query |
| `create-dialog` | `CreateDialog` controlado |
| `display.html` / `display.js` | `DisplayPage` en `/display/operations` |
| `api()` y refresh | `src/lib/api.ts` |

## Contratos preservados

La migración consume los endpoints FastAPI existentes. El único cambio backend requerido previamente fue hacer opcional `organization_id` en login: si el usuario tiene una sola membresía, se resuelve server-side; el UUID nunca se pide en el login.

## Estructura

React monta una sola vez desde `src/main.tsx`, con React Router y TanStack Query. Las mutaciones de WorkItem invalidan las queries afectadas. El diálogo es controlado y conserva el formulario ante error. El pipeline genera columnas desde `WorkflowState` y solicita la transición al backend. La pantalla de operaciones también está integrada en React y no usa sidebar ni controles de edición.
