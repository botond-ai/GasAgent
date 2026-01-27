"""
Health check endpoints.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import get_qdrant_service, get_redis_service
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response (Pydantic v2)."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "services": {
                    "redis": "healthy",
                    "qdrant": "healthy",
                    "qdrant_points": "1250"
                }
            }
        }
    )
    
    status: str = Field(description="Overall health status: healthy, degraded, or unhealthy")
    services: dict[str, str] = Field(description="Individual service health status")


@router.get("/health", response_model=HealthResponse)
async def health_check(
    qdrant_service = Depends(get_qdrant_service),
    redis_service = Depends(get_redis_service)
) -> HealthResponse:
    """
    Check application health.

    Returns:
        Health status and service connectivity
    """
    services = {}

    # Check Redis
    try:
        redis_ok = redis_service.health_check()
        services["redis"] = "healthy" if redis_ok else "unhealthy"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        services["redis"] = "unhealthy"

    # Check Qdrant
    try:
        info = qdrant_service.get_collection_info()
        services["qdrant"] = "healthy"
        services["qdrant_points"] = str(info.get("points_count", 0))
    except Exception as e:
        logger.error(f"Qdrant health check failed: {e}")
        services["qdrant"] = "unhealthy"

    # Overall status
    overall_status = "healthy" if all(
        v == "healthy" for k, v in services.items() if k in ["redis", "qdrant"]
    ) else "degraded"

    return HealthResponse(
        status=overall_status,
        services=services
    )


@router.get("/ready")
async def readiness_check() -> dict:
    """
    Kubernetes readiness probe.

    Returns:
        Simple ready status
    """
    return {"status": "ready"}


@router.get("/live")
async def liveness_check() -> dict:
    """
    Kubernetes liveness probe.

    Returns:
        Simple alive status
    """
    return {"status": "alive"}
