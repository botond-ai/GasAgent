"""Unit tests for geocode tool."""
import pytest
import responses
from src.agent.tools.geocode import geocode_city, GeocodeInput, GeocodeOutput


class TestGeocodeCity:
    """Test cases for geocode_city function."""
    
    @responses.activate
    def test_geocode_success(self):
        """Test successful geocoding of a city."""
        # Mock the API response
        responses.add(
            responses.GET,
            "https://geocoding-api.open-meteo.com/v1/search",
            json={
                "results": [
                    {
                        "name": "Budapest",
                        "country": "Hungary",
                        "latitude": 47.4979,
                        "longitude": 19.0402,
                        "admin1": "Budapest",
                        "timezone": "Europe/Budapest"
                    }
                ]
            },
            status=200
        )
        
        result = geocode_city(city="Budapest", country="HU")
        
        assert result.success is True
        assert result.name == "Budapest"
        assert result.country == "Hungary"
        assert result.latitude == 47.4979
        assert result.longitude == 19.0402
        assert result.error_message is None
    
    @responses.activate
    def test_geocode_city_not_found(self):
        """Test geocoding when city is not found."""
        responses.add(
            responses.GET,
            "https://geocoding-api.open-meteo.com/v1/search",
            json={"results": []},
            status=200
        )
        
        result = geocode_city(city="NonExistentCity123456")
        
        assert result.success is False
        assert result.error_message is not None
        assert "Nem található város" in result.error_message
    
    @responses.activate
    def test_geocode_api_error(self):
        """Test geocoding when API returns error."""
        responses.add(
            responses.GET,
            "https://geocoding-api.open-meteo.com/v1/search",
            status=500
        )
        
        result = geocode_city(city="Budapest")
        
        assert result.success is False
        assert result.error_message is not None
        assert "API hiba" in result.error_message
    
    @responses.activate
    def test_geocode_timeout(self):
        """Test geocoding when request times out."""
        import requests
        responses.add(
            responses.GET,
            "https://geocoding-api.open-meteo.com/v1/search",
            body=requests.exceptions.Timeout("Timeout")
        )
        
        result = geocode_city(city="Budapest")
        
        assert result.success is False
        assert result.error_message is not None
    
    @responses.activate
    def test_geocode_with_country_filter(self):
        """Test geocoding with country filter."""
        responses.add(
            responses.GET,
            "https://geocoding-api.open-meteo.com/v1/search",
            json={
                "results": [
                    {
                        "name": "Paris",
                        "country": "France",
                        "country_code": "FR",
                        "latitude": 48.8566,
                        "longitude": 2.3522,
                        "admin1": "Île-de-France",
                        "timezone": "Europe/Paris"
                    },
                    {
                        "name": "Paris",
                        "country": "United States",
                        "country_code": "US",
                        "latitude": 33.6609,
                        "longitude": -95.5555,
                        "admin1": "Texas",
                        "timezone": "America/Chicago"
                    }
                ]
            },
            status=200
        )
        
        result = geocode_city(city="Paris", country="FR")
        
        assert result.success is True
        assert result.country == "France"
        assert result.latitude == 48.8566
    
    def test_geocode_input_model(self):
        """Test GeocodeInput Pydantic model."""
        input_data = GeocodeInput(city="Budapest", country="HU")
        
        assert input_data.city == "Budapest"
        assert input_data.country == "HU"
        assert input_data.count == 1
        assert input_data.language == "en"
    
    def test_geocode_output_model(self):
        """Test GeocodeOutput Pydantic model."""
        output_data = GeocodeOutput(
            success=True,
            name="Budapest",
            latitude=47.4979,
            longitude=19.0402
        )
        
        assert output_data.success is True
        assert output_data.name == "Budapest"
        assert output_data.latitude == 47.4979
