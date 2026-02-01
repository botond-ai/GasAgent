"""
Simple HTTP wrapper for MCP servers for testing.
This provides HTTP endpoints that the MCP client expects.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uvicorn
import os

app = FastAPI(title="MCP Memory Server")

# In-memory storage for testing
memory_store: Dict[str, Dict[str, str]] = {}


class StoreRequest(BaseModel):
    conversation_id: str
    key: str
    value: str


class RetrieveRequest(BaseModel):
    conversation_id: str
    key: str


class ListRequest(BaseModel):
    conversation_id: str


class DeleteRequest(BaseModel):
    conversation_id: str
    key: str


@app.get("/health")
async def health():
    return {"status": "ok", "service": "memory-mcp"}


@app.get("/tools")
async def list_tools():
    return {
        "tools": [
            {"name": "store", "description": "Store a memory"},
            {"name": "retrieve", "description": "Retrieve a memory"},
            {"name": "list", "description": "List all memories"},
            {"name": "delete", "description": "Delete a memory"},
        ]
    }


@app.post("/tools/store")
async def store(req: StoreRequest):
    if req.conversation_id not in memory_store:
        memory_store[req.conversation_id] = {}
    
    memory_store[req.conversation_id][req.key] = req.value
    
    return {
        "success": True,
        "message": f"Stored {req.key} for conversation {req.conversation_id}",
        "data": {"key": req.key, "value": req.value}
    }


@app.post("/tools/retrieve")
async def retrieve(req: RetrieveRequest):
    if req.conversation_id not in memory_store:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if req.key not in memory_store[req.conversation_id]:
        raise HTTPException(status_code=404, detail="Key not found")
    
    value = memory_store[req.conversation_id][req.key]
    
    return {
        "success": True,
        "data": {"key": req.key, "value": value}
    }


@app.post("/tools/list")
async def list_memories(req: ListRequest):
    if req.conversation_id not in memory_store:
        return {"success": True, "data": {"memories": []}}
    
    memories = [
        {"key": k, "value": v}
        for k, v in memory_store[req.conversation_id].items()
    ]
    
    return {"success": True, "data": {"memories": memories}}


@app.post("/tools/delete")
async def delete(req: DeleteRequest):
    if req.conversation_id not in memory_store:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if req.key not in memory_store[req.conversation_id]:
        raise HTTPException(status_code=404, detail="Key not found")
    
    del memory_store[req.conversation_id][req.key]
    
    return {"success": True, "message": f"Deleted {req.key}"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "3100"))
    uvicorn.run(app, host="0.0.0.0", port=port)
