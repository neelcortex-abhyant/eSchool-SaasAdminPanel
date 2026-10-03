from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.admin import router as admin_router
from app.api.deps import ApiError
from app.api.mobile import router as mobile_router
from app.api.staff_and_writes import router as staff_and_writes_router
from app.api.student_reads import router as student_reads_router
from app.api.stubs import router as stub_router
from app.core.config import get_settings

logging.basicConfig(level=getattr(logging, get_settings().log_level.upper(), logging.INFO))
logger = logging.getLogger("eschool")

settings = get_settings()
app = FastAPI(title="eSchool SaaS API", docs_url="/docs" if settings.app_debug else None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
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
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


@app.get("/ready")
def ready():
    """Readiness: config loaded; DB ping is added when MySQL is configured."""
    checks = {
        "settings": True,
        "db_connection": settings.db_connection,
        "allow_ddl": settings.allow_ddl,
    }
    if settings.allow_ddl and settings.app_env == "production":
        return Response(
            content='{"status":"fail","reason":"DDL enabled in production"}',
            media_type="application/json",
            status_code=503,
        )
    return {"status": "ready", "checks": checks}


app.include_router(mobile_router, prefix="/api")
app.include_router(student_reads_router, prefix="/api")
app.include_router(staff_and_writes_router, prefix="/api")
app.include_router(stub_router, prefix="/api")
app.include_router(admin_router, prefix="/api/admin")
