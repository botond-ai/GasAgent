"""Tests for external tool clients (geolocation, weather, crypto, forex)."""
from __future__ import annotations

import pytest
from unittest.mock import Mock, patch, MagicMock
import requests

from app.tool_clients import (
    IPAPIGeolocationClient,
    OpenWeatherMapClient,
    CoinGeckoClient,
    ExchangeRateAPIClient,
)


class TestIPAPIGeolocationClient:
    @patch("app.tool_clients.requests.Session.get")
    def test_get_location_from_ip_success(self, mock_get):
        """Test successful IP geolocation lookup."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "success",
            "continent": "North America",
            "country": "United States",
            "region": "California",
            "city": "Mountain View",
            "lat": 37.386,
            "lon": -122.084,
            "isp": "Google LLC",
            "org": "Google",
            "timezone": "America/Los_Angeles",
            "query": "8.8.8.8",
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        client = IPAPIGeolocationClient()
        result = client.get_location_from_ip("8.8.8.8")

        assert result is not None
        assert result["ip"] == "8.8.8.8"
        assert result["country"] == "United States"
        assert result["city"] == "Mountain View"

    @patch("app.tool_clients.requests.Session.get")
    def test_get_location_from_ip_failure(self, mock_get):
        """Test IP geolocation lookup failure."""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "fail", "message": "invalid query"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        client = IPAPIGeolocationClient()
        result = client.get_location_from_ip("invalid-ip")

        assert result is None

    @patch("app.tool_clients.requests.Session.get")
    def test_get_location_from_ip_request_exception(self, mock_get):
        """Test geolocation lookup with request exception."""
        mock_get.side_effect = requests.RequestException("Connection error")

        client = IPAPIGeolocationClient()
        result = client.get_location_from_ip("8.8.8.8")

        assert result is None


class TestOpenWeatherMapClient:
    @patch("app.tool_clients.requests.Session.get")
    def test_get_weather_success(self, mock_get):
        """Test successful weather lookup."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "New York",
            "sys": {"country": "US"},
            "main": {
                "temp": 20,
                "feels_like": 19,
                "humidity": 65,
                "pressure": 1013,
            },
            "weather": [{"description": "clear sky"}],
            "wind": {"speed": 5.2},
            "clouds": {"all": 10},
            "dt": 1672531200,
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        client = OpenWeatherMapClient(api_key="test-key")
        result = client.get_weather("New York")

        assert result is not None
        assert result["city"] == "New York"
        assert result["temperature"] == 20

    @patch("app.tool_clients.requests.Session.get")
    def test_get_weather_failure(self, mock_get):
        """Test weather lookup failure."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"message": "city not found"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        client = OpenWeatherMapClient(api_key="test-key")
        result = client.get_weather("InvalidCity")

        assert result is None


class TestCoinGeckoClient:
    @patch("app.tool_clients.requests.Session.get")
    def test_get_crypto_price_success(self, mock_get):
        """Test successful crypto price lookup."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "bitcoin": {
                "usd": 43000,
                "usd_market_cap": 839000000000,
                "usd_24h_vol": 28000000000,
                "usd_24h_change": 5.2,
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        client = CoinGeckoClient()
        result = client.get_crypto_price("bitcoin", "usd")

        assert result is not None
        assert result["price"] == 43000
        assert result["change_24h"] == 5.2

    @patch("app.tool_clients.requests.Session.get")
    def test_get_crypto_price_not_found(self, mock_get):
        """Test crypto price lookup for non-existent coin."""
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        client = CoinGeckoClient()
        result = client.get_crypto_price("unknowncoin", "usd")

        assert result is None


class TestExchangeRateAPIClient:
    @patch("app.tool_clients.requests.Session.get")
    def test_get_exchange_rate_success(self, mock_get):
        """Test successful exchange rate lookup."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "rates": {
                "EUR": 0.92,
                "GBP": 0.79,
                "JPY": 133.5,
            },
            "date": "2024-01-17",
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        client = ExchangeRateAPIClient()
        result = client.get_exchange_rate("USD", "EUR")

        assert result is not None
        assert result["rate"] == 0.92
        assert result["base"] == "USD"

    @patch("app.tool_clients.requests.Session.get")
    def test_get_exchange_rate_currency_not_found(self, mock_get):
        """Test exchange rate lookup for non-existent currency."""
        mock_response = Mock()
        mock_response.json.return_value = {"rates": {}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        client = ExchangeRateAPIClient()
        result = client.get_exchange_rate("USD", "INVALID")

        assert result is None
