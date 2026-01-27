"""
Unit tests for FleetAPIClient.
Tests business logic in isolation using mocked dependencies.
"""

import pytest
from typing import Dict, Any

from fleet_client import FleetAPIClient
from conftest import MockHTTPClient
from models import LoginResponse, UserResponse, HostDetail
from exceptions import AuthenticationError, ResourceNotFoundError


@pytest.mark.unit
@pytest.mark.asyncio
class TestFleetAPIClientAuthentication:
    """Test authentication methods."""
    
    async def test_login_success(
        self,
        fleet_client: FleetAPIClient,
        mock_http_client: MockHTTPClient,
        sample_login_response: Dict[str, Any]
    ):
        """Test successful login."""
        # Arrange
        mock_http_client.post_mock.return_value = sample_login_response
        
        # Act
        result = await fleet_client.login(
            "janedoe@example.com",
            "password123"
        )
        
        # Assert
        assert isinstance(result, LoginResponse)
        assert result.token == "test-token-abc123"
        assert result.user.email == "janedoe@example.com"
        mock_http_client.post_mock.assert_called_once()
    
    async def test_logout_success(
        self,
        fleet_client: FleetAPIClient,
        mock_http_client: MockHTTPClient
    ):
        """Test successful logout."""
        # Arrange
        mock_http_client.post_mock.return_value = {}
        
        # Act
        await fleet_client.logout()
        
        # Assert
        mock_http_client.post_mock.assert_called_once_with(
            "/api/v1/fleet/logout"
        )
    
    async def test_get_me_success(
        self,
        fleet_client: FleetAPIClient,
        mock_http_client: MockHTTPClient,
        sample_user_data: Dict[str, Any]
    ):
        """Test getting current user information."""
        # Arrange
        mock_http_client.get_mock.return_value = {"user": sample_user_data}
        
        # Act
        result = await fleet_client.get_me()
        
        # Assert
        assert isinstance(result, UserResponse)
        assert result.email == "janedoe@example.com"
        assert result.global_role == "admin"
    
    async def test_change_password_success(
        self,
        fleet_client: FleetAPIClient,
        mock_http_client: MockHTTPClient
    ):
        """Test successful password change."""
        # Arrange
        mock_http_client.post_mock.return_value = {}
        
        # Act
        await fleet_client.change_password(
            old_password="old_pass",
            new_password="new_pass"
        )
        
        # Assert
        mock_http_client.post_mock.assert_called_once()
        call_args = mock_http_client.post_mock.call_args
        assert call_args[0][0] == "/api/v1/fleet/change_password"
        assert call_args[1]["json"]["old_password"] == "old_pass"
        assert call_args[1]["json"]["new_password"] == "new_pass"


@pytest.mark.unit
@pytest.mark.asyncio
class TestFleetAPIClientHosts:
    """Test host management methods."""
    
    async def test_list_hosts_success(
        self,
        fleet_client: FleetAPIClient,
        mock_http_client: MockHTTPClient,
        sample_host_data: Dict[str, Any]
    ):
        """Test listing hosts."""
        # Arrange
        mock_http_client.get_mock.return_value = {
            "hosts": [sample_host_data]
        }
        
        # Act
        result = await fleet_client.list_hosts(page=0, per_page=10)
        
        # Assert
        assert len(result) == 1
        assert isinstance(result[0], HostDetail)
        assert result[0].hostname == "test-host"
        
        # Verify correct parameters were passed
        call_args = mock_http_client.get_mock.call_args
        assert call_args[1]["params"]["page"] == 0
        assert call_args[1]["params"]["per_page"] == 10
    
    async def test_get_host_success(
        self,
        fleet_client: FleetAPIClient,
        mock_http_client: MockHTTPClient,
        sample_host_data: Dict[str, Any]
    ):
        """Test getting a specific host."""
        # Arrange
        host_id = 1
        mock_http_client.get_mock.return_value = {"host": sample_host_data}
        
        # Act
        result = await fleet_client.get_host(host_id)
        
        # Assert
        assert isinstance(result, HostDetail)
        assert result.id == host_id
        assert result.hostname == "test-host"
        mock_http_client.get_mock.assert_called_once_with(
            f"/api/v1/fleet/hosts/{host_id}"
        )
    
    async def test_delete_host_success(
        self,
        fleet_client: FleetAPIClient,
        mock_http_client: MockHTTPClient
    ):
        """Test deleting a host."""
        # Arrange
        host_id = 1
        mock_http_client.delete_mock.return_value = {}
        
        # Act
        await fleet_client.delete_host(host_id)
        
        # Assert
        mock_http_client.delete_mock.assert_called_once_with(
            f"/api/v1/fleet/hosts/{host_id}"
        )


@pytest.mark.unit
@pytest.mark.asyncio
class TestFleetAPIClientQueries:
    """Test query execution methods."""
    
    async def test_run_query_with_host_ids(
        self,
        fleet_client: FleetAPIClient,
        mock_http_client: MockHTTPClient
    ):
        """Test running a query with host IDs."""
        # Arrange
        mock_http_client.post_mock.return_value = {
            "campaign_id": 123,
            "query_id": 456
        }
        
        # Act
        result = await fleet_client.run_query(
            query="SELECT * FROM processes",
            host_ids=[1, 2, 3]
        )
        
        # Assert
        assert result.campaign_id == 123
        assert result.query_id == 456
        
        call_args = mock_http_client.post_mock.call_args
        payload = call_args[1]["json"]
        assert payload["query"] == "SELECT * FROM processes"
        assert payload["selected"]["hosts"] == [1, 2, 3]
    
    async def test_run_query_with_label_ids(
        self,
        fleet_client: FleetAPIClient,
        mock_http_client: MockHTTPClient
    ):
        """Test running a query with label IDs."""
        # Arrange
        mock_http_client.post_mock.return_value = {
            "campaign_id": 789
        }
        
        # Act
        result = await fleet_client.run_query(
            query="SELECT * FROM users",
            label_ids=[10, 20]
        )
        
        # Assert
        assert result.campaign_id == 789
        
        call_args = mock_http_client.post_mock.call_args
        payload = call_args[1]["json"]
        assert payload["selected"]["labels"] == [10, 20]


@pytest.mark.unit
@pytest.mark.asyncio
class TestFleetAPIClientLabels:
    """Test label management methods."""
    
    async def test_list_labels(
        self,
        fleet_client: FleetAPIClient,
        mock_http_client: MockHTTPClient
    ):
        """Test listing labels."""
        # Arrange
        mock_http_client.get_mock.return_value = {
            "labels": [
                {
                    "id": 1,
                    "name": "Test Label",
                    "description": "Test description",
                    "query": "SELECT 1",
                    "platform": None,
                    "created_at": "2021-01-01T00:00:00Z",
                    "updated_at": "2021-01-01T00:00:00Z",
                    "type": "regular",
                    "host_count": 5
                }
            ]
        }
        
        # Act
        result = await fleet_client.list_labels()
        
        # Assert
        assert len(result) == 1
        assert result[0].name == "Test Label"
        assert result[0].host_count == 5
    
    async def test_create_label(
        self,
        fleet_client: FleetAPIClient,
        mock_http_client: MockHTTPClient
    ):
        """Test creating a label."""
        # Arrange
        from models import LabelCreate
        
        label_data = {
            "name": "New Label",
            "description": "Label description",
            "query": "SELECT * FROM osquery_info",
            "platform": "darwin"
        }
        
        mock_http_client.post_mock.return_value = {
            "label": {
                **label_data,
                "id": 99,
                "created_at": "2021-01-01T00:00:00Z",
                "updated_at": "2021-01-01T00:00:00Z",
                "type": "regular",
                "host_count": 0
            }
        }
        
        # Act
        label = LabelCreate(**label_data)
        result = await fleet_client.create_label(label)
        
        # Assert
        assert result.id == 99
        assert result.name == "New Label"


@pytest.mark.unit
def test_settings_url_validation():
    """Test that settings properly validates URLs."""
    from config import Settings
    
    # URL with trailing slash should be stripped
    settings = Settings(fleet_api_base_url="https://example.com/")
    assert settings.fleet_api_base_url == "https://example.com"
