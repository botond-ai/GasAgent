"""Pydantic models for FleetDM API responses."""
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class FleetHost(BaseModel):
    """FleetDM host search result."""
    
    model_config = ConfigDict(extra='allow')
    
    id: int = Field(description="Host ID")
    hostname: str = Field(description="Host hostname")
    platform: Optional[str] = Field(default=None, description="Platform (darwin, windows, linux)")
    os_version: Optional[str] = Field(default=None, description="Operating system version")
    status: Optional[str] = Field(default=None, description="Host status (online, offline, etc.)")


class FleetHostDetail(BaseModel):
    """FleetDM host detailed information."""
    
    model_config = ConfigDict(extra='allow')
    
    id: int = Field(description="Host ID")
    hostname: str = Field(description="Host hostname")
    platform: Optional[str] = Field(default=None, description="Platform")
    os_version: Optional[str] = Field(default=None, description="OS version")
    status: Optional[str] = Field(default=None, description="Host status")
    seen_time: Optional[str] = Field(default=None, description="Last seen timestamp")
    cpu_type: Optional[str] = Field(default=None, description="CPU type")
    memory: Optional[int] = Field(default=None, description="RAM in GB")
    gigs_disk_space_available: Optional[int] = Field(default=None, description="Available disk space in GB")


class FleetSearchResponse(BaseModel):
    """FleetDM host search response."""
    
    model_config = ConfigDict(extra='allow')
    
    hosts: List[FleetHost] = Field(default_factory=list, description="List of found hosts")


class FleetHostDetailResponse(BaseModel):
    """FleetDM host detail response."""
    
    model_config = ConfigDict(extra='allow')
    
    host: FleetHostDetail = Field(description="Host details")
