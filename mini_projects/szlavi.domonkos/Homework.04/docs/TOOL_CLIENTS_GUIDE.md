# Tool Clients Integration Guide

## Overview

The Homework.03 project includes comprehensive tool client integrations for external APIs:

- **IP Geolocation** (IPAPIGeolocationClient) - Get location from IP address
- **Weather** (OpenWeatherMapClient) - Get weather information by city
- **Cryptocurrency** (CoinGeckoClient) - Get crypto prices (free, no API key required)
- **Foreign Exchange** (ExchangeRateAPIClient) - Get currency exchange rates

All clients follow SOLID principles with abstract interfaces and concrete implementations.

---

## IP Geolocation Client

### Overview
Uses **ip-api.com** free tier to geolocate IP addresses.

### Configuration
No API key required for free tier. Free tier limits: 45 requests/minute.

```bash
# In .env (optional for free tier):
# For pro tier (requires key):
IPAPI_API_KEY=your_pro_api_key_here
```

### Usage

**Interactive CLI:**
```
/geo 8.8.8.8
/geo 1.1.1.1
```

**Output:**
```
--- IP Geolocation ---
IP Address: 8.8.8.8
Country: United States
Region: California
City: Mountain View
Coordinates: 37.386, -122.084
Timezone: America/Los_Angeles
ISP: Google LLC
Organization: Google
```

### API Response Fields
- `ip` - IP address queried
- `country` - Country name
- `region` - State/Province
- `city` - City name
- `latitude`, `longitude` - Coordinates
- `timezone` - IANA timezone
- `isp` - Internet Service Provider
- `organization` - Organization name
- `continent` - Continent name

### Python Code Example
```python
from app.tool_clients import IPAPIGeolocationClient

client = IPAPIGeolocationClient(use_pro=False)
location = client.get_location_from_ip("8.8.8.8")
if location:
    print(f"{location['city']}, {location['country']}")
    print(f"Coordinates: {location['latitude']}, {location['longitude']}")
```

---

## Weather Client

### Overview
Uses **OpenWeatherMap API** to retrieve weather data for any city.

### Configuration
Requires free API key from https://openweathermap.org/api

```bash
# In .env:
OPENWEATHER_API_KEY=your_openweather_api_key_here
```

### Setup
1. Visit https://openweathermap.org/api
2. Sign up for a free account
3. Generate an API key
4. Add to `.env` file

### Usage

**Interactive CLI:**
```
/weather London
/weather New York
/weather Tokyo
```

**Output:**
```
--- Weather ---
City: London, GB
Temperature: 12°C
Feels Like: 10°C
Condition: overcast clouds
Humidity: 72%
Wind Speed: 4.3 m/s
Clouds: 90%
Timestamp: 2026-01-17T15:30:00
```

### API Response Fields
- `city` - City name
- `country` - Country code
- `temperature` - Temperature in Celsius
- `feels_like` - "Feels like" temperature
- `humidity` - Humidity percentage
- `pressure` - Atmospheric pressure (hPa)
- `description` - Weather condition
- `wind_speed` - Wind speed (m/s)
- `clouds` - Cloud percentage
- `timestamp` - UTC timestamp

### Python Code Example
```python
from app.tool_clients import OpenWeatherMapClient

client = OpenWeatherMapClient(api_key="your_key_here")
weather = client.get_weather("London")
if weather:
    print(f"{weather['city']}: {weather['temperature']}°C, {weather['description']}")
```

---

## Cryptocurrency Price Client

### Overview
Uses **CoinGecko API** (free, no key required) to retrieve cryptocurrency prices.

### Configuration
No API key required. Free tier: 10-50 calls/second.

```bash
# No configuration needed - CoinGecko is free
```

### Usage

**Interactive CLI:**
```
/crypto bitcoin
/crypto ethereum
/crypto cardano
/crypto litecoin
```

**Output:**
```
--- BITCOIN Price ---
Price: 43250.75 usd
24h Change: 2.45%
Market Cap: 843250000000 usd
24h Volume: 31250000000 usd
Updated: 2026-01-17T15:30:45.123456
```

### Supported Symbols
Any symbol supported by CoinGecko:
- `bitcoin`, `ethereum`, `cardano`, `solana`, `dogecoin`, etc.
- Full list: https://api.coingecko.com/api/v3/simple/supported_vs_currencies

### API Response Fields
- `symbol` - Cryptocurrency symbol
- `currency` - Target currency (USD, EUR, etc.)
- `price` - Current price
- `market_cap` - Market capitalization
- `volume_24h` - 24-hour trading volume
- `change_24h` - 24-hour percentage change
- `timestamp` - ISO timestamp

### Python Code Example
```python
from app.tool_clients import CoinGeckoClient

client = CoinGeckoClient()
crypto = client.get_crypto_price("bitcoin", vs_currency="usd")
if crypto:
    print(f"{crypto['symbol']}: ${crypto['price']} ({crypto['change_24h']:+.2f}%)")
```

---

## Foreign Exchange Client

### Overview
Uses **ExchangeRate API** to retrieve currency exchange rates.

### Configuration
Free tier available at https://www.exchangerate-api.com

```bash
# In .env (optional for free tier):
EXCHANGERATE_API_KEY=your_api_key_here
```

### Setup (Optional - Free tier available)
1. Visit https://www.exchangerate-api.com
2. Sign up (free tier: 1,500 requests/month)
3. Get API key (optional)
4. Add to `.env` if using pro tier

### Usage

**Interactive CLI:**
```
/forex USD EUR
/forex USD GBP
/forex EUR JPY
```

**Output:**
```
--- Exchange Rate ---
USD → EUR
Rate: 1 USD = 0.92 EUR
Date: 2026-01-17
```

### Supported Currencies
All ISO 4217 currency codes:
- Major: USD, EUR, GBP, JPY, CAD, AUD, CHF, CNY, INR
- Full list: https://www.exchangerate-api.com/docs/supported-currencies

### API Response Fields
- `base` - Base currency code
- `target` - Target currency code
- `rate` - Exchange rate
- `timestamp` - Date of rate

### Python Code Example
```python
from app.tool_clients import ExchangeRateAPIClient

client = ExchangeRateAPIClient(api_key=None)  # None for free tier
rate = client.get_exchange_rate("USD", "EUR")
if rate:
    print(f"{rate['rate']} {rate['target']} per {rate['base']}")
```

---

## Integration Architecture

All clients follow a consistent pattern:

```python
from abc import ABC, abstractmethod

# Abstract interface
class SomeClient(ABC):
    @abstractmethod
    def method(self, param: str) -> Optional[Dict[str, Any]]:
        """Get data."""

# Concrete implementation
class ConcreteSomeClient(SomeClient):
    def method(self, param: str) -> Optional[Dict[str, Any]]:
        # Implementation with error handling
        pass
```

### Benefits
- **Loose coupling**: Easy to swap implementations
- **Testability**: Can mock abstract interfaces
- **Extensibility**: Add new clients without changing existing code
- **Error handling**: Graceful degradation if API unavailable

---

## Error Handling

All clients implement robust error handling:

1. **Network errors**: RequestException → None
2. **Timeout**: 5-second timeout per request
3. **Invalid responses**: Validation before returning data
4. **Logging**: All errors logged at WARN/ERROR level

### Example
```python
from app.tool_clients import IPAPIGeolocationClient

client = IPAPIGeolocationClient()
result = client.get_location_from_ip("8.8.8.8")

if result is None:
    print("Geolocation lookup failed - check logs for details")
else:
    print(f"Located: {result['city']}, {result['country']}")
```

---

## Testing

Unit tests available in `tests/test_tool_clients.py`:

```bash
pytest tests/test_tool_clients.py -v
```

Tests include:
- Successful API responses
- Failure scenarios
- Exception handling
- Response parsing

---

## Best Practices

1. **Rate Limiting**: Free tiers have request limits
   - IP Geolocation: 45/min
   - OpenWeather: See plan
   - CoinGecko: 10-50/sec
   - ExchangeRate: 1,500/month (free)

2. **Caching**: Consider caching results in production
   - Exchange rates: Cache for 1+ hours (changes infrequently)
   - Weather: Cache for 15-30 minutes
   - Crypto: Cache for 1-5 minutes (volatile)
   - Geolocation: Cache per IP (unlikely to change)

3. **API Keys**: Store in `.env`, never commit to repo

4. **Fallbacks**: Handle gracefully when APIs unavailable

---

## Extending the Tool Clients

To add a new tool client:

1. Create abstract interface (inherits from ABC)
2. Implement concrete client with error handling
3. Add configuration to `config.py`
4. Initialize in `main.py`
5. Add CLI command handler in `cli.py`
6. Write tests in `tests/test_tool_clients.py`

Example:
```python
# 1. Abstract interface
class NewsClient(ABC):
    @abstractmethod
    def get_headlines(self, country: str) -> Optional[List[Dict]]:
        pass

# 2. Concrete implementation
class NewsAPIClient(NewsClient):
    def __init__(self, api_key: str):
        self.api_key = api_key
        
    def get_headlines(self, country: str) -> Optional[List[Dict]]:
        # Implementation
        pass
```

---

## Troubleshooting

**"Service not available"**
- Check `.env` for API keys
- Verify network connectivity
- Check API rate limits
- See logs for detailed error

**"Invalid response"**
- API might be down
- Check documentation for response format changes
- Verify API key is valid

**"Timeout"**
- Network latency issue
- API might be slow
- Try again

---

## Resources

- [ip-api.com](https://ip-api.com)
- [OpenWeatherMap](https://openweathermap.org/api)
- [CoinGecko API](https://www.coingecko.com/api)
- [ExchangeRate API](https://www.exchangerate-api.com)

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│                    CLI Layer                        │
│  /geo | /weather | /crypto | /forex                │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────────┐
│              Tool Clients (Abstract)                │
│  GeolocationClient | WeatherClient | ...           │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────────┐
│         Tool Clients (Implementations)             │
│  IPAPIGeolocationClient | OpenWeatherMapClient     │
│  CoinGeckoClient | ExchangeRateAPIClient           │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────────┐
│                External APIs                       │
│  ip-api.com | openweathermap.org | coingecko.com  │
└─────────────────────────────────────────────────────┘
```
