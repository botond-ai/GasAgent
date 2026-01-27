from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests
from pydantic import BaseModel, Field

from app.openai_client import OpenAICompatClient


class ToolError(RuntimeError):
    def __init__(self, tool: str, error_type: str, message: str):
        super().__init__(message)
        self.tool = tool
        self.error_type = error_type
        self.message = message


class WeatherQuery(BaseModel):
    city: str = Field(min_length=2, max_length=120)
    timezone: str = Field(default="Europe/Budapest", max_length=80)


class WeatherResult(BaseModel):
    city: str
    temperature_c: float
    wind_kph: float
    weather_code: int
    observed_at: str
    source: str = "open-meteo"


@dataclass
class OpenMeteoClient:
    geo_url: str
    forecast_url: str
    timeout_s: float
    dev_mode: bool

    def get_current_weather(self, q: WeatherQuery, log) -> WeatherResult:
        # DEV_MODE: deterministic, no network
        if self.dev_mode:
            # stable fake based on city
            h = int(hashlib.blake2b(q.city.encode("utf-8"), digest_size=2).hexdigest(), 16)
            temp = 5.0 + (h % 200) / 10.0  # 5.0..24.9
            wind = (h % 80) / 2.0  # 0..39.5
            return WeatherResult(
                city=q.city,
                temperature_c=float(round(temp, 1)),
                wind_kph=float(round(wind, 1)),
                weather_code=int(h % 100),
                observed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )

        t0 = time.time()
        try:
            geo = requests.get(
                self.geo_url,
                params={"name": q.city, "count": 1, "language": "hu", "format": "json"},
                timeout=self.timeout_s,
            )
        except requests.Timeout as e:
            raise ToolError("open_meteo", "timeout", "Open-Meteo geocoding timeout") from e
        except requests.RequestException as e:
            raise ToolError("open_meteo", "network", "Open-Meteo geocoding network error") from e

        if geo.status_code != 200:
            raise ToolError("open_meteo", "http", f"Open-Meteo geocoding HTTP {geo.status_code}")

        data = geo.json() if geo.content else {}
        results = data.get("results") or []
        if not results:
            raise ToolError("open_meteo", "not_found", f"City not found: {q.city}")

        lat = results[0].get("latitude")
        lon = results[0].get("longitude")
        if lat is None or lon is None:
            raise ToolError("open_meteo", "invalid", "Open-Meteo geocoding missing lat/lon")

        try:
            fc = requests.get(
                self.forecast_url,
                params={"latitude": lat, "longitude": lon, "current_weather": True, "timezone": q.timezone},
                timeout=self.timeout_s,
            )
        except requests.Timeout as e:
            raise ToolError("open_meteo", "timeout", "Open-Meteo forecast timeout") from e
        except requests.RequestException as e:
            raise ToolError("open_meteo", "network", "Open-Meteo forecast network error") from e

        if fc.status_code != 200:
            raise ToolError("open_meteo", "http", f"Open-Meteo forecast HTTP {fc.status_code}")

        fcd = fc.json() if fc.content else {}
        cw = fcd.get("current_weather") or {}
        if not cw:
            raise ToolError("open_meteo", "invalid", "Open-Meteo forecast missing current_weather")

        dt_ms = int((time.time() - t0) * 1000)
        log.info("tool_open_meteo_ok", city=q.city, latency_ms=dt_ms)

        return WeatherResult(
            city=q.city,
            temperature_c=float(cw.get("temperature")),
            wind_kph=float(cw.get("windspeed")),
            weather_code=int(cw.get("weathercode")),
            observed_at=str(cw.get("time")),
        )


def summarize_weather(r: WeatherResult) -> str:
    return f"{r.city}: {r.temperature_c}°C, szél {r.wind_kph} km/h (code={r.weather_code}, at={r.observed_at})"

# ---- HF4 compatibility wrapper (used by agents/action.py) ----
def open_meteo_weather(query: str, cfg, log):
    """
    Minimal wrapper so HF4 action_node can call Open-Meteo without depending
    on the internal class API of this module.

    Returns: {"ok": bool, "summary": str, ...}
    """
    dev_mode = bool(getattr(cfg, "dev_mode", True))
    if dev_mode:
        city = "Budapest" if "budapest" in query.lower() else "Budapest"
        res = {"ok": True, "city": city, "summary": f"[DEV_MODE] Weather for {city}: 3°C, light wind"}
        try:
            log.info("tool_open_meteo_ok", city=city, run_id=getattr(cfg, "run_id", None))
        except Exception:
            pass
        return res

    # Non-dev: try real call using Open-Meteo (geocoding + forecast)
    import httpx

    ql = query.lower()
    city = "Budapest" if "budapest" in ql else "Budapest"

    timeout = float(getattr(cfg, "http_timeout_s", 10.0))
    with httpx.Client(timeout=timeout) as client:
        geo = client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "en", "format": "json"},
        )
        geo.raise_for_status()
        gj = geo.json()
        results = (gj or {}).get("results") or []
        if not results:
            return {"ok": False, "error": "geocode_not_found", "city": city}

        lat = results[0]["latitude"]
        lon = results[0]["longitude"]

        fc = client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,wind_speed_10m",
                "timezone": "auto",
            },
        )
        fc.raise_for_status()
        fj = fc.json()
        cur = (fj or {}).get("current") or {}
        temp = cur.get("temperature_2m")
        wind = cur.get("wind_speed_10m")

    summary = f"{city}: {temp}°C, wind {wind} km/h"
    try:
        log.info("tool_open_meteo_ok", city=city)
    except Exception:
        pass
    return {"ok": True, "city": city, "summary": summary}
