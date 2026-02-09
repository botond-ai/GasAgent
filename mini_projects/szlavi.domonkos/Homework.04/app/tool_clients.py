"""Tool clients for external API integrations.

Provides abstractions and concrete implementations for various external APIs
following SOLID principles and dependency injection patterns.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class GeolocationClient(ABC):
    """Abstract geolocation service interface."""

    @abstractmethod
    def get_location_from_ip(self, ip: str) -> Optional[Dict[str, Any]]:
        """Get location information from an IP address.

        Args:
            ip: IP address to geolocate

        Returns:
            Dict with location data or None if failed
        """


class IPAPIGeolocationClient(GeolocationClient):
    """IP geolocation client using ip-api.com (free tier).

    API: https://ip-api.com/docs/api:json
    Free tier: 45 requests per minute
    """

    def __init__(self, use_pro: bool = False, api_key: Optional[str] = None) -> None:
        """Initialize IP API geolocation client.

        Args:
            use_pro: Use pro endpoint (requires API key)
            api_key: API key for pro endpoint
        """
        self.use_pro = use_pro
        self.api_key = api_key
        self.base_url = (
            "http://pro.ip-api.com/json" if use_pro else "http://ip-api.com/json"
        )
        self.session = requests.Session()

    def get_location_from_ip(self, ip: str) -> Optional[Dict[str, Any]]:
        """Get location information from an IP address.

        Returns fields: continent, country, region, city, lat, lon, isp, org, timezone, etc.
        """
        try:
            params = {
                "fields": "status,continent,country,region,city,lat,lon,isp,org,timezone,query"
            }

            if self.use_pro and self.api_key:
                params["key"] = self.api_key

            response = self.session.get(
                self.base_url, params={**params, "query": ip}, timeout=5
            )
            response.raise_for_status()

            data = response.json()

            if data.get("status") == "success":
                logger.info("Geolocation lookup successful for IP: %s", ip)
                return {
                    "ip": ip,
                    "continent": data.get("continent"),
                    "country": data.get("country"),
                    "region": data.get("region"),
                    "city": data.get("city"),
                    "latitude": data.get("lat"),
                    "longitude": data.get("lon"),
                    "isp": data.get("isp"),
                    "organization": data.get("org"),
                    "timezone": data.get("timezone"),
                    "query": data.get("query"),
                }
            else:
                logger.warning(
                    "Geolocation failed for IP %s: %s", ip, data.get("message")
                )
                return None

        except requests.RequestException as exc:
            logger.error("Geolocation request failed: %s", exc)
            return None
        except Exception as exc:
            logger.error("Geolocation error: %s", exc)
            return None


class WeatherClient(ABC):
    """Abstract weather service interface."""

    @abstractmethod
    def get_weather(self, city: str) -> Optional[Dict[str, Any]]:
        """Get weather information for a city."""


class OpenWeatherMapClient(WeatherClient):
    """Weather client using OpenWeatherMap API.

    API: https://openweathermap.org/api
    """

    def __init__(self, api_key: str) -> None:
        """Initialize OpenWeatherMap client.

        Args:
            api_key: OpenWeatherMap API key
        """
        self.api_key = api_key
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"
        self.session = requests.Session()

    def get_weather(self, city: str) -> Optional[Dict[str, Any]]:
        """Get weather information for a city."""
        try:
            params = {"q": city, "appid": self.api_key, "units": "metric"}

            response = self.session.get(self.base_url, params=params, timeout=5)
            response.raise_for_status()

            data = response.json()

            if response.status_code == 200:
                logger.info("Weather lookup successful for city: %s", city)
                weather = data.get("weather", [{}])[0]
                main = data.get("main", {})

                return {
                    "city": data.get("name"),
                    "country": data.get("sys", {}).get("country"),
                    "temperature": main.get("temp"),
                    "feels_like": main.get("feels_like"),
                    "humidity": main.get("humidity"),
                    "pressure": main.get("pressure"),
                    "description": weather.get("description"),
                    "wind_speed": data.get("wind", {}).get("speed"),
                    "clouds": data.get("clouds", {}).get("all"),
                    "timestamp": datetime.fromtimestamp(data.get("dt")).isoformat(),
                }
            else:
                logger.warning("Weather lookup failed: %s", data.get("message"))
                return None

        except requests.RequestException as exc:
            logger.error("Weather request failed: %s", exc)
            return None
        except Exception as exc:
            logger.error("Weather error: %s", exc)
            return None


class CryptoClient(ABC):
    """Abstract cryptocurrency price service interface."""

    @abstractmethod
    def get_crypto_price(
        self, symbol: str, vs_currency: str = "usd"
    ) -> Optional[Dict[str, Any]]:
        """Get cryptocurrency price information."""


class CoinGeckoClient(CryptoClient):
    """Cryptocurrency client using CoinGecko API (free, no key required).

    API: https://www.coingecko.com/en/api
    """

    def __init__(self) -> None:
        """Initialize CoinGecko client."""
        self.base_url = "https://api.coingecko.com/api/v3"
        self.session = requests.Session()

    def get_crypto_price(
        self, symbol: str, vs_currency: str = "usd"
    ) -> Optional[Dict[str, Any]]:
        """Get cryptocurrency price from CoinGecko.

        Args:
            symbol: Crypto symbol (e.g., 'bitcoin', 'ethereum')
            vs_currency: Target currency (default: 'usd')

        Returns:
            Dict with price data or None if failed
        """
        try:
            endpoint = f"{self.base_url}/simple/price"
            params = {
                "ids": symbol.lower(),
                "vs_currencies": vs_currency.lower(),
                "include_market_cap": "true",
                "include_24hr_vol": "true",
                "include_24hr_change": "true",
            }

            response = self.session.get(endpoint, params=params, timeout=5)
            response.raise_for_status()

            data = response.json()

            if symbol.lower() in data:
                price_data = data[symbol.lower()]
                logger.info("Crypto price lookup successful for: %s", symbol)

                return {
                    "symbol": symbol,
                    "currency": vs_currency,
                    "price": price_data.get(vs_currency.lower()),
                    "market_cap": price_data.get(f"{vs_currency.lower()}_market_cap"),
                    "volume_24h": price_data.get(f"{vs_currency.lower()}_24h_vol"),
                    "change_24h": price_data.get(f"{vs_currency.lower()}_24h_change"),
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                logger.warning("Crypto not found: %s", symbol)
                return None

        except requests.RequestException as exc:
            logger.error("Crypto request failed: %s", exc)
            return None
        except Exception as exc:
            logger.error("Crypto error: %s", exc)
            return None


class ForexClient(ABC):
    """Abstract foreign exchange service interface."""

    @abstractmethod
    def get_exchange_rate(self, base: str, target: str) -> Optional[Dict[str, Any]]:
        """Get exchange rate between two currencies."""


class ExchangeRateAPIClient(ForexClient):
    """Forex client using exchangerate-api.com (free tier available).

    API: https://www.exchangerate-api.com
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Initialize ExchangeRate API client.

        Args:
            api_key: API key (optional, free tier available without key)
        """
        self.api_key = api_key
        self.base_url = "https://api.exchangerate-api.com/v4/latest"
        self.session = requests.Session()

    def get_exchange_rate(self, base: str, target: str) -> Optional[Dict[str, Any]]:
        """Get exchange rate between two currencies.

        Args:
            base: Base currency (e.g., 'USD')
            target: Target currency (e.g., 'EUR')

        Returns:
            Dict with exchange rate data or None if failed
        """
        try:
            url = f"{self.base_url}/{base.upper()}"

            response = self.session.get(url, timeout=5)
            response.raise_for_status()

            data = response.json()

            if "rates" in data and target.upper() in data["rates"]:
                rate = data["rates"][target.upper()]
                logger.info("Exchange rate lookup successful: %s -> %s", base, target)

                return {
                    "base": base.upper(),
                    "target": target.upper(),
                    "rate": rate,
                    "timestamp": data.get("date"),
                }
            else:
                logger.warning("Exchange rate not found: %s -> %s", base, target)
                return None

        except requests.RequestException as exc:
            logger.error("Exchange rate request failed: %s", exc)
            return None
        except Exception as exc:
            logger.error("Exchange rate error: %s", exc)
            return None
