#!/usr/bin/env python3
"""
EIA MCP Server - JSON-RPC 2.0 over stdio
Provides tools for querying U.S. Energy Information Administration data
"""
import sys
import json
import os
import asyncio
from typing import Any, Dict
import requests


class EIAMCPServer:
    def __init__(self):
        self.api_key = os.environ.get("EIA_API_KEY", "")
        self.base_url = "https://api.eia.gov/v2"
        
    def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request"""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "eia-mcp-server",
                "version": "0.1.0"
            }
        }
    
    def handle_list_tools(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List available EIA tools"""
        return {
            "tools": [
                {
                    "name": "natural_gas.prices",
                    "description": "Query natural gas prices from EIA API",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "series": {"type": "string", "description": "Price series (e.g., henry_hub_spot)"},
                            "start": {"type": "string", "description": "Start date YYYY-MM-DD"},
                            "end": {"type": "string", "description": "End date YYYY-MM-DD"},
                            "frequency": {"type": "string", "description": "Data frequency (daily, weekly, monthly)"}
                        },
                        "required": ["series"]
                    }
                },
                {
                    "name": "natural_gas.storage",
                    "description": "Query natural gas storage data from EIA API",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "region": {"type": "string", "description": "Region (e.g., lower48)"},
                            "start": {"type": "string", "description": "Start date YYYY-MM-DD"},
                            "end": {"type": "string", "description": "End date YYYY-MM-DD"},
                            "frequency": {"type": "string", "description": "Data frequency (daily, weekly, monthly)"}
                        },
                        "required": ["region"]
                    }
                },
                {
                    "name": "natural_gas.production",
                    "description": "Query natural gas production data from EIA API",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "region": {"type": "string", "description": "Region"},
                            "start": {"type": "string", "description": "Start date YYYY-MM-DD"},
                            "end": {"type": "string", "description": "End date YYYY-MM-DD"}
                        }
                    }
                }
            ]
        }
    
    def handle_call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool call"""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        
        try:
            if tool_name == "natural_gas.prices":
                result = self._query_prices(arguments)
            elif tool_name == "natural_gas.storage":
                result = self._query_storage(arguments)
            elif tool_name == "natural_gas.production":
                result = self._query_production(arguments)
            else:
                return {"error": f"Unknown tool: {tool_name}"}
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, indent=2)
                    }
                ]
            }
        except Exception as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: {str(e)}"
                    }
                ],
                "isError": True
            }
    
    def _query_prices(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Query natural gas prices from EIA API"""
        api_key = self.api_key or os.environ.get("EIA_API_KEY", "")
        start = args.get("start")
        end = args.get("end")
        url = "https://api.eia.gov/v2/seriesid/NG.RNGWHHD.D"
        params = {
            "api_key": api_key
        }
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            # Szűrés dátum szerint
            if start or end:
                filtered = []
                for row in data.get("response", {}).get("data", []):
                    date = row.get("period") or row.get("date")
                    if date:
                        if start and date < start:
                            continue
                        if end and date > end:
                            continue
                        filtered.append(row)
                data["response"]["data"] = filtered
            return data
        except Exception as e:
            return {"error": str(e)}
    
    def _query_storage(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Query natural gas storage"""
        # Mock implementation
        return {
            "region": args.get("region"),
            "data": [
                {"date": "2022-01-01", "storage": 2500},
                {"date": "2022-01-08", "storage": 2450}
            ]
        }
    
    def _query_production(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Query natural gas production"""
        # Mock implementation
        return {
            "region": args.get("region"),
            "data": [
                {"date": "2023-01-01", "production": 95.5}
            ]
        }
    
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming JSON-RPC request"""
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")
        
        if method == "initialize":
            result = self.handle_initialize(params)
        elif method == "initialized":
            # This is a notification, no response needed but we'll return success
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {}
            }
        elif method == "tools/list":
            result = self.handle_list_tools(params)
        elif method == "tools/call":
            result = self.handle_call_tool(params)
        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            }
        
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result
        }


async def main():
    """Main server loop - read from stdin, write to stdout"""
    server = EIAMCPServer()
    
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    
    while True:
        try:
            line = await reader.readline()
            if not line:
                break
                
            request = json.loads(line.decode('utf-8'))
            response = server.handle_request(request)
            
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
            
        except json.JSONDecodeError:
            continue
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(e)}
            }
            sys.stdout.write(json.dumps(error_response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())
