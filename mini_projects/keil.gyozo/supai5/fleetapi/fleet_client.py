"""
Fleet API Client Service.
Implements the Single Responsibility Principle - handles all Fleet API communication.
Uses Dependency Inversion - depends on abstractions (config, http client).
"""

from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
import httpx
from config import Settings
from models import (
    LoginRequest, LoginResponse, UserResponse,
    HostDetail, QueryRequest, QueryResponse,
    Label, LabelCreate, Policy, PolicyCreate,
    Team, TeamCreate, CustomVariable, CustomVariableCreate
)
from exceptions import (
    AuthenticationError, AuthorizationError, 
    ResourceNotFoundError, ValidationError,
    RateLimitError, ServerError, NetworkError
)


class HTTPClientInterface(ABC):
    """Abstract interface for HTTP client (Dependency Inversion Principle)."""
    
    @abstractmethod
    async def get(self, url: str, **kwargs) -> Dict[str, Any]:
        """GET request."""
        pass
    
    @abstractmethod
    async def post(self, url: str, **kwargs) -> Dict[str, Any]:
        """POST request."""
        pass
    
    @abstractmethod
    async def patch(self, url: str, **kwargs) -> Dict[str, Any]:
        """PATCH request."""
        pass
    
    @abstractmethod
    async def delete(self, url: str, **kwargs) -> Dict[str, Any]:
        """DELETE request."""
        pass


class HTTPXClient(HTTPClientInterface):
    """HTTPX implementation of HTTP client."""
    
    def __init__(self, base_url: str, token: Optional[str] = None):
        self.base_url = base_url
        self.headers = {"Content-Type": "application/json"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers=self.headers,
            timeout=30.0
        )
    
    async def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Handle HTTP response and raise appropriate exceptions."""
        try:
            data = response.json()
        except Exception:
            data = {"message": response.text}
        
        if response.status_code == 401:
            raise AuthenticationError(
                data.get("message", "Authentication failed"),
                details=data.get("errors", [])
            )
        elif response.status_code == 403:
            raise AuthorizationError(
                data.get("message", "Insufficient permissions"),
                details=data.get("errors", [])
            )
        elif response.status_code == 404:
            raise ResourceNotFoundError(
                "Resource",
                details=data.get("errors", [])
            )
        elif response.status_code == 422:
            raise ValidationError(
                data.get("message", "Validation failed"),
                details=data.get("errors", [])
            )
        elif response.status_code == 429:
            retry_after = response.headers.get("retry-after")
            raise RateLimitError(
                retry_after=int(retry_after) if retry_after else None,
                message=data.get("message", "Rate limit exceeded")
            )
        elif response.status_code >= 500:
            raise ServerError(
                data.get("message", "Internal server error"),
                details=data.get("errors", [])
            )
        
        response.raise_for_status()
        return data
    
    async def get(self, url: str, **kwargs) -> Dict[str, Any]:
        """GET request."""
        try:
            response = await self.client.get(url, **kwargs)
            return await self._handle_response(response)
        except httpx.RequestError as e:
            raise NetworkError(f"Network error: {str(e)}")
    
    async def post(self, url: str, **kwargs) -> Dict[str, Any]:
        """POST request."""
        try:
            response = await self.client.post(url, **kwargs)
            return await self._handle_response(response)
        except httpx.RequestError as e:
            raise NetworkError(f"Network error: {str(e)}")
    
    async def patch(self, url: str, **kwargs) -> Dict[str, Any]:
        """PATCH request."""
        try:
            response = await self.client.patch(url, **kwargs)
            return await self._handle_response(response)
        except httpx.RequestError as e:
            raise NetworkError(f"Network error: {str(e)}")
    
    async def delete(self, url: str, **kwargs) -> Dict[str, Any]:
        """DELETE request."""
        try:
            response = await self.client.delete(url, **kwargs)
            return await self._handle_response(response)
        except httpx.RequestError as e:
            raise NetworkError(f"Network error: {str(e)}")
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class FleetAPIClient:
    """
    Fleet API client implementing business logic.
    Single Responsibility: Handles Fleet API operations.
    Dependency Inversion: Depends on HTTPClientInterface abstraction.
    """
    
    def __init__(
        self,
        http_client: HTTPClientInterface,
        settings: Optional[Settings] = None
    ):
        self.http_client = http_client
        self.settings = settings
    
    # Authentication Methods
    async def login(self, email: str, password: str) -> LoginResponse:
        """
        Authenticate user and retrieve API token.
        
        Args:
            email: User's email address
            password: User's password
            
        Returns:
            LoginResponse with user data and token
        """
        request = LoginRequest(email=email, password=password)
        data = await self.http_client.post(
            "/api/v1/fleet/login",
            json=request.model_dump()
        )
        return LoginResponse(**data)
    
    async def logout(self) -> None:
        """Logout current user."""
        await self.http_client.post("/api/v1/fleet/logout")
    
    async def get_me(self) -> UserResponse:
        """Get current user information."""
        data = await self.http_client.get("/api/v1/fleet/me")
        return UserResponse(**data["user"])
    
    async def change_password(
        self,
        old_password: str,
        new_password: str
    ) -> None:
        """Change user password."""
        await self.http_client.post(
            "/api/v1/fleet/change_password",
            json={
                "old_password": old_password,
                "new_password": new_password
            }
        )
    
    async def forgot_password(self, email: str) -> None:
        """Request password reset email."""
        await self.http_client.post(
            "/api/v1/fleet/forgot_password",
            json={"email": email}
        )
    
    # Host Methods
    async def list_hosts(
        self,
        page: int = 0,
        per_page: int = 100,
        order_key: str = "id",
        order_direction: str = "asc",
        **filters
    ) -> List[HostDetail]:
        """
        List all hosts with optional filtering.
        
        Args:
            page: Page number
            per_page: Results per page
            order_key: Field to order by
            order_direction: Sort direction (asc/desc)
            **filters: Additional filter parameters
            
        Returns:
            List of HostDetail objects
        """
        params = {
            "page": page,
            "per_page": per_page,
            "order_key": order_key,
            "order_direction": order_direction,
            **filters
        }
        data = await self.http_client.get(
            "/api/v1/fleet/hosts",
            params=params
        )
        return [HostDetail(**host) for host in data.get("hosts", [])]
    
    async def get_host(self, host_id: int) -> HostDetail:
        """Get detailed information about a specific host."""
        data = await self.http_client.get(f"/api/v1/fleet/hosts/{host_id}")
        return HostDetail(**data["host"])
    
    async def delete_host(self, host_id: int) -> None:
        """Delete a host."""
        await self.http_client.delete(f"/api/v1/fleet/hosts/{host_id}")
    
    # Query Methods
    async def run_query(
        self,
        query: str,
        host_ids: Optional[List[int]] = None,
        label_ids: Optional[List[int]] = None
    ) -> QueryResponse:
        """
        Run a live query on selected hosts.
        
        Args:
            query: SQL query to execute
            host_ids: List of host IDs to target
            label_ids: List of label IDs to target
            
        Returns:
            QueryResponse with campaign information
        """
        selected = {}
        if host_ids:
            selected["hosts"] = host_ids
        if label_ids:
            selected["labels"] = label_ids
        
        request = QueryRequest(query=query, selected=selected or None)
        data = await self.http_client.post(
            "/api/v1/fleet/queries/run",
            json=request.model_dump()
        )
        return QueryResponse(**data)
    
    # Label Methods
    async def list_labels(self) -> List[Label]:
        """List all labels."""
        data = await self.http_client.get("/api/v1/fleet/labels")
        return [Label(**label) for label in data.get("labels", [])]
    
    async def create_label(self, label: LabelCreate) -> Label:
        """Create a new label."""
        data = await self.http_client.post(
            "/api/v1/fleet/labels",
            json=label.model_dump()
        )
        return Label(**data["label"])
    
    async def delete_label(self, label_id: int) -> None:
        """Delete a label."""
        await self.http_client.delete(f"/api/v1/fleet/labels/{label_id}")
    
    # Policy Methods
    async def list_policies(self, team_id: Optional[int] = None) -> List[Policy]:
        """List all policies."""
        params = {"team_id": team_id} if team_id else {}
        data = await self.http_client.get(
            "/api/v1/fleet/policies",
            params=params
        )
        return [Policy(**policy) for policy in data.get("policies", [])]
    
    async def create_policy(self, policy: PolicyCreate) -> Policy:
        """Create a new policy."""
        data = await self.http_client.post(
            "/api/v1/fleet/policies",
            json=policy.model_dump()
        )
        return Policy(**data["policy"])
    
    async def delete_policy(self, policy_id: int) -> None:
        """Delete a policy."""
        await self.http_client.delete(f"/api/v1/fleet/policies/{policy_id}")
    
    # Team Methods
    async def list_teams(self) -> List[Team]:
        """List all teams."""
        data = await self.http_client.get("/api/v1/fleet/teams")
        return [Team(**team) for team in data.get("teams", [])]
    
    async def create_team(self, team: TeamCreate) -> Team:
        """Create a new team."""
        data = await self.http_client.post(
            "/api/v1/fleet/teams",
            json=team.model_dump()
        )
        return Team(**data["team"])
    
    async def delete_team(self, team_id: int) -> None:
        """Delete a team."""
        await self.http_client.delete(f"/api/v1/fleet/teams/{team_id}")
    
    # Custom Variables Methods
    async def list_custom_variables(
        self,
        page: int = 0,
        per_page: int = 100
    ) -> List[CustomVariable]:
        """List all custom variables."""
        params = {"page": page, "per_page": per_page}
        data = await self.http_client.get(
            "/api/v1/fleet/custom_variables",
            params=params
        )
        return [
            CustomVariable(**var) 
            for var in data.get("custom_variables", [])
        ]
    
    async def create_custom_variable(
        self,
        variable: CustomVariableCreate
    ) -> CustomVariable:
        """Create a new custom variable."""
        data = await self.http_client.post(
            "/api/v1/fleet/custom_variables",
            json=variable.model_dump()
        )
        return CustomVariable(**data)
    
    async def delete_custom_variable(self, variable_id: int) -> None:
        """Delete a custom variable."""
        await self.http_client.delete(
            f"/api/v1/fleet/custom_variables/{variable_id}"
        )


def create_fleet_client(
    base_url: Optional[str] = None,
    token: Optional[str] = None,
    settings: Optional[Settings] = None
) -> FleetAPIClient:
    """
    Factory function to create FleetAPIClient instance.
    Implements Dependency Injection pattern.
    
    Args:
        base_url: Fleet API base URL
        token: API authentication token
        settings: Application settings
        
    Returns:
        Configured FleetAPIClient instance
    """
    if settings is None:
        from config import settings as default_settings
        settings = default_settings
    
    base_url = base_url or settings.fleet_api_base_url
    token = token or settings.fleet_api_token
    
    http_client = HTTPXClient(base_url=base_url, token=token)
    return FleetAPIClient(http_client=http_client, settings=settings)
