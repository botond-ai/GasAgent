"""
Simple HTTP wrapper for Filesystem MCP for testing.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
import uvicorn
import os
from pathlib import Path

app = FastAPI(title="MCP Filesystem Server")

# Allowed paths (relative to project root)
ALLOWED_DIRS = ["docs", "data"]


class ReadFileRequest(BaseModel):
    path: str


class WriteFileRequest(BaseModel):
    path: str
    content: str


class ListDirectoryRequest(BaseModel):
    path: str


class SearchRequest(BaseModel):
    path: str
    pattern: str


def is_path_allowed(path: str) -> bool:
    """Check if path is within allowed directories."""
    path_obj = Path(path)
    for allowed_dir in ALLOWED_DIRS:
        if str(path_obj).startswith(allowed_dir):
            return True
    return False


@app.get("/health")
async def health():
    return {"status": "ok", "service": "filesystem-mcp"}


@app.get("/tools")
async def list_tools():
    return {
        "tools": [
            {"name": "read_file", "description": "Read a file"},
            {"name": "write_file", "description": "Write to a file"},
            {"name": "list_directory", "description": "List directory contents"},
            {"name": "search", "description": "Search for files"},
        ]
    }


@app.post("/tools/read_file")
async def read_file(req: ReadFileRequest):
    if not is_path_allowed(req.path):
        raise HTTPException(status_code=403, detail="Path not allowed")
    
    try:
        with open(req.path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return {
            "success": True,
            "data": {"path": req.path, "content": content}
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/tools/write_file")
async def write_file(req: WriteFileRequest):
    if not is_path_allowed(req.path):
        raise HTTPException(status_code=403, detail="Path not allowed")
    
    try:
        os.makedirs(os.path.dirname(req.path), exist_ok=True)
        with open(req.path, 'w', encoding='utf-8') as f:
            f.write(req.content)
        
        return {
            "success": True,
            "message": f"Wrote to {req.path}",
            "data": {"path": req.path, "bytes": len(req.content)}
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/tools/list_directory")
async def list_directory(req: ListDirectoryRequest):
    if not is_path_allowed(req.path):
        raise HTTPException(status_code=403, detail="Path not allowed")
    
    try:
        path_obj = Path(req.path)
        if not path_obj.exists():
            raise HTTPException(status_code=404, detail="Directory not found")
        
        if not path_obj.is_dir():
            raise HTTPException(status_code=400, detail="Path is not a directory")
        
        items = []
        for item in path_obj.iterdir():
            items.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "path": str(item)
            })
        
        return {
            "success": True,
            "data": {"path": req.path, "items": items}
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/tools/search")
async def search_files(req: SearchRequest):
    if not is_path_allowed(req.path):
        raise HTTPException(status_code=403, detail="Path not allowed")
    
    try:
        path_obj = Path(req.path)
        matches = list(path_obj.glob(req.pattern))
        
        results = [
            {
                "name": item.name,
                "path": str(item),
                "type": "directory" if item.is_dir() else "file"
            }
            for item in matches
        ]
        
        return {
            "success": True,
            "data": {"pattern": req.pattern, "results": results}
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "3102"))
    uvicorn.run(app, host="0.0.0.0", port=port)
