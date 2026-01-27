"""
Fleet API module - FleetDM integration for the support system.
"""
from .client import FleetAPIClient, create_fleet_client, HTTPXClient
from .models import HostDetail, HostSummary
from .exceptions import (
    FleetAPIException,
    AuthenticationError,
    AuthorizationError,
    ResourceNotFoundError,
    NetworkError
)

__all__ = [
    "FleetAPIClient",
    "create_fleet_client",
    "HTTPXClient",
    "HostDetail",
    "HostSummary",
    "FleetAPIException",
    "AuthenticationError",
    "AuthorizationError",
    "ResourceNotFoundError",
    "NetworkError",
]
