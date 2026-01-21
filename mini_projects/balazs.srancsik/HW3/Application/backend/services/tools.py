"""
Service layer - LangGraph agent tools implementation.
Following SOLID: Single Responsibility - each tool wrapper has one clear purpose.
"""
from typing import Dict, Any, Optional
from pathlib import Path
import json
from datetime import datetime
import logging

from domain.interfaces import (
    IWeatherClient, IGeocodeClient, IIPGeolocationClient,
    IFXRatesClient, ICryptoPriceClient, IConversationRepository,
    IRadioBrowserClient, IBookRAGClient
)

logger = logging.getLogger(__name__)


class WeatherTool:
    """Weather forecast tool."""
    
    def __init__(self, client: IWeatherClient):
        self.client = client
        self.name = "weather"
        self.description = "Get weather forecast for a city or coordinates. Useful when user asks about weather, temperature, or forecast."
    
    async def execute(self, city: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None) -> Dict[str, Any]:
        """Get weather forecast."""
        logger.info(f"Weather tool called: city={city}, lat={lat}, lon={lon}")
        result = await self.client.get_forecast(city=city, lat=lat, lon=lon)
        
        if "error" not in result:
            # Format result for agent with today and tomorrow summary
            current_temp = result.get("current_temperature", "N/A")
            hourly = result.get("hourly_forecast", {})
            
            # Extract tomorrow's data (hours 24-47 in the forecast)
            tomorrow_temps = hourly.get("temperature_2m", [])[24:48] if len(hourly.get("temperature_2m", [])) > 24 else []
            tomorrow_avg = sum(tomorrow_temps) / len(tomorrow_temps) if tomorrow_temps else None
            tomorrow_min = min(tomorrow_temps) if tomorrow_temps else None
            tomorrow_max = max(tomorrow_temps) if tomorrow_temps else None
            
            # Format summary
            summary = f"Current temperature: {current_temp}°C. "
            if tomorrow_avg:
                summary += f"Tomorrow's forecast: Min {tomorrow_min:.1f}°C, Max {tomorrow_max:.1f}°C, Avg {tomorrow_avg:.1f}°C."
            
            return {
                "success": True,
                "message": summary,
                "data": {
                    **result,
                    "tomorrow": {
                        "min_temp": tomorrow_min,
                        "max_temp": tomorrow_max,
                        "avg_temp": tomorrow_avg
                    } if tomorrow_avg else None
                },
                "system_message": f"Fetched weather forecast for location ({result['location']['latitude']}, {result['location']['longitude']}). {summary}"
            }
        else:
            return {
                "success": False,
                "error": result["error"],
                "system_message": f"Failed to fetch weather: {result['error']}"
            }


class GeocodeTool:
    """Geocoding and reverse geocoding tool."""
    
    def __init__(self, client: IGeocodeClient):
        self.client = client
        self.name = "geocode"
        self.description = "Convert address to coordinates or coordinates to address. Useful for location lookups."
    
    async def execute(self, address: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None) -> Dict[str, Any]:
        """Geocode or reverse geocode."""
        logger.info(f"Geocode tool called: address={address}, lat={lat}, lon={lon}")
        
        if address:
            result = await self.client.geocode(address)
        elif lat is not None and lon is not None:
            result = await self.client.reverse_geocode(lat, lon)
        else:
            return {
                "success": False,
                "error": "Either address or coordinates required",
                "system_message": "Geocoding failed: missing parameters"
            }
        
        if "error" not in result:
            return {
                "success": True,
                "data": result,
                "system_message": f"Geocoded location: {result.get('display_name', 'Unknown')}"
            }
        else:
            return {
                "success": False,
                "error": result["error"],
                "system_message": f"Geocoding failed: {result['error']}"
            }


class IPGeolocationTool:
    """IP geolocation tool."""
    
    def __init__(self, client: IIPGeolocationClient):
        self.client = client
        self.name = "ip_geolocation"
        self.description = "Get geographic location from IP address. Useful when user provides or asks about IP addresses."
    
    async def execute(self, ip_address: str) -> Dict[str, Any]:
        """Get location from IP."""
        logger.info(f"IP geolocation tool called: ip={ip_address}")
        result = await self.client.get_location(ip_address)
        
        if "error" not in result:
            location_str = f"{result.get('city', 'Unknown')}, {result.get('country', 'Unknown')}"
            return {
                "success": True,
                "data": result,
                "system_message": f"Resolved IP {ip_address} to {location_str} (lat: {result.get('latitude')}, lon: {result.get('longitude')})"
            }
        else:
            return {
                "success": False,
                "error": result["error"],
                "system_message": f"IP geolocation failed: {result['error']}"
            }


class FXRatesTool:
    """Foreign exchange rates tool."""
    
    def __init__(self, client: IFXRatesClient):
        self.client = client
        self.name = "fx_rates"
        self.description = "Get foreign exchange rates between currencies. Useful for currency conversion questions."
    
    async def execute(self, base: str, target: str, date: Optional[str] = None) -> Dict[str, Any]:
        """Get exchange rate."""
        logger.info(f"FX rates tool called: {base} -> {target}, date={date}")
        result = await self.client.get_rate(base, target, date)
        
        if "error" not in result:
            rate = result.get("rate")
            return {
                "success": True,
                "data": result,
                "system_message": f"1 {base} equals {rate} {target} (as of {result.get('date')})"
            }
        else:
            return {
                "success": False,
                "error": result["error"],
                "system_message": f"FX rate lookup failed: {result['error']}"
            }


class CryptoPriceTool:
    """Cryptocurrency price tool."""
    
    def __init__(self, client: ICryptoPriceClient):
        self.client = client
        self.name = "crypto_price"
        self.description = "Get current cryptocurrency prices. Useful when user asks about Bitcoin, Ethereum, or other crypto prices."
    
    async def execute(self, symbol: str, fiat: str = "USD") -> Dict[str, Any]:
        """Get crypto price."""
        logger.info(f"Crypto price tool called: {symbol} in {fiat}")
        result = await self.client.get_price(symbol, fiat)
        
        if "error" not in result:
            price = result.get("price")
            change = result.get("change_24h", 0)
            return {
                "success": True,
                "data": result,
                "system_message": f"{symbol} price is {price} {fiat} with a 24h change of {change:+.2f}%"
            }
        else:
            return {
                "success": False,
                "error": result["error"],
                "system_message": f"Crypto price lookup failed: {result['error']}"
            }


class FileCreationTool:
    """File creation tool for saving user notes/documents."""
    
    def __init__(self, data_dir: str = "data/files"):
        self.data_dir = Path(data_dir)
        self.name = "create_file"
        self.description = "Save text content to a file. Useful when user wants to save notes, plans, or documents."
    
    async def execute(self, user_id: str, filename: str, content: str) -> Dict[str, Any]:
        """Create a file."""
        logger.info(f"File creation tool called: user={user_id}, filename={filename}")
        
        try:
            user_dir = self.data_dir / user_id
            user_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = user_dir / filename
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {
                "success": True,
                "data": {"path": str(file_path), "size": len(content)},
                "system_message": f"Saved content to {file_path}"
            }
        except Exception as e:
            logger.error(f"File creation error: {e}")
            return {
                "success": False,
                "error": str(e),
                "system_message": f"Failed to create file: {e}"
            }


class HistorySearchTool:
    """History search tool for searching past conversations."""
    
    def __init__(self, repository: IConversationRepository):
        self.repository = repository
        self.name = "search_history"
        self.description = "Search through past conversation history. Useful when user asks to remember or find previous discussions."
    
    async def execute(self, query: str) -> Dict[str, Any]:
        """Search conversation history."""
        logger.info(f"History search tool called: query='{query}'")
        
        try:
            results = await self.repository.search_messages(query)
            
            # Format results
            formatted_results = [
                {
                    "session": r.session_id,
                    "snippet": r.snippet,
                    "timestamp": r.timestamp.isoformat(),
                    "role": r.role
                }
                for r in results[:10]  # Limit to 10 results
            ]
            
            return {
                "success": True,
                "data": {"results": formatted_results, "count": len(results)},
                "system_message": f"Found {len(results)} messages matching '{query}'"
            }
        except Exception as e:
            logger.error(f"History search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "system_message": f"History search failed: {e}"
            }


class RadioTool:
    """
    Radio browser tool for finding and exploring radio stations worldwide.
    
    Uses the Radio Browser API (https://fi1.api.radio-browser.info) to:
    - Search stations by name, country, language, or genre/tag
    - Get top stations by votes, clicks, or recent activity
    - Browse available countries, languages, and tags
    """
    
    def __init__(self, client: IRadioBrowserClient):
        self.client = client
        self.name = "radio"
        self.description = """Search and explore radio stations worldwide. Supports multiple actions:
- Search by country (country_code like 'HU', 'US', 'GB'), name, language, or tag/genre
- Get top stations globally by votes, clicks, or recent activity
- List available countries, languages, or tags/genres
Useful when user asks about radio stations, music genres, or wants to discover new stations."""
    
    async def execute(
        self,
        action: str = "search",
        country_code: Optional[str] = None,
        country: Optional[str] = None,
        name: Optional[str] = None,
        language: Optional[str] = None,
        tag: Optional[str] = None,
        by: str = "votes",
        limit: int = 10,
        filter_tag: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute radio browser actions.
        
        Args:
            action: One of 'search', 'top', 'countries', 'languages', 'tags'
            country_code: ISO country code for search (e.g., 'HU', 'US')
            country: Country name for search
            name: Station name to search for
            language: Language to filter by
            tag: Genre/tag to filter by
            by: For 'top' action - 'votes', 'clicks', 'recent_clicks', 'recently_changed'
            limit: Maximum number of results
            filter_tag: For 'tags' action - filter tags by name
        """
        logger.info(f"Radio tool called: action={action}, country_code={country_code}, name={name}, tag={tag}, limit={limit}")
        
        try:
            if action == "search":
                result = await self.client.search_stations(
                    name=name,
                    country=country,
                    country_code=country_code,
                    language=language,
                    tag=tag,
                    order=by,
                    limit=limit
                )
            elif action == "top":
                result = await self.client.get_top_stations(by=by, limit=limit)
            elif action == "countries":
                result = await self.client.get_countries()
            elif action == "languages":
                result = await self.client.get_languages()
            elif action == "tags":
                result = await self.client.get_tags(filter_tag=filter_tag)
            else:
                return {
                    "success": False,
                    "error": f"Unknown action: {action}",
                    "system_message": f"Unknown radio action: {action}. Use: search, top, countries, languages, tags"
                }
            
            logger.info(f"Radio tool result keys: {result.keys() if isinstance(result, dict) else 'not a dict'}")
            
            if "error" in result:
                logger.error(f"Radio tool error: {result['error']}")
                return {
                    "success": False,
                    "error": result["error"],
                    "system_message": f"Radio API error: {result['error']}"
                }
            
            # Format response based on action type
            if action in ("search", "top"):
                return self._format_stations_response(result, action)
            elif action == "countries":
                return self._format_countries_response(result)
            elif action == "languages":
                return self._format_languages_response(result)
            elif action == "tags":
                return self._format_tags_response(result)
            
        except Exception as e:
            logger.error(f"Radio tool exception: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "system_message": f"Radio tool failed: {e}"
            }
    
    def _format_stations_response(self, result: Dict[str, Any], action: str) -> Dict[str, Any]:
        """Format stations search/top response."""
        stations = result.get("stations", [])
        
        if not stations:
            filters = result.get("filters", {})
            filter_desc = ", ".join(f"{k}={v}" for k, v in filters.items() if v) if filters else "none"
            return {
                "success": False,
                "error": f"No radio stations found with filters: {filter_desc}",
                "system_message": f"No stations found matching criteria"
            }
        
        # Build summary
        if action == "top":
            ranked_by = result.get("ranked_by", "votes")
            summary = f"Top {len(stations)} radio stations by {ranked_by}:\n\n"
        else:
            summary = f"Found {len(stations)} radio stations:\n\n"
        
        for idx, station in enumerate(stations, 1):
            summary += f"{idx}. 📻 **{station['name']}**\n"
            if station.get('country'):
                summary += f"   🌍 {station['country']}"
                if station.get('language'):
                    summary += f" | 🗣️ {station['language']}"
                summary += "\n"
            if station.get('tags'):
                summary += f"   🏷️ {station['tags']}\n"
            if station.get('quality'):
                summary += f"   🎧 {station['quality']}\n"
            if station.get('votes') or station.get('click_count'):
                summary += f"   ⭐ {station.get('votes', 0)} votes | 👆 {station.get('click_count', 0)} clicks\n"
            if station.get('stream_url'):
                summary += f"   🔗 {station['stream_url']}\n"
            summary += "\n"
        
        return {
            "success": True,
            "message": summary,
            "data": result,
            "system_message": f"Retrieved {len(stations)} radio stations"
        }
    
    def _format_countries_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Format countries list response."""
        countries = result.get("countries", [])
        total = result.get("total_countries", len(countries))
        
        summary = f"Top {len(countries)} countries with radio stations (of {total} total):\n\n"
        for c in countries[:20]:
            summary += f"• **{c['name']}** ({c['code']}): {c['station_count']} stations\n"
        
        if len(countries) > 20:
            summary += f"\n... and {len(countries) - 20} more countries"
        
        return {
            "success": True,
            "message": summary,
            "data": result,
            "system_message": f"Retrieved {len(countries)} countries with radio stations"
        }
    
    def _format_languages_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Format languages list response."""
        languages = result.get("languages", [])
        total = result.get("total_languages", len(languages))
        
        summary = f"Top {len(languages)} languages with radio stations (of {total} total):\n\n"
        for lang in languages[:20]:
            summary += f"• **{lang['name']}**: {lang['station_count']} stations\n"
        
        if len(languages) > 20:
            summary += f"\n... and {len(languages) - 20} more languages"
        
        return {
            "success": True,
            "message": summary,
            "data": result,
            "system_message": f"Retrieved {len(languages)} languages with radio stations"
        }
    
    def _format_tags_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Format tags/genres list response."""
        tags = result.get("tags", [])
        total = result.get("total_tags", len(tags))
        filter_used = result.get("filter")
        
        if filter_used:
            summary = f"Tags matching '{filter_used}' ({len(tags)} found):\n\n"
        else:
            summary = f"Top {len(tags)} radio genres/tags (of {total} total):\n\n"
        
        for t in tags[:30]:
            summary += f"• **{t['name']}**: {t['station_count']} stations\n"
        
        if len(tags) > 30:
            summary += f"\n... and {len(tags) - 30} more tags"
        
        return {
            "success": True,
            "message": summary,
            "data": result,
            "system_message": f"Retrieved {len(tags)} radio tags/genres"
        }


class TranslatorTool:
    """
    Translation tool using lingua for language detection and OpenAI GPT for translation.
    
    This tool provides:
    - Language detection for any text
    - Translation between supported languages
    - Can be used standalone or by other tools (like BookTool)
    """
    
    SUPPORTED_LANGUAGES = {
        'en': 'English',
        'hu': 'Hungarian',
        'de': 'German',
        'fr': 'French',
        'es': 'Spanish',
        'it': 'Italian',
        'pt': 'Portuguese',
        'ru': 'Russian'
    }
    
    def __init__(self, openai_api_key: str):
        self.openai_api_key = openai_api_key
        self.name = "translator"
        self.description = """Detect language and translate text between languages.
Actions:
- 'detect': Detect the language of the provided text
- 'translate': Translate text to a target language
Supported languages: English (en), Hungarian (hu), German (de), French (fr), Spanish (es), Italian (it), Portuguese (pt), Russian (ru)"""
    
    def detect_language(self, text: str) -> str:
        """
        Detect language using lingua-language-detector.
        Returns ISO 639-1 language code (e.g., 'en', 'hu', 'de').
        """
        if not text or len(text.strip()) < 3:
            return "en"
        
        try:
            from lingua import Language, LanguageDetectorBuilder
            
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
            
            detected = detector.detect_language_of(text)
            
            if detected is None:
                logger.warning(f"Could not detect language for: '{text[:50]}...', defaulting to English")
                return "en"
            
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
    
    async def translate(self, text: str, target_lang: str, source_lang: Optional[str] = None) -> str:
        """
        Translate text to target language using OpenAI GPT.
        
        Args:
            text: Text to translate
            target_lang: Target language code (e.g., 'en', 'hu')
            source_lang: Optional source language code (auto-detected if not provided)
        
        Returns:
            Translated text
        """
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage, SystemMessage
            
            if not self.openai_api_key:
                logger.warning("No OpenAI API key found, skipping translation")
                return text
            
            target_lang_name = self.SUPPORTED_LANGUAGES.get(target_lang, 'English')
            
            llm = ChatOpenAI(
                model="gpt-4-turbo-preview",
                temperature=0.1,
                openai_api_key=self.openai_api_key
            )
            
            messages = [
                SystemMessage(content=f"You are a professional translator. Translate the following text to {target_lang_name}. Preserve formatting, markdown, and structure. Only output the translation, nothing else."),
                HumanMessage(content=text)
            ]
            
            response = await llm.ainvoke(messages)
            translated = response.content.strip()
            
            logger.info(f"Translated text to {target_lang_name}")
            return translated
            
        except Exception as e:
            logger.error(f"Translation error: {e}, returning original text")
            return text
    
    async def execute(
        self,
        action: str = "detect",
        text: Optional[str] = None,
        target_language: Optional[str] = None,
        source_language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute translator actions.
        
        Args:
            action: 'detect' to detect language, 'translate' to translate text
            text: The text to detect language of or translate
            target_language: Target language code for translation (e.g., 'en', 'hu', 'de')
            source_language: Optional source language code (auto-detected if not provided)
        
        Returns:
            Dict with detected language or translated text
        """
        logger.info(f"Translator tool called: action={action}, text_len={len(text) if text else 0}")
        
        try:
            if not text:
                return {
                    "success": False,
                    "error": "Text is required",
                    "system_message": "Translator failed: no text provided"
                }
            
            if action == "detect":
                detected_lang = self.detect_language(text)
                lang_name = self.SUPPORTED_LANGUAGES.get(detected_lang, 'Unknown')
                
                return {
                    "success": True,
                    "message": f"🌐 **Detected Language:** {lang_name} ({detected_lang})",
                    "data": {
                        "language_code": detected_lang,
                        "language_name": lang_name,
                        "text_preview": text[:100] + "..." if len(text) > 100 else text
                    },
                    "system_message": f"Detected language: {lang_name} ({detected_lang})"
                }
            
            elif action == "translate":
                if not target_language:
                    return {
                        "success": False,
                        "error": "Target language is required for translation",
                        "system_message": "Translation failed: no target language specified"
                    }
                
                if target_language not in self.SUPPORTED_LANGUAGES:
                    return {
                        "success": False,
                        "error": f"Unsupported target language: {target_language}. Supported: {', '.join(self.SUPPORTED_LANGUAGES.keys())}",
                        "system_message": f"Translation failed: unsupported language {target_language}"
                    }
                
                # Detect source language if not provided
                if not source_language:
                    source_language = self.detect_language(text)
                
                source_name = self.SUPPORTED_LANGUAGES.get(source_language, 'Unknown')
                target_name = self.SUPPORTED_LANGUAGES.get(target_language, 'Unknown')
                
                # Skip translation if source and target are the same
                if source_language == target_language:
                    return {
                        "success": True,
                        "message": f"🌐 **No translation needed** - text is already in {target_name}",
                        "data": {
                            "original_text": text,
                            "translated_text": text,
                            "source_language": source_language,
                            "target_language": target_language,
                            "was_translated": False
                        },
                        "system_message": f"Text already in {target_name}, no translation needed"
                    }
                
                translated_text = await self.translate(text, target_language, source_language)
                
                return {
                    "success": True,
                    "message": f"🌐 **Translation ({source_name} → {target_name}):**\n\n{translated_text}",
                    "data": {
                        "original_text": text,
                        "translated_text": translated_text,
                        "source_language": source_language,
                        "target_language": target_language,
                        "was_translated": True
                    },
                    "system_message": f"Translated from {source_name} to {target_name}"
                }
            
            else:
                return {
                    "success": False,
                    "error": f"Unknown action: {action}",
                    "system_message": f"Unknown translator action: {action}. Use: detect, translate"
                }
        
        except Exception as e:
            logger.error(f"Translator tool exception: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "system_message": f"Translator tool failed: {e}"
            }


class BookTool:
    """
    Book Q&A tool using RAG (Retrieval-Augmented Generation) pipeline.
    
    This tool allows users to ask questions about the content of a book (PDF).
    It uses vector similarity search to find relevant passages and generates
    answers based on the retrieved context.
    
    Uses TranslatorTool for language detection and translation to respond
    in the same language as the user's question.
    """
    
    def __init__(self, client: IBookRAGClient, translator_tool: 'TranslatorTool' = None):
        self.client = client
        self.translator = translator_tool
        self.name = "book"
        self.description = """Ask questions about the book "Pál utcai fiúk" (The Paul Street Boys).
This tool uses RAG (Retrieval-Augmented Generation) to search through the book content and provide answers.
Useful when user asks about:
- Characters in the book (Boka, Nemecsek, Geréb, Áts Feri, etc.)
- Plot events and story details
- Themes and meanings
- Specific scenes or chapters
- Quotes or passages from the book
Actions: 'query' (ask a question), 'info' (get book information)"""
    
    def _detect_language(self, text: str) -> str:
        """
        Detect language using the TranslatorTool.
        Falls back to 'en' if translator is not available.
        """
        if self.translator:
            return self.translator.detect_language(text)
        return "en"
    
    async def _translate_if_needed(self, text: str, target_lang: str) -> str:
        """
        Translate text to target language using the TranslatorTool.
        Returns original text if translator is not available.
        """
        if self.translator:
            return await self.translator.translate(text, target_lang)
        return text
    
    async def execute(
        self,
        action: str = "query",
        question: Optional[str] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Execute book-related actions.
        
        Args:
            action: 'query' to ask questions, 'info' to get book information
            question: The question to ask about the book (required for 'query' action)
            top_k: Number of relevant passages to retrieve (default: 5)
        
        Returns:
            Dict with answer, sources, and metadata
        """
        logger.info(f"Book tool called: action={action}, question={question[:50] if question else 'None'}...")
        
        try:
            if action == "query":
                if not question:
                    return {
                        "success": False,
                        "error": "Question is required for query action",
                        "system_message": "Book query failed: no question provided"
                    }
                
                result = await self.client.query(question, top_k)
                
                if "error" in result:
                    return {
                        "success": False,
                        "error": result["error"],
                        "system_message": f"Book query failed: {result['error']}"
                    }
                
                # Format the response
                answer = result.get("answer", "No answer found")
                sources = result.get("sources", [])
                book_title = result.get("book_title", "Unknown")
                
                # CRITICAL: Verify language match and translate if needed
                question_lang = self._detect_language(question)
                answer_lang = self._detect_language(answer)
                
                logger.info(f"Language verification - Question: {question_lang}, Answer: {answer_lang}")
                
                # If languages don't match, translate the answer
                if question_lang != answer_lang:
                    logger.warning(f"Language mismatch detected! Translating from {answer_lang} to {question_lang}")
                    answer = await self._translate_if_needed(answer, question_lang)
                    logger.info("Translation completed")
                
                # Build source references
                source_refs = []
                for i, src in enumerate(sources[:3], 1):
                    page = src.get("page", "?")
                    preview = src.get("content_preview", "")[:100]
                    source_refs.append(f"[Page {page}]: {preview}...")
                
                summary = f"📚 **Answer from '{book_title}'** | Q: {question_lang.upper()} → A: {answer_lang.upper()}:\n\n{answer}"
                if source_refs:
                    summary += f"\n\n**Sources:**\n" + "\n".join(source_refs)
                
                return {
                    "success": True,
                    "message": summary,
                    "data": result,
                    "system_message": f"❓: {question_lang.upper()} → 💬: {answer_lang.upper()}"
                }
            
            elif action == "info":
                result = await self.client.get_book_info()
                
                if "error" in result:
                    return {
                        "success": False,
                        "error": result["error"],
                        "system_message": f"Failed to get book info: {result['error']}"
                    }
                
                title = result.get("title", "Unknown")
                chunks = result.get("chunks_count", 0)
                pages = result.get("pages_count", "N/A")
                status = result.get("status", "unknown")
                
                summary = f"📖 **Book Information:**\n"
                summary += f"- **Title:** {title}\n"
                summary += f"- **Pages:** {pages}\n"
                summary += f"- **Indexed chunks:** {chunks}\n"
                summary += f"- **Status:** {status}"
                
                return {
                    "success": True,
                    "message": summary,
                    "data": result,
                    "system_message": f"Book '{title}' is loaded with {chunks} indexed chunks"
                }
            
            else:
                return {
                    "success": False,
                    "error": f"Unknown action: {action}",
                    "system_message": f"Unknown book action: {action}. Use: query, info"
                }
        
        except Exception as e:
            logger.error(f"Book tool exception: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "system_message": f"Book tool failed: {e}"
            }


class PhotoUploadTool:
    """
    Photo upload tool for uploading images to pCloud.
    
    This tool:
    - Asks questions to understand when/where photos were taken and what event they're from
    - Creates a folder with naming convention: YYYY.MM.DD - [EVENT NAME] - [PLACE]
    - Uploads photos to the folder in Photo_Memories
    - Lists the folder structure after upload
    """
    
    def __init__(self, cloud_client, photo_memories_folder_id: Optional[int] = None):
        """
        Initialize PhotoUploadTool.
        
        Args:
            cloud_client: PCloudClient instance for cloud storage operations
            photo_memories_folder_id: ID of the Photo_Memories folder in pCloud
        """
        self.drive_client = cloud_client
        self.photo_memories_folder_id = photo_memories_folder_id
        self.name = "photo_upload"
        self.description = """Upload photos to pCloud Photo_Memories folder.
This tool is used when the user has attached files/photos to upload.
The tool will:
1. Ask about the date (when were the photos taken) - converts to YYYY.MM.DD format
2. Ask about the event name (what event/occasion)
3. Ask about the location (where the photos were taken)
4. Create a folder: YYYY.MM.DD - [EVENT NAME] - [LOCATION]
5. Upload all attached photos to that folder
6. Show the Photo_Memories folder structure with the new folder's contents

Parameters:
- action: 'upload' to upload files, 'list' to list Photo_Memories structure
- date: Date in any format (will be converted to YYYY.MM.DD)
- event_name: Name of the event
- location: Where the event took place
- file_paths: List of file paths to upload (provided by the system)
- file_names: List of original file names"""
    
    def _parse_date(self, date_str: str) -> str:
        """
        Parse date string and convert to YYYY.MM.DD format.
        Handles various date formats.
        """
        import re
        from datetime import datetime
        
        if not date_str:
            return datetime.now().strftime("%Y.%m.%d")
        
        date_str = date_str.strip()
        
        # Try common date formats
        formats = [
            "%Y-%m-%d",      # 2024-01-15
            "%Y.%m.%d",      # 2024.01.15
            "%Y/%m/%d",      # 2024/01/15
            "%d-%m-%Y",      # 15-01-2024
            "%d.%m.%Y",      # 15.01.2024
            "%d/%m/%Y",      # 15/01/2024
            "%m-%d-%Y",      # 01-15-2024
            "%m/%d/%Y",      # 01/15/2024
            "%B %d, %Y",     # January 15, 2024
            "%b %d, %Y",     # Jan 15, 2024
            "%d %B %Y",      # 15 January 2024
            "%d %b %Y",      # 15 Jan 2024
            "%Y %B %d",      # 2024 January 15
            "%Y %b %d",      # 2024 Jan 15
        ]
        
        for fmt in formats:
            try:
                parsed = datetime.strptime(date_str, fmt)
                return parsed.strftime("%Y.%m.%d")
            except ValueError:
                continue
        
        # Try to extract date components with regex
        # Match patterns like "15th January 2024" or "January 15th, 2024"
        date_str_clean = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
        for fmt in formats:
            try:
                parsed = datetime.strptime(date_str_clean, fmt)
                return parsed.strftime("%Y.%m.%d")
            except ValueError:
                continue
        
        # If all else fails, return today's date
        logger.warning(f"Could not parse date '{date_str}', using today's date")
        return datetime.now().strftime("%Y.%m.%d")
    
    def _sanitize_folder_name(self, name: str) -> str:
        """Sanitize folder name by removing/replacing invalid characters and capitalizing first letter."""
        import re
        # Replace invalid characters with underscores
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
        # Remove leading/trailing spaces and dots
        sanitized = sanitized.strip(' .')
        # Capitalize first letter
        if sanitized:
            sanitized = sanitized[0].upper() + sanitized[1:]
        return sanitized
    
    def _get_mime_type(self, filename: str) -> str:
        """Get MIME type based on file extension."""
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        mime_types = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'bmp': 'image/bmp',
            'webp': 'image/webp',
            'heic': 'image/heic',
            'heif': 'image/heif',
            'tiff': 'image/tiff',
            'tif': 'image/tiff',
            'svg': 'image/svg+xml',
        }
        return mime_types.get(ext, 'application/octet-stream')
    
    async def _ensure_photo_memories_folder(self) -> str:
        """Ensure Photo_Memories folder exists and return its ID."""
        if self.photo_memories_folder_id:
            return self.photo_memories_folder_id
        
        # Search for existing Photo_Memories folder
        result = await self.drive_client.find_folder("Photo_Memories")
        if result.get("found"):
            self.photo_memories_folder_id = result["folder_id"]
            return self.photo_memories_folder_id
        
        # Create the folder if it doesn't exist
        result = await self.drive_client.create_folder("Photo_Memories")
        if result.get("success"):
            self.photo_memories_folder_id = result["folder_id"]
            return self.photo_memories_folder_id
        
        raise Exception(f"Failed to create or find Photo_Memories folder: {result.get('error', 'Unknown error')}")
    
    async def execute(
        self,
        action: str = "upload",
        date: Optional[str] = None,
        event_name: Optional[str] = None,
        location: Optional[str] = None,
        file_paths: Optional[list] = None,
        file_names: Optional[list] = None,
        file_data: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Execute photo upload actions.
        
        Args:
            action: 'upload' to upload files, 'list' to list folder structure
            date: Date when photos were taken (any format)
            event_name: Name of the event
            location: Where the photos were taken
            file_paths: List of temporary file paths to upload
            file_names: List of original file names
            file_data: List of file bytes (alternative to file_paths)
        
        Returns:
            Dict with upload results and folder structure
        """
        logger.info(f"PhotoUpload tool called: action={action}, date={date}, event={event_name}, location={location}")
        
        try:
            if action == "list":
                # List Photo_Memories folder structure
                photo_memories_id = await self._ensure_photo_memories_folder()
                structure = await self.drive_client.get_folder_structure(photo_memories_id)
                
                if "error" in structure:
                    return {
                        "success": False,
                        "error": structure["error"],
                        "system_message": f"Failed to list Photo_Memories: {structure['error']}"
                    }
                
                folders = structure.get("subfolders", [])
                summary = "📁 **Photo_Memories Folder Structure:**\n\n"
                
                if folders:
                    for folder in folders:
                        summary += f"📂 {folder['name']}\n"
                else:
                    summary += "_No folders yet_\n"
                
                return {
                    "success": True,
                    "message": summary,
                    "data": structure,
                    "system_message": f"Listed {len(folders)} folders in Photo_Memories"
                }
            
            elif action == "upload":
                # Validate required parameters
                if not date or not event_name or not location:
                    missing = []
                    if not date:
                        missing.append("date (when were the photos taken?)")
                    if not event_name:
                        missing.append("event_name (what event/occasion?)")
                    if not location:
                        missing.append("location (where were the photos taken?)")
                    
                    return {
                        "success": False,
                        "error": f"Missing required information: {', '.join(missing)}",
                        "system_message": f"Photo upload needs more info: {', '.join(missing)}",
                        "needs_info": missing
                    }
                
                if not file_paths and not file_data:
                    return {
                        "success": False,
                        "error": "No files provided for upload",
                        "system_message": "Photo upload failed: no files attached"
                    }
                
                # Parse and format date
                formatted_date = self._parse_date(date)
                
                # Create folder name
                sanitized_event = self._sanitize_folder_name(event_name)
                sanitized_location = self._sanitize_folder_name(location)
                folder_name = f"{formatted_date} - {sanitized_event} - {sanitized_location}"
                
                logger.info(f"Creating folder: {folder_name}")
                
                # Ensure Photo_Memories folder exists
                photo_memories_id = await self._ensure_photo_memories_folder()
                
                # Check if folder already exists
                existing = await self.drive_client.find_folder(folder_name, photo_memories_id)
                if existing.get("found"):
                    event_folder_id = existing["folder_id"]
                    logger.info(f"Using existing folder: {folder_name}")
                else:
                    # Create the event folder
                    folder_result = await self.drive_client.create_folder(folder_name, photo_memories_id)
                    if "error" in folder_result:
                        return {
                            "success": False,
                            "error": f"Failed to create folder: {folder_result['error']}",
                            "system_message": f"Failed to create folder '{folder_name}'"
                        }
                    event_folder_id = folder_result["folder_id"]
                    logger.info(f"Created folder: {folder_name} with ID: {event_folder_id}")
                
                # Upload files
                uploaded_files = []
                failed_files = []
                
                num_files = len(file_paths) if file_paths else len(file_data) if file_data else 0
                file_names = file_names or [f"photo_{i+1}.jpg" for i in range(num_files)]
                
                for i in range(num_files):
                    file_name = file_names[i] if i < len(file_names) else f"photo_{i+1}.jpg"
                    mime_type = self._get_mime_type(file_name)
                    
                    try:
                        if file_paths and i < len(file_paths):
                            # Upload from file path
                            result = await self.drive_client.upload_file(
                                file_paths[i],
                                file_name,
                                event_folder_id,
                                mime_type
                            )
                        elif file_data and i < len(file_data):
                            # Upload from bytes
                            result = await self.drive_client.upload_file_from_bytes(
                                file_data[i],
                                file_name,
                                event_folder_id,
                                mime_type
                            )
                        else:
                            continue
                        
                        if result.get("success"):
                            uploaded_files.append({
                                "name": file_name,
                                "id": result.get("file_id"),
                                "web_link": result.get("web_link")
                            })
                            logger.info(f"Uploaded: {file_name}")
                        else:
                            failed_files.append({
                                "name": file_name,
                                "error": result.get("error", "Unknown error")
                            })
                            logger.error(f"Failed to upload {file_name}: {result.get('error')}")
                    
                    except Exception as e:
                        failed_files.append({
                            "name": file_name,
                            "error": str(e)
                        })
                        logger.error(f"Exception uploading {file_name}: {e}")
                
                # Get folder contents after upload
                folder_contents = await self.drive_client.list_folder_contents(event_folder_id)
                
                # Get Photo_Memories structure
                photo_memories_structure = await self.drive_client.get_folder_structure(photo_memories_id)
                
                # Build response
                summary = f"📸 **Photo Upload Complete!**\n\n"
                summary += f"📂 **Folder Created/Used:** {folder_name}\n"
                summary += f"✅ **Successfully Uploaded:** {len(uploaded_files)} file(s)\n"
                
                if failed_files:
                    summary += f"❌ **Failed:** {len(failed_files)} file(s)\n"
                
                # Show files in the uploaded folder
                summary += f"\n**📁 Files in '{folder_name}':**\n"
                folder_files = [item for item in folder_contents.get("contents", []) if item["type"] == "file"]
                if folder_files:
                    for item in folder_files:
                        file_size = item.get('size', 0)
                        size_kb = file_size / 1024 if file_size else 0
                        summary += f"  📷 {item['name']} ({size_kb:.1f} KB)\n"
                else:
                    summary += f"  _No files in this folder_\n"
                
                # Show all Photo_Memories folders - without folder listing in system_message
                summary += f"\n**📂 All Photo_Memories Folders:**\n"
                all_folders = photo_memories_structure.get("subfolders", [])
                if all_folders:
                    for folder in all_folders:
                        if folder["name"] == folder_name:
                            summary += f"📂 **{folder['name']}** ← _just uploaded here_\n"
                        else:
                            summary += f"📂 {folder['name']}\n"
                else:
                    summary += f"  _Only this folder exists_\n"
                
                return {
                    "success": True,
                    "message": summary,
                    "data": {
                        "folder_name": folder_name,
                        "folder_id": event_folder_id,
                        "uploaded_files": uploaded_files,
                        "failed_files": failed_files,
                        "folder_contents": folder_contents.get("contents", []),
                        "photo_memories_structure": photo_memories_structure.get("subfolders", [])
                    },
                    "system_message": f"Uploaded {len(uploaded_files)} photos to '{folder_name}'"
                }
            
            else:
                return {
                    "success": False,
                    "error": f"Unknown action: {action}",
                    "system_message": f"Unknown photo_upload action: {action}. Use: upload, list"
                }
        
        except Exception as e:
            logger.error(f"PhotoUpload tool exception: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "system_message": f"Photo upload failed: {e}"
            }
