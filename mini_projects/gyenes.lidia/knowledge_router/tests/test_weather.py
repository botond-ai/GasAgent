import pytest
from src.weather_tool import WeatherClient

def test_weather_client_structure():
    """Teszteli, hogy az osztály helyesen példányosítható-e."""
    client = WeatherClient()
    assert client.BASE_URL == "https://wttr.in"

def test_weather_api_call():
    """
    Integrációs teszt: Valódi hívást küld a wttr.in-re.
    Megjegyzés: CI/CD környezetben ezt 'mock'-olni illene, de a házihoz 
    a valódi hívás bizonyítja a legjobban a működést.
    """
    client = WeatherClient()
    result = client.get_weather("Budapest")
    
    # Ellenőrizzük a JSON válasz struktúráját
    assert result['success'] is True
    assert result['city'] == "Budapest"
    assert 'temp_C' in result
    assert 'humidity' in result