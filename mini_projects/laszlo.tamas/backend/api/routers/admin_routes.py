"""
Admin API routes - System configuration and monitoring control

Endpoints:
- GET/POST/DELETE /api/admin/tracking-config/{tenant_id}
- GET /api/admin/tracking-config/system

Features:
- Runtime node-level tracking configuration
- Tenant-level granularity
- Temporary debug mode (auto-revert)
- Storage impact estimation
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, Literal
from services.workflow_tracking_config_service import (
    workflow_tracking_config_service,
    TrackingLevel
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])


# ===== REQUEST/RESPONSE MODELS =====

class TrackingConfigRequest(BaseModel):
    """Request model for setting tracking configuration."""
    tenant_id: int = Field(..., description="Tenant identifier")
    level: Literal["OFF", "METADATA_ONLY", "FULL_STATE"] = Field(
        ..., 
        description="Tracking level"
    )
    duration_hours: Optional[int] = Field(
        None, 
        ge=1, 
        le=24, 
        description="Temporary override duration (1-24 hours). If None, permanent."
    )
    tracked_nodes: Optional[list[str]] = Field(
        None,
        description="Filter specific nodes (e.g. ['agent_decide', 'search']). If None, all nodes."
    )


class TrackingConfigResponse(BaseModel):
    """Response model for tracking configuration."""
    enabled: bool
    level: str
    tracked_nodes: Optional[list[str]]
    is_override: bool
    override_expires_at: Optional[str]


class StorageImpactResponse(BaseModel):
    """Storage impact estimation."""
    level: str
    per_node_kb: float
    per_workflow_kb: float
    per_day_mb: float
    per_month_gb: float


# ===== ENDPOINTS =====

@router.get("/tracking-config/system", response_model=TrackingConfigResponse)
def get_system_tracking_config():
    """
    Get system default tracking configuration.
    
    This is the fallback config for all tenants without specific override.
    """
    config = workflow_tracking_config_service.get_system_default()
    if not config:
        raise HTTPException(status_code=500, detail="System default config not found")
    
    return TrackingConfigResponse(**config)


@router.get("/tracking-config/{tenant_id}", response_model=TrackingConfigResponse)
def get_tenant_tracking_config(tenant_id: int):
    """
    Get effective tracking configuration for tenant.
    
    Returns tenant-specific config if exists, otherwise system default.
    """
    try:
        config = workflow_tracking_config_service.get_tracking_config(tenant_id)
        return TrackingConfigResponse(**config)
    except Exception as e:
        logger.error(f"Failed to get tracking config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tracking-config")
def set_tenant_tracking_config(request: TrackingConfigRequest):
    """
    Set tracking level for tenant (all users in tenant).
    
    Examples:
    - Enable debug mode for 1 hour:
      ```json
      {
        "tenant_id": 1,
        "level": "FULL_STATE",
        "duration_hours": 1
      }
      ```
    
    - Permanent metadata tracking:
      ```json
      {
        "tenant_id": 1,
        "level": "METADATA_ONLY"
      }
      ```
    
    - Disable tracking:
      ```json
      {
        "tenant_id": 1,
        "level": "OFF"
      }
      ```
    
    - Track only agent nodes:
      ```json
      {
        "tenant_id": 1,
        "level": "METADATA_ONLY",
        "tracked_nodes": ["agent_decide", "agent_reflection"]
      }
      ```
    """
    try:
        success = workflow_tracking_config_service.set_tenant_tracking_level(
            tenant_id=request.tenant_id,
            level=request.level,
            duration_hours=request.duration_hours,
            tracked_nodes=request.tracked_nodes
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update tracking config")
        
        duration_msg = f" for {request.duration_hours} hours" if request.duration_hours else ""
        nodes_msg = f" (nodes: {request.tracked_nodes})" if request.tracked_nodes else ""
        
        return {
            "status": "success",
            "message": f"Tracking level set to {request.level}{duration_msg}{nodes_msg}",
            "tenant_id": request.tenant_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set tracking config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tracking-config/{tenant_id}")
def reset_tenant_tracking_config(tenant_id: int):
    """
    Reset tenant to system default (remove tenant-specific override).
    
    After reset, tenant will use system default configuration.
    """
    try:
        success = workflow_tracking_config_service.reset_tenant_config(tenant_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to reset tracking config")
        
        return {
            "status": "success",
            "message": f"Tenant {tenant_id} reset to system default",
            "tenant_id": tenant_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reset tracking config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tracking-config/storage-impact", response_model=list[StorageImpactResponse])
def get_storage_impact_estimation(
    workflows_per_day: int = Query(1000, ge=1, le=100000, description="Expected workflows per day"),
    nodes_per_workflow: int = Query(12, ge=1, le=50, description="Average nodes per workflow")
):
    """
    Calculate storage impact estimation for different tracking levels.
    
    Query params:
    - workflows_per_day: Expected daily workflow count (default: 1000)
    - nodes_per_workflow: Average nodes per workflow (default: 12)
    
    Returns storage impact for OFF, METADATA_ONLY, FULL_STATE levels.
    """
    impacts = []
    
    # OFF
    impacts.append(StorageImpactResponse(
        level="OFF",
        per_node_kb=0,
        per_workflow_kb=0,
        per_day_mb=0,
        per_month_gb=0
    ))
    
    # METADATA_ONLY
    per_node_metadata = 2  # KB
    per_workflow_metadata = per_node_metadata * nodes_per_workflow
    per_day_metadata = (per_workflow_metadata * workflows_per_day) / 1024  # MB
    per_month_metadata = (per_day_metadata * 30) / 1024  # GB
    
    impacts.append(StorageImpactResponse(
        level="METADATA_ONLY",
        per_node_kb=per_node_metadata,
        per_workflow_kb=per_workflow_metadata,
        per_day_mb=round(per_day_metadata, 2),
        per_month_gb=round(per_month_metadata, 2)
    ))
    
    # FULL_STATE
    per_node_full = 200  # KB (full state snapshot)
    per_workflow_full = per_node_full * nodes_per_workflow
    per_day_full = (per_workflow_full * workflows_per_day) / 1024  # MB
    per_month_full = (per_day_full * 30) / 1024  # GB
    
    impacts.append(StorageImpactResponse(
        level="FULL_STATE",
        per_node_kb=per_node_full,
        per_workflow_kb=per_workflow_full,
        per_day_mb=round(per_day_full, 2),
        per_month_gb=round(per_month_full, 2)
    ))
    
    return impacts
