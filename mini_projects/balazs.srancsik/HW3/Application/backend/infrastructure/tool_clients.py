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
    IBookRAGClient, IGoogleDriveClient
)
import logging

logger = logging.getLogger(__name__)


class OpenMeteoWeatherClient(IWeatherClient):
    """Open-Meteo weather API client."""
    
    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    
    def __init__(self, geocode_client: IGeocodeClient):
        self.geocode_client = geocode_client
    
    async def get_forecast(self, city: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None) -> Dict[str, Any]:
        """Get weather forecast."""
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
            
            async with httpx.AsyncClient(timeout=10.0) as client:
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
        except Exception as e:
            logger.error(f"Weather API error: {e}")
            return {"error": str(e)}
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        return await self.get_forecast(**kwargs)


class NominatimGeocodeClient(IGeocodeClient):
    """OpenStreetMap Nominatim geocoding client."""
    
    GEOCODE_URL = "https://nominatim.openstreetmap.org/search"
    REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
    
    async def geocode(self, address: str) -> Dict[str, Any]:
        """Convert address to coordinates."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
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
        except Exception as e:
            logger.error(f"Geocoding error: {e}")
            return {"error": str(e)}
    
    async def reverse_geocode(self, lat: float, lon: float) -> Dict[str, Any]:
        """Convert coordinates to address."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.REVERSE_URL,
                    params={"lat": lat, "lon": lon, "format": "json"},
                    headers={"User-Agent": "AI-Agent-Demo/1.0"}
                )
                response.raise_for_status()
                data = response.json()
                
                logger.info(f"Reverse geocoded ({lat}, {lon})")
                
                return {
                    "display_name": data["display_name"],
                    "address": data.get("address", {})
                }
        except Exception as e:
            logger.error(f"Reverse geocoding error: {e}")
            return {"error": str(e)}
    
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


class BookRAGClient(IBookRAGClient):
    """
    Book RAG (Retrieval-Augmented Generation) client using LangChain and FAISS.
    
    This client:
    - Loads and processes PDF documents
    - Creates embeddings using OpenAI embeddings
    - Stores vectors in FAISS for efficient retrieval
    - Uses OpenAI for generating answers based on retrieved context
    """
    
    def __init__(
        self,
        pdf_path: str,
        openai_api_key: str,
        persist_directory: str = "data/book_vectordb",
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        self.pdf_path = Path(pdf_path)
        self.openai_api_key = openai_api_key
        self.persist_directory = Path(persist_directory)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        self._vectorstore = None
        self._book_info = None
        self._initialized = False
    
    def _initialize(self):
        """Initialize the RAG pipeline (lazy loading)."""
        if self._initialized:
            return
        
        logger.info(f"Initializing Book RAG pipeline for: {self.pdf_path}")
        
        try:
            from langchain_community.document_loaders import PyPDFLoader
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
                self._book_info = {
                    "title": self.pdf_path.stem,
                    "path": str(self.pdf_path),
                    "chunks_count": len(self._vectorstore.docstore._dict),
                    "status": "loaded_from_cache"
                }
                logger.info(f"Loaded FAISS vector store")
            else:
                # Load and process PDF
                logger.info(f"Loading PDF: {self.pdf_path}")
                loader = PyPDFLoader(str(self.pdf_path))
                documents = loader.load()
                
                logger.info(f"Loaded {len(documents)} pages from PDF")
                
                # Split into chunks
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
                
                self._book_info = {
                    "title": self.pdf_path.stem,
                    "path": str(self.pdf_path),
                    "pages_count": len(documents),
                    "chunks_count": len(chunks),
                    "status": "newly_indexed"
                }
                
                logger.info(f"Created FAISS vector store with {len(chunks)} chunks")
            
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize Book RAG pipeline: {e}", exc_info=True)
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

    async def query(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Query the book content using RAG pipeline.
        
        Args:
            question: The question to answer based on book content
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
            logger.info(f"Querying book: '{question[:50]}...' (Detected language: {detected_lang})")
            
            # Configure language-specific system messages based on detected language
            language_system_messages = {
                'hu': "Te egy magyar nyelvű könyv-asszisztens vagy. Válaszolj MINDIG MAGYARUL a megadott könyvrészletek alapján. Ha a kontextus más nyelven van, fordítsd le a választ magyarra. Soha ne válaszolj angolul vagy más nyelven.",
                'de': "Sie sind ein deutschsprachiger Buchassistent. Antworten Sie IMMER auf DEUTSCH basierend auf dem Buchkontext. Wenn der Kontext in einer anderen Sprache ist, übersetzen Sie die Antwort ins Deutsche. Antworten Sie niemals auf Englisch oder einer anderen Sprache.",
                'fr': "Vous êtes un assistant de livre en français. Répondez TOUJOURS en FRANÇAIS basé sur le contexte du livre. Si le contexte est dans une autre langue, traduisez la réponse en français. Ne répondez jamais en anglais ou dans une autre langue.",
                'es': "Eres un asistente de libros en español. Responde SIEMPRE en ESPAÑOL basándote en el contexto del libro. Si el contexto está en otro idioma, traduce la respuesta al español. Nunca respondas en inglés u otro idioma.",
                'it': "Sei un assistente di libri in italiano. Rispondi SEMPRE in ITALIANO basandoti sul contesto del libro. Se il contesto è in un'altra lingua, traduci la risposta in italiano. Non rispondere mai in inglese o in un'altra lingua.",
                'pt': "Você é um assistente de livros em português. Responda SEMPRE em PORTUGUÊS com base no contexto do livro. Se o contexto estiver em outro idioma, traduza a resposta para o português. Nunca responda em inglês ou outro idioma.",
                'ru': "Вы книжный ассистент на русском языке. ВСЕГДА отвечайте на РУССКОМ на основе контекста книги. Если контекст на другом языке, переведите ответ на русский. Никогда не отвечайте на английском или другом языке.",
                'en': "You are an English-speaking book assistant. ALWAYS answer in ENGLISH based on the book context. If the context is in another language, translate the answer to English. Never respond in another language."
            }
            
            # Get system message for detected language, default to English
            system_message = language_system_messages.get(detected_lang, language_system_messages['en'])

            # Retrieve relevant chunks
            retriever = self._vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": top_k}
            )
            
            # Get relevant documents (Synchronous invoke to avoid event loop issues)
            docs = retriever.invoke(question)
            
            # Build context
            context = "\n\n".join([doc.page_content for doc in docs])
            
            # Create prompt with proper system/user message structure
            from langchain_core.messages import SystemMessage, HumanMessage
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_message),
                ("human", """Context from the book:
{context}

Question: {question}

Provide your answer based on the context above.""")
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
            
            # Extract sources
            sources = []
            for doc in docs:
                sources.append({
                    "page": doc.metadata.get("page", "unknown"),
                    "content_preview": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
                })
            
            logger.info(f"Query completed, found {len(sources)} relevant sources")
            
            return {
                "answer": answer,
                "sources": sources,
                "question": question,
                "book_title": self._book_info.get("title", "Unknown")
            }
            
        except Exception as e:
            logger.error(f"Book query error: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def get_book_info(self) -> Dict[str, Any]:
        """Get information about the loaded book."""
        try:
            self._initialize()
            return self._book_info
        except Exception as e:
            logger.error(f"Get book info error: {e}")
            return {"error": str(e)}
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute book RAG operations."""
        action = kwargs.get("action", "query")
        
        if action == "query":
            question = kwargs.get("question", "")
            if not question:
                return {"error": "Question is required for query action"}
            top_k = kwargs.get("top_k", 5)
            return await self.query(question, top_k)
        elif action == "info":
            return await self.get_book_info()
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
