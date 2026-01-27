"""
Main FastAPI application.
Implements clean architecture with dependency injection.
"""

from typing import Optional, List
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from fleet_client import FleetAPIClient, create_fleet_client
from models import (
    LoginRequest, LoginResponse, UserResponse,
    PasswordChangeRequest, ForgotPasswordRequest,
    HostDetail, QueryRequest, QueryResponse,
    LabelCreate, Label, PolicyCreate, Policy,
    TeamCreate, Team, CustomVariableCreate, CustomVariable,
    APIError, SuccessResponse
)
from exceptions import FleetAPIException


# Application lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    # Startup
    print(f"Starting {settings.app_name} v{settings.app_version}")
    yield
    # Shutdown
    print("Shutting down application")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Fleet API Client - SOLID, testable, LangGraph-ready",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency injection for Fleet client
async def get_fleet_client() -> FleetAPIClient:
    """
    Dependency that provides FleetAPIClient instance.
    This enables easy testing with mock clients.
    """
    return create_fleet_client()


# Exception handlers
@app.exception_handler(FleetAPIException)
async def fleet_api_exception_handler(request, exc: FleetAPIException):
    """Handle Fleet API exceptions."""
    return JSONResponse(
        status_code=exc.status_code or 500,
        content={
            "message": exc.message,
            "details": exc.details
        }
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}


# Authentication Endpoints
@app.post(
    "/api/auth/login",
    response_model=LoginResponse,
    tags=["Authentication"],
    summary="Login to Fleet"
)
async def login(
    credentials: LoginRequest,
    client: FleetAPIClient = Depends(get_fleet_client)
) -> LoginResponse:
    """
    Authenticate with Fleet and receive an API token.
    
    - **email**: User's email address
    - **password**: User's password
    """
    return await client.login(credentials.email, credentials.password)


@app.post(
    "/api/auth/logout",
    response_model=SuccessResponse,
    tags=["Authentication"],
    summary="Logout from Fleet"
)
async def logout(
    client: FleetAPIClient = Depends(get_fleet_client)
) -> SuccessResponse:
    """Logout current authenticated user."""
    await client.logout()
    return SuccessResponse(message="Logged out successfully")


@app.get(
    "/api/auth/me",
    response_model=UserResponse,
    tags=["Authentication"],
    summary="Get current user"
)
async def get_current_user(
    client: FleetAPIClient = Depends(get_fleet_client)
) -> UserResponse:
    """Get information about the currently authenticated user."""
    return await client.get_me()


@app.post(
    "/api/auth/change-password",
    response_model=SuccessResponse,
    tags=["Authentication"],
    summary="Change password"
)
async def change_password(
    password_data: PasswordChangeRequest,
    client: FleetAPIClient = Depends(get_fleet_client)
) -> SuccessResponse:
    """Change the password for the authenticated user."""
    await client.change_password(
        password_data.old_password,
        password_data.new_password
    )
    return SuccessResponse(message="Password changed successfully")


@app.post(
    "/api/auth/forgot-password",
    response_model=SuccessResponse,
    tags=["Authentication"],
    summary="Request password reset"
)
async def forgot_password(
    request_data: ForgotPasswordRequest,
    client: FleetAPIClient = Depends(get_fleet_client)
) -> SuccessResponse:
    """Send password reset email to user."""
    await client.forgot_password(request_data.email)
    return SuccessResponse(message="Password reset email sent")


# Host Endpoints
@app.get(
    "/api/hosts",
    response_model=List[HostDetail],
    tags=["Hosts"],
    summary="List hosts"
)
async def list_hosts(
    page: int = 0,
    per_page: int = 100,
    order_key: str = "id",
    order_direction: str = "asc",
    client: FleetAPIClient = Depends(get_fleet_client)
) -> List[HostDetail]:
    """
    List all hosts with pagination and filtering.
    
    - **page**: Page number (default: 0)
    - **per_page**: Results per page (default: 100)
    - **order_key**: Field to sort by (default: id)
    - **order_direction**: Sort direction (default: asc)
    """
    return await client.list_hosts(
        page=page,
        per_page=per_page,
        order_key=order_key,
        order_direction=order_direction
    )


@app.get(
    "/api/hosts/{host_id}",
    response_model=HostDetail,
    tags=["Hosts"],
    summary="Get host details"
)
async def get_host(
    host_id: int,
    client: FleetAPIClient = Depends(get_fleet_client)
) -> HostDetail:
    """Get detailed information about a specific host."""
    return await client.get_host(host_id)


@app.delete(
    "/api/hosts/{host_id}",
    response_model=SuccessResponse,
    tags=["Hosts"],
    summary="Delete host"
)
async def delete_host(
    host_id: int,
    client: FleetAPIClient = Depends(get_fleet_client)
) -> SuccessResponse:
    """Delete a host from Fleet."""
    await client.delete_host(host_id)
    return SuccessResponse(message=f"Host {host_id} deleted successfully")


# Query Endpoints
@app.post(
    "/api/queries/run",
    response_model=QueryResponse,
    tags=["Queries"],
    summary="Run live query"
)
async def run_query(
    query_request: QueryRequest,
    client: FleetAPIClient = Depends(get_fleet_client)
) -> QueryResponse:
    """
    Execute a live query on selected hosts.
    
    - **query**: SQL query to execute
    - **selected**: Target hosts or labels
    """
    host_ids = None
    label_ids = None
    
    if query_request.selected:
        host_ids = query_request.selected.get("hosts")
        label_ids = query_request.selected.get("labels")
    
    return await client.run_query(
        query=query_request.query,
        host_ids=host_ids,
        label_ids=label_ids
    )


# Label Endpoints
@app.get(
    "/api/labels",
    response_model=List[Label],
    tags=["Labels"],
    summary="List labels"
)
async def list_labels(
    client: FleetAPIClient = Depends(get_fleet_client)
) -> List[Label]:
    """List all labels."""
    return await client.list_labels()


@app.post(
    "/api/labels",
    response_model=Label,
    tags=["Labels"],
    summary="Create label",
    status_code=status.HTTP_201_CREATED
)
async def create_label(
    label: LabelCreate,
    client: FleetAPIClient = Depends(get_fleet_client)
) -> Label:
    """Create a new label."""
    return await client.create_label(label)


@app.delete(
    "/api/labels/{label_id}",
    response_model=SuccessResponse,
    tags=["Labels"],
    summary="Delete label"
)
async def delete_label(
    label_id: int,
    client: FleetAPIClient = Depends(get_fleet_client)
) -> SuccessResponse:
    """Delete a label."""
    await client.delete_label(label_id)
    return SuccessResponse(message=f"Label {label_id} deleted successfully")


# Policy Endpoints
@app.get(
    "/api/policies",
    response_model=List[Policy],
    tags=["Policies"],
    summary="List policies"
)
async def list_policies(
    team_id: Optional[int] = None,
    client: FleetAPIClient = Depends(get_fleet_client)
) -> List[Policy]:
    """List all policies, optionally filtered by team."""
    return await client.list_policies(team_id=team_id)


@app.post(
    "/api/policies",
    response_model=Policy,
    tags=["Policies"],
    summary="Create policy",
    status_code=status.HTTP_201_CREATED
)
async def create_policy(
    policy: PolicyCreate,
    client: FleetAPIClient = Depends(get_fleet_client)
) -> Policy:
    """Create a new policy."""
    return await client.create_policy(policy)


@app.delete(
    "/api/policies/{policy_id}",
    response_model=SuccessResponse,
    tags=["Policies"],
    summary="Delete policy"
)
async def delete_policy(
    policy_id: int,
    client: FleetAPIClient = Depends(get_fleet_client)
) -> SuccessResponse:
    """Delete a policy."""
    await client.delete_policy(policy_id)
    return SuccessResponse(message=f"Policy {policy_id} deleted successfully")


# Team Endpoints
@app.get(
    "/api/teams",
    response_model=List[Team],
    tags=["Teams"],
    summary="List teams"
)
async def list_teams(
    client: FleetAPIClient = Depends(get_fleet_client)
) -> List[Team]:
    """List all teams."""
    return await client.list_teams()


@app.post(
    "/api/teams",
    response_model=Team,
    tags=["Teams"],
    summary="Create team",
    status_code=status.HTTP_201_CREATED
)
async def create_team(
    team: TeamCreate,
    client: FleetAPIClient = Depends(get_fleet_client)
) -> Team:
    """Create a new team."""
    return await client.create_team(team)


@app.delete(
    "/api/teams/{team_id}",
    response_model=SuccessResponse,
    tags=["Teams"],
    summary="Delete team"
)
async def delete_team(
    team_id: int,
    client: FleetAPIClient = Depends(get_fleet_client)
) -> SuccessResponse:
    """Delete a team."""
    await client.delete_team(team_id)
    return SuccessResponse(message=f"Team {team_id} deleted successfully")


# Custom Variables Endpoints
@app.get(
    "/api/custom-variables",
    response_model=List[CustomVariable],
    tags=["Custom Variables"],
    summary="List custom variables"
)
async def list_custom_variables(
    page: int = 0,
    per_page: int = 100,
    client: FleetAPIClient = Depends(get_fleet_client)
) -> List[CustomVariable]:
    """List all custom variables."""
    return await client.list_custom_variables(page=page, per_page=per_page)


@app.post(
    "/api/custom-variables",
    response_model=CustomVariable,
    tags=["Custom Variables"],
    summary="Create custom variable",
    status_code=status.HTTP_201_CREATED
)
async def create_custom_variable(
    variable: CustomVariableCreate,
    client: FleetAPIClient = Depends(get_fleet_client)
) -> CustomVariable:
    """Create a new custom variable."""
    return await client.create_custom_variable(variable)


@app.delete(
    "/api/custom-variables/{variable_id}",
    response_model=SuccessResponse,
    tags=["Custom Variables"],
    summary="Delete custom variable"
)
async def delete_custom_variable(
    variable_id: int,
    client: FleetAPIClient = Depends(get_fleet_client)
) -> SuccessResponse:
    """Delete a custom variable."""
    await client.delete_custom_variable(variable_id)
    return SuccessResponse(
        message=f"Custom variable {variable_id} deleted successfully"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
