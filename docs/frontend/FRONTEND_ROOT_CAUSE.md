# Causa raíz del frontend

La aplicación era un frontend estático compuesto por `frontend/index.html`, `frontend/app.js` y `frontend/styles.css`, servido por FastAPI en `/app`. El HTML tenía dos árboles de presentación hermanos: `#auth` y `#shell`. Aunque `#shell` comenzaba con el atributo `hidden`, la lógica de autenticación solo alternaba visibilidad en el cliente y no tenía una ruta ni un guard centralizado. Por eso una sesión expirada podía dejar el shell montado mientras el login volvía a aparecer.

El formulario de login también contenía el formulario administrativo de bootstrap y el campo técnico `organization_id`. La navegación era hash-only (`#home`, `#pipeline`), por lo que todas las vistas se renderizaban dentro del mismo documento sin rutas reales.

La corrección reemplaza ese modelo por un único punto de decisión en `app.js`: una ruta pública monta exclusivamente `AuthLayout` y una ruta protegida monta exclusivamente `AppLayout`. El setup vive en `/setup`, las rutas usan `history.pushState`, las rutas del frontend tienen fallback server-side y una respuesta 401 limpia tokens y redirige a `/login`. El backend permite omitir el identificador de organización cuando el usuario tiene una única membresía, preservando compatibilidad con clientes que todavía lo envíen.
