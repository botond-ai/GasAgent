"""
Pydantic models for Fleet API entities.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class HostSummary(BaseModel):
    """Host summary information."""
    id: int
    hostname: str
    display_name: Optional[str] = None
    platform: Optional[str] = None
    osquery_version: Optional[str] = None
    status: Optional[str] = None
    team_id: Optional[int] = None


class HostDetail(BaseModel):
    """Detailed host information from FleetDM."""
    id: int
    hostname: str
    display_name: Optional[str] = None
    platform: Optional[str] = None
    osquery_version: Optional[str] = None
    status: Optional[str] = None
    team_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    seen_time: Optional[datetime] = None
    primary_ip: Optional[str] = None
    primary_mac: Optional[str] = None
    hardware_serial: Optional[str] = None
    hardware_vendor: Optional[str] = None
    hardware_model: Optional[str] = None
    computer_name: Optional[str] = None
    os_version: Optional[str] = None
    uptime: Optional[int] = None
    memory: Optional[int] = None
    cpu_type: Optional[str] = None
    cpu_brand: Optional[str] = None
    cpu_physical_cores: Optional[int] = None
    cpu_logical_cores: Optional[int] = None
    gigs_disk_space_available: Optional[float] = None
    percent_disk_space_available: Optional[float] = None
    gigs_total_disk_space: Optional[float] = None
    last_restarted_at: Optional[datetime] = None
    issues: Optional[Dict[str, Any]] = None
    mdm: Optional[Dict[str, Any]] = None

    class Config:
        extra = "allow"

    def format_for_context(self) -> str:
        """Format host information for LLM context."""
        memory_gb = self.memory / (1024**3) if self.memory else "Unknown"
        if isinstance(memory_gb, float):
            memory_gb = f"{memory_gb:.1f}"

        lines = [
            "Device Information (from FleetDM):",
            f"- Hostname: {self.hostname}",
            f"- Computer Name: {self.computer_name or self.hostname}",
            f"- Platform: {self.platform or 'Unknown'}",
            f"- OS Version: {self.os_version or 'Unknown'}",
            f"- Status: {self.status or 'Unknown'}",
        ]

        if self.hardware_vendor or self.hardware_model:
            lines.append(f"- Hardware: {self.hardware_vendor or ''} {self.hardware_model or ''}".strip())

        if self.cpu_brand:
            lines.append(f"- CPU: {self.cpu_brand}")
            if self.cpu_physical_cores:
                lines.append(f"- CPU Cores: {self.cpu_physical_cores} physical, {self.cpu_logical_cores or self.cpu_physical_cores} logical")

        lines.append(f"- Memory: {memory_gb} GB")

        if self.gigs_disk_space_available is not None:
            lines.append(f"- Disk Space Available: {self.gigs_disk_space_available} GB ({self.percent_disk_space_available or 0}%)")

        if self.seen_time:
            lines.append(f"- Last Seen: {self.seen_time}")

        if self.issues and self.issues.get("total_issues_count", 0) > 0:
            lines.append(f"- Issues: {self.issues.get('total_issues_count', 0)} total ({self.issues.get('failing_policies_count', 0)} failing policies)")

        return "\n".join(lines)


class QueryRequest(BaseModel):
    """Query execution request."""
    query: str = Field(..., description="SQL query to execute")
    selected: Optional[dict] = Field(default=None, description="Target hosts/labels")


class QueryResponse(BaseModel):
    """Query execution response."""
    campaign_id: int
    query_id: Optional[int] = None


class Label(BaseModel):
    """Label model."""
    id: int
    name: str
    description: str = ""
    query: str
    platform: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    type: Optional[str] = None
    host_count: int = 0


class LabelCreate(BaseModel):
    """Label creation request."""
    name: str
    description: str = ""
    query: str
    platform: Optional[str] = None


class Policy(BaseModel):
    """Policy model."""
    id: int
    name: str
    description: str = ""
    query: str
    resolution: str = ""
    critical: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    author_id: Optional[int] = None
    author_name: Optional[str] = None
    author_email: Optional[str] = None
    team_id: Optional[int] = None
    passing_host_count: int = 0
    failing_host_count: int = 0


class PolicyCreate(BaseModel):
    """Policy creation request."""
    name: str
    description: str = ""
    query: str
    resolution: str = ""
    critical: bool = False
    team_id: Optional[int] = None


class Team(BaseModel):
    """Team model."""
    id: int
    name: str
    description: str = ""
    created_at: Optional[datetime] = None
    user_count: int = 0
    host_count: int = 0


class TeamCreate(BaseModel):
    """Team creation request."""
    name: str
    description: str = ""
