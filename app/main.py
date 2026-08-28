import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text as sql_text
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.domain.errors import AuthorizationError, ConflictError, DomainError, NotFoundError
from app.infrastructure.database import SessionLocal, create_schema
from app.infrastructure.rate_limit import InMemoryRateLimiter
from app.presentation.admin import router as admin_router
from app.presentation.agents import router as agents_router
from app.presentation.configuration import router as configuration_router
from app.presentation.http import router
from app.presentation.integrations import router as integrations_router
from app.presentation.operations import router as operations_router
from app.presentation.people import router as people_router
from app.presentation.projects import router as projects_router
from app.presentation.workflows import router as workflows_router
from app.settings import get_settings

logger = logging.getLogger("linteam.http")
settings = get_settings()
rate_limiter = InMemoryRateLimiter(settings.rate_limit_per_minute)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    create_schema()
    yield


app = FastAPI(title="LINTEAM API", version="0.1.0", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Bootstrap-Token"],
)
app.include_router(router)
app.include_router(admin_router)
app.include_router(operations_router)
app.include_router(workflows_router)
app.include_router(integrations_router)
app.include_router(agents_router)
app.include_router(projects_router)
app.include_router(configuration_router)
app.include_router(people_router)
DIST_DIRECTORY = Path(__file__).resolve().parent.parent / "frontend" / "dist"
SPA_INDEX = DIST_DIRECTORY / "index.html"
ASSETS_DIRECTORY = DIST_DIRECTORY / "assets"

if not SPA_INDEX.is_file() or not ASSETS_DIRECTORY.is_dir():
    raise RuntimeError("React frontend build is missing: expected frontend/dist")


def frontend_file(path: str) -> Path | None:
    """Return a real file inside the Vite build, never a path outside it."""
    candidate = (DIST_DIRECTORY / path).resolve()
    try:
        candidate.relative_to(DIST_DIRECTORY.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


app.mount("/app/assets", StaticFiles(directory=ASSETS_DIRECTORY), name="frontend-assets")


@app.get("/login", include_in_schema=False)
@app.get("/setup", include_in_schema=False)
@app.get("/join", include_in_schema=False)
@app.get("/invite", include_in_schema=False)
@app.get("/app/create", include_in_schema=False)
@app.get("/display/operations", include_in_schema=False)
def public_frontend() -> FileResponse:
    return FileResponse(SPA_INDEX)


@app.get("/app", include_in_schema=False)
@app.get("/app/", include_in_schema=False)
def app_index() -> FileResponse:
    return FileResponse(SPA_INDEX)


@app.get("/app/{route:path}", include_in_schema=False)
def frontend_route(route: str) -> FileResponse:
    return FileResponse(frontend_file(route) or SPA_INDEX)


@app.middleware("http")
async def request_id(request: Request, call_next: Any):  # type: ignore[no-untyped-def]
    correlation_id = request.headers.get("X-Request-ID", str(uuid4()))
    client_ip = request.client.host if request.client else "unknown"
    if request.url.path.startswith("/api/") and not rate_limiter.allow(client_ip):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers={"Retry-After": "60", "X-Request-ID": correlation_id},
        )
    started = perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = correlation_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; script-src 'self'; "
        "img-src 'self' data:; connect-src 'self'"
    )
    logger.info(
        json.dumps(
            {
                "event": "http_request",
                "request_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            }
        )
    )
    return response


@app.exception_handler(DomainError)
async def domain_error_handler(_request: Request, error: DomainError) -> JSONResponse:
    status_code = 400
    if isinstance(error, AuthorizationError):
        status_code = 403
    elif isinstance(error, NotFoundError):
        status_code = 404
    elif isinstance(error, ConflictError):
        status_code = 409
    return JSONResponse(status_code=status_code, content={"detail": str(error)})


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["operations"])
def ready() -> dict[str, str]:
    with SessionLocal() as session:
        session.execute(sql_text("SELECT 1"))
    return {"status": "ready", "database": "ok"}


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/login")
