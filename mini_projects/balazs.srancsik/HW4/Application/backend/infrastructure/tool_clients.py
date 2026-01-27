"""
Infrastructure layer - External API client implementations.
Following SOLID: Single Responsibility - each client handles one external service.
Open/Closed Principle - easy to add new tool clients without modifying existing ones.
"""
import httpx
from typing import Dict, Any, Optional, List
from pathlib import Path
from domain.interfaces import (
    IWeatherClient, IGeocodeClient, IIPGeolocationClient, 
    IFXRatesClient, ICryptoPriceClient, IRadioBrowserClient,
    IDocumentsRAGClient, IGoogleDriveClient
)
import logging

logger = logging.getLogger(__name__)


class OpenMeteoWeatherClient(IWeatherClient):
    """Open-Meteo weather API client."""
    
    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    DEFAULT_TIMEOUT = 15.0
    MAX_RETRIES = 2
    
    def __init__(self, geocode_client: IGeocodeClient):
        self.geocode_client = geocode_client
    
    async def get_forecast(self, city: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None) -> Dict[str, Any]:
        """Get weather forecast with retry logic."""
        try:
            # If city is provided, geocode it first
            if city and (lat is None or lon is None):
                geo_result = await self.geocode_client.geocode(city)
                if "error" in geo_result:
                    return geo_result
                lat = geo_result["latitude"]
                lon = geo_result["longitude"]
            
            if lat is None or lon is None:
                return {"error": "Either city or coordinates must be provided"}
            
            # Validate coordinates
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                return {"error": f"Invalid coordinates: lat={lat}, lon={lon}"}
            
            last_error = None
            for attempt in range(self.MAX_RETRIES + 1):
                try:
                    async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT) as client:
                        response = await client.get(
                            self.BASE_URL,
                            params={
                                "latitude": lat,
                                "longitude": lon,
                                "current": "temperature_2m,weathercode",
                                "hourly": "temperature_2m,weathercode",
                                "forecast_days": 2
                            }
                        )
                        response.raise_for_status()
                        data = response.json()
                        
                        logger.info(f"Fetched weather for coords ({lat}, {lon})")
                        
                        return {
                            "location": {"latitude": lat, "longitude": lon},
                            "current_temperature": data["current"]["temperature_2m"],
                            "hourly_forecast": data["hourly"],
                            "units": data.get("hourly_units", {})
                        }
                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    last_error = e
                    if attempt < self.MAX_RETRIES:
                        logger.warning(f"Weather API retry {attempt + 1}/{self.MAX_RETRIES}: {e}")
                        import asyncio
                        await asyncio.sleep(1.0 * (attempt + 1))
                    continue
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (429, 500, 502, 503, 504) and attempt < self.MAX_RETRIES:
                        logger.warning(f"Weather API retry {attempt + 1}/{self.MAX_RETRIES}: HTTP {e.response.status_code}")
                        import asyncio
                        await asyncio.sleep(2.0 * (attempt + 1))
                        continue
                    raise
            
            if last_error:
                raise last_error
                
        except httpx.TimeoutException:
            logger.error(f"Weather API timeout for ({lat}, {lon})")
            return {"error": "Weather service timed out. Please try again."}
        except httpx.ConnectError:
            logger.error(f"Weather API connection error for ({lat}, {lon})")
            return {"error": "Unable to connect to weather service. Please try again later."}
        except httpx.HTTPStatusError as e:
            logger.error(f"Weather API HTTP error: {e.response.status_code}")
            return {"error": f"Weather service error (HTTP {e.response.status_code})"}
        except Exception as e:
            logger.error(f"Weather API error: {e}", exc_info=True)
            return {"error": f"Weather lookup failed: {str(e)[:100]}"}
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        return await self.get_forecast(**kwargs)


class NominatimGeocodeClient(IGeocodeClient):
    """OpenStreetMap Nominatim geocoding client."""
    
    GEOCODE_URL = "https://nominatim.openstreetmap.org/search"
    REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
    DEFAULT_TIMEOUT = 15.0
    
    async def geocode(self, address: str) -> Dict[str, Any]:
        """Convert address to coordinates."""
        if not address or not address.strip():
            return {"error": "Address cannot be empty"}
        
        # Sanitize address (limit length)
        address = address.strip()[:500]
        
        try:
            async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT) as client:
                response = await client.get(
                    self.GEOCODE_URL,
                    params={"q": address, "format": "json", "limit": 1},
                    headers={"User-Agent": "AI-Agent-Demo/1.0"}
                )
                response.raise_for_status()
                data = response.json()
                
                if not data:
                    return {"error": f"Location not found: {address}"}
                
                result = data[0]
                logger.info(f"Geocoded '{address}' to ({result['lat']}, {result['lon']})")
                
                return {
                    "latitude": float(result["lat"]),
                    "longitude": float(result["lon"]),
                    "display_name": result["display_name"]
                }
        except httpx.TimeoutException:
            logger.error(f"Geocoding timeout for: {address}")
            return {"error": "Geocoding service timed out. Please try again."}
        except httpx.ConnectError:
            logger.error(f"Geocoding connection error for: {address}")
            return {"error": "Unable to connect to geocoding service."}
        except httpx.HTTPStatusError as e:
            logger.error(f"Geocoding HTTP error: {e.response.status_code}")
            return {"error": f"Geocoding service error (HTTP {e.response.status_code})"}
        except (ValueError, KeyError) as e:
            logger.error(f"Geocoding parse error: {e}")
            return {"error": "Invalid response from geocoding service"}
        except Exception as e:
            logger.error(f"Geocoding error: {e}", exc_info=True)
            return {"error": f"Geocoding failed: {str(e)[:100]}"}
    
    async def reverse_geocode(self, lat: float, lon: float) -> Dict[str, Any]:
        """Convert coordinates to address."""
        # Validate coordinates
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return {"error": f"Invalid coordinates: lat={lat}, lon={lon}"}
        
        try:
            async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT) as client:
                response = await client.get(
                    self.REVERSE_URL,
                    params={"lat": lat, "lon": lon, "format": "json"},
                    headers={"User-Agent": "AI-Agent-Demo/1.0"}
                )
                response.raise_for_status()
                data = response.json()
                
                if "error" in data:
                    return {"error": data.get("error", "Location not found")}
                
                logger.info(f"Reverse geocoded ({lat}, {lon})")
                
                return {
                    "display_name": data.get("display_name", "Unknown location"),
                    "address": data.get("address", {})
                }
        except httpx.TimeoutException:
            logger.error(f"Reverse geocoding timeout for ({lat}, {lon})")
            return {"error": "Reverse geocoding service timed out."}
        except httpx.ConnectError:
            logger.error(f"Reverse geocoding connection error")
            return {"error": "Unable to connect to geocoding service."}
        except httpx.HTTPStatusError as e:
            logger.error(f"Reverse geocoding HTTP error: {e.response.status_code}")
            return {"error": f"Geocoding service error (HTTP {e.response.status_code})"}
        except Exception as e:
            logger.error(f"Reverse geocoding error: {e}", exc_info=True)
            return {"error": f"Reverse geocoding failed: {str(e)[:100]}"}
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        if "address" in kwargs:
            return await self.geocode(kwargs["address"])
        elif "lat" in kwargs and "lon" in kwargs:
            return await self.reverse_geocode(kwargs["lat"], kwargs["lon"])
        return {"error": "Either address or lat/lon required"}


class IPAPIGeolocationClient(IIPGeolocationClient):
    """ipapi.co IP geolocation client."""
    
    BASE_URL = "https://ipapi.co"
    
    async def get_location(self, ip_address: str) -> Dict[str, Any]:
        """Get location from IP address."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.BASE_URL}/{ip_address}/json/")
                response.raise_for_status()
                data = response.json()
                
                if "error" in data:
                    return {"error": data["reason"]}
                
                logger.info(f"Resolved IP {ip_address} to {data.get('city')}, {data.get('country_name')}")
                
                return {
                    "ip": ip_address,
                    "city": data.get("city"),
                    "region": data.get("region"),
                    "country": data.get("country_name"),
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude")
                }
        except Exception as e:
            logger.error(f"IP geolocation error: {e}")
            return {"error": str(e)}
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        return await self.get_location(kwargs.get("ip_address", ""))


class ExchangeRateHostClient(IFXRatesClient):
    """ExchangeRate.host API client - using frankfurter.app (free, no API key needed)."""
    
    BASE_URL = "https://api.frankfurter.app"
    
    async def get_rate(self, base: str, target: str, date: Optional[str] = None) -> Dict[str, Any]:
        """Get exchange rate."""
        try:
            # Frankfurter uses date in URL path or 'latest'
            endpoint = f"{self.BASE_URL}/{date if date else 'latest'}"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    endpoint,
                    params={"from": base, "to": target}
                )
                response.raise_for_status()
                data = response.json()
                
                # Check if we got a valid response
                if "rates" not in data or target not in data["rates"]:
                    return {"error": f"Exchange rate not available for {base} to {target}"}
                
                rate = data["rates"][target]
                logger.info(f"FX rate: 1 {base} = {rate} {target}")
                
                return {
                    "base": base,
                    "target": target,
                    "rate": rate,
                    "date": data.get("date")
                }
        except httpx.HTTPStatusError as e:
            logger.error(f"FX rate HTTP error: {e}")
            return {"error": f"Currency not supported: {e.response.status_code}"}
        except Exception as e:
            logger.error(f"FX rate error: {e}")
            return {"error": str(e)}
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        return await self.get_rate(
            kwargs.get("base", "EUR"),
            kwargs.get("target", "USD"),
            kwargs.get("date")
        )


class CoinGeckoCryptoClient(ICryptoPriceClient):
    """CoinGecko cryptocurrency price client."""
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    
    async def get_price(self, symbol: str, fiat: str = "USD") -> Dict[str, Any]:
        """Get crypto price."""
        try:
            # Convert symbol to CoinGecko ID (simplified mapping)
            coin_map = {
                "BTC": "bitcoin",
                "ETH": "ethereum",
                "USDT": "tether",
                "BNB": "binancecoin",
                "SOL": "solana",
                "ADA": "cardano",
                "XRP": "ripple",
                "DOT": "polkadot"
            }
            coin_id = coin_map.get(symbol.upper(), symbol.lower())
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/simple/price",
                    params={
                        "ids": coin_id,
                        "vs_currencies": fiat.lower(),
                        "include_24hr_change": "true"
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                if coin_id not in data:
                    return {"error": f"Cryptocurrency {symbol} not found"}
                
                price = data[coin_id][fiat.lower()]
                change_24h = data[coin_id].get(f"{fiat.lower()}_24h_change", 0)
                
                logger.info(f"Crypto price: {symbol} = {price} {fiat}")
                
                return {
                    "symbol": symbol,
                    "fiat": fiat,
                    "price": price,
                    "change_24h": round(change_24h, 2)
                }
        except Exception as e:
            logger.error(f"Crypto price error: {e}")
            return {"error": str(e)}
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        return await self.get_price(
            kwargs.get("symbol", "BTC"),
            kwargs.get("fiat", "USD")
        )


class RadioBrowserClient(IRadioBrowserClient):
    """
    Radio Browser API client using direct HTTP calls to Radio Browser API servers.
    
    API Documentation: https://api.radio-browser.info
    
    Supports:
    - Advanced station search (by name, country, language, tag, etc.)
    - Top stations by votes, clicks, or recent activity
    - Browse available countries, languages, and tags/genres
    """
    
    API_SERVERS = [
        "https://de1.api.radio-browser.info",
        "https://fi1.api.radio-browser.info",
        "https://nl1.api.radio-browser.info",
        "https://at1.api.radio-browser.info",
    ]
    USER_AGENT = "AI-Agent-RadioBrowser/1.0"
    
    def __init__(self):
        self._working_server: Optional[str] = None
    
    async def _request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Make an async HTTP request to the Radio Browser API with server fallback."""
        
        servers_to_try = [self._working_server] if self._working_server else []
        servers_to_try.extend([s for s in self.API_SERVERS if s != self._working_server])
        
        last_error = None
        
        for server in servers_to_try:
            if not server:
                continue
            url = f"{server}{endpoint}"
            logger.info(f"Radio Browser API request: {url} params={params}")
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    response = await client.get(
                        url,
                        params=params,
                        headers={"User-Agent": self.USER_AGENT}
                    )
                    response.raise_for_status()
                    data = response.json()
                    logger.info(f"Radio Browser API response from {server}: status={response.status_code}, type={type(data).__name__}, len={len(data) if isinstance(data, list) else 'N/A'}")
                    self._working_server = server
                    return data
            except httpx.HTTPStatusError as e:
                logger.error(f"Radio Browser API HTTP error from {server}: {e}")
                last_error = f"API request failed: {e.response.status_code}"
            except httpx.ConnectError as e:
                logger.warning(f"Radio Browser API connection error from {server}: {e}")
                last_error = f"Connection failed: {str(e)}"
            except httpx.TimeoutException as e:
                logger.warning(f"Radio Browser API timeout from {server}: {e}")
                last_error = f"Request timed out: {str(e)}"
            except httpx.RequestError as e:
                logger.warning(f"Radio Browser API request error from {server}: {e}")
                last_error = f"Request failed: {str(e)}"
            except Exception as e:
                logger.error(f"Radio Browser API error from {server}: {e}", exc_info=True)
                last_error = str(e)
        
        logger.error(f"All Radio Browser API servers failed. Last error: {last_error}")
        return {"error": f"All API servers failed. Last error: {last_error}"}
    
    def _format_station(self, station: Dict[str, Any]) -> Dict[str, Any]:
        """Format a station response into a clean structure."""
        codec = station.get("codec", "Unknown")
        bitrate = station.get("bitrate", 0)
        quality = f"{codec} @ {bitrate}kbps" if bitrate else codec
        
        return {
            "uuid": station.get("stationuuid"),
            "name": station.get("name", "Unknown Station"),
            "country": station.get("country", ""),
            "country_code": station.get("countrycode", ""),
            "language": station.get("language", ""),
            "tags": station.get("tags", ""),
            "homepage": station.get("homepage") or None,
            "stream_url": station.get("url_resolved") or station.get("url"),
            "favicon": station.get("favicon") or None,
            "quality": quality,
            "votes": station.get("votes", 0),
            "click_count": station.get("clickcount", 0),
            "is_working": station.get("lastcheckok") == 1,
        }
    
    async def search_stations(
        self,
        name: Optional[str] = None,
        country: Optional[str] = None,
        country_code: Optional[str] = None,
        language: Optional[str] = None,
        tag: Optional[str] = None,
        order: str = "votes",
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Advanced search for radio stations with multiple filters.
        
        Args:
            name: Station name (partial match)
            country: Country name (partial match)
            country_code: ISO 3166-1 alpha-2 country code (exact match)
            language: Language name (partial match)
            tag: Tag/genre (partial match)
            order: Sort order - votes, clickcount, name, country, language, etc.
            limit: Maximum number of results (default 10)
        
        Returns:
            Dict with stations list and count
        """
        params = {
            "order": order,
            "reverse": "true",
            "limit": limit,
            "hidebroken": "true",
        }
        
        if name:
            params["name"] = name
        if country:
            params["country"] = country
        if country_code:
            params["countrycode"] = country_code.upper()
        if language:
            params["language"] = language
        if tag:
            params["tag"] = tag
        
        logger.info(f"Searching radio stations with params: {params}")
        data = await self._request("/json/stations/search", params)
        
        if isinstance(data, dict) and "error" in data:
            return data
        
        if not isinstance(data, list):
            return {"error": "Unexpected API response format"}
        
        stations = [self._format_station(s) for s in data]
        
        logger.info(f"Found {len(stations)} radio stations")
        return {
            "stations": stations,
            "count": len(stations),
            "filters": {
                "name": name,
                "country": country,
                "country_code": country_code,
                "language": language,
                "tag": tag,
            }
        }
    
    async def get_top_stations(self, by: str = "votes", limit: int = 10) -> Dict[str, Any]:
        """
        Get top stations by votes, clicks, or recent activity.
        
        Args:
            by: Ranking type - "votes" (topvote), "clicks" (topclick), 
                "recent_clicks" (lastclick), "recently_changed" (lastchange)
            limit: Maximum number of results
        
        Returns:
            Dict with stations list and count
        """
        endpoint_map = {
            "votes": "/json/stations/topvote",
            "clicks": "/json/stations/topclick",
            "recent_clicks": "/json/stations/lastclick",
            "recently_changed": "/json/stations/lastchange",
        }
        
        endpoint = endpoint_map.get(by, "/json/stations/topvote")
        endpoint = f"{endpoint}/{limit}"
        
        logger.info(f"Fetching top stations by {by}, limit {limit}")
        data = await self._request(endpoint)
        
        if isinstance(data, dict) and "error" in data:
            return data
        
        if not isinstance(data, list):
            return {"error": "Unexpected API response format"}
        
        stations = [self._format_station(s) for s in data]
        
        logger.info(f"Retrieved {len(stations)} top stations by {by}")
        return {
            "stations": stations,
            "count": len(stations),
            "ranked_by": by
        }
    
    async def get_countries(self) -> Dict[str, Any]:
        """
        Get list of available countries with station counts.
        
        Returns:
            Dict with countries list
        """
        logger.info("Fetching available countries")
        data = await self._request("/json/countries")
        
        if isinstance(data, dict) and "error" in data:
            return data
        
        if not isinstance(data, list):
            return {"error": "Unexpected API response format"}
        
        countries = [
            {
                "name": c.get("name", ""),
                "code": c.get("iso_3166_1", ""),
                "station_count": c.get("stationcount", 0)
            }
            for c in data
            if c.get("stationcount", 0) > 0
        ]
        
        countries.sort(key=lambda x: x["station_count"], reverse=True)
        
        logger.info(f"Retrieved {len(countries)} countries")
        return {
            "countries": countries[:50],
            "total_countries": len(countries)
        }
    
    async def get_languages(self) -> Dict[str, Any]:
        """
        Get list of available languages with station counts.
        
        Returns:
            Dict with languages list
        """
        logger.info("Fetching available languages")
        data = await self._request("/json/languages")
        
        if isinstance(data, dict) and "error" in data:
            return data
        
        if not isinstance(data, list):
            return {"error": "Unexpected API response format"}
        
        languages = [
            {
                "name": lang.get("name", ""),
                "iso_639": lang.get("iso_639"),
                "station_count": lang.get("stationcount", 0)
            }
            for lang in data
            if lang.get("stationcount", 0) > 0
        ]
        
        languages.sort(key=lambda x: x["station_count"], reverse=True)
        
        logger.info(f"Retrieved {len(languages)} languages")
        return {
            "languages": languages[:50],
            "total_languages": len(languages)
        }
    
    async def get_tags(self, filter_tag: Optional[str] = None) -> Dict[str, Any]:
        """
        Get list of available tags/genres with station counts.
        
        Args:
            filter_tag: Optional filter to search for specific tags
        
        Returns:
            Dict with tags list
        """
        endpoint = f"/json/tags/{filter_tag}" if filter_tag else "/json/tags"
        
        logger.info(f"Fetching tags{f' matching {filter_tag}' if filter_tag else ''}")
        data = await self._request(endpoint)
        
        if isinstance(data, dict) and "error" in data:
            return data
        
        if not isinstance(data, list):
            return {"error": "Unexpected API response format"}
        
        tags = [
            {
                "name": t.get("name", ""),
                "station_count": t.get("stationcount", 0)
            }
            for t in data
            if t.get("stationcount", 0) > 0
        ]
        
        tags.sort(key=lambda x: x["station_count"], reverse=True)
        
        logger.info(f"Retrieved {len(tags)} tags")
        return {
            "tags": tags[:100],
            "total_tags": len(tags),
            "filter": filter_tag
        }
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute a radio browser action based on provided parameters.
        
        Supported actions:
        - search: Search stations with filters (name, country, country_code, language, tag)
        - top: Get top stations (by: votes, clicks, recent_clicks, recently_changed)
        - countries: List available countries
        - languages: List available languages
        - tags: List available tags/genres
        """
        action = kwargs.get("action", "search")
        
        if action == "search":
            return await self.search_stations(
                name=kwargs.get("name"),
                country=kwargs.get("country"),
                country_code=kwargs.get("country_code"),
                language=kwargs.get("language"),
                tag=kwargs.get("tag"),
                order=kwargs.get("order", "votes"),
                limit=kwargs.get("limit", 10)
            )
        elif action == "top":
            return await self.get_top_stations(
                by=kwargs.get("by", "votes"),
                limit=kwargs.get("limit", 10)
            )
        elif action == "countries":
            return await self.get_countries()
        elif action == "languages":
            return await self.get_languages()
        elif action == "tags":
            return await self.get_tags(kwargs.get("filter_tag"))
        else:
            return {"error": f"Unknown action: {action}. Supported: search, top, countries, languages, tags"}


class DocumentsRAGClient(IDocumentsRAGClient):
    """
    Documents RAG (Retrieval-Augmented Generation) client using LangChain and FAISS.
    
    This client:
    - Loads and processes Excel files containing support issue types and details
    - Creates embeddings using OpenAI embeddings
    - Stores vectors in FAISS for efficient retrieval
    - Implements re-ranking (Cohere or LLM-based) for improved relevance
    - Uses OpenAI for generating answers based on retrieved context
    
    Re-ranking workflow (per original_tasks.md):
    - Vector search retrieves top-10 candidates
    - Re-ranker selects top-3 most relevant documents
    """
    
    def __init__(
        self,
        documents_directory: str,
        openai_api_key: str,
        persist_directory: str = "data/documents_vectordb",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        reranker_type: str = "llm",
        cohere_api_key: str = None
    ):
        self.documents_directory = Path(documents_directory)
        self.openai_api_key = openai_api_key
        self.persist_directory = Path(persist_directory)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.reranker_type = reranker_type  # "cohere" or "llm"
        self.cohere_api_key = cohere_api_key
        
        self._vectorstore = None
        self._documents_info = None
        self._initialized = False
        self._cohere_client = None
        
        # Initialize Cohere client if using Cohere re-ranker
        if self.reranker_type == "cohere" and self.cohere_api_key:
            try:
                import cohere
                self._cohere_client = cohere.Client(self.cohere_api_key)
                logger.info("Cohere re-ranker client initialized")
            except ImportError:
                logger.warning("Cohere package not installed, falling back to LLM-based re-ranking")
                self.reranker_type = "llm"
            except Exception as e:
                logger.warning(f"Failed to initialize Cohere client: {e}, falling back to LLM-based re-ranking")
                self.reranker_type = "llm"
        
        logger.info(f"DocumentsRAGClient initialized with re-ranker type: {self.reranker_type}")
    
    def _load_excel_files(self) -> List[Dict[str, Any]]:
        """Load all Excel files from the documents directory and convert to text documents."""
        import pandas as pd
        from langchain_core.documents import Document
        
        documents = []
        excel_files = list(self.documents_directory.glob("*.xlsx"))
        
        logger.info(f"Found {len(excel_files)} Excel files in {self.documents_directory}")
        
        for excel_file in excel_files:
            try:
                df = pd.read_excel(excel_file)
                category = excel_file.stem.replace("_", " ")
                
                logger.info(f"Processing {excel_file.name}: {len(df)} rows")
                
                # Convert each row to a document
                for idx, row in df.iterrows():
                    # Build a rich text representation of the issue
                    content_parts = [f"Category: {category}"]
                    
                    for col in df.columns:
                        value = row[col]
                        if pd.notna(value):
                            content_parts.append(f"{col}: {value}")
                    
                    content = "\n".join(content_parts)
                    
                    # Extract key fields from the row
                    potential_issue = str(row.get("Potential Issue", "")) if "Potential Issue" in df.columns else ""
                    notes_dependencies = str(row.get("Notes / Dependencies", "")) if "Notes / Dependencies" in df.columns else ""
                    
                    # Create document with metadata
                    doc = Document(
                        page_content=content,
                        metadata={
                            "source": excel_file.name,
                            "category": category,
                            "row_index": idx,
                            "issue_type": str(row.get("Potential Issue", row.get("Issue", "Unknown"))) if "Potential Issue" in df.columns or "Issue" in df.columns else "Unknown",
                            "potential_issue": potential_issue,
                            "notes_and_dependencies": notes_dependencies
                        }
                    )
                    documents.append(doc)
                    
            except Exception as e:
                logger.error(f"Error processing {excel_file.name}: {e}")
                continue
        
        return documents
    
    def _initialize(self):
        """Initialize the RAG pipeline (lazy loading)."""
        if self._initialized:
            return
        
        logger.info(f"Initializing Documents RAG pipeline for: {self.documents_directory}")
        
        try:
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            from langchain_openai import OpenAIEmbeddings
            from langchain_community.vectorstores import FAISS
            
            # Create embeddings using OpenAI
            embeddings = OpenAIEmbeddings(openai_api_key=self.openai_api_key)
            
            # Check if vectorstore already exists
            faiss_index_path = self.persist_directory / "index.faiss"
            if faiss_index_path.exists():
                logger.info("Loading existing FAISS vector store...")
                self._vectorstore = FAISS.load_local(
                    str(self.persist_directory),
                    embeddings
                )
                self._documents_info = {
                    "directory": str(self.documents_directory),
                    "chunks_count": len(self._vectorstore.docstore._dict),
                    "status": "loaded_from_cache"
                }
                logger.info(f"Loaded FAISS vector store with {self._documents_info['chunks_count']} chunks")
            else:
                # Load and process Excel files
                logger.info(f"Loading Excel files from: {self.documents_directory}")
                documents = self._load_excel_files()
                
                if not documents:
                    raise ValueError(f"No documents found in {self.documents_directory}")
                
                logger.info(f"Loaded {len(documents)} document entries from Excel files")
                
                # Split into chunks (for larger documents)
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                    length_function=len,
                    separators=["\n\n", "\n", " ", ""]
                )
                chunks = text_splitter.split_documents(documents)
                
                logger.info(f"Split into {len(chunks)} chunks")
                
                # Create persist directory
                self.persist_directory.mkdir(parents=True, exist_ok=True)
                
                # Create FAISS vector store
                self._vectorstore = FAISS.from_documents(
                    documents=chunks,
                    embedding=embeddings
                )
                
                # Save to disk
                self._vectorstore.save_local(str(self.persist_directory))
                
                # Get unique categories
                categories = set()
                for doc in documents:
                    categories.add(doc.metadata.get("category", "Unknown"))
                
                self._documents_info = {
                    "directory": str(self.documents_directory),
                    "files_count": len(list(self.documents_directory.glob("*.xlsx"))),
                    "documents_count": len(documents),
                    "chunks_count": len(chunks),
                    "categories": list(categories),
                    "status": "newly_indexed"
                }
                
                logger.info(f"Created FAISS vector store with {len(chunks)} chunks from {len(documents)} documents")
            
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize Documents RAG pipeline: {e}", exc_info=True)
            raise
    
    def _detect_language_lingua(self, text: str) -> str:
        """
        Detect language using lingua-language-detector.
        Returns ISO 639-1 language code (e.g., 'en', 'hu', 'de').
        """
        if not text or len(text.strip()) < 3:
            return "en"
        
        try:
            from lingua import Language, LanguageDetectorBuilder
            
            # Build detector with minimum relative distance for better accuracy
            detector = LanguageDetectorBuilder.from_languages(
                Language.ENGLISH,
                Language.HUNGARIAN,
                Language.GERMAN,
                Language.FRENCH,
                Language.SPANISH,
                Language.ITALIAN,
                Language.PORTUGUESE,
                Language.RUSSIAN
            ).with_minimum_relative_distance(0.15).build()
            
            # Detect language
            detected = detector.detect_language_of(text)
            
            if detected is None:
                logger.warning(f"Could not detect language for: '{text[:50]}...', defaulting to English")
                return "en"
            
            # Map lingua Language enum to ISO 639-1 codes
            lang_map = {
                Language.ENGLISH: "en",
                Language.HUNGARIAN: "hu",
                Language.GERMAN: "de",
                Language.FRENCH: "fr",
                Language.SPANISH: "es",
                Language.ITALIAN: "it",
                Language.PORTUGUESE: "pt",
                Language.RUSSIAN: "ru"
            }
            
            lang_code = lang_map.get(detected, "en")
            logger.info(f"Detected language by lingua: {detected.name} ({lang_code})")
            return lang_code
            
        except Exception as e:
            logger.error(f"Language detection error: {e}, defaulting to English")
            return "en"

    def _rerank_with_cohere(self, query: str, documents: List, top_n: int = 3) -> List:
        """
        Re-rank documents using Cohere Rerank API.
        
        Args:
            query: The search query
            documents: List of documents to re-rank
            top_n: Number of top documents to return after re-ranking
        
        Returns:
            List of top-n re-ranked documents
        """
        if not self._cohere_client or not documents:
            return documents[:top_n]
        
        try:
            # Prepare documents for Cohere
            doc_texts = [doc.page_content for doc in documents]
            
            # Call Cohere Rerank API
            rerank_response = self._cohere_client.rerank(
                query=query,
                documents=doc_texts,
                top_n=top_n,
                model="rerank-english-v3.0"
            )
            
            # Get re-ranked documents
            reranked_docs = []
            for result in rerank_response.results:
                doc = documents[result.index]
                # Add rerank score to metadata
                doc.metadata["rerank_score"] = result.relevance_score
                reranked_docs.append(doc)
            
            logger.info(f"Cohere re-ranking: {len(documents)} -> {len(reranked_docs)} documents")
            return reranked_docs
            
        except Exception as e:
            logger.error(f"Cohere re-ranking failed: {e}, returning original top-{top_n}")
            return documents[:top_n]

    def _rerank_with_llm(self, query: str, documents: List, top_n: int = 3) -> List:
        """
        Re-rank documents using LLM-based scoring.
        
        Args:
            query: The search query
            documents: List of documents to re-rank
            top_n: Number of top documents to return after re-ranking
        
        Returns:
            List of top-n re-ranked documents
        """
        if not documents:
            return []
        
        if len(documents) <= top_n:
            return documents
        
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.prompts import ChatPromptTemplate
            import json
            
            # Create LLM for re-ranking
            llm = ChatOpenAI(
                model="gpt-4-turbo-preview",
                temperature=0,
                openai_api_key=self.openai_api_key
            )
            
            # Prepare document summaries for LLM
            doc_summaries = []
            for i, doc in enumerate(documents):
                summary = {
                    "index": i,
                    "content": doc.page_content[:500],  # Limit content length
                    "source": doc.metadata.get("source", "unknown"),
                    "category": doc.metadata.get("category", "unknown")
                }
                doc_summaries.append(summary)
            
            # Create re-ranking prompt
            rerank_prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a document relevance scorer. Given a query and a list of documents, 
score each document's relevance to the query on a scale of 0-100.

Return ONLY a JSON array of objects with "index" and "score" fields, sorted by score descending.
Example: [{"index": 2, "score": 95}, {"index": 0, "score": 78}, {"index": 1, "score": 45}]"""),
                ("human", """Query: {query}

Documents:
{documents}

Return the top {top_n} most relevant documents as a JSON array with index and score.""")
            ])
            
            # Format documents for prompt
            docs_text = "\n\n".join([
                f"[{d['index']}] Source: {d['source']}, Category: {d['category']}\nContent: {d['content']}"
                for d in doc_summaries
            ])
            
            # Get LLM response
            chain = rerank_prompt | llm
            response = chain.invoke({
                "query": query,
                "documents": docs_text,
                "top_n": top_n
            })
            
            # Parse response
            response_text = response.content.strip()
            # Extract JSON from response (handle markdown code blocks)
            if "```" in response_text:
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            scores = json.loads(response_text)
            
            # Get re-ranked documents
            reranked_docs = []
            for item in scores[:top_n]:
                idx = item.get("index", 0)
                if 0 <= idx < len(documents):
                    doc = documents[idx]
                    doc.metadata["rerank_score"] = item.get("score", 0) / 100.0
                    reranked_docs.append(doc)
            
            logger.info(f"LLM re-ranking: {len(documents)} -> {len(reranked_docs)} documents")
            return reranked_docs
            
        except Exception as e:
            logger.error(f"LLM re-ranking failed: {e}, returning original top-{top_n}")
            return documents[:top_n]

    def _rerank_documents(self, query: str, documents: List, top_n: int = 3) -> List:
        """
        Re-rank documents using configured re-ranker (Cohere or LLM).
        
        Per original_tasks.md:
        - Vector search retrieves top-10 candidates
        - Re-ranker selects top-3 most relevant documents
        
        Args:
            query: The search query
            documents: List of documents from vector search
            top_n: Number of documents to return after re-ranking
        
        Returns:
            List of top-n re-ranked documents
        """
        if self.reranker_type == "cohere" and self._cohere_client:
            return self._rerank_with_cohere(query, documents, top_n)
        else:
            return self._rerank_with_llm(query, documents, top_n)

    async def query(self, question: str, top_k: int = 3) -> Dict[str, Any]:
        """
        Query the documents content using RAG pipeline.
        
        Args:
            question: The question to answer based on document content
            top_k: Number of relevant chunks to retrieve
        
        Returns:
            Dict with answer, sources, and metadata
        """
        try:
            self._initialize()
            
            from langchain_openai import ChatOpenAI
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import StrOutputParser
            
            # Detect language using lingua
            detected_lang = self._detect_language_lingua(question)
            logger.info(f"Querying documents: '{question[:50]}...' (Detected language: {detected_lang})")
            
            # Configure language-specific system messages based on detected language
            language_system_messages = {
                'hu': "Te egy magyar nyelvű ügyfélszolgálati asszisztens vagy. Válaszolj MINDIG MAGYARUL a megadott dokumentumok alapján. A dokumentumok támogatási problématípusokat és megoldásokat tartalmaznak. Adj pontos információt a prioritásról, megoldási időről és felelős csapatról.",
                'de': "Sie sind ein deutschsprachiger Kundensupport-Assistent. Antworten Sie IMMER auf DEUTSCH basierend auf den Dokumenten. Die Dokumente enthalten Support-Problemtypen und Lösungen. Geben Sie genaue Informationen zu Priorität, Lösungszeit und zuständigem Team.",
                'fr': "Vous êtes un assistant de support client en français. Répondez TOUJOURS en FRANÇAIS basé sur les documents. Les documents contiennent des types de problèmes de support et des solutions. Fournissez des informations précises sur la priorité, le temps de résolution et l'équipe responsable.",
                'es': "Eres un asistente de soporte al cliente en español. Responde SIEMPRE en ESPAÑOL basándote en los documentos. Los documentos contienen tipos de problemas de soporte y soluciones. Proporciona información precisa sobre prioridad, tiempo de resolución y equipo responsable.",
                'it': "Sei un assistente di supporto clienti in italiano. Rispondi SEMPRE in ITALIANO basandoti sui documenti. I documenti contengono tipi di problemi di supporto e soluzioni. Fornisci informazioni accurate su priorità, tempo di risoluzione e team responsabile.",
                'pt': "Você é um assistente de suporte ao cliente em português. Responda SEMPRE em PORTUGUÊS com base nos documentos. Os documentos contêm tipos de problemas de suporte e soluções. Forneça informações precisas sobre prioridade, tempo de resolução e equipe responsável.",
                'ru': "Вы ассистент службы поддержки клиентов на русском языке. ВСЕГДА отвечайте на РУССКОМ на основе документов. Документы содержат типы проблем поддержки и решения. Предоставьте точную информацию о приоритете, времени решения и ответственной команде.",
                'en': "You are a customer support assistant. ALWAYS answer in ENGLISH based on the documents. The documents contain support issue types, priorities, resolution times, and responsible teams. Provide accurate information about the issue category, priority level, acknowledgment time, resolution time, owning team, and any associated costs."
            }
            
            # Get system message for detected language, default to English
            system_message = language_system_messages.get(detected_lang, language_system_messages['en'])

            # STEP 1: Vector search - retrieve top-10 candidates (per original_tasks.md)
            retrieval_k = 10  # Retrieve more candidates for re-ranking
            retriever = self._vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": retrieval_k}
            )
            
            # Get relevant documents (Synchronous invoke to avoid event loop issues)
            initial_docs = retriever.invoke(question)
            logger.info(f"Vector search retrieved {len(initial_docs)} candidates")
            
            # STEP 2: Re-ranking - select top-3 most relevant (per original_tasks.md)
            rerank_top_n = min(top_k, 3)  # Re-rank to top-3 as per spec
            docs = self._rerank_documents(question, initial_docs, top_n=rerank_top_n)
            logger.info(f"Re-ranking selected {len(docs)} documents from {len(initial_docs)} candidates")
            
            # Build context from re-ranked documents
            context = "\n\n---\n\n".join([doc.page_content for doc in docs])
            
            # Create prompt with proper system/user message structure
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_message),
                ("human", """Context from support documents:
{context}

User Question: {question}

Based on the context above, provide a helpful answer about the support issue. Include relevant details like:
- Issue category and type
- Priority level (P1/P2/etc.)
- Acknowledgment time
- Resolution time (SLA)
- Responsible team
- Any costs to the customer""")
            ])
            
            # Create LLM
            llm = ChatOpenAI(
                model="gpt-4-turbo-preview",
                temperature=0.3,
                openai_api_key=self.openai_api_key
            )
            
            # Create chain
            chain = prompt | llm | StrOutputParser()
            
            # Run chain (Synchronous invoke)
            answer = chain.invoke({"context": context, "question": question})
            
            # Extract sources with re-rank scores
            sources = []
            for doc in docs:
                sources.append({
                    "source": doc.metadata.get("source", "unknown"),
                    "category": doc.metadata.get("category", "unknown"),
                    "issue_type": doc.metadata.get("issue_type", "unknown"),
                    "potential_issue": doc.metadata.get("potential_issue", ""),
                    "notes_and_dependencies": doc.metadata.get("notes_and_dependencies", ""),
                    "rerank_score": doc.metadata.get("rerank_score", 0.0),
                    "content_preview": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
                })
            
            logger.info(f"Query completed, found {len(sources)} relevant sources (re-ranked)")
            
            return {
                "answer": answer,
                "sources": sources,
                "question": question,
                "detected_language": detected_lang,
                "reranker_type": self.reranker_type,
                "retrieval_stats": {
                    "initial_candidates": len(initial_docs),
                    "after_reranking": len(docs)
                }
            }
            
        except Exception as e:
            logger.error(f"Documents query error: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def get_documents_info(self) -> Dict[str, Any]:
        """Get information about the loaded documents."""
        try:
            self._initialize()
            return self._documents_info
        except Exception as e:
            logger.error(f"Get documents info error: {e}")
            return {"error": str(e)}
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute documents RAG operations."""
        action = kwargs.get("action", "query")
        
        if action == "query":
            question = kwargs.get("question", "")
            if not question:
                return {"error": "Question is required for query action"}
            top_k = kwargs.get("top_k", 5)
            return await self.query(question, top_k)
        elif action == "info":
            return await self.get_documents_info()
        else:
            return {"error": f"Unknown action: {action}. Supported: query, info"}


class GoogleDriveClient(IGoogleDriveClient):
    """
    Google Drive API client for photo uploads.
    
    Uses Google Drive API v3 with service account authentication.
    Requires GOOGLE_DRIVE_CREDENTIALS_JSON environment variable with service account JSON.
    """
    
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
    def __init__(self, credentials_json: str, photo_memories_folder_id: Optional[str] = None, impersonated_user_email: Optional[str] = None):
        """
        Initialize Google Drive client.
        
        Args:
            credentials_json: JSON string containing service account credentials
            photo_memories_folder_id: Optional ID of the Photo_Memories folder. If not provided,
                                     the client will search for it by name.
            impersonated_user_email: Optional email of the user to impersonate (requires domain-wide delegation).
        """
        self.credentials_json = credentials_json
        self._photo_memories_folder_id = photo_memories_folder_id
        self.impersonated_user_email = impersonated_user_email
        self._service = None
        self._initialized = False
    
    def _initialize(self):
        """Initialize the Google Drive service (lazy loading)."""
        if self._initialized:
            return
        
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            import json
            
            # Parse credentials JSON
            creds_dict = json.loads(self.credentials_json)
            
            if self.impersonated_user_email:
                logger.info(f"Initializing Google Drive with Service Account impersonating {self.impersonated_user_email}")
                credentials = service_account.Credentials.from_service_account_info(
                    creds_dict,
                    scopes=self.SCOPES,
                    subject=self.impersonated_user_email
                )
            else:
                logger.info("Initializing Google Drive with standard Service Account credentials")
                credentials = service_account.Credentials.from_service_account_info(
                    creds_dict,
                    scopes=self.SCOPES
                )
            
            # Build the Drive service
            self._service = build('drive', 'v3', credentials=credentials)
            self._initialized = True
            
            logger.info("Google Drive client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive client: {e}", exc_info=True)
            raise
    
    async def _ensure_photo_memories_folder(self) -> str:
        """Ensure Photo_Memories folder exists and return its ID."""
        if self._photo_memories_folder_id:
            return self._photo_memories_folder_id
        
        # Search for existing Photo_Memories folder
        result = await self.find_folder("Photo_Memories")
        if result.get("found"):
            self._photo_memories_folder_id = result["folder_id"]
            return self._photo_memories_folder_id
        
        # Create the folder if it doesn't exist
        result = await self.create_folder("Photo_Memories")
        if result.get("success"):
            self._photo_memories_folder_id = result["folder_id"]
            return self._photo_memories_folder_id
        
        raise Exception("Failed to create or find Photo_Memories folder")
    
    async def create_folder(self, folder_name: str, parent_folder_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a folder in Google Drive."""
        try:
            self._initialize()
            
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            if parent_folder_id:
                file_metadata['parents'] = [parent_folder_id]
            
            folder = self._service.files().create(
                body=file_metadata,
                fields='id, name, webViewLink',
                supportsAllDrives=True
            ).execute()
            
            logger.info(f"Created folder '{folder_name}' with ID: {folder.get('id')}")
            
            return {
                "success": True,
                "folder_id": folder.get('id'),
                "folder_name": folder.get('name'),
                "web_link": folder.get('webViewLink')
            }
            
        except Exception as e:
            logger.error(f"Failed to create folder: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def upload_file(self, file_path: str, file_name: str, folder_id: str, mime_type: str = "image/jpeg") -> Dict[str, Any]:
        """Upload a file to a specific folder in Google Drive."""
        try:
            self._initialize()
            from googleapiclient.http import MediaFileUpload
            
            file_metadata = {
                'name': file_name,
                'parents': [folder_id]
            }
            
            media = MediaFileUpload(
                file_path,
                mimetype=mime_type,
                resumable=True
            )
            
            file = self._service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink, size',
                supportsAllDrives=True
            ).execute()
            
            logger.info(f"Uploaded file '{file_name}' with ID: {file.get('id')}")
            
            return {
                "success": True,
                "file_id": file.get('id'),
                "file_name": file.get('name'),
                "web_link": file.get('webViewLink'),
                "size": file.get('size')
            }
            
        except Exception as e:
            logger.error(f"Failed to upload file: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def upload_file_from_bytes(self, file_bytes: bytes, file_name: str, folder_id: str, mime_type: str = "image/jpeg") -> Dict[str, Any]:
        """Upload a file from bytes to a specific folder in Google Drive."""
        try:
            self._initialize()
            from googleapiclient.http import MediaInMemoryUpload
            
            file_metadata = {
                'name': file_name,
                'parents': [folder_id]
            }
            
            media = MediaInMemoryUpload(
                file_bytes,
                mimetype=mime_type,
                resumable=True
            )
            
            file = self._service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink, size'
            ).execute()
            
            logger.info(f"Uploaded file '{file_name}' with ID: {file.get('id')}")
            
            return {
                "success": True,
                "file_id": file.get('id'),
                "file_name": file.get('name'),
                "web_link": file.get('webViewLink'),
                "size": file.get('size')
            }
            
        except Exception as e:
            logger.error(f"Failed to upload file from bytes: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def find_folder(self, folder_name: str, parent_folder_id: Optional[str] = None) -> Dict[str, Any]:
        """Find a folder by name in Google Drive."""
        try:
            self._initialize()
            
            query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            if parent_folder_id:
                query += f" and '{parent_folder_id}' in parents"
            
            results = self._service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, webViewLink)'
            ).execute()
            
            files = results.get('files', [])
            
            if files:
                folder = files[0]
                logger.info(f"Found folder '{folder_name}' with ID: {folder.get('id')}")
                return {
                    "found": True,
                    "folder_id": folder.get('id'),
                    "folder_name": folder.get('name'),
                    "web_link": folder.get('webViewLink')
                }
            else:
                logger.info(f"Folder '{folder_name}' not found")
                return {"found": False}
                
        except Exception as e:
            logger.error(f"Failed to find folder: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def list_folder_contents(self, folder_id: str) -> Dict[str, Any]:
        """List contents of a folder in Google Drive."""
        try:
            self._initialize()
            
            query = f"'{folder_id}' in parents and trashed = false"
            
            results = self._service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, mimeType, webViewLink, size, createdTime)',
                orderBy='name'
            ).execute()
            
            files = results.get('files', [])
            
            contents = []
            for f in files:
                is_folder = f.get('mimeType') == 'application/vnd.google-apps.folder'
                contents.append({
                    "id": f.get('id'),
                    "name": f.get('name'),
                    "type": "folder" if is_folder else "file",
                    "mime_type": f.get('mimeType'),
                    "web_link": f.get('webViewLink'),
                    "size": f.get('size'),
                    "created_time": f.get('createdTime')
                })
            
            logger.info(f"Listed {len(contents)} items in folder {folder_id}")
            
            return {
                "success": True,
                "folder_id": folder_id,
                "contents": contents,
                "count": len(contents)
            }
            
        except Exception as e:
            logger.error(f"Failed to list folder contents: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def get_folder_structure(self, folder_id: str) -> Dict[str, Any]:
        """Get the folder structure recursively (folders only, one level deep for subfolders)."""
        try:
            self._initialize()
            
            # Get immediate contents
            contents = await self.list_folder_contents(folder_id)
            if "error" in contents:
                return contents
            
            folders = []
            for item in contents.get("contents", []):
                if item["type"] == "folder":
                    folders.append({
                        "id": item["id"],
                        "name": item["name"],
                        "web_link": item["web_link"]
                    })
            
            logger.info(f"Found {len(folders)} subfolders in folder {folder_id}")
            
            return {
                "success": True,
                "folder_id": folder_id,
                "subfolders": folders,
                "count": len(folders)
            }
            
        except Exception as e:
            logger.error(f"Failed to get folder structure: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute Google Drive operations."""
        action = kwargs.get("action", "list")
        
        if action == "create_folder":
            return await self.create_folder(
                kwargs.get("folder_name", ""),
                kwargs.get("parent_folder_id")
            )
        elif action == "upload":
            return await self.upload_file(
                kwargs.get("file_path", ""),
                kwargs.get("file_name", ""),
                kwargs.get("folder_id", ""),
                kwargs.get("mime_type", "image/jpeg")
            )
        elif action == "find_folder":
            return await self.find_folder(
                kwargs.get("folder_name", ""),
                kwargs.get("parent_folder_id")
            )
        elif action == "list":
            return await self.list_folder_contents(kwargs.get("folder_id", ""))
        elif action == "structure":
            return await self.get_folder_structure(kwargs.get("folder_id", ""))
        else:
            return {"error": f"Unknown action: {action}"}


class PCloudClient:
    """
    pCloud API client for photo uploads.
    
    Uses pCloud API with username/password or OAuth authentication.
    Requires PCLOUD_USERNAME and PCLOUD_PASSWORD environment variables,
    or PCLOUD_ACCESS_TOKEN for OAuth.
    
    Implements retry logic with exponential backoff for transient failures.
    """
    
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 2  # seconds
    MAX_RETRY_DELAY = 30  # seconds
    
    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        access_token: Optional[str] = None,
        photo_memories_folder_id: Optional[int] = None,
        endpoint: str = "eapi"
    ):
        """
        Initialize pCloud client.
        
        Args:
            username: pCloud account email (for password auth)
            password: pCloud account password (for password auth)
            access_token: OAuth access token (alternative to username/password)
            photo_memories_folder_id: Optional ID of the Photo_Memories folder.
            endpoint: API endpoint - 'api' for US, 'eapi' for Europe, 'nearest' for auto
        """
        self.username = username
        self.password = password
        self.access_token = access_token
        self._photo_memories_folder_id = photo_memories_folder_id
        self.endpoint = endpoint
        self._client = None
        self._initialized = False
        self._auth_validated = False
    
    def _initialize(self):
        """Initialize the pCloud client (lazy loading)."""
        if self._initialized:
            return
        
        try:
            from pcloud import PyCloud
            
            if self.access_token:
                logger.info("Initializing pCloud with OAuth access token")
                try:
                    self._client = PyCloud(oauth2_token=self.access_token, endpoint=self.endpoint)
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'invalid' in error_msg or 'token' in error_msg:
                        raise ValueError("pCloud OAuth token is invalid or expired. Please refresh your access token.")
                    elif 'auth' in error_msg:
                        raise ValueError(f"pCloud authentication failed: {e}")
                    else:
                        raise ValueError(f"Failed to connect to pCloud: {e}")
            elif self.username and self.password:
                logger.info(f"Initializing pCloud with username: {self.username}")
                try:
                    self._client = PyCloud(self.username, self.password, endpoint=self.endpoint)
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'login' in error_msg or 'password' in error_msg or 'invalid' in error_msg:
                        raise ValueError("pCloud login failed. Please check your username and password.")
                    elif 'locked' in error_msg or 'disabled' in error_msg:
                        raise ValueError("pCloud account is locked or disabled. Please contact pCloud support.")
                    elif 'network' in error_msg or 'connection' in error_msg:
                        raise ConnectionError(f"Cannot connect to pCloud servers: {e}")
                    else:
                        raise ValueError(f"pCloud authentication error: {e}")
            else:
                raise ValueError("pCloud credentials not configured. Either access_token or username/password must be provided.")
            
            self._initialized = True
            logger.info("pCloud client initialized successfully")
            
            # Validate authentication by making a test call
            self._validate_authentication()
            
        except (ValueError, ConnectionError):
            raise
        except Exception as e:
            logger.error(f"Failed to initialize pCloud client: {e}", exc_info=True)
            raise ValueError(f"Unexpected error initializing pCloud: {e}")
    
    def _validate_authentication(self):
        """Validate authentication by making a test API call."""
        if self._auth_validated:
            return
        
        try:
            # Test authentication with a simple API call
            result = self._client.listfolder(folderid=0)
            if result.get('result') != 0:
                error_code = result.get('result')
                if error_code == 2000:
                    raise ValueError("pCloud authentication failed: Invalid credentials")
                elif error_code == 2094:
                    raise ValueError("pCloud authentication failed: Access token expired")
                else:
                    raise ValueError(f"pCloud API error during authentication: {result}")
            
            self._auth_validated = True
            logger.info("pCloud authentication validated successfully")
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Authentication validation failed: {e}")
            raise ValueError(f"Failed to validate pCloud credentials: {e}")
    
    async def _ensure_photo_memories_folder(self) -> int:
        """Ensure Photo_Memories folder exists and return its ID."""
        if self._photo_memories_folder_id:
            return self._photo_memories_folder_id
        
        # Search for existing Photo_Memories folder in root
        result = await self.find_folder("Photo_Memories", parent_folder_id=0)
        if result.get("found"):
            self._photo_memories_folder_id = result["folder_id"]
            return self._photo_memories_folder_id
        
        # Create the folder if it doesn't exist
        result = await self.create_folder("Photo_Memories", parent_folder_id=0)
        if result.get("success"):
            self._photo_memories_folder_id = result["folder_id"]
            return self._photo_memories_folder_id
        
        raise Exception("Failed to create or find Photo_Memories folder")
    
    async def create_folder(self, folder_name: str, parent_folder_id: Optional[int] = None) -> Dict[str, Any]:
        """Create a folder in pCloud."""
        try:
            self._initialize()
            
            parent_id = parent_folder_id if parent_folder_id is not None else 0
            
            # Use createfolderifnotexists to avoid errors if folder already exists
            result = self._client.createfolderifnotexists(
                name=folder_name,
                folderid=parent_id
            )
            
            if result.get('result') == 0:
                metadata = result.get('metadata', {})
                folder_id = metadata.get('folderid')
                folder_path = metadata.get('path', '')
                
                logger.info(f"Created/found folder '{folder_name}' with ID: {folder_id}")
                
                return {
                    "success": True,
                    "folder_id": folder_id,
                    "folder_name": metadata.get('name'),
                    "path": folder_path,
                    "created": result.get('created', False)
                }
            else:
                error_msg = f"pCloud API error: {result}"
                logger.error(error_msg)
                return {"error": error_msg}
            
        except Exception as e:
            logger.error(f"Failed to create folder: {e}", exc_info=True)
            return {"error": str(e)}
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if an error is retryable."""
        error_str = str(error).lower()
        retryable_keywords = [
            'timeout', 'connection', 'network', 'temporary', 'unavailable',
            'rate limit', 'too many requests', '503', '504', '429'
        ]
        return any(keyword in error_str for keyword in retryable_keywords)
    
    async def _retry_with_backoff(self, operation, operation_name: str, *args, **kwargs):
        """Execute operation with exponential backoff retry logic."""
        import asyncio
        import time
        
        last_exception = None
        delay = self.INITIAL_RETRY_DELAY
        
        for attempt in range(self.MAX_RETRIES):
            try:
                return await operation(*args, **kwargs) if asyncio.iscoroutinefunction(operation) else operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if not self._is_retryable_error(e) or attempt == self.MAX_RETRIES - 1:
                    raise
                
                logger.warning(f"{operation_name} failed (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
                delay = min(delay * 2, self.MAX_RETRY_DELAY)  # Exponential backoff with cap
        
        raise last_exception
    
    async def upload_file(self, file_path: str, file_name: str, folder_id: int, mime_type: str = "image/jpeg") -> Dict[str, Any]:
        """Upload a file to a specific folder in pCloud with retry logic."""
        try:
            self._initialize()
            
            # Upload file using the pcloud library with retry
            result = await self._retry_with_backoff(
                lambda: self._client.uploadfile(files=[file_path], folderid=folder_id),
                f"Upload file '{file_name}'"
            )
            
            if result.get('result') == 0:
                metadata_list = result.get('metadata', [])
                if metadata_list:
                    file_metadata = metadata_list[0]
                    file_id = file_metadata.get('fileid')
                    
                    logger.info(f"Uploaded file '{file_name}' with ID: {file_id}")
                    
                    return {
                        "success": True,
                        "file_id": file_id,
                        "file_name": file_metadata.get('name'),
                        "path": file_metadata.get('path'),
                        "size": file_metadata.get('size')
                    }
                else:
                    return {"error": "No metadata returned from upload"}
            else:
                error_code = result.get('result')
                if error_code == 2008:
                    return {"error": "Storage quota exceeded", "error_code": error_code}
                elif error_code == 2009:
                    return {"error": "File already exists", "error_code": error_code}
                else:
                    error_msg = f"pCloud upload error (code {error_code}): {result}"
                    logger.error(error_msg)
                    return {"error": error_msg, "error_code": error_code}
            
        except Exception as e:
            logger.error(f"Failed to upload file: {e}", exc_info=True)
            return {"error": str(e), "retryable": self._is_retryable_error(e)}
    
    async def upload_file_from_bytes(self, file_bytes: bytes, file_name: str, folder_id: int, mime_type: str = "image/jpeg") -> Dict[str, Any]:
        """Upload a file from bytes to a specific folder in pCloud with retry logic."""
        try:
            self._initialize()
            
            # Upload file data directly with retry
            result = await self._retry_with_backoff(
                lambda: self._client.uploadfile(data=file_bytes, filename=file_name, folderid=folder_id),
                f"Upload file '{file_name}' from bytes"
            )
            
            if result.get('result') == 0:
                metadata_list = result.get('metadata', [])
                if metadata_list:
                    file_metadata = metadata_list[0]
                    file_id = file_metadata.get('fileid')
                    
                    logger.info(f"Uploaded file '{file_name}' with ID: {file_id}")
                    
                    return {
                        "success": True,
                        "file_id": file_id,
                        "file_name": file_metadata.get('name'),
                        "path": file_metadata.get('path'),
                        "size": file_metadata.get('size')
                    }
                else:
                    return {"error": "No metadata returned from upload"}
            else:
                error_code = result.get('result')
                if error_code == 2008:
                    return {"error": "Storage quota exceeded", "error_code": error_code}
                elif error_code == 2009:
                    return {"error": "File already exists", "error_code": error_code}
                else:
                    error_msg = f"pCloud upload error (code {error_code}): {result}"
                    logger.error(error_msg)
                    return {"error": error_msg, "error_code": error_code}
            
        except Exception as e:
            logger.error(f"Failed to upload file from bytes: {e}", exc_info=True)
            return {"error": str(e), "retryable": self._is_retryable_error(e)}
    
    async def find_folder(self, folder_name: str, parent_folder_id: Optional[int] = None) -> Dict[str, Any]:
        """Find a folder by name in pCloud."""
        try:
            self._initialize()
            
            parent_id = parent_folder_id if parent_folder_id is not None else 0
            
            # List contents of parent folder
            result = self._client.listfolder(folderid=parent_id)
            
            if result.get('result') == 0:
                metadata = result.get('metadata', {})
                contents = metadata.get('contents', [])
                
                for item in contents:
                    if item.get('isfolder') and item.get('name') == folder_name:
                        folder_id = item.get('folderid')
                        logger.info(f"Found folder '{folder_name}' with ID: {folder_id}")
                        return {
                            "found": True,
                            "folder_id": folder_id,
                            "folder_name": item.get('name'),
                            "path": item.get('path')
                        }
                
                logger.info(f"Folder '{folder_name}' not found in parent {parent_id}")
                return {"found": False}
            else:
                error_msg = f"pCloud API error: {result}"
                logger.error(error_msg)
                return {"error": error_msg}
                
        except Exception as e:
            logger.error(f"Failed to find folder: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def list_folder_contents(self, folder_id: int) -> Dict[str, Any]:
        """List contents of a folder in pCloud."""
        try:
            self._initialize()
            
            result = self._client.listfolder(folderid=folder_id)
            
            if result.get('result') == 0:
                metadata = result.get('metadata', {})
                contents_raw = metadata.get('contents', [])
                
                contents = []
                for item in contents_raw:
                    is_folder = item.get('isfolder', False)
                    contents.append({
                        "id": item.get('folderid') if is_folder else item.get('fileid'),
                        "name": item.get('name'),
                        "type": "folder" if is_folder else "file",
                        "path": item.get('path'),
                        "size": item.get('size'),
                        "created_time": item.get('created')
                    })
                
                logger.info(f"Listed {len(contents)} items in folder {folder_id}")
                
                return {
                    "success": True,
                    "folder_id": folder_id,
                    "contents": contents,
                    "count": len(contents)
                }
            else:
                error_msg = f"pCloud API error: {result}"
                logger.error(error_msg)
                return {"error": error_msg}
            
        except Exception as e:
            logger.error(f"Failed to list folder contents: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def get_folder_structure(self, folder_id: int) -> Dict[str, Any]:
        """Get the folder structure (folders only, one level deep)."""
        try:
            self._initialize()
            
            contents = await self.list_folder_contents(folder_id)
            if "error" in contents:
                return contents
            
            folders = []
            for item in contents.get("contents", []):
                if item["type"] == "folder":
                    folders.append({
                        "id": item["id"],
                        "name": item["name"],
                        "path": item.get("path")
                    })
            
            logger.info(f"Found {len(folders)} subfolders in folder {folder_id}")
            
            return {
                "success": True,
                "folder_id": folder_id,
                "subfolders": folders,
                "count": len(folders)
            }
            
        except Exception as e:
            logger.error(f"Failed to get folder structure: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute pCloud operations."""
        action = kwargs.get("action", "list")
        
        if action == "create_folder":
            return await self.create_folder(
                kwargs.get("folder_name", ""),
                kwargs.get("parent_folder_id")
            )
        elif action == "upload":
            return await self.upload_file(
                kwargs.get("file_path", ""),
                kwargs.get("file_name", ""),
                kwargs.get("folder_id", 0),
                kwargs.get("mime_type", "image/jpeg")
            )
        elif action == "find_folder":
            return await self.find_folder(
                kwargs.get("folder_name", ""),
                kwargs.get("parent_folder_id")
            )
        elif action == "list":
            return await self.list_folder_contents(kwargs.get("folder_id", 0))
        elif action == "structure":
            return await self.get_folder_structure(kwargs.get("folder_id", 0))
        else:
            return {"error": f"Unknown action: {action}"}


class SentimentAnalysisClient:
    """
    Sentiment analysis client using OpenAI API.
    Analyzes text to determine if it's negative, neutral, or positive with confidence.
    """
    
    def __init__(self, openai_api_key: str):
        """
        Initialize SentimentAnalysisClient.
        
        Args:
            openai_api_key: OpenAI API key for sentiment analysis
        """
        self.api_key = openai_api_key
        self.api_url = "https://api.openai.com/v1/chat/completions"
    
    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of the given text.
        
        Args:
            text: The text to analyze
            
        Returns:
            Dict with sentiment, confidence, and explanation
        """
        try:
            logger.info(f"Analyzing sentiment for text: '{text[:50]}...'")
            
            prompt = f"""Analyze the sentiment of the following text and respond with a JSON object.

Text: "{text}"

Respond with ONLY a JSON object in this exact format:
{{
  "sentiment": "positive" or "neutral" or "frustrated",
  "confidence": 0.0 to 1.0,
  "explanation": "Brief explanation of why this sentiment was detected"
}}

Consider:
- Positive: Happy, satisfied, grateful, excited, pleased
- Neutral: Factual, informational, neither positive nor frustrated
- Frustrated: Angry, frustrated, disappointed, upset, complaining, annoyed

Be accurate and consider the overall tone."""

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "system", "content": "You are a sentiment analysis expert. Always respond with valid JSON only."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 150
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                    return {"error": f"API error: {response.status_code}"}
                
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()
                
                # Parse JSON response
                import json
                try:
                    sentiment_data = json.loads(content)
                    return {
                        "sentiment": sentiment_data.get("sentiment", "neutral"),
                        "confidence": float(sentiment_data.get("confidence", 0.5)),
                        "explanation": sentiment_data.get("explanation", "")
                    }
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse sentiment JSON: {content}")
                    # Fallback: try to extract sentiment from text
                    content_lower = content.lower()
                    if "positive" in content_lower:
                        sentiment = "positive"
                    elif "frustrated" in content_lower or "negative" in content_lower:
                        sentiment = "frustrated"
                    else:
                        sentiment = "neutral"
                    
                    return {
                        "sentiment": sentiment,
                        "confidence": 0.7,
                        "explanation": "Sentiment detected from response text"
                    }
        
        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}", exc_info=True)
            return {"error": str(e)}
