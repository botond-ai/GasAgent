"""
Pydantic models for Fleet API entities.
These models ensure type safety and automatic validation.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


# Authentication Models
class LoginRequest(BaseModel):
    """Login request payload."""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="User's password")


class UserResponse(BaseModel):
    """User information response."""
    created_at: datetime
    updated_at: datetime
    id: int
    name: str
    email: EmailStr
    enabled: bool
    force_password_reset: bool
    gravatar_url: str
    sso_enabled: bool
    mfa_enabled: bool
    global_role: Optional[str] = None
    teams: List[dict] = Field(default_factory=list)


class LoginResponse(BaseModel):
    """Login response with user and token."""
    user: UserResponse
    token: str


class PasswordChangeRequest(BaseModel):
    """Password change request."""
    old_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")


class PasswordResetRequest(BaseModel):
    """Password reset request."""
    new_password: str = Field(..., min_length=8)
    new_password_confirmation: str = Field(..., min_length=8)
    password_reset_token: str


class ForgotPasswordRequest(BaseModel):
    """Forgot password request."""
    email: EmailStr


# Host Models
class HostSummary(BaseModel):
    """Host summary information."""
    id: int
    hostname: str
    display_name: str
    platform: str
    osquery_version: str
    status: str
    team_id: Optional[int] = None


class HostDetail(HostSummary):
    """Detailed host information."""
    created_at: datetime
    updated_at: datetime
    seen_time: Optional[datetime] = None
    primary_ip: Optional[str] = None
    primary_mac: Optional[str] = None
    hardware_serial: Optional[str] = None
    computer_name: Optional[str] = None
    os_version: Optional[str] = None
    uptime: Optional[int] = None
    memory: Optional[int] = None
    cpu_type: Optional[str] = None


# Query Models
class QueryRequest(BaseModel):
    """Query execution request."""
    query: str = Field(..., description="SQL query to execute")
    selected: Optional[dict] = Field(
        default=None,
        description="Target hosts/labels"
    )


class QueryResponse(BaseModel):
    """Query execution response."""
    campaign_id: int
    query_id: Optional[int] = None


# Label Models
class LabelBase(BaseModel):
    """Base label model."""
    name: str
    description: str = ""
    query: str
    platform: Optional[str] = None


class LabelCreate(LabelBase):
    """Label creation request."""
    pass


class Label(LabelBase):
    """Label response."""
    id: int
    created_at: datetime
    updated_at: datetime
    type: str
    host_count: int = 0


# Policy Models
class PolicyBase(BaseModel):
    """Base policy model."""
    name: str
    description: str = ""
    query: str
    resolution: str = ""
    critical: bool = False


class PolicyCreate(PolicyBase):
    """Policy creation request."""
    team_id: Optional[int] = None


class Policy(PolicyBase):
    """Policy response."""
    id: int
    created_at: datetime
    updated_at: datetime
    author_id: int
    author_name: str
    author_email: str
    team_id: Optional[int] = None
    passing_host_count: int = 0
    failing_host_count: int = 0


# Team Models
class TeamBase(BaseModel):
    """Base team model."""
    name: str
    description: str = ""


class TeamCreate(TeamBase):
    """Team creation request."""
    pass


class Team(TeamBase):
    """Team response."""
    id: int
    created_at: datetime
    user_count: int = 0
    host_count: int = 0


# Software Models
class Software(BaseModel):
    """Software package information."""
    id: int
    name: str
    version: str
    source: str
    generated_cpe: str = ""
    vulnerabilities: List[dict] = Field(default_factory=list)


# Custom Variables Models
class CustomVariableCreate(BaseModel):
    """Custom variable creation request."""
    name: str = Field(
        ...,
        description="Variable name (without FLEET_SECRET_ prefix)"
    )
    value: str = Field(..., description="Variable value")


class CustomVariable(BaseModel):
    """Custom variable response."""
    id: int
    name: str


# Error Models
class ErrorDetail(BaseModel):
    """Error detail."""
    name: str
    reason: str


class APIError(BaseModel):
    """API error response."""
    message: str
    errors: List[ErrorDetail]
    uuid: Optional[str] = None


# Pagination Models
class PaginationMeta(BaseModel):
    """Pagination metadata."""
    has_next_results: bool = False
    has_previous_results: bool = False


class PaginatedResponse(BaseModel):
    """Base paginated response."""
    meta: PaginationMeta
    count: int


# Generic Response Models
class SuccessResponse(BaseModel):
    """Generic success response."""
    message: str = "Operation completed successfully"
    data: Optional[dict] = None
