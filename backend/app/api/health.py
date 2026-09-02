from fastapi import APIRouter, Response, status
from backend.app.config import settings
from backend.app.db.session import check_db_health
from backend.app.core.redis import check_redis_health

router = APIRouter(tags=["Health"])


@router.get("/health")
@router.get("/api/health")
async def health_check(response: Response):
    """
    Service health check endpoint verifying database and Redis connectivity.
    Returns 200 when all core components are reachable, 503 if any dependency fails.
    """
    db_healthy = check_db_health()
    redis_healthy = await check_redis_health()

    is_healthy = db_healthy and redis_healthy

    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "database": "connected" if db_healthy else "unreachable",
        "redis": "connected" if redis_healthy else "unreachable",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.APP_ENV,
    }
