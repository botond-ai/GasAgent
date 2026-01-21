"""Test tool status detection."""
from src.agent.tools.timeparse import parse_time

# Simulate parse_time result
result = parse_time("milyen idő van most Pécsett?")
print(f"parse_time success: {result.success}")
print(f"Data: days_from_now={result.days_from_now}, date={result.date}")

# Now simulate the tool_status check
tool_status = {
    "parse_time": False,
    "geocode_city": False,
    "get_weather": False
}

# Simulate tool result
class ToolResult:
    def __init__(self, tool_name, success, data):
        self.tool_name = tool_name
        self.success = success
        self.data = data

tool_results = [
    ToolResult("parse_time", True, {
        "date": result.date,
        "days_from_now": result.days_from_now,
        "time_type": result.time_type,
        "description": result.description
    })
]

# Update status
for result in tool_results:
    if result.success:
        tool_status[result.tool_name] = True

print(f"\nTool status:")
for tool, status in tool_status.items():
    print(f"  {tool}: {status}")

# Format for LLM
import json
tool_results_str = ""
for result in tool_results:
    tool_results_str += f"\n{result.tool_name}: {'✓ SIKERES' if result.success else '✗ SIKERTELEN'}"
    if result.success and result.data:
        tool_results_str += f" (adat: {json.dumps(result.data, ensure_ascii=False)})"

tool_results_str = f"""TOOL STATUS:
- parse_time: {'✓ KÉSZ' if tool_status['parse_time'] else '✗ HIÁNYZIK'}
- geocode_city: {'✓ KÉSZ' if tool_status['geocode_city'] else '✗ HIÁNYZIK'}
- get_weather: {'✓ KÉSZ' if tool_status['get_weather'] else '✗ HIÁNYZIK'}

RÉSZLETEK:{tool_results_str}"""

print(f"\nFormatted for LLM:")
print(tool_results_str)
