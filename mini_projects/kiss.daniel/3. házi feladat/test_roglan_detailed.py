"""Detailed debug for Roglán weather query."""
import sys
import os
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from src.agent.tools.geocode import geocode_city

# Test geocoding for Roglán
print("Testing geocoding for 'Roglán':\n")

result = geocode_city(city="Roglán", language="hu")

print(f"Success: {result.success}")
if result.success:
    print(f"Name: {result.name}")
    print(f"Latitude: {result.latitude}")
    print(f"Longitude: {result.longitude}")
    print(f"Country: {result.country}")
else:
    print(f"Error: {result.error_message}")

# Also test the LLM parsing
print("\n" + "="*60)
print("Testing LLM city extraction:\n")

from src.agent.llm import GroqClient

llm = GroqClient()

prompt = """A felhasználó ezt kérdezte: "milyen lesz az időjárás holnap Roglán?"

Válaszolj KIZÁRÓLAG JSON formátumban, SEMMI MÁS SZÖVEGGEL:
{
  "city": "a város neve, ha megtalálható, különben null"
}"""

response = llm.invoke_json("You must respond with valid JSON only.", prompt)
print(f"LLM response: {response}")
