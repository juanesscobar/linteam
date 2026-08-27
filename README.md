# LINTEAM

Sistema operativo organizacional de Lin Group construido como monolito modular con
arquitectura limpia. El dominio y los casos de uso no dependen de FastAPI, SQLAlchemy ni
proveedores externos; las integraciones entran mediante adaptadores.

## Ejecutar con Docker

```powershell
Copy-Item .env.example .env
# Cambiar los secretos de .env
docker compose up --build -d
docker compose ps
```

La aplicación queda disponible en http://localhost:8000/app/, OpenAPI en
http://localhost:8000/docs y readiness en http://localhost:8000/ready. En el primer uso,
la pantalla inicial solicita `LINTEAM_BOOTSTRAP_TOKEN` para crear la organización y el
administrador. Las migraciones Alembic se aplican automáticamente al iniciar el contenedor.

Para detener sin eliminar datos: `docker compose down`. Para eliminar también los volúmenes
locales: `docker compose down -v` (acción destructiva).

## Desarrollo sin Docker

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\uvicorn app.main:app --reload
```

Validación:

```powershell
.\.venv\Scripts\ruff check app tests alembic
.\.venv\Scripts\pytest -q
```

## Documentación

- [Estado actual](docs/CURRENT_STATE.md)
- [Arquitectura](docs/ARCHITECTURE.md)
- [Modelo de datos](docs/DATA_MODEL.md)
- [Modelo de seguridad](docs/SECURITY_MODEL.md)
- [Plan de implementación](docs/IMPLEMENTATION_PLAN.md)
