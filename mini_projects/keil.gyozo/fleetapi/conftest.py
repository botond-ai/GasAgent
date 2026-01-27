"""
Pytest configuration and fixtures.
Provides reusable test fixtures following SOLID principles.
"""

import pytest
from typing import AsyncGenerator, Dict, Any
from unittest.mock import AsyncMock, MagicMock

from config import Settings
from fleet_client import FleetAPIClient, HTTPClientInterface
from models import LoginResponse, UserResponse, HostDetail


class MockHTTPClient(HTTPClientInterface):
    """Mock HTTP client for testing."""
    
    def __init__(self):
        self.get_mock = AsyncMock()
        self.post_mock = AsyncMock()
        self.patch_mock = AsyncMock()
        self.delete_mock = AsyncMock()
    
    async def get(self, url: str, **kwargs) -> Dict[str, Any]:
        return await self.get_mock(url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> Dict[str, Any]:
        return await self.post_mock(url, **kwargs)
    
    async def patch(self, url: str, **kwargs) -> Dict[str, Any]:
        return await self.patch_mock(url, **kwargs)
    
    async def delete(self, url: str, **kwargs) -> Dict[str, Any]:
        return await self.delete_mock(url, **kwargs)


@pytest.fixture
def mock_settings() -> Settings:
    """Provide mock settings for testing."""
    return Settings(
        fleet_api_base_url="https://test.fleet.local",
        fleet_api_token="test-token-123",
        test_mode=True
    )


@pytest.fixture
def mock_http_client() -> MockHTTPClient:
    """Provide mock HTTP client for testing."""
    return MockHTTPClient()


@pytest.fixture
def fleet_client(
    mock_http_client: MockHTTPClient,
    mock_settings: Settings
) -> FleetAPIClient:
    """Provide FleetAPIClient with mocked dependencies."""
    return FleetAPIClient(
        http_client=mock_http_client,
        settings=mock_settings
    )


@pytest.fixture
def sample_user_data() -> Dict[str, Any]:
    """Sample user data for testing."""
    return {
        "created_at": "2020-11-13T22:57:12Z",
        "updated_at": "2020-11-13T22:57:12Z",
        "id": 1,
        "name": "Jane Doe",
        "email": "janedoe@example.com",
        "enabled": True,
        "force_password_reset": False,
        "gravatar_url": "",
        "sso_enabled": False,
        "mfa_enabled": False,
        "global_role": "admin",
        "teams": []
    }


@pytest.fixture
def sample_login_response(sample_user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Sample login response for testing."""
    return {
        "user": sample_user_data,
        "token": "test-token-abc123"
    }


@pytest.fixture
def sample_host_data() -> Dict[str, Any]:
    """Sample host data for testing."""
    return {
        "id": 1,
        "created_at": "2021-01-01T00:00:00Z",
        "updated_at": "2021-01-01T00:00:00Z",
        "hostname": "test-host",
        "display_name": "Test Host",
        "platform": "ubuntu",
        "osquery_version": "5.0.0",
        "status": "online",
        "team_id": None,
        "seen_time": "2021-01-01T00:00:00Z",
        "primary_ip": "192.168.1.100",
        "primary_mac": "00:11:22:33:44:55",
        "hardware_serial": "ABC123",
        "computer_name": "test-computer",
        "os_version": "Ubuntu 20.04",
        "uptime": 3600000,
        "memory": 8589934592,
        "cpu_type": "Intel Core i7"
    }


# Pytest configuration
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests"
    )
    config.addinivalue_line(
        "markers", "asyncio: Async tests"
    )
