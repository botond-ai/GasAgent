"""
Fleet API Client Service.
"""
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
import httpx

from app.core.config import settings
from app.core.logging import get_logger
from .models import HostDetail, HostSummary, Label, LabelCreate, Policy, PolicyCreate, Team, TeamCreate, QueryRequest, QueryResponse
from .exceptions import (
    AuthenticationError, AuthorizationError,
    ResourceNotFoundError, ValidationError,
    RateLimitError, ServerError, NetworkError
)

logger = get_logger(__name__)


class HTTPClientInterface(ABC):
    """Abstract interface for HTTP client."""

    @abstractmethod
    async def get(self, url: str, **kwargs) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def post(self, url: str, **kwargs) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def patch(self, url: str, **kwargs) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def delete(self, url: str, **kwargs) -> Dict[str, Any]:
        pass


class HTTPXClient(HTTPClientInterface):
    """HTTPX implementation of HTTP client."""

    def __init__(self, base_url: str, token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Content-Type": "application/json"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.headers,
                timeout=30.0
            )
        return self._client

    async def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Handle HTTP response and raise appropriate exceptions."""
        try:
            data = response.json()
        except Exception:
            data = {"message": response.text}

        if response.status_code == 401:
            raise AuthenticationError(data.get("message", "Authentication failed"))
        elif response.status_code == 403:
            raise AuthorizationError(data.get("message", "Insufficient permissions"))
        elif response.status_code == 404:
            raise ResourceNotFoundError("Resource")
        elif response.status_code == 422:
            raise ValidationError(data.get("message", "Validation failed"))
        elif response.status_code == 429:
            retry_after = response.headers.get("retry-after")
            raise RateLimitError(retry_after=int(retry_after) if retry_after else None)
        elif response.status_code >= 500:
            raise ServerError(data.get("message", "Internal server error"))

        response.raise_for_status()
        return data

    async def get(self, url: str, **kwargs) -> Dict[str, Any]:
        try:
            client = await self._get_client()
            response = await client.get(url, **kwargs)
            return await self._handle_response(response)
        except httpx.RequestError as e:
            raise NetworkError(f"Network error: {str(e)}")

    async def post(self, url: str, **kwargs) -> Dict[str, Any]:
        try:
            client = await self._get_client()
            response = await client.post(url, **kwargs)
            return await self._handle_response(response)
        except httpx.RequestError as e:
            raise NetworkError(f"Network error: {str(e)}")

    async def patch(self, url: str, **kwargs) -> Dict[str, Any]:
        try:
            client = await self._get_client()
            response = await client.patch(url, **kwargs)
            return await self._handle_response(response)
        except httpx.RequestError as e:
            raise NetworkError(f"Network error: {str(e)}")

    async def delete(self, url: str, **kwargs) -> Dict[str, Any]:
        try:
            client = await self._get_client()
            response = await client.delete(url, **kwargs)
            return await self._handle_response(response)
        except httpx.RequestError as e:
            raise NetworkError(f"Network error: {str(e)}")

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


class FleetAPIClient:
    """Fleet API client with full functionality."""

    def __init__(self, http_client: HTTPClientInterface):
        self.http_client = http_client

    @property
    def enabled(self) -> bool:
        """Check if Fleet API is configured."""
        return bool(settings.fleet_url and settings.fleet_api_token)

    # Host Methods
    async def list_hosts(
        self,
        page: int = 0,
        per_page: int = 100,
        order_key: str = "id",
        order_direction: str = "asc",
        query: Optional[str] = None,
        **filters
    ) -> List[HostDetail]:
        """List all hosts with optional filtering."""
        params = {
            "page": page,
            "per_page": per_page,
            "order_key": order_key,
            "order_direction": order_direction,
            **filters
        }
        if query:
            params["query"] = query

        data = await self.http_client.get("/api/v1/fleet/hosts", params=params)
        return [HostDetail(**host) for host in data.get("hosts", [])]

    async def search_host(self, query: str) -> Optional[HostDetail]:
        """Search for a host by hostname, email, or identifier."""
        try:
            hosts = await self.list_hosts(query=query, per_page=10)
            if hosts:
                logger.info(f"FleetDM found {len(hosts)} host(s) for query: {query}")
                return hosts[0]
            logger.info(f"FleetDM found no hosts for query: {query}")
            return None
        except Exception as e:
            logger.error(f"FleetDM search error: {e}")
            return None

    async def get_host(self, host_id: int) -> HostDetail:
        """Get detailed information about a specific host."""
        data = await self.http_client.get(f"/api/v1/fleet/hosts/{host_id}")
        return HostDetail(**data["host"])

    async def get_host_details(self, host_id: int) -> Optional[HostDetail]:
        """Get detailed information about a host (alias for compatibility)."""
        try:
            return await self.get_host(host_id)
        except Exception as e:
            logger.error(f"FleetDM error retrieving host {host_id}: {e}")
            return None

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
        """Run a live query on selected hosts."""
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
        data = await self.http_client.get("/api/v1/fleet/policies", params=params)
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

    # Utility Methods
    def format_device_context(self, host: Optional[HostDetail]) -> str:
        """Format host information for LLM context."""
        if not host:
            return ""
        return host.format_for_context()


def create_fleet_client(
    base_url: Optional[str] = None,
    token: Optional[str] = None
) -> FleetAPIClient:
    """
    Factory function to create FleetAPIClient instance.

    Args:
        base_url: Fleet API base URL (defaults to settings.fleet_url)
        token: API authentication token (defaults to settings.fleet_api_token)

    Returns:
        Configured FleetAPIClient instance
    """
    base_url = base_url or settings.fleet_url
    token = token or settings.fleet_api_token

    if not base_url:
        logger.warning("FleetDM URL not configured")

    http_client = HTTPXClient(base_url=base_url or "", token=token)
    return FleetAPIClient(http_client=http_client)


# Singleton instance for convenience
_fleet_client: Optional[FleetAPIClient] = None


def get_fleet_client() -> FleetAPIClient:
    """Get or create the Fleet API client singleton."""
    global _fleet_client
    if _fleet_client is None:
        _fleet_client = create_fleet_client()
    return _fleet_client
