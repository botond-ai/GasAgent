"""Unit tests for weather tool."""
import pytest
import responses
import os
from unittest.mock import patch
from src.agent.tools.weather import get_weather, WeatherInput, WeatherOutput


class TestGetWeather:
    """Test cases for get_weather function."""
    
    @responses.activate
    @patch.dict(os.environ, {"OPENWEATHER_API_KEY": "test_api_key_12345"})
    def test_get_weather_success(self):
        """Test successful weather retrieval."""
        responses.add(
            responses.GET,
            "https://api.openweathermap.org/data/2.5/weather",
            json={
                "name": "Budapest",
                "main": {
                    "temp": 15.5,
                    "humidity": 65
                },
                "weather": [
                    {
                        "description": "tiszta ég"
                    }
                ],
                "wind": {
                    "speed": 3.5
                }
            },
            status=200
        )
        
        result = get_weather(latitude=47.4979, longitude=19.0402)
        
        assert result.success is True
        assert result.temperature_c == 15.5
        assert result.description == "tiszta ég"
        assert result.wind_speed == 3.5
        assert result.humidity == 65
        assert result.location_name == "Budapest"
        assert result.error_message is None
    
    @patch.dict(os.environ, {"OPENWEATHER_API_KEY": ""})
    def test_get_weather_missing_api_key(self):
        """Test weather retrieval when API key is missing."""
        result = get_weather(latitude=47.4979, longitude=19.0402)
        
        assert result.success is False
        assert result.error_message is not None
        assert "API kulcs hiányzik" in result.error_message
    
    @patch.dict(os.environ, {"OPENWEATHER_API_KEY": "your_api_key_here"})
    def test_get_weather_invalid_api_key_placeholder(self):
        """Test weather retrieval when API key is placeholder."""
        result = get_weather(latitude=47.4979, longitude=19.0402)
        
        assert result.success is False
        assert result.error_message is not None
        assert "API kulcs hiányzik" in result.error_message
    
    @responses.activate
    @patch.dict(os.environ, {"OPENWEATHER_API_KEY": "test_api_key_12345"})
    def test_get_weather_invalid_api_key_response(self):
        """Test weather retrieval when API returns 401 (invalid key)."""
        responses.add(
            responses.GET,
            "https://api.openweathermap.org/data/2.5/weather",
            status=401
        )
        
        result = get_weather(latitude=47.4979, longitude=19.0402)
        
        assert result.success is False
        assert result.error_message is not None
        assert "Érvénytelen API kulcs" in result.error_message
    
    @responses.activate
    @patch.dict(os.environ, {"OPENWEATHER_API_KEY": "test_api_key_12345"})
    def test_get_weather_api_error(self):
        """Test weather retrieval when API returns error."""
        responses.add(
            responses.GET,
            "https://api.openweathermap.org/data/2.5/weather",
            status=500
        )
        
        result = get_weather(latitude=47.4979, longitude=19.0402)
        
        assert result.success is False
        assert result.error_message is not None
        assert "API hiba" in result.error_message
    
    @responses.activate
    @patch.dict(os.environ, {"OPENWEATHER_API_KEY": "test_api_key_12345"})
    def test_get_weather_timeout(self):
        """Test weather retrieval when request times out."""
        import requests
        responses.add(
            responses.GET,
            "https://api.openweathermap.org/data/2.5/weather",
            body=requests.exceptions.Timeout("Timeout")
        )
        
        result = get_weather(latitude=47.4979, longitude=19.0402)
        
        assert result.success is False
        assert result.error_message is not None
    
    @responses.activate
    @patch.dict(os.environ, {"OPENWEATHER_API_KEY": "test_api_key_12345"})
    def test_get_weather_with_units(self):
        """Test weather retrieval with different units."""
        responses.add(
            responses.GET,
            "https://api.openweathermap.org/data/2.5/weather",
            json={
                "name": "New York",
                "main": {"temp": 68.5, "humidity": 70},
                "weather": [{"description": "clear sky"}],
                "wind": {"speed": 5.2}
            },
            status=200
        )
        
        result = get_weather(
            latitude=40.7128,
            longitude=-74.0060,
            units="imperial",
            lang="en"
        )
        
        assert result.success is True
        assert result.temperature_c == 68.5
    
    def test_weather_input_model(self):
        """Test WeatherInput Pydantic model."""
        input_data = WeatherInput(latitude=47.4979, longitude=19.0402)
        
        assert input_data.latitude == 47.4979
        assert input_data.longitude == 19.0402
        assert input_data.units == "metric"
        assert input_data.lang == "hu"
    
    def test_weather_output_model(self):
        """Test WeatherOutput Pydantic model."""
        output_data = WeatherOutput(
            success=True,
            temperature_c=15.5,
            description="tiszta ég",
            wind_speed=3.5,
            humidity=65
        )
        
        assert output_data.success is True
        assert output_data.temperature_c == 15.5
        assert output_data.description == "tiszta ég"
