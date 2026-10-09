from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.admin import router as admin_router
from app.api.admin_writes import router as admin_writes_router
from app.api.deps import ApiError
from app.api.mobile import router as mobile_router
from app.api.staff_and_writes import router as staff_and_writes_router
from app.api.student_reads import router as student_reads_router
from app.api.stubs import router as stub_router
from app.api.v1.router import router as v1_router
from app.core.config import get_settings

logging.basicConfig(level=getattr(logging, get_settings().log_level.upper(), logging.INFO))
logger = logging.getLogger("eschool")

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Promote V1_SUPER_ADMIN_EMAIL to super_admin if that user already exists."""
    if settings.neon_configured and (settings.v1_super_admin_email or "").strip():
        try:
            from app.core.v1_database import get_v1_session_factory
            from app.services.v1 import auth_service

            db = get_v1_session_factory()()
            try:
                promoted = auth_service.bootstrap_super_admin(db)
                if promoted is not None:
                    logger.info("v1_super_admin_bootstrap email=%s", promoted.email)
            finally:
                db.close()
        except Exception:
            logger.exception("v1_super_admin_bootstrap_failed")
    yield


app = FastAPI(
    title="eSchool SaaS API",
    docs_url="/docs" if settings.app_debug else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Netlify preview/production hosts (admin-web). Exact origins still come from FRONTEND_ORIGIN.
    allow_origin_regex=r"https://.*\.netlify\.app$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "school-code",
        "X-Tracking-Token",
        "X-Requested-With",
        "X-Request-ID",
    ],
    expose_headers=["X-Request-ID"],
)


@app.exception_handler(ApiError)
async def api_error_handler(_request: Request, exc: ApiError):
    return JSONResponse(content=exc.payload)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    school_code = request.headers.get("school-code") or ""
    started = time.perf_counter()
    request.state.request_id = request_id
    request.state.school_code = school_code
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "request_id=%s school_code=%s method=%s path=%s status=%s elapsed_ms=%.1f",
        request_id,
        school_code or "-",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.get("/health")
def health():
    """Liveness probe — does not open database connections."""
    from app.core.db_urls import safe_url_target

    neon_target = None
    if settings.neon_configured:
        neon_target = safe_url_target(settings.neon_database_url)
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
        "database": {
            "engine": "postgresql+psycopg",
            "configured": settings.neon_configured,
            "target": neon_target,
            "tenancy": "school_id (single Neon database)",
        },
    }


@app.get("/ready")
def ready():
    """Readiness: config loaded; Neon URL must be present."""
    checks = {
        "settings": True,
        "allow_ddl": settings.allow_ddl,
        "neon_configured": settings.neon_configured,
    }
    if settings.allow_ddl and settings.app_env == "production":
        return Response(
            content='{"status":"fail","reason":"DDL enabled in production"}',
            media_type="application/json",
            status_code=503,
        )
    if not settings.neon_configured:
        return Response(
            content='{"status":"fail","reason":"NEON_DATABASE_URL not set"}',
            media_type="application/json",
            status_code=503,
        )
    return {"status": "ready", "checks": checks}


app.include_router(mobile_router, prefix="/api")
app.include_router(student_reads_router, prefix="/api")
app.include_router(staff_and_writes_router, prefix="/api")
app.include_router(stub_router, prefix="/api")
app.include_router(admin_router, prefix="/api/admin")
app.include_router(admin_writes_router, prefix="/api/admin")
app.include_router(v1_router)

