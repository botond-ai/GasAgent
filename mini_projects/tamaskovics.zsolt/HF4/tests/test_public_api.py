from unittest.mock import Mock

import requests

from tools.public_api import OpenMeteoClient, WeatherQuery


def test_open_meteo_dev_mode_is_deterministic():
    client = OpenMeteoClient(
        geo_url="https://example.com/geo",
        forecast_url="https://example.com/fc",
        timeout_s=1.0,
        dev_mode=True,
    )
    log = Mock()
    r1 = client.get_current_weather(WeatherQuery(city="Budapest", timezone="Europe/Budapest"), log)
    r2 = client.get_current_weather(WeatherQuery(city="Budapest", timezone="Europe/Budapest"), log)
    assert r1.temperature_c == r2.temperature_c
    assert r1.wind_kph == r2.wind_kph
    assert r1.city == "Budapest"


def test_open_meteo_live_mode_mocks_http(monkeypatch):
    # no real network: mock requests.get
    def fake_get(url, params=None, timeout=None):
        resp = Mock()
        resp.status_code = 200
        if "geocoding" in url or "search" in url:
            resp.content = b"1"
            resp.json.return_value = {"results": [{"latitude": 47.4979, "longitude": 19.0402}]}
        else:
            resp.content = b"1"
            resp.json.return_value = {"current_weather": {"temperature": 1.2, "windspeed": 3.4, "weathercode": 2, "time": "2026-01-24T10:00"}}
        return resp

    monkeypatch.setattr(requests, "get", fake_get)

    client = OpenMeteoClient(
        geo_url="https://geocoding-api.open-meteo.com/v1/search",
        forecast_url="https://api.open-meteo.com/v1/forecast",
        timeout_s=1.0,
        dev_mode=False,
    )
    log = Mock()
    r = client.get_current_weather(WeatherQuery(city="Budapest", timezone="Europe/Budapest"), log)
    assert r.temperature_c == 1.2
    assert r.wind_kph == 3.4
    assert r.weather_code == 2
