"""
Service layer - LangGraph agent tools implementation.
Following SOLID: Single Responsibility - each tool wrapper has one clear purpose.
"""
from typing import Dict, Any, Optional, List
from pathlib import Path
import json
from datetime import datetime
import logging
import sqlite3

from domain.interfaces import (
    IWeatherClient, IGeocodeClient, IIPGeolocationClient,
    IFXRatesClient, ICryptoPriceClient, IConversationRepository,
    IRadioBrowserClient, IDocumentsRAGClient
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


class DocumentsTool:
    """
    Documents Q&A tool using RAG (Retrieval-Augmented Generation) pipeline with FAISS vector database.
    
    This tool allows users to ask questions about support issues based on Excel documents
    containing issue types, priorities, resolution times, and responsible teams.
    It uses vector similarity search to find relevant information and generates
    answers based on the retrieved context.
    
    Uses TranslatorTool for language detection and translation to respond
    in the same language as the user's question.
    """
    
    def __init__(self, client: IDocumentsRAGClient, translator_tool: 'TranslatorTool' = None):
        self.client = client
        self.translator = translator_tool
        self.name = "documents"
        self.description = """Search and query support documentation for issue types, priorities, and resolution information.
This tool uses RAG (Retrieval-Augmented Generation) with FAISS vector database to search through support documents.
Useful when user asks about:
- Support issue types (billing, technical, account, feature requests)
- Issue priorities (P1, P2) and SLA times
- Resolution times and acknowledgment times
- Responsible teams for different issues
- Costs associated with support issues
- How to handle specific customer problems
Actions: 'query' (ask a question), 'info' (get documents information)"""
    
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
        Execute documents-related actions.
        
        Args:
            action: 'query' to ask questions, 'info' to get documents information
            question: The question to ask about support issues (required for 'query' action)
            top_k: Number of relevant passages to retrieve (default: 5)
        
        Returns:
            Dict with answer, sources, and metadata
        """
        logger.info(f"Documents tool called: action={action}, question={question[:50] if question else 'None'}...")
        
        try:
            if action == "query":
                if not question:
                    return {
                        "success": False,
                        "error": "Question is required for query action",
                        "system_message": "Documents query failed: no question provided"
                    }
                
                # Detect the original question language
                original_question_lang = self._detect_language(question)
                logger.info(f"Original question language: {original_question_lang}")
                
                # Translate question to English if it's not already in English
                # This ensures the RAG can find relevant documents (which are in English)
                query_for_rag = question
                if original_question_lang != "en":
                    logger.info(f"Translating question from {original_question_lang} to English for RAG query")
                    query_for_rag = await self._translate_if_needed(question, "en")
                    logger.info(f"Translated query: {query_for_rag[:100]}...")
                
                # Query the RAG with English text
                result = await self.client.query(query_for_rag, top_k)
                
                if "error" in result:
                    return {
                        "success": False,
                        "error": result["error"],
                        "system_message": f"Documents query failed: {result['error']}"
                    }
                
                # Format the response
                answer = result.get("answer", "No answer found")
                sources = result.get("sources", [])
                
                # Translate the answer back to the original question language
                if original_question_lang != "en":
                    logger.info(f"Translating answer from English back to {original_question_lang}")
                    answer = await self._translate_if_needed(answer, original_question_lang)
                    logger.info("Translation completed")
                
                answer_lang = original_question_lang
                
                # Build source references
                source_refs = []
                for i, src in enumerate(sources[:3], 1):
                    category = src.get("category", "Unknown")
                    issue_type = src.get("issue_type", "Unknown")
                    source_refs.append(f"[{category}] {issue_type}")
                
                summary = f"📋 **Support Documentation Answer** | Q: {original_question_lang.upper()} → A: {answer_lang.upper()}:\n\n{answer}"
                if source_refs:
                    summary += f"\n\n**Sources:**\n" + "\n".join(f"- {ref}" for ref in source_refs)
                
                return {
                    "success": True,
                    "message": summary,
                    "data": result,
                    "system_message": f"❓: {original_question_lang.upper()} → 💬: {answer_lang.upper()}"
                }
            
            elif action == "info":
                result = await self.client.get_documents_info()
                
                if "error" in result:
                    return {
                        "success": False,
                        "error": result["error"],
                        "system_message": f"Failed to get documents info: {result['error']}"
                    }
                
                directory = result.get("directory", "Unknown")
                files_count = result.get("files_count", "N/A")
                documents_count = result.get("documents_count", "N/A")
                chunks = result.get("chunks_count", 0)
                categories = result.get("categories", [])
                status = result.get("status", "unknown")
                
                summary = f"📁 **Documents Information:**\n"
                summary += f"- **Directory:** {directory}\n"
                summary += f"- **Excel files:** {files_count}\n"
                summary += f"- **Total documents:** {documents_count}\n"
                summary += f"- **Indexed chunks:** {chunks}\n"
                summary += f"- **Categories:** {', '.join(categories) if categories else 'N/A'}\n"
                summary += f"- **Status:** {status}"
                
                return {
                    "success": True,
                    "message": summary,
                    "data": result,
                    "system_message": f"Documents loaded with {chunks} indexed chunks from {files_count} files"
                }
            
            else:
                return {
                    "success": False,
                    "error": f"Unknown action: {action}",
                    "system_message": f"Unknown documents action: {action}. Use: query, info"
                }
        
        except Exception as e:
            logger.error(f"Documents tool exception: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "system_message": f"Documents tool failed: {e}"
            }


class PhotoUploadTool:
    """
    Photo upload tool for uploading images to pCloud.
    
    This tool:
    - Uploads photos to the Tickets folder in pCloud
    - Creates a subfolder with the ticket number
    - Uploads all attached images to that ticket subfolder
    - Lists the folder structure after upload
    """
    
    def __init__(self, cloud_client, tickets_folder_id: Optional[int] = None):
        """
        Initialize PhotoUploadTool.
        
        Args:
            cloud_client: PCloudClient instance for cloud storage operations
            tickets_folder_id: ID of the Tickets folder in pCloud
        """
        self.drive_client = cloud_client
        self.tickets_folder_id = tickets_folder_id
        self.name = "photo_upload"
        self.description = """Upload photos to pCloud Tickets folder.
This tool is used when the user has attached files/photos to upload.
The tool will:
1. Create a subfolder in Tickets folder with the ticket number
2. Upload all attached photos to that ticket subfolder
3. Show the folder structure after upload

Parameters:
- action: 'upload' to upload files, 'list' to list Tickets structure
- ticket_number: The ticket number (e.g., TK001) to create subfolder
- file_paths: List of file paths to upload (provided by the system)
- file_names: List of original file names"""
    
    def _validate_input(self, event_name: str, location: str, date_str: str) -> Dict[str, str]:
        """
        Validate and sanitize user inputs.
        Returns dict with 'errors' key if validation fails, or sanitized values.
        """
        errors = []
        
        # Validate event_name
        if not event_name or not event_name.strip():
            errors.append("Event name cannot be empty")
        elif len(event_name) > 100:
            errors.append(f"Event name too long ({len(event_name)} chars). Maximum 100 characters.")
        
        # Validate location
        if not location or not location.strip():
            errors.append("Location cannot be empty")
        elif len(location) > 100:
            errors.append(f"Location too long ({len(location)} chars). Maximum 100 characters.")
        
        # Validate date
        if date_str:
            parsed_date = self._parse_date(date_str)
            if parsed_date.startswith("ERROR:"):
                errors.append(parsed_date)
        
        if errors:
            return {"errors": errors}
        
        return {
            "event_name": event_name.strip(),
            "location": location.strip(),
            "date": date_str.strip() if date_str else None
        }
    
    def _parse_date(self, date_str: str) -> str:
        """
        Parse date string and convert to YYYY.MM.DD format.
        Handles various date formats with validation.
        """
        import re
        from datetime import datetime
        
        if not date_str:
            return datetime.now().strftime("%Y.%m.%d")
        
        date_str = date_str.strip()
        
        # Validate date is not in the future by more than 1 day
        # (allow some flexibility for timezone differences)
        current_date = datetime.now()
        future_limit = datetime(current_date.year + 1, 12, 31)  # Max 1 year in future
        past_limit = datetime(1900, 1, 1)  # Reasonable past limit
        
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
                
                # Validate date range
                if parsed < past_limit:
                    return f"ERROR: Date too far in the past (before 1900)"
                if parsed > future_limit:
                    return f"ERROR: Date too far in the future (after {future_limit.year})"
                
                return parsed.strftime("%Y.%m.%d")
            except ValueError:
                continue
        
        # Try to extract date components with regex
        # Match patterns like "15th January 2024" or "January 15th, 2024"
        date_str_clean = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
        for fmt in formats:
            try:
                parsed = datetime.strptime(date_str_clean, fmt)
                
                # Validate date range
                if parsed < past_limit:
                    return f"ERROR: Date too far in the past (before 1900)"
                if parsed > future_limit:
                    return f"ERROR: Date too far in the future (after {future_limit.year})"
                
                return parsed.strftime("%Y.%m.%d")
            except ValueError:
                continue
        
        # If all else fails, return error
        logger.warning(f"Could not parse date '{date_str}'")
        return f"ERROR: Could not parse date '{date_str}'. Please use format like: YYYY-MM-DD, DD/MM/YYYY, or 'January 15, 2024'"
    
    def _sanitize_folder_name(self, name: str) -> str:
        """Sanitize folder name by removing/replacing invalid characters and capitalizing first letter."""
        import re
        # Replace invalid characters with underscores
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
        # Remove control characters and excessive whitespace
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', sanitized)
        sanitized = re.sub(r'\s+', ' ', sanitized)
        # Remove leading/trailing spaces and dots
        sanitized = sanitized.strip(' .')
        # Limit length
        if len(sanitized) > 100:
            sanitized = sanitized[:100].rstrip()
        # Capitalize first letter
        if sanitized:
            sanitized = sanitized[0].upper() + sanitized[1:]
        return sanitized if sanitized else "Untitled"
    
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
    
    async def _ensure_tickets_folder(self) -> str:
        """Ensure Tickets folder exists and return its ID."""
        if self.tickets_folder_id:
            return self.tickets_folder_id
        
        # Search for existing Tickets folder
        result = await self.drive_client.find_folder("Tickets")
        if result.get("found"):
            self.tickets_folder_id = result["folder_id"]
            return self.tickets_folder_id
        
        # Create the folder if it doesn't exist
        result = await self.drive_client.create_folder("Tickets")
        if result.get("success"):
            self.tickets_folder_id = result["folder_id"]
            return self.tickets_folder_id
        
        raise Exception(f"Failed to create or find Tickets folder: {result.get('error', 'Unknown error')}")
    
    async def execute(
        self,
        action: str = "upload",
        ticket_number: Optional[str] = None,
        file_paths: Optional[list] = None,
        file_names: Optional[list] = None,
        file_data: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Execute photo upload actions.
        
        Args:
            action: 'upload' to upload files, 'list' to list folder structure
            ticket_number: Ticket number to create subfolder (e.g., TK001)
            file_paths: List of temporary file paths to upload
            file_names: List of original file names
            file_data: List of file bytes (alternative to file_paths)
        
        Returns:
            Dict with upload results and folder structure
        """
        logger.info(f"PhotoUpload tool called: action={action}, ticket_number={ticket_number}")
        
        try:
            if action == "list":
                # List Tickets folder structure
                tickets_id = await self._ensure_tickets_folder()
                structure = await self.drive_client.get_folder_structure(tickets_id)
                
                if "error" in structure:
                    return {
                        "success": False,
                        "error": structure["error"],
                        "system_message": f"Failed to list Tickets: {structure['error']}"
                    }
                
                folders = structure.get("subfolders", [])
                summary = "📁 **Tickets Folder Structure:**\n\n"
                
                if folders:
                    for folder in folders:
                        summary += f"📂 {folder['name']}\n"
                else:
                    summary += "_No ticket folders yet_\n"
                
                return {
                    "success": True,
                    "message": summary,
                    "data": structure,
                    "system_message": f"Listed {len(folders)} ticket folders in Tickets"
                }
            
            elif action == "upload":
                # Validate required parameters
                if not ticket_number:
                    return {
                        "success": False,
                        "error": "Missing ticket number",
                        "system_message": "Photo upload needs ticket number",
                        "needs_info": ["ticket_number"]
                    }
                
                if not file_paths and not file_data:
                    return {
                        "success": False,
                        "error": "No files provided for upload",
                        "system_message": "Photo upload failed: no files attached"
                    }
                
                # Sanitize ticket number for folder name
                folder_name = self._sanitize_folder_name(ticket_number)
                
                logger.info(f"Creating ticket folder: {folder_name}")
                
                # Ensure Tickets folder exists
                tickets_id = await self._ensure_tickets_folder()
                
                # Check if ticket folder already exists
                existing = await self.drive_client.find_folder(folder_name, tickets_id)
                folder_already_existed = False
                if existing.get("found"):
                    event_folder_id = existing["folder_id"]
                    folder_already_existed = True
                    logger.info(f"Using existing folder: {folder_name} (ID: {event_folder_id})")
                    
                    # Check how many files are already in the folder
                    existing_contents = await self.drive_client.list_folder_contents(event_folder_id)
                    existing_file_count = len([item for item in existing_contents.get("contents", []) if item["type"] == "file"])
                    
                    if existing_file_count > 0:
                        logger.warning(f"Folder '{folder_name}' already contains {existing_file_count} files. New files will be added to it.")
                else:
                    # Create the ticket folder
                    folder_result = await self.drive_client.create_folder(folder_name, tickets_id)
                    if "error" in folder_result:
                        return {
                            "success": False,
                            "error": f"Failed to create folder: {folder_result['error']}",
                            "system_message": f"Failed to create ticket folder '{folder_name}'"
                        }
                    event_folder_id = folder_result["folder_id"]
                    logger.info(f"Created new ticket folder: {folder_name} with ID: {event_folder_id}")
                
                # Upload files with improved error tracking
                uploaded_files = []
                failed_files = []
                quota_exceeded = False
                
                num_files = len(file_paths) if file_paths else len(file_data) if file_data else 0
                
                # Ensure file_names list matches the number of files
                if not file_names:
                    file_names = [f"photo_{i+1}.jpg" for i in range(num_files)]
                elif len(file_names) < num_files:
                    logger.warning(f"file_names list ({len(file_names)}) shorter than num_files ({num_files}), padding with defaults")
                    for i in range(len(file_names), num_files):
                        file_names.append(f"photo_{i+1}.jpg")
                
                logger.info(f"Starting upload of {num_files} files to folder {event_folder_id}")
                logger.info(f"file_paths count: {len(file_paths) if file_paths else 0}, file_data count: {len(file_data) if file_data else 0}, file_names count: {len(file_names)}")
                
                for i in range(num_files):
                    file_name = file_names[i] if i < len(file_names) else f"photo_{i+1}.jpg"
                    mime_type = self._get_mime_type(file_name)
                    
                    # Get file size for reporting
                    file_size = 0
                    try:
                        if file_paths and i < len(file_paths):
                            import os
                            file_size = os.path.getsize(file_paths[i])
                        elif file_data and i < len(file_data):
                            file_size = len(file_data[i])
                    except:
                        pass
                    
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
                                "size": result.get("size", file_size),
                                "web_link": result.get("web_link")
                            })
                            logger.info(f"Uploaded: {file_name} ({file_size/1024:.1f} KB)")
                        else:
                            error_msg = result.get("error", "Unknown error")
                            error_code = result.get("error_code")
                            is_retryable = result.get("retryable", False)
                            
                            # Check for quota exceeded
                            if error_code == 2008 or "quota" in error_msg.lower():
                                quota_exceeded = True
                            
                            failed_files.append({
                                "name": file_name,
                                "size": file_size,
                                "error": error_msg,
                                "error_code": error_code,
                                "retryable": is_retryable
                            })
                            logger.error(f"Failed to upload {file_name}: {error_msg} (code: {error_code})")
                            
                            # Stop if quota exceeded
                            if quota_exceeded:
                                logger.error("Storage quota exceeded, stopping upload")
                                # Mark remaining files as not attempted
                                for j in range(i + 1, num_files):
                                    remaining_name = file_names[j] if j < len(file_names) else f"photo_{j+1}.jpg"
                                    failed_files.append({
                                        "name": remaining_name,
                                        "size": 0,
                                        "error": "Not attempted - storage quota exceeded",
                                        "retryable": False
                                    })
                                break
                    
                    except Exception as e:
                        failed_files.append({
                            "name": file_name,
                            "size": file_size,
                            "error": str(e),
                            "retryable": False
                        })
                        logger.error(f"Exception uploading {file_name}: {e}", exc_info=True)
                
                # Get folder contents after upload
                folder_contents = await self.drive_client.list_folder_contents(event_folder_id)
                
                # Get Tickets folder structure
                tickets_structure = await self.drive_client.get_folder_structure(tickets_id)
                
                # Build response with detailed failure information
                if quota_exceeded:
                    summary = f"⚠️ **Photo Upload Partially Complete - Quota Exceeded**\n\n"
                elif failed_files and not uploaded_files:
                    summary = f"❌ **Photo Upload Failed**\n\n"
                elif failed_files:
                    summary = f"⚠️ **Photo Upload Partially Complete**\n\n"
                else:
                    summary = f"📸 **Photo Upload Complete!**\n\n"
                
                # Show folder status
                if folder_already_existed:
                    summary += f"📂 **Folder Used (Existing):** {folder_name}\n"
                    if existing_file_count > 0:
                        summary += f"ℹ️ _Note: This folder already contained {existing_file_count} file(s). New files were added to it._\n"
                else:
                    summary += f"📂 **Folder Created:** {folder_name}\n"
                summary += f"✅ **Successfully Uploaded:** {len(uploaded_files)} file(s)\n"
                
                if failed_files:
                    summary += f"❌ **Failed:** {len(failed_files)} file(s)\n"
                    
                    # Show detailed failure information
                    if quota_exceeded:
                        summary += f"\n⚠️ **Storage quota exceeded!** Please free up space in your pCloud account.\n"
                    
                    # List failed files with details
                    summary += f"\n**Failed Files:**\n"
                    for failed in failed_files[:10]:  # Show first 10 failures
                        size_kb = failed.get('size', 0) / 1024
                        error = failed.get('error', 'Unknown error')
                        retry_info = " (retryable)" if failed.get('retryable') else ""
                        summary += f"  ❌ {failed['name']} ({size_kb:.1f} KB): {error}{retry_info}\n"
                    
                    if len(failed_files) > 10:
                        summary += f"  ... and {len(failed_files) - 10} more\n"
                
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
                
                # Show all Tickets folders - without folder listing in system_message
                summary += f"\n**📂 All Ticket Folders:**\n"
                all_folders = tickets_structure.get("subfolders", [])
                if all_folders:
                    for folder in all_folders:
                        if folder["name"] == folder_name:
                            summary += f"📂 **{folder['name']}** ← _just uploaded here_\n"
                        else:
                            summary += f"📂 {folder['name']}\n"
                else:
                    summary += f"  _Only this folder exists_\n"
                
                # Determine overall success
                overall_success = len(uploaded_files) > 0 and not quota_exceeded
                
                return {
                    "success": overall_success,
                    "message": summary,
                    "data": {
                        "folder_name": folder_name,
                        "folder_id": event_folder_id,
                        "uploaded_files": uploaded_files,
                        "failed_files": failed_files,
                        "quota_exceeded": quota_exceeded,
                        "folder_contents": folder_contents.get("contents", []),
                        "tickets_structure": tickets_structure.get("subfolders", [])
                    },
                    "system_message": f"Uploaded {len(uploaded_files)}/{num_files} files to ticket folder '{folder_name}'" + 
                                    (f" ({len(failed_files)} failed)" if failed_files else "") +
                                    (" - QUOTA EXCEEDED" if quota_exceeded else "") +
                                    (f" (added to existing folder)" if folder_already_existed else ""),
                    "folder_already_existed": folder_already_existed,
                    "existing_file_count": existing_file_count if folder_already_existed else 0
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


class JSONCreatorTool:
    """
    JSON Creator tool that generates a structured JSON ticket from the conversation data.
    Creates a ticket with sequential numbering (TK001, TK002, etc.) and stores all
    relevant conversation information including user details, issue classification,
    sentiment analysis, and the full conversation.
    """
    
    def __init__(self, data_dir: str = "data/tickets"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.name = "json_creator"
        self.description = """Create a structured JSON ticket from the conversation data.
Captures all conversation details including:
- Ticket number (sequential: TK001, TK002, etc.)
- User information and contact time
- Original message and detected language
- Issue classification and owning team
- Priority, acknowledgement time, and resolution time
- Cost and currency conversions
- Sentiment analysis results
- Full conversation history"""
    
    def _get_next_ticket_number(self) -> str:
        """Get the next sequential ticket number."""
        ticket_files = list(self.data_dir.glob("TK*.json"))
        if not ticket_files:
            return "TK001"
        
        # Extract ticket numbers and find the highest
        ticket_numbers = []
        for f in ticket_files:
            try:
                num = int(f.stem[2:])  # Extract number from TKxxx
                ticket_numbers.append(num)
            except ValueError:
                continue
        
        if not ticket_numbers:
            return "TK001"
        
        next_num = max(ticket_numbers) + 1
        return f"TK{next_num:03d}"
    
    async def execute(
        self,
        user_name: str = None,
        contact_time: str = None,
        original_language: str = None,
        original_message: str = None,
        issue_type: str = None,
        potential_issue: str = None,
        owning_team: str = None,
        xlsx_file_name: str = None,
        priority: str = None,
        acknowledgement_time: str = None,
        resolve_time: str = None,
        cost_usd: str = None,
        eur_per_usd: str = None,
        huf_per_usd: str = None,
        notes_and_dependencies: str = None,
        sentiment: str = None,
        sentiment_confidence: float = None,
        full_conversation: str = None,
        file_names: list = None
    ) -> Dict[str, Any]:
        """
        Create a JSON ticket with all conversation data.
        
        Args:
            user_name: The user's name
            contact_time: When the user contacted (CET)
            original_language: Detected language of the original message
            original_message: The original message sent by the user
            issue_type: The identified issue type
            potential_issue: The potential issue value from the identified issue
            owning_team: The team responsible for handling the issue
            xlsx_file_name: The Excel file referenced for issue details
            priority: Priority level of the issue
            acknowledgement_time: Time to acknowledge the issue
            resolve_time: Time to resolve the issue
            cost_usd: Cost to customer in USD
            eur_per_usd: EUR/USD exchange rate
            huf_per_usd: HUF/USD exchange rate
            notes_and_dependencies: Notes and dependencies for the issue
            sentiment: User's sentiment (positive/neutral/frustrated)
            sentiment_confidence: Confidence level of sentiment analysis
            full_conversation: The entire conversation including response
            file_names: List of file names attached to the user message
        
        Returns:
            Dict with success status and the generated JSON ticket
        """
        try:
            logger.info("JSON Creator tool called - generating ticket")
            
            # Get next ticket number
            ticket_number = self._get_next_ticket_number()
            
            # Build the ticket JSON
            ticket_data = {
                "ticket_number": ticket_number,
                "user_name": user_name or "Unknown",
                "contact_time": contact_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "original_language": original_language or "Unknown",
                "original_message": original_message or "",
                "issue_type": issue_type or "Unclassified",
                "potential_issue": potential_issue or "",
                "owning_team": owning_team or "General Support",
                "xlsx_file_name": xlsx_file_name or "",
                "priority": priority or "P2",
                "acknowledgement_time": acknowledgement_time or "",
                "resolve_time": resolve_time or "",
                "cost_to_customer": {
                    "usd": cost_usd or "0",
                    "eur_rate": eur_per_usd or "",
                    "huf_rate": huf_per_usd or ""
                },
                "notes_and_dependencies": notes_and_dependencies or "",
                "sentiment_analysis": {
                    "sentiment": sentiment or "neutral",
                    "confidence": sentiment_confidence or 0.0
                },
                "full_conversation": full_conversation or "",
                "files": file_names or [],
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Save the ticket to file
            ticket_file = self.data_dir / f"{ticket_number}.json"
            with open(ticket_file, 'w', encoding='utf-8') as f:
                json.dump(ticket_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Created ticket {ticket_number} at {ticket_file}")
            
            # Format the JSON for display
            json_display = json.dumps(ticket_data, indent=2, ensure_ascii=False)
            
            return {
                "success": True,
                "message": f"📋 **Ticket Created: {ticket_number}**",
                "data": {
                    "ticket_number": ticket_number,
                    "ticket_data": ticket_data,
                    "json_content": json_display,
                    "file_path": str(ticket_file)
                },
                "system_message": f"Created support ticket {ticket_number}"
            }
        
        except Exception as e:
            logger.error(f"JSON Creator tool exception: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "system_message": f"Failed to create JSON ticket: {e}"
            }


class GuardrailsTool:
    """
    Guardrails tool for PII (Personal Identifiable Information) masking and legal compliance.
    
    This tool ensures data protection by:
    - Detecting and masking personal information (names, emails, phones, addresses, etc.)
    - Ensuring GDPR/legal compliance before data is stored or transmitted
    - Providing audit trail of what was masked
    
    PII types detected and masked:
    - Email addresses
    - Phone numbers (international formats)
    - Credit card numbers
    - Social Security Numbers / National IDs
    - IP addresses
    - Physical addresses
    - Bank account numbers (IBAN)
    - Dates of birth
    - Personal names (when context suggests PII)
    """
    
    # Regex patterns for PII detection
    PII_PATTERNS = {
        'email': {
            'pattern': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'description': 'Email address',
            'mask': '###EMAIL###'
        },
        'phone_international': {
            'pattern': r'\+?[1-9]\d{0,2}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
            'description': 'Phone number',
            'mask': '###PHONE###'
        },
        'phone_hu': {
            'pattern': r'\+36[-.\s]?\d{1,2}[-.\s]?\d{3}[-.\s]?\d{4}',
            'description': 'Hungarian phone number',
            'mask': '###PHONE###'
        },
        'credit_card': {
            'pattern': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
            'description': 'Credit card number',
            'mask': '###CREDIT_CARD###'
        },
        'ssn_us': {
            'pattern': r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',
            'description': 'US Social Security Number',
            'mask': '###SSN###'
        },
        'national_id_hu': {
            'pattern': r'\b\d{6}[A-Z]{2}\b',
            'description': 'Hungarian National ID',
            'mask': '###NATIONAL_ID###'
        },
        'ip_address': {
            'pattern': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
            'description': 'IP address',
            'mask': '###IP###'
        },
        'iban': {
            'pattern': r'\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b',
            'description': 'IBAN bank account',
            'mask': '###IBAN###'
        },
        'date_of_birth': {
            'pattern': r'\b(?:born|születet[ti]?|dob|birth\s*date|születési\s*dátum)[:\s]*(\d{4}[-./]\d{1,2}[-./]\d{1,2}|\d{1,2}[-./]\d{1,2}[-./]\d{4})\b',
            'description': 'Date of birth',
            'mask': '###DOB###'
        },
        'passport': {
            'pattern': r'\b[A-Z]{1,2}\d{6,9}\b',
            'description': 'Passport number',
            'mask': '###PASSPORT###'
        },
        'address_zip_hu': {
            'pattern': r'\b\d{4}\s+[A-ZÁÉÍÓÖŐÚÜŰa-záéíóöőúüű]+(?:\s+[A-ZÁÉÍÓÖŐÚÜŰa-záéíóöőúüű]+)*,?\s+[A-ZÁÉÍÓÖŐÚÜŰa-záéíóöőúüű]+\s+(?:utca|út|tér|körút|köz|sor)\s*\d+',
            'description': 'Hungarian address',
            'mask': '###ADDRESS###'
        },
        'tax_id_hu': {
            'pattern': r'\b\d{10}\b',
            'description': 'Hungarian Tax ID',
            'mask': '###TAX_ID###'
        }
    }
    
    # Sensitive keywords that might indicate PII context
    SENSITIVE_KEYWORDS = [
        'password', 'jelszó', 'pin', 'secret', 'titkos',
        'social security', 'taj szám', 'személyi', 'adószám',
        'bank account', 'bankszámla', 'card number', 'kártyaszám',
        'passport', 'útlevél', 'driver license', 'jogosítvány'
    ]
    
    def __init__(self):
        self.name = "guardrails"
        self.description = """PII masking and legal compliance tool.
Detects and masks personal identifiable information (PII) to ensure GDPR compliance.

Masks the following PII types with ###:
- Email addresses → ###EMAIL###
- Phone numbers → ###PHONE###
- Credit card numbers → ###CREDIT_CARD###
- Social Security Numbers → ###SSN###
- National IDs → ###NATIONAL_ID###
- IP addresses → ###IP###
- IBAN bank accounts → ###IBAN###
- Dates of birth → ###DOB###
- Passport numbers → ###PASSPORT###
- Physical addresses → ###ADDRESS###
- Tax IDs → ###TAX_ID###

Use this tool BEFORE storing or transmitting any user data."""
        
        # Compile regex patterns for efficiency
        import re
        self._compiled_patterns = {
            name: re.compile(info['pattern'], re.IGNORECASE)
            for name, info in self.PII_PATTERNS.items()
        }
    
    def _detect_pii(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect all PII in the given text.
        
        Returns:
            List of detected PII with type, value, and position
        """
        detected = []
        
        for pii_type, pattern in self._compiled_patterns.items():
            for match in pattern.finditer(text):
                detected.append({
                    'type': pii_type,
                    'description': self.PII_PATTERNS[pii_type]['description'],
                    'value': match.group(),
                    'start': match.start(),
                    'end': match.end(),
                    'mask': self.PII_PATTERNS[pii_type]['mask']
                })
        
        # Sort by position (descending) for safe replacement
        detected.sort(key=lambda x: x['start'], reverse=True)
        return detected
    
    def _mask_pii(self, text: str, detected_pii: List[Dict[str, Any]]) -> str:
        """
        Mask all detected PII in the text.
        
        Args:
            text: Original text
            detected_pii: List of detected PII (sorted by position descending)
        
        Returns:
            Text with PII masked
        """
        masked_text = text
        for pii in detected_pii:
            masked_text = masked_text[:pii['start']] + pii['mask'] + masked_text[pii['end']:]
        return masked_text
    
    def _check_sensitive_keywords(self, text: str) -> List[str]:
        """Check for sensitive keywords that might indicate PII context."""
        text_lower = text.lower()
        found_keywords = []
        for keyword in self.SENSITIVE_KEYWORDS:
            if keyword in text_lower:
                found_keywords.append(keyword)
        return found_keywords
    
    def _generate_audit_log(self, detected_pii: List[Dict[str, Any]], sensitive_keywords: List[str]) -> Dict[str, Any]:
        """Generate audit log of what was detected and masked."""
        pii_summary = {}
        for pii in detected_pii:
            pii_type = pii['description']
            if pii_type not in pii_summary:
                pii_summary[pii_type] = 0
            pii_summary[pii_type] += 1
        
        return {
            'pii_types_found': pii_summary,
            'total_pii_masked': len(detected_pii),
            'sensitive_keywords_detected': sensitive_keywords,
            'compliance_status': 'MASKED' if detected_pii else 'CLEAN'
        }
    
    async def execute(
        self,
        text: str = None,
        action: str = "mask",
        include_audit: bool = True
    ) -> Dict[str, Any]:
        """
        Execute guardrails PII masking.
        
        Args:
            text: The text to scan and mask for PII
            action: 'mask' to mask PII, 'detect' to only detect without masking
            include_audit: Whether to include audit log in response
        
        Returns:
            Dict with masked text, detected PII count, and audit log
        """
        try:
            logger.info(f"Guardrails tool called: action={action}, text_len={len(text) if text else 0}")
            
            if not text:
                return {
                    "success": False,
                    "error": "No text provided for PII scanning",
                    "system_message": "Guardrails failed: empty text"
                }
            
            # Detect PII
            detected_pii = self._detect_pii(text)
            sensitive_keywords = self._check_sensitive_keywords(text)
            
            # Generate audit log
            audit_log = self._generate_audit_log(detected_pii, sensitive_keywords)
            
            if action == "detect":
                # Only detect, don't mask
                pii_details = [
                    {
                        'type': pii['description'],
                        'masked_value': pii['value'][:3] + '***' if len(pii['value']) > 3 else '***'
                    }
                    for pii in detected_pii
                ]
                
                return {
                    "success": True,
                    "message": f"🔍 **PII Detection Complete**\n\nFound {len(detected_pii)} PII items",
                    "data": {
                        "pii_found": len(detected_pii) > 0,
                        "pii_count": len(detected_pii),
                        "pii_details": pii_details,
                        "sensitive_keywords": sensitive_keywords,
                        "original_text": text
                    },
                    "audit_log": audit_log if include_audit else None,
                    "system_message": f"Detected {len(detected_pii)} PII items in text"
                }
            
            else:  # action == "mask"
                # Mask all detected PII
                masked_text = self._mask_pii(text, detected_pii)
                
                # Build summary message
                if detected_pii:
                    summary_parts = []
                    for pii_type, count in audit_log['pii_types_found'].items():
                        summary_parts.append(f"- {pii_type}: {count}")
                    summary = "\n".join(summary_parts)
                    
                    message = f"🛡️ **Guardrails PII Masking Complete**\n\n"
                    message += f"**{len(detected_pii)} PII items masked:**\n{summary}\n\n"
                    message += f"**Compliance Status:** ✅ GDPR Compliant (PII Masked)"
                else:
                    message = "🛡️ **Guardrails Scan Complete**\n\n"
                    message += "**No PII detected** - Text is clean\n\n"
                    message += "**Compliance Status:** ✅ GDPR Compliant"
                
                if sensitive_keywords:
                    message += f"\n\n⚠️ **Warning:** Sensitive keywords detected: {', '.join(sensitive_keywords)}"
                
                return {
                    "success": True,
                    "message": message,
                    "data": {
                        "original_text": text,
                        "masked_text": masked_text,
                        "pii_masked": len(detected_pii) > 0,
                        "pii_count": len(detected_pii),
                        "sensitive_keywords": sensitive_keywords,
                        "compliance_status": "MASKED" if detected_pii else "CLEAN"
                    },
                    "audit_log": audit_log if include_audit else None,
                    "system_message": f"Guardrails: Masked {len(detected_pii)} PII items, compliance status: {'MASKED' if detected_pii else 'CLEAN'}"
                }
        
        except Exception as e:
            logger.error(f"Guardrails tool exception: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "system_message": f"Guardrails PII masking failed: {e}"
            }


class SentimentTool:
    """
    Sentiment analysis tool that analyzes the emotional tone of user messages.
    Identifies if the user is negative, neutral, or positive with confidence score.
    """
    
    def __init__(self, client):
        """
        Initialize SentimentTool.
        
        Args:
            client: SentimentAnalysisClient instance for sentiment analysis
        """
        self.client = client
        self.name = "sentiment"
        self.description = """Analyze the sentiment/emotional tone of user messages.
Returns:
- sentiment: 'negative', 'neutral', or 'positive'
- confidence: confidence score (0-1)
- explanation: brief explanation of the sentiment

Use this to understand the user's emotional state and tone."""
    
    async def execute(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of the given text.
        
        Args:
            text: The text to analyze
            
        Returns:
            Dict with success, sentiment, confidence, and explanation
        """
        try:
            logger.info(f"Sentiment tool called for text: '{text[:50]}...'")
            
            if not text or not text.strip():
                return {
                    "success": False,
                    "error": "No text provided for sentiment analysis",
                    "system_message": "Sentiment analysis failed: empty text"
                }
            
            result = await self.client.analyze_sentiment(text)
            
            if "error" in result:
                return {
                    "success": False,
                    "error": result["error"],
                    "system_message": f"Sentiment analysis failed: {result['error']}"
                }
            
            sentiment = result.get("sentiment", "neutral")
            confidence = result.get("confidence", 0.0)
            explanation = result.get("explanation", "")
            
            # Format the message
            emoji_map = {
                "positive": "😊",
                "neutral": "😐",
                "frustrated": "😟"
            }
            emoji = emoji_map.get(sentiment, "🤔")
            
            message = f"{emoji} **Sentiment Analysis:**\n"
            message += f"- **Tone:** {sentiment.capitalize()}\n"
            message += f"- **Confidence:** {confidence:.1%}\n"
            if explanation:
                message += f"- **Analysis:** {explanation}"
            
            return {
                "success": True,
                "message": message,
                "data": {
                    "sentiment": sentiment,
                    "confidence": confidence,
                    "explanation": explanation
                },
                "system_message": f"Sentiment: {sentiment} ({confidence:.1%} confidence)"
            }
        
        except Exception as e:
            logger.error(f"Sentiment tool exception: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "system_message": f"Sentiment analysis failed: {e}"
            }


class SQLiteSaveTool:
    """Tool to save ticket data to SQLite database."""
    
    def __init__(self, db_path: str = None):
        self.name = "sqlite_save"
        self.description = "Save ticket data to SQLite database for persistent storage and analytics."
        
        # Default to tickets.db in the data directory
        if db_path is None:
            data_dir = Path(__file__).parent.parent / "data"
            db_path = str(data_dir / "tickets.db")
        
        self.db_path = db_path
        logger.info(f"SQLiteSaveTool initialized with database: {self.db_path}")
    
    def _ensure_database_exists(self):
        """Ensure database and tables exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tickets table if not exists
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_number TEXT PRIMARY KEY,
            user_name TEXT NOT NULL,
            contact_time TEXT NOT NULL,
            original_language TEXT,
            original_message TEXT,
            issue_type TEXT,
            potential_issue TEXT,
            owning_team TEXT,
            xlsx_file_name TEXT,
            priority TEXT,
            acknowledgement_time TEXT,
            resolve_time TEXT,
            cost_usd TEXT,
            cost_eur_rate TEXT,
            cost_huf_rate TEXT,
            notes_and_dependencies TEXT,
            sentiment TEXT,
            sentiment_confidence REAL,
            full_conversation TEXT,
            created_at TEXT NOT NULL
        )
        """)
        
        # Create files table if not exists
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticket_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_number TEXT NOT NULL,
            file_name TEXT NOT NULL,
            FOREIGN KEY (ticket_number) REFERENCES tickets(ticket_number)
        )
        """)
        
        conn.commit()
        conn.close()
    
    async def execute(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save ticket data to SQLite database.
        
        Args:
            ticket_data: Dictionary containing ticket information from JSON creator
        
        Returns:
            Dict with success status and message
        """
        try:
            logger.info(f"SQLiteSaveTool executing for ticket: {ticket_data.get('ticket_number')}")
            
            # Ensure database exists
            self._ensure_database_exists()
            
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Extract nested data
            cost_data = ticket_data.get('cost_to_customer', {})
            sentiment_data = ticket_data.get('sentiment_analysis', {})
            files = ticket_data.get('files', [])
            
            # Insert or replace ticket data
            cursor.execute("""
            INSERT OR REPLACE INTO tickets (
                ticket_number, user_name, contact_time, original_language, original_message,
                issue_type, potential_issue, owning_team, xlsx_file_name, priority,
                acknowledgement_time, resolve_time, cost_usd, cost_eur_rate, cost_huf_rate,
                notes_and_dependencies, sentiment, sentiment_confidence, full_conversation, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticket_data.get('ticket_number'),
                ticket_data.get('user_name'),
                ticket_data.get('contact_time'),
                ticket_data.get('original_language'),
                ticket_data.get('original_message'),
                ticket_data.get('issue_type'),
                ticket_data.get('potential_issue'),
                ticket_data.get('owning_team'),
                ticket_data.get('xlsx_file_name'),
                ticket_data.get('priority'),
                ticket_data.get('acknowledgement_time'),
                ticket_data.get('resolve_time'),
                cost_data.get('usd'),
                cost_data.get('eur_rate'),
                cost_data.get('huf_rate'),
                ticket_data.get('notes_and_dependencies'),
                sentiment_data.get('sentiment'),
                sentiment_data.get('confidence'),
                ticket_data.get('full_conversation'),
                ticket_data.get('created_at')
            ))
            
            # Insert attached files
            ticket_number = ticket_data.get('ticket_number')
            
            # First, delete existing file entries for this ticket (in case of update)
            cursor.execute("DELETE FROM ticket_files WHERE ticket_number = ?", (ticket_number,))
            
            # Insert new file entries
            for file_name in files:
                cursor.execute("""
                INSERT INTO ticket_files (ticket_number, file_name)
                VALUES (?, ?)
                """, (ticket_number, file_name))
            
            conn.commit()
            
            # Get statistics
            cursor.execute("SELECT COUNT(*) FROM tickets")
            total_tickets = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM ticket_files WHERE ticket_number = ?", (ticket_number,))
            file_count = cursor.fetchone()[0]
            
            conn.close()
            
            message = f"💾 **Database Save Complete!**\n\n"
            message += f"📋 **Ticket:** {ticket_number}\n"
            message += f"📊 **Total Tickets in DB:** {total_tickets}\n"
            if file_count > 0:
                message += f"📎 **Attached Files Saved:** {file_count}\n"
            message += f"✅ **Status:** Successfully saved to database"
            
            logger.info(f"Ticket {ticket_number} saved to database successfully")
            
            return {
                "success": True,
                "message": message,
                "data": {
                    "ticket_number": ticket_number,
                    "total_tickets": total_tickets,
                    "files_saved": file_count,
                    "database_path": self.db_path
                },
                "system_message": f"Saved ticket {ticket_number} to database (Total: {total_tickets} tickets)"
            }
        
        except Exception as e:
            logger.error(f"SQLiteSaveTool exception: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "system_message": f"Database save failed: {e}"
            }


class EmailSendTool:
    """Tool to send ticket notification emails via SMTP (Gmail)."""
    
    def __init__(self, email_client, from_email: str, to_email: str):
        self.name = "send_ticket_via_email"
        self.description = "Send ticket notification email with details to configured recipient via SMTP."
        self.email_client = email_client
        self.from_email = from_email
        self.to_email = to_email
        logger.info(f"EmailSendTool initialized with sender: {from_email}, recipient: {to_email}")
    
    def _format_ticket_table(self, ticket_data: Dict[str, Any]) -> str:
        """Format ticket data as a nice HTML table."""
        
        # Extract nested data
        cost_data = ticket_data.get('cost_to_customer', {})
        sentiment_data = ticket_data.get('sentiment_analysis', {})
        files = ticket_data.get('files', [])
        
        html = """
        <table style="border-collapse: collapse; width: 100%; font-family: Arial, sans-serif;">
            <tr style="background-color: #f2f2f2;">
                <th style="border: 1px solid #ddd; padding: 12px; text-align: left;">Field</th>
                <th style="border: 1px solid #ddd; padding: 12px; text-align: left;">Value</th>
            </tr>
        """
        
        # Define fields to display
        fields = [
            ("Ticket Number", ticket_data.get('ticket_number', 'N/A')),
            ("User Name", ticket_data.get('user_name', 'N/A')),
            ("Contact Time", ticket_data.get('contact_time', 'N/A')),
            ("Original Language", ticket_data.get('original_language', 'N/A')),
            ("Original Message", ticket_data.get('original_message', 'N/A')),
            ("Issue Type", ticket_data.get('issue_type', 'N/A')),
            ("Potential Issue", ticket_data.get('potential_issue', 'N/A')),
            ("Owning Team", ticket_data.get('owning_team', 'N/A')),
            ("Priority", ticket_data.get('priority', 'N/A')),
            ("Acknowledgement Time", ticket_data.get('acknowledgement_time', 'N/A')),
            ("Resolve Time", ticket_data.get('resolve_time', 'N/A')),
            ("Cost (USD)", cost_data.get('usd', 'N/A')),
            ("EUR Rate", cost_data.get('eur_rate', 'N/A')),
            ("HUF Rate", cost_data.get('huf_rate', 'N/A')),
            ("Notes/Dependencies", ticket_data.get('notes_and_dependencies', 'N/A')),
            ("Sentiment", f"{sentiment_data.get('sentiment', 'N/A')} ({sentiment_data.get('confidence', 0):.2f})"),
            ("Attached Files", ', '.join(files) if files else 'None'),
            ("Created At", ticket_data.get('created_at', 'N/A'))
        ]
        
        # Add rows
        for i, (field, value) in enumerate(fields):
            bg_color = "#ffffff" if i % 2 == 0 else "#f9f9f9"
            html += f"""
            <tr style="background-color: {bg_color};">
                <td style="border: 1px solid #ddd; padding: 12px; font-weight: bold;">{field}</td>
                <td style="border: 1px solid #ddd; padding: 12px;">{value}</td>
            </tr>
            """
        
        html += "</table>"
        return html
    
    def _format_ticket_text(self, ticket_data: Dict[str, Any]) -> str:
        """Format ticket data as plain text."""
        
        # Extract nested data
        cost_data = ticket_data.get('cost_to_customer', {})
        sentiment_data = ticket_data.get('sentiment_analysis', {})
        files = ticket_data.get('files', [])
        
        text = f"""
Ticket Number:          {ticket_data.get('ticket_number', 'N/A')}
User Name:              {ticket_data.get('user_name', 'N/A')}
Contact Time:           {ticket_data.get('contact_time', 'N/A')}
Original Language:      {ticket_data.get('original_language', 'N/A')}
Original Message:       {ticket_data.get('original_message', 'N/A')}
Issue Type:             {ticket_data.get('issue_type', 'N/A')}
Potential Issue:        {ticket_data.get('potential_issue', 'N/A')}
Owning Team:            {ticket_data.get('owning_team', 'N/A')}
Priority:               {ticket_data.get('priority', 'N/A')}
Acknowledgement Time:   {ticket_data.get('acknowledgement_time', 'N/A')}
Resolve Time:           {ticket_data.get('resolve_time', 'N/A')}
Cost (USD):             {cost_data.get('usd', 'N/A')}
EUR Rate:               {cost_data.get('eur_rate', 'N/A')}
HUF Rate:               {cost_data.get('huf_rate', 'N/A')}
Notes/Dependencies:     {ticket_data.get('notes_and_dependencies', 'N/A')}
Sentiment:              {sentiment_data.get('sentiment', 'N/A')} ({sentiment_data.get('confidence', 0):.2f})
Attached Files:         {', '.join(files) if files else 'None'}
Created At:             {ticket_data.get('created_at', 'N/A')}
        """
        
        return text.strip()
    
    async def execute(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send ticket notification email.
        
        Args:
            ticket_data: Dictionary containing ticket information
        
        Returns:
            Dict with success status and message
        """
        try:
            ticket_number = ticket_data.get('ticket_number', 'Unknown')
            logger.info(f"EmailSendTool executing for ticket: {ticket_number}")
            
            # Prepare email content
            subject = f"Ticket {ticket_number} has been created"
            
            # Plain text body
            text_body = f"""Hello,

The new ticket {ticket_number} has been created.
Below are the details:

{self._format_ticket_text(ticket_data)}

Kind regards,
Ticket Automation"""
            
            # HTML body with formatted table
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: #2c3e50;">Ticket {ticket_number} Created</h2>
                <p>Hello,</p>
                <p>The new ticket <strong>{ticket_number}</strong> has been created.</p>
                <p>Below are the details:</p>
                {self._format_ticket_table(ticket_data)}
                <p style="margin-top: 20px;">Kind regards,<br><strong>Ticket Automation</strong></p>
            </body>
            </html>
            """
            
            # Send email
            result = self.email_client.send_email(
                to_email=self.to_email,
                from_email=self.from_email,
                subject=subject,
                text_body=text_body,
                html_body=html_body
            )
            
            if result.get("success"):
                message = f"📧 **Email Sent Successfully!**\n\n"
                message += f"📋 **Ticket:** {ticket_number}\n"
                message += f"📬 **To:** {self.to_email}\n"
                message += f"✉️ **Subject:** {subject}\n"
                message += f"✅ **Status:** Email delivered"
                
                logger.info(f"Email sent successfully for ticket {ticket_number}")
                
                return {
                    "success": True,
                    "message": message,
                    "data": {
                        "ticket_number": ticket_number,
                        "recipient": self.to_email,
                        "message_id": result.get("message_id"),
                        "subject": subject
                    },
                    "system_message": f"Email sent to {self.to_email} for ticket {ticket_number}"
                }
            else:
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Failed to send email for ticket {ticket_number}: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "system_message": f"Email send failed: {error_msg}"
                }
        
        except Exception as e:
            logger.error(f"EmailSendTool exception: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "system_message": f"Email send failed: {e}"
            }
