"""Debug script to test Roglán weather query."""
import sys
import os
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from src.agent.weather_graph import get_weather_via_subgraph

# Test the weather subgraph directly
print("Testing: 'milyen lesz az időjárás holnap Roglán?'\n")

result = get_weather_via_subgraph("milyen lesz az időjárás holnap Roglán?")

print("Result:")
print(f"  Success: {result.success}")
if result.success:
    print(f"  Temperature: {result.temperature_c}°C")
    print(f"  Description: {result.description}")
    print(f"  Wind: {result.wind_speed} m/s")
    print(f"  Humidity: {result.humidity}%")
    print(f"  Location: {result.location_name}")
    print(f"  Date: {result.date}")
    print(f"  Is forecast: {result.is_forecast}")
else:
    print(f"  Error: {result.error_message}")
