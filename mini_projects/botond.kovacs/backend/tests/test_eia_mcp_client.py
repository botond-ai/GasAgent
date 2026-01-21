import pytest
import asyncio
from infrastructure.tool_clients import MCPClient

@pytest.mark.asyncio
async def test_initialize_and_list_tools():
    client = MCPClient()
    await client.connect()
    tools = await client.list_tools()
    assert isinstance(tools, list)
    assert any("natural_gas" in (t.get("name","") + t.get("description","")) for t in tools)

@pytest.mark.asyncio
async def test_prices_and_storage_calls():
    client = MCPClient()
    await client.connect()
    prices = await client.call_tool("natural_gas.prices", {
        "series": "henry_hub_spot", "start": "2023-01-01", "frequency": "daily"
    })
    storage = await client.call_tool("natural_gas.storage", {
        "region": "lower48", "start": "2022-01-01", "frequency": "weekly"
    })
    assert "content" in prices or prices != {}
    assert "content" in storage or storage != {}
