import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from backend.app.config import settings
from backend.app.core.logging import setup_logging, request_id_ctx, logger
from backend.app.core.redis import close_redis_connection
from backend.app.api.health import router as health_router

# Legacy routers preserved for backward compatibility
from backend.app.api.voice import router as voice_router
from backend.app.api.sales import router as sales_router
from backend.app.api.recovery import router as recovery_router
from backend.app.api.dashboard import router as dashboard_router
from backend.app.api.admin import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize structured logging
    setup_logging(settings.LOG_LEVEL)
    logger.info(
        "Starting %s v%s (environment: %s)",
        settings.PROJECT_NAME,
        settings.VERSION,
        settings.APP_ENV,
    )
    yield
    # Cleanup resources on shutdown
    await close_redis_connection()
    logger.info("Application shutdown complete")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="VoiceLedger: Payment event and voice notification platform",
    lifespan=lifespan,
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """
    Inject baseline security headers on every response:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Referrer-Policy: strict-origin-when-cross-origin
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.middleware("http")
async def request_id_and_logging_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    token = request_id_ctx.set(req_id)
    start_time = time.perf_counter()
    try:
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = req_id
        logger.info(
            "%s %s -> %s in %.2fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
    except Exception:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.exception(
            "Unhandled request error for %s %s after %.2fms",
            request.method,
            request.url.path,
            duration_ms,
        )
        raise
    finally:
        request_id_ctx.reset(token)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Global exception safety net: prevents stack traces, internal SQL errors,
    or database connection details from being exposed to clients in response bodies.
    """
    req_id = request.headers.get("X-Request-ID", "unknown")
    logger.exception("Unhandled server error: %s (request_id=%s)", exc, req_id)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "request_id": req_id},
    )


# CORS Middleware configuration
allowed_origins = (
    settings.CORS_ALLOWED_ORIGINS
    if isinstance(settings.CORS_ALLOWED_ORIGINS, list)
    else [settings.CORS_ALLOWED_ORIGINS]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
    allow_origin_regex=r"^https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core Health Check Router (mounted at root /health and /api/health)
app.include_router(health_router)

# Legacy Routers preserved under /api for compatibility (non-financial/catalog prototype only)
app.include_router(voice_router, prefix=settings.API_V1_STR)
app.include_router(sales_router, prefix=settings.API_V1_STR)
app.include_router(recovery_router, prefix=settings.API_V1_STR)
app.include_router(dashboard_router, prefix=settings.API_V1_STR)
app.include_router(admin_router, prefix=settings.API_V1_STR)

# Canonical VoiceLedger API v1 Routers (Authoritative Production Path)
from backend.app.api.v1.auth import router as auth_v1_router
from backend.app.api.v1.merchants import router as merchants_v1_router
from backend.app.api.v1.webhooks import router as webhooks_v1_router
app.include_router(auth_v1_router, prefix="/api/v1")
app.include_router(merchants_v1_router, prefix="/api/v1")
app.include_router(webhooks_v1_router, prefix="/api/v1")


# Frontend Static Files Mount (for local monolithic runs if built)
frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
dist_dir = frontend_dir / "dist"

if dist_dir.exists() and (dist_dir / "index.html").exists():
    app.mount("/_expo", StaticFiles(directory=str(dist_dir / "_expo")), name="expo-static")
    if (dist_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="assets-static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(dist_dir / "index.html")
else:
    @app.get("/", tags=["API Info"])
    def root():
        return {
            "service": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "status": "online",
            "docs": "/docs",
            "health": "/health",
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
