"""
Simple HTTP wrapper for Brave Search MCP for testing.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import uvicorn
import os
import httpx

app = FastAPI(title="MCP Brave Search Server")


class SearchRequest(BaseModel):
    query: str
    count: int = 5


class LocalSearchRequest(BaseModel):
    query: str
    count: int = 3


@app.get("/health")
async def health():
    return {"status": "ok", "service": "brave-search-mcp"}


@app.get("/tools")
async def list_tools():
    return {
        "tools": [
            {"name": "search", "description": "Web search"},
            {"name": "local_search", "description": "Local places search"},
        ]
    }


@app.post("/tools/search")
async def search(req: SearchRequest):
    api_key = os.getenv("BRAVE_API_KEY")
    
    if not api_key:
        return {
            "success": False,
            "error": "BRAVE_API_KEY not configured"
        }
    
    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": api_key
            }
            params = {
                "q": req.query,
                "count": req.count
            }
            
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers=headers,
                params=params,
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                if "web" in data and "results" in data["web"]:
                    for item in data["web"]["results"][:req.count]:
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "description": item.get("description", "")
                        })
                
                return {
                    "success": True,
                    "data": {"results": results, "query": req.query}
                }
            else:
                return {
                    "success": False,
                    "error": f"Brave API error: {response.status_code}"
                }
                
    except Exception as e:
        return {
            "success": False,
            "error": f"Search failed: {str(e)}"
        }


@app.post("/tools/local_search")
async def local_search(req: LocalSearchRequest):
    # For testing, return mock data
    return {
        "success": True,
        "data": {
            "results": [
                {
                    "title": f"Local result for: {req.query}",
                    "address": "Test Address",
                    "rating": 4.5
                }
            ]
        }
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", "3101"))
    uvicorn.run(app, host="0.0.0.0", port=port)
