"""
External API Service - Weather and Currency API integrations.

HW 07-08: External API tool integration with:
- Pydantic validation
- Retry logic with exponential backoff
- Timeout handling
- Error recovery patterns
"""
import logging
import httpx
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, ConfigDict, Field
from services.retry_helper import retry_with_backoff
from services.exceptions import ServiceError

logger = logging.getLogger(__name__)


# ===== PYDANTIC SCHEMAS =====

class WeatherRequest(BaseModel):
    """Weather API request schema."""
    city: Optional[str] = Field(None, description="City name (e.g., 'Budapest', 'Paris')")
    lat: Optional[float] = Field(None, description="Latitude coordinate")
    lon: Optional[float] = Field(None, description="Longitude coordinate")
    days: Optional[int] = Field(2, description="Forecast days (max 16)")
    include_precipitation: Optional[bool] = Field(False, description="Include precipitation probability")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"city": "Budapest", "days": 16, "include_precipitation": True}
        }
    )


class WeatherResponse(BaseModel):
    """Weather API response schema."""
    success: bool
    location: Optional[Dict[str, Any]] = None
    current_temperature: Optional[float] = None
    hourly_forecast: Optional[Dict[str, Any]] = None
    tomorrow_summary: Optional[Dict[str, Any]] = None
    daily_forecast: Optional[List[Dict[str, Any]]] = None  # Extended forecast
    low_precipitation_days: Optional[List[Dict[str, Any]]] = None  # Days with ≤20% precipitation
    error: Optional[str] = None


class CurrencyRequest(BaseModel):
    """Currency exchange rate request schema."""
    base: str = Field(..., description="Base currency code (e.g., 'EUR', 'USD')")
    target: str = Field(..., description="Target currency code (e.g., 'HUF', 'USD')")
    date: Optional[str] = Field(None, description="Historical date (YYYY-MM-DD format, or 'latest')")
    date_range: Optional[str] = Field(
        None, 
        description="Date range for multi-day data (e.g., '2026-01-01..2026-01-31'). Overrides 'date' parameter."
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"base": "EUR", "target": "HUF"}
        }
    )


class CurrencyStatistics(BaseModel):
    """Statistical analysis for multi-day currency data."""
    min: float = Field(..., description="Minimum rate in the period")
    max: float = Field(..., description="Maximum rate in the period")
    avg: float = Field(..., description="Average (mean) rate")
    median: float = Field(..., description="Median rate")
    std_dev: float = Field(..., description="Standard deviation (volatility measure)")
    trend_direction: str = Field(..., description="'increasing', 'decreasing', or 'stable'")
    trend_strength: str = Field(..., description="'strong', 'moderate', or 'weak'")
    change_percent: float = Field(..., description="Percentage change from first to last day")
    volatility: str = Field(..., description="'low', 'medium', or 'high' based on std_dev")
    moving_avg_7d: Optional[float] = Field(None, description="7-day moving average (if >= 7 days)")
    moving_avg_30d: Optional[float] = Field(None, description="30-day moving average (if >= 30 days)")
    data_points: int = Field(..., description="Number of data points")


class CurrencyResponse(BaseModel):
    """Currency exchange rate response schema."""
    success: bool
    base: Optional[str] = None
    target: Optional[str] = None
    rate: Optional[float] = None  # Single rate (for latest/specific date)
    date: Optional[str] = None  # Single date
    rates_by_date: Optional[Dict[str, float]] = None  # Multi-day rates {"2026-01-01": 385.5, ...}
    statistics: Optional[CurrencyStatistics] = None  # Statistical analysis for multi-day data
    error: Optional[str] = None


# ===== HELPER FUNCTIONS =====

def calculate_currency_statistics(rates_by_date: Dict[str, float]) -> CurrencyStatistics:
    """
    Calculate statistical analysis for multi-day currency rates.
    
    Args:
        rates_by_date: Dictionary of {"YYYY-MM-DD": rate} pairs
        
    Returns:
        CurrencyStatistics with trend analysis, volatility, and moving averages
    """
    import statistics
    from datetime import datetime
    
    if not rates_by_date:
        raise ValueError("rates_by_date cannot be empty")
    
    # Sort by date and extract values
    sorted_items = sorted(rates_by_date.items())
    dates = [item[0] for item in sorted_items]
    rates = [item[1] for item in sorted_items]
    
    n = len(rates)
    
    # Basic statistics
    min_rate = min(rates)
    max_rate = max(rates)
    avg_rate = statistics.mean(rates)
    median_rate = statistics.median(rates)
    std_dev = statistics.stdev(rates) if n > 1 else 0.0
    
    # Trend analysis (simple linear regression)
    # Using least squares: slope = sum((x - x_mean) * (y - y_mean)) / sum((x - x_mean)^2)
    x_values = list(range(n))  # 0, 1, 2, ..., n-1
    x_mean = statistics.mean(x_values)
    y_mean = avg_rate
    
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, rates))
    denominator = sum((x - x_mean) ** 2 for x in x_values)
    
    slope = numerator / denominator if denominator != 0 else 0.0
    
    # Determine trend direction and strength
    first_rate = rates[0]
    last_rate = rates[-1]
    change_percent = ((last_rate - first_rate) / first_rate) * 100
    
    # Trend direction based on slope
    if abs(change_percent) < 0.5:  # Less than 0.5% change = stable
        trend_direction = "stable"
    elif slope > 0:
        trend_direction = "increasing"
    else:
        trend_direction = "decreasing"
    
    # Trend strength based on magnitude of change
    abs_change = abs(change_percent)
    if abs_change < 1.0:
        trend_strength = "weak"
    elif abs_change < 3.0:
        trend_strength = "moderate"
    else:
        trend_strength = "strong"
    
    # Volatility classification based on coefficient of variation (CV = std_dev / mean)
    cv = (std_dev / avg_rate) * 100 if avg_rate != 0 else 0
    if cv < 0.5:
        volatility = "low"
    elif cv < 1.5:
        volatility = "medium"
    else:
        volatility = "high"
    
    # Moving averages
    moving_avg_7d = None
    moving_avg_30d = None
    
    if n >= 7:
        moving_avg_7d = statistics.mean(rates[-7:])
    
    if n >= 30:
        moving_avg_30d = statistics.mean(rates[-30:])
    
    return CurrencyStatistics(
        min=round(min_rate, 4),
        max=round(max_rate, 4),
        avg=round(avg_rate, 4),
        median=round(median_rate, 4),
        std_dev=round(std_dev, 4),
        trend_direction=trend_direction,
        trend_strength=trend_strength,
        change_percent=round(change_percent, 2),
        volatility=volatility,
        moving_avg_7d=round(moving_avg_7d, 4) if moving_avg_7d else None,
        moving_avg_30d=round(moving_avg_30d, 4) if moving_avg_30d else None,
        data_points=n
    )


# ===== API CLIENTS =====

class WeatherAPIClient:
    """
    Open-Meteo Weather API client.
    
    Free, no API key needed. Returns weather forecast for given location.
    Implements retry logic and timeout handling.
    """
    
    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    GEOCODE_URL = "https://nominatim.openstreetmap.org/search"
    
    @retry_with_backoff(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_forecast(self, request: WeatherRequest) -> WeatherResponse:
        """
        Get weather forecast with retry logic.
        
        Args:
            request: Weather request (city OR lat/lon)
            
        Returns:
            WeatherResponse with forecast data or error
        """
        try:
            # Step 1: Get coordinates (geocode if city provided)
            lat, lon = request.lat, request.lon
            
            if request.city and (lat is None or lon is None):
                # Geocode city to coordinates
                lat, lon = await self._geocode_city(request.city)
            
            if lat is None or lon is None:
                return WeatherResponse(
                    success=False,
                    error="Either city or coordinates (lat/lon) must be provided"
                )
            
            # Step 2: Determine forecast parameters
            forecast_days = min(request.days or 2, 16)  # Max 16 days for free API
            
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weathercode",
                "hourly": "temperature_2m,weathercode",
                "forecast_days": forecast_days
            }
            
            # Add daily precipitation if requested
            if request.include_precipitation:
                params["daily"] = "precipitation_probability_max,precipitation_sum,temperature_2m_max,temperature_2m_min"
                params["timezone"] = "auto"
            
            # Step 3: Fetch weather forecast from Open-Meteo
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()
            
            # Extract current and tomorrow's forecast
            current_temp = data["current"]["temperature_2m"]
            hourly = data["hourly"]
            
            # Tomorrow = hours 24-47 in forecast
            tomorrow_temps = hourly.get("temperature_2m", [])[24:48]
            tomorrow_summary = None
            
            if tomorrow_temps:
                tomorrow_summary = {
                    "min_temp": round(min(tomorrow_temps), 1),
                    "max_temp": round(max(tomorrow_temps), 1),
                    "avg_temp": round(sum(tomorrow_temps) / len(tomorrow_temps), 1)
                }
            
            # Process extended forecast if daily data available
            daily_forecast = None
            low_precipitation_days = None
            
            if "daily" in data and request.include_precipitation:
                daily_forecast = []
                low_precipitation_days = []
                
                daily = data["daily"]
                dates = daily.get("time", [])
                precip_probs = daily.get("precipitation_probability_max", [])
                precip_sums = daily.get("precipitation_sum", [])
                temp_max = daily.get("temperature_2m_max", [])
                temp_min = daily.get("temperature_2m_min", [])
                
                for i, date in enumerate(dates):
                    precip_prob = precip_probs[i] if i < len(precip_probs) and precip_probs[i] is not None else 0
                    precip_sum = precip_sums[i] if i < len(precip_sums) and precip_sums[i] is not None else 0
                    
                    day_data = {
                        "date": date,
                        "precipitation_probability": precip_prob,
                        "precipitation_sum": precip_sum,
                        "temp_max": temp_max[i] if i < len(temp_max) else None,
                        "temp_min": temp_min[i] if i < len(temp_min) else None
                    }
                    daily_forecast.append(day_data)
                    
                    # Collect days with low precipitation probability (≤20%)
                    if precip_prob <= 20:
                        low_precipitation_days.append(day_data)
            
            logger.info(
                f"✅ Weather API success: ({lat}, {lon}) - "
                f"Current: {current_temp}°C, Tomorrow: {tomorrow_summary}"
            )
            
            return WeatherResponse(
                success=True,
                location={"latitude": lat, "longitude": lon},
                current_temperature=current_temp,
                hourly_forecast=hourly,
                tomorrow_summary=tomorrow_summary,
                daily_forecast=daily_forecast,
                low_precipitation_days=low_precipitation_days
            )
        
        except httpx.HTTPStatusError as e:
            logger.error(f"Weather API HTTP error: {e.response.status_code}")
            return WeatherResponse(
                success=False,
                error=f"Weather API error: {e.response.status_code}"
            )
        except httpx.TimeoutException:
            logger.error("Weather API timeout")
            return WeatherResponse(
                success=False,
                error="Weather API timeout (service unavailable)"
            )
        except Exception as e:
            logger.error(f"Weather API error: {e}", exc_info=True)
            return WeatherResponse(
                success=False,
                error=f"Weather API error: {str(e)}"
            )
    
    async def _geocode_city(self, city: str) -> tuple[Optional[float], Optional[float]]:
        """
        Geocode city name to coordinates using Nominatim.
        
        Returns:
            (latitude, longitude) or (None, None) on error
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.GEOCODE_URL,
                    params={"q": city, "format": "json", "limit": 1},
                    headers={"User-Agent": "KnowledgeRouter/1.0"}
                )
                response.raise_for_status()
                data = response.json()
            
            if not data:
                logger.warning(f"City not found: {city}")
                return None, None
            
            result = data[0]
            lat, lon = float(result["lat"]), float(result["lon"])
            logger.info(f"Geocoded '{city}' → ({lat}, {lon})")
            return lat, lon
        
        except Exception as e:
            logger.error(f"Geocoding error for '{city}': {e}")
            return None, None


class CurrencyAPIClient:
    """
    Frankfurter Currency API client (free, no API key).
    
    Returns exchange rates between currencies.
    Implements retry logic and timeout handling.
    """
    
    BASE_URL = "https://api.frankfurter.app"
    
    @retry_with_backoff(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_rate(self, request: CurrencyRequest) -> CurrencyResponse:
        """
        Get currency exchange rate with retry logic.
        
        Args:
            request: Currency request (base, target, optional date/date_range)
            
        Returns:
            CurrencyResponse with exchange rate or error
        """
        try:
            # Validate currency codes (basic check)
            if not request.base or not request.target:
                return CurrencyResponse(
                    success=False,
                    error="Both base and target currency codes required"
                )
            
            # Build endpoint (latest, historical single date, or date range)
            if request.date_range:
                # Multi-day range: /2026-01-01..2026-01-31
                endpoint = f"{self.BASE_URL}/{request.date_range}"
            elif request.date:
                # Single historical date
                endpoint = f"{self.BASE_URL}/{request.date}"
            else:
                # Latest rates
                endpoint = f"{self.BASE_URL}/latest"
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    endpoint,
                    params={"from": request.base.upper(), "to": request.target.upper()}
                )
                response.raise_for_status()
                data = response.json()
            
            target_upper = request.target.upper()
            
            # Handle multi-day response (date_range query)
            if request.date_range and "rates" in data:
                rates_by_date = {}
                for date_str, rates_dict in data["rates"].items():
                    if target_upper in rates_dict:
                        rates_by_date[date_str] = rates_dict[target_upper]
                
                if not rates_by_date:
                    return CurrencyResponse(
                        success=False,
                        error=f"No rates available for {request.base}/{request.target} in range {request.date_range}"
                    )
                
                # Calculate statistical analysis for multi-day data
                try:
                    statistics = calculate_currency_statistics(rates_by_date)
                except Exception as e:
                    logger.warning(f"Failed to calculate statistics: {e}")
                    statistics = None
                
                logger.info(
                    f"✅ Currency API success (multi-day): {request.base}/{request.target} "
                    f"range {request.date_range} - {len(rates_by_date)} days"
                )
                
                if statistics:
                    logger.info(
                        f"📊 Statistics: trend={statistics.trend_direction} ({statistics.trend_strength}), "
                        f"change={statistics.change_percent:.2f}%, volatility={statistics.volatility}"
                    )
                
                return CurrencyResponse(
                    success=True,
                    base=request.base.upper(),
                    target=target_upper,
                    rates_by_date=rates_by_date,
                    statistics=statistics
                )
            
            # Handle single-day response (latest or specific date)
            if "rates" not in data or target_upper not in data["rates"]:
                return CurrencyResponse(
                    success=False,
                    error=f"Exchange rate not available for {request.base}/{request.target}"
                )
            
            rate = data["rates"][target_upper]
            date = data.get("date")
            
            logger.info(
                f"✅ Currency API success: 1 {request.base} = {rate} {request.target} "
                f"(date: {date})"
            )
            
            return CurrencyResponse(
                success=True,
                base=request.base.upper(),
                target=request.target.upper(),
                rate=rate,
                date=date
            )
        
        except httpx.HTTPStatusError as e:
            logger.error(f"Currency API HTTP error: {e.response.status_code}")
            
            if e.response.status_code == 404:
                return CurrencyResponse(
                    success=False,
                    error=f"Currency pair not supported: {request.base}/{request.target}"
                )
            
            return CurrencyResponse(
                success=False,
                error=f"Currency API error: {e.response.status_code}"
            )
        
        except httpx.TimeoutException:
            logger.error("Currency API timeout")
            return CurrencyResponse(
                success=False,
                error="Currency API timeout (service unavailable)"
            )
        
        except Exception as e:
            logger.error(f"Currency API error: {e}", exc_info=True)
            return CurrencyResponse(
                success=False,
                error=f"Currency API error: {str(e)}"
            )


# ===== SERVICE FACADE =====

class ExternalAPIService:
    """
    Facade for all external API clients.
    
    Centralizes API call logic with:
    - Retry mechanisms
    - Timeout handling
    - Error recovery
    - Logging and observability
    """
    
    def __init__(self):
        self.weather_client = WeatherAPIClient()
        self.currency_client = CurrencyAPIClient()
        logger.info("✅ ExternalAPIService initialized (Weather + Currency)")
    
    async def get_weather(self, city: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None) -> WeatherResponse:
        """Get basic weather forecast (2 days)."""
        request = WeatherRequest(city=city, lat=lat, lon=lon, days=2, include_precipitation=False)
        return await self.weather_client.get_forecast(request)
    
    async def get_forecast_extended(
        self, 
        city: Optional[str] = None, 
        lat: Optional[float] = None, 
        lon: Optional[float] = None,
        days: int = 2,
        include_precipitation: bool = False
    ) -> WeatherResponse:
        """Get extended weather forecast with optional precipitation analysis."""
        request = WeatherRequest(
            city=city, lat=lat, lon=lon, 
            days=days, include_precipitation=include_precipitation
        )
        return await self.weather_client.get_forecast(request)
    
    async def get_currency_rate(
        self, 
        base: str, 
        target: str, 
        date: Optional[str] = None,
        date_range: Optional[str] = None
    ) -> CurrencyResponse:
        """Get currency exchange rate (single date or range)."""
        request = CurrencyRequest(base=base, target=target, date=date, date_range=date_range)
        return await self.currency_client.get_rate(request)
