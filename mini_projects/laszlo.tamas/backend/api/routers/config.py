"""
Public Configuration Endpoint

Provides frontend-relevant configuration values.
No authentication required - only exposes safe, public settings.
"""

import logging
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict
from typing import List

from services.config_service import ConfigService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["Configuration"])


class FileUploadConfig(BaseModel):
    """File upload configuration for frontend."""
    max_file_size_mb: int = Field(..., description="Maximum file size in megabytes")
    allowed_file_types: List[str] = Field(..., description="List of allowed file extensions")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "max_file_size_mb": 10,
                "allowed_file_types": [".pdf", ".txt", ".md"]
            }
        }
    )


class PublicConfig(BaseModel):
    """Public configuration exposed to frontend."""
    app_version: str = Field(..., description="Application version string")
    file_upload: FileUploadConfig = Field(..., description="File upload configuration")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "app_version": "0.6.2",
                "file_upload": {
                    "max_file_size_mb": 10,
                    "allowed_file_types": [".pdf", ".txt", ".md"]
                }
            }
        }
    )


@router.get(
    "",
    response_model=PublicConfig,
    status_code=status.HTTP_200_OK,
    summary="Get public configuration",
    description="Returns frontend-relevant configuration values. No authentication required."
)
async def get_public_config() -> PublicConfig:
    """
    Get public configuration values for frontend.
    
    Returns safe configuration values that the frontend needs:
    - app_version: Application version string
    - file_upload: File upload limits and allowed types
    
    Returns:
        PublicConfig: Configuration object with app version and upload settings
        
    Raises:
        HTTPException(500): Configuration service error
    """
    try:
        config = ConfigService()
        
        return PublicConfig(
            app_version=config.get("application", "APP_VERSION", "0.0.0"),
            file_upload=FileUploadConfig(
                max_file_size_mb=config.get_max_file_size_mb(),
                allowed_file_types=[".pdf", ".txt", ".md"]
            )
        )
    except Exception as e:
        logger.error(f"Failed to load public config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load configuration"
        )
