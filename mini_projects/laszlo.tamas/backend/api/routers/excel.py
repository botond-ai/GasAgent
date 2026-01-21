"""
Excel File Download Endpoints

Provides download endpoints for Excel files created by the Excel MCP tools.
Files are stored in the shared excel_files volume.
"""

import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Excel files directory (mounted volume shared with Excel MCP server)
EXCEL_FILES_DIR = Path("/app/data/excel_files")


@router.get("/{filename}")
async def download_excel_file(filename: str):
    """
    Download an Excel file by filename.
    
    Args:
        filename: Name of the Excel file (e.g., 'report.xlsx')
    
    Returns:
        FileResponse with the Excel file
    
    Raises:
        404: File not found
        400: Invalid filename (path traversal attempt)
    """
    # Security: prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        logger.warning(f"Path traversal attempt blocked: {filename}")
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # Only allow .xlsx files
    if not filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")
    
    filepath = EXCEL_FILES_DIR / filename
    
    if not filepath.exists():
        logger.warning(f"Excel file not found: {filepath}")
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    
    logger.info(f"Serving Excel file: {filename}")
    
    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@router.get("")
async def list_excel_files():
    """
    List all available Excel files.
    
    Returns:
        List of Excel filenames with download URLs
    """
    if not EXCEL_FILES_DIR.exists():
        return {"files": [], "count": 0}
    
    files = []
    for f in EXCEL_FILES_DIR.glob("*.xlsx"):
        files.append({
            "filename": f.name,
            "download_url": f"/api/excel/{f.name}",
            "size_bytes": f.stat().st_size
        })
    
    logger.info(f"Listed {len(files)} Excel files")
    
    return {"files": files, "count": len(files)}
