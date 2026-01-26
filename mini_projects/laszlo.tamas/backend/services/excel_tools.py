"""
Excel tools for LangGraph workflow.

Provides LangChain-compatible tool wrappers for Excel operations through MCP protocol.
Following the same BaseTool pattern as CurrencyTool for async compatibility.
"""
import logging
import asyncio
import json
from typing import List, Optional, Type, Any
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from infrastructure.tool_clients import ExcelMCPClient

logger = logging.getLogger(__name__)


# ===== INPUT SCHEMAS =====

class CreateWorkbookInput(BaseModel):
    """Input schema for CreateExcelWorkbookTool."""
    filepath: str = Field(..., description="Path where to create the workbook (e.g., 'report.xlsx')")


class WriteDataInput(BaseModel):
    """Input schema for WriteExcelDataTool."""
    filepath: str = Field(..., description="Path to Excel file")
    sheet_name: str = Field(..., description="Name of the worksheet")
    data: List[List] = Field(..., description="List of lists (rows) containing data to write")
    start_cell: str = Field(default="A1", description="Starting cell (default: A1)")


class ReadDataInput(BaseModel):
    """Input schema for ReadExcelDataTool."""
    filepath: str = Field(..., description="Path to Excel file")
    sheet_name: str = Field(..., description="Name of the worksheet")
    start_cell: str = Field(default="A1", description="Starting cell (default: A1)")
    end_cell: Optional[str] = Field(None, description="Optional ending cell")


class CreateChartInput(BaseModel):
    """Input schema for CreateExcelChartTool."""
    filepath: str = Field(..., description="Path to Excel file")
    sheet_name: str = Field(..., description="Name of the worksheet")
    data_range: str = Field(..., description="Range containing chart data (e.g., 'A1:C10')")
    chart_type: str = Field(..., description="Type of chart: line, bar, pie, scatter, or area")
    target_cell: str = Field(..., description="Cell where to place chart (e.g., 'E2')")
    title: str = Field(default="", description="Optional chart title")


class FormatRangeInput(BaseModel):
    """Input schema for FormatExcelRangeTool."""
    filepath: str = Field(..., description="Path to Excel file")
    sheet_name: str = Field(..., description="Name of the worksheet")
    start_cell: str = Field(..., description="Starting cell of range")
    end_cell: Optional[str] = Field(None, description="Optional ending cell")
    bold: bool = Field(default=False, description="Apply bold formatting")
    italic: bool = Field(default=False, description="Apply italic formatting")
    font_size: Optional[int] = Field(None, description="Font size (e.g., 12, 14)")
    bg_color: Optional[str] = Field(None, description="Background color (e.g., 'FFFF00' for yellow)")


class CreateWorksheetInput(BaseModel):
    """Input schema for CreateExcelWorksheetTool."""
    filepath: str = Field(..., description="Path to Excel file")
    sheet_name: str = Field(..., description="Name for the new worksheet")


class GetMetadataInput(BaseModel):
    """Input schema for GetExcelMetadataTool."""
    filepath: str = Field(..., description="Path to Excel file")
    include_ranges: bool = Field(default=False, description="Whether to include range information")


# ===== TOOL IMPLEMENTATIONS (BaseTool pattern) =====

def _get_download_url(filepath: str) -> str:
    """Generate download URL for an Excel file."""
    # Extract just the filename from the path
    filename = filepath.split("/")[-1].split("\\")[-1]
    return f"/api/excel/{filename}"


class CreateExcelWorkbookTool(BaseTool):
    """Create a new Excel workbook."""
    name: str = "create_excel_workbook"
    description: str = (
        "Create a new Excel workbook. Use this when the user wants to create a new Excel file. "
        "The file will be created on the server. Returns a download URL for the created file."
    )
    args_schema: Type[BaseModel] = CreateWorkbookInput
    excel_client: Any = None  # ExcelMCPClient instance (dependency injection)
    
    def _run(self, filepath: str) -> str:
        """Sync wrapper (LangChain compatibility)."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            client = self.excel_client or ExcelMCPClient()
            result = loop.run_until_complete(client.create_workbook(filepath))
        finally:
            loop.close()
        
        if result["success"]:
            download_url = _get_download_url(filepath)
            logger.info(f"✅ Excel workbook created: {filepath}, download: {download_url}")
            return f"✓ Created workbook: {filepath}\n📥 Download: {download_url}"
        else:
            logger.error(f"✗ Failed to create workbook: {result.get('error')}")
            return f"✗ Failed to create workbook: {result.get('error', 'Unknown error')}"
    
    async def _arun(self, filepath: str) -> str:
        """Async version."""
        client = self.excel_client or ExcelMCPClient()
        result = await client.create_workbook(filepath)
        
        if result["success"]:
            download_url = _get_download_url(filepath)
            logger.info(f"✅ Excel workbook created: {filepath}, download: {download_url}")
            return f"✓ Created workbook: {filepath}\n📥 Download: {download_url}"
        else:
            logger.error(f"✗ Failed to create workbook: {result.get('error')}")
            return f"✗ Failed to create workbook: {result.get('error', 'Unknown error')}"


class WriteExcelDataTool(BaseTool):
    """Write data to Excel worksheet."""
    name: str = "write_excel_data"
    description: str = (
        "Write data to Excel worksheet. Data should be provided as a list of lists where each inner list represents a row. "
        "Example: [[\"Name\", \"Age\"], [\"Alice\", 30], [\"Bob\", 25]]. Returns a download URL for the file."
    )
    args_schema: Type[BaseModel] = WriteDataInput
    excel_client: Any = None
    
    def _run(self, filepath: str, sheet_name: str, data: List[List], start_cell: str = "A1") -> str:
        """Sync wrapper."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            client = self.excel_client or ExcelMCPClient()
            result = loop.run_until_complete(client.write_data(filepath, sheet_name, data, start_cell))
        finally:
            loop.close()
        
        if result["success"]:
            download_url = _get_download_url(filepath)
            logger.info(f"✅ Data written to {sheet_name}!{start_cell} in {filepath}")
            return f"✓ Data written to {sheet_name}!{start_cell} in {filepath}\n📥 Download: {download_url}"
        else:
            logger.error(f"✗ Failed to write data: {result.get('error')}")
            return f"✗ Failed to write data: {result.get('error', 'Unknown error')}"
    
    async def _arun(self, filepath: str, sheet_name: str, data: List[List], start_cell: str = "A1") -> str:
        """Async version."""
        client = self.excel_client or ExcelMCPClient()
        result = await client.write_data(filepath, sheet_name, data, start_cell)
        
        if result["success"]:
            download_url = _get_download_url(filepath)
            logger.info(f"✅ Data written to {sheet_name}!{start_cell} in {filepath}")
            return f"✓ Data written to {sheet_name}!{start_cell} in {filepath}\n📥 Download: {download_url}"
        else:
            logger.error(f"✗ Failed to write data: {result.get('error')}")
            return f"✗ Failed to write data: {result.get('error', 'Unknown error')}"


class ReadExcelDataTool(BaseTool):
    """Read data from Excel worksheet."""
    name: str = "read_excel_data"
    description: str = "Read data from Excel worksheet. Returns the cell data as a JSON string."
    args_schema: Type[BaseModel] = ReadDataInput
    excel_client: Any = None
    
    def _run(self, filepath: str, sheet_name: str, start_cell: str = "A1", end_cell: Optional[str] = None) -> str:
        """Sync wrapper."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            client = self.excel_client or ExcelMCPClient()
            result = loop.run_until_complete(client.read_data(filepath, sheet_name, start_cell, end_cell))
        finally:
            loop.close()
        
        if result["success"]:
            logger.info(f"✅ Data read from {sheet_name} in {filepath}")
            return json.dumps(result["data"], indent=2, ensure_ascii=False)
        else:
            logger.error(f"✗ Failed to read data: {result.get('error')}")
            return f"✗ Failed to read data: {result.get('error', 'Unknown error')}"
    
    async def _arun(self, filepath: str, sheet_name: str, start_cell: str = "A1", end_cell: Optional[str] = None) -> str:
        """Async version."""
        client = self.excel_client or ExcelMCPClient()
        result = await client.read_data(filepath, sheet_name, start_cell, end_cell)
        
        if result["success"]:
            logger.info(f"✅ Data read from {sheet_name} in {filepath}")
            return json.dumps(result["data"], indent=2, ensure_ascii=False)
        else:
            logger.error(f"✗ Failed to read data: {result.get('error')}")
            return f"✗ Failed to read data: {result.get('error', 'Unknown error')}"


class CreateExcelChartTool(BaseTool):
    """Create a chart in Excel worksheet."""
    name: str = "create_excel_chart"
    description: str = (
        "Create a chart in Excel worksheet. Supported chart types: line, bar, pie, scatter, area. "
        "Use this to visualize data with charts."
    )
    args_schema: Type[BaseModel] = CreateChartInput
    excel_client: Any = None
    
    def _run(self, filepath: str, sheet_name: str, data_range: str, chart_type: str, target_cell: str, title: str = "") -> str:
        """Sync wrapper."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            client = self.excel_client or ExcelMCPClient()
            result = loop.run_until_complete(
                client.create_chart(filepath, sheet_name, data_range, chart_type, target_cell, title)
            )
        finally:
            loop.close()
        
        if result["success"]:
            logger.info(f"✅ Created {chart_type} chart in {sheet_name}!{target_cell}")
            return f"✓ Created {chart_type} chart in {sheet_name}!{target_cell}"
        else:
            logger.error(f"✗ Failed to create chart: {result.get('error')}")
            return f"✗ Failed to create chart: {result.get('error', 'Unknown error')}"
    
    async def _arun(self, filepath: str, sheet_name: str, data_range: str, chart_type: str, target_cell: str, title: str = "") -> str:
        """Async version."""
        client = self.excel_client or ExcelMCPClient()
        result = await client.create_chart(filepath, sheet_name, data_range, chart_type, target_cell, title)
        
        if result["success"]:
            logger.info(f"✅ Created {chart_type} chart in {sheet_name}!{target_cell}")
            return f"✓ Created {chart_type} chart in {sheet_name}!{target_cell}"
        else:
            logger.error(f"✗ Failed to create chart: {result.get('error')}")
            return f"✗ Failed to create chart: {result.get('error', 'Unknown error')}"


class FormatExcelRangeTool(BaseTool):
    """Apply formatting to Excel cells."""
    name: str = "format_excel_range"
    description: str = "Apply formatting to a range of cells in Excel (bold, italic, colors, font size)."
    args_schema: Type[BaseModel] = FormatRangeInput
    excel_client: Any = None
    
    def _run(
        self, filepath: str, sheet_name: str, start_cell: str, 
        end_cell: Optional[str] = None, bold: bool = False, italic: bool = False,
        font_size: Optional[int] = None, bg_color: Optional[str] = None
    ) -> str:
        """Sync wrapper."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            client = self.excel_client or ExcelMCPClient()
            result = loop.run_until_complete(
                client.format_range(filepath, sheet_name, start_cell, end_cell, bold, italic, font_size, bg_color)
            )
        finally:
            loop.close()
        
        if result["success"]:
            logger.info(f"✅ Formatted {sheet_name}!{start_cell}")
            return f"✓ Formatted {sheet_name}!{start_cell}"
        else:
            logger.error(f"✗ Failed to format range: {result.get('error')}")
            return f"✗ Failed to format range: {result.get('error', 'Unknown error')}"
    
    async def _arun(
        self, filepath: str, sheet_name: str, start_cell: str,
        end_cell: Optional[str] = None, bold: bool = False, italic: bool = False,
        font_size: Optional[int] = None, bg_color: Optional[str] = None
    ) -> str:
        """Async version."""
        client = self.excel_client or ExcelMCPClient()
        result = await client.format_range(filepath, sheet_name, start_cell, end_cell, bold, italic, font_size, bg_color)
        
        if result["success"]:
            logger.info(f"✅ Formatted {sheet_name}!{start_cell}")
            return f"✓ Formatted {sheet_name}!{start_cell}"
        else:
            logger.error(f"✗ Failed to format range: {result.get('error')}")
            return f"✗ Failed to format range: {result.get('error', 'Unknown error')}"


class CreateExcelWorksheetTool(BaseTool):
    """Create a new worksheet in Excel workbook."""
    name: str = "create_excel_worksheet"
    description: str = "Create a new worksheet in an existing Excel workbook."
    args_schema: Type[BaseModel] = CreateWorksheetInput
    excel_client: Any = None
    
    def _run(self, filepath: str, sheet_name: str) -> str:
        """Sync wrapper."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            client = self.excel_client or ExcelMCPClient()
            result = loop.run_until_complete(client.create_worksheet(filepath, sheet_name))
        finally:
            loop.close()
        
        if result["success"]:
            logger.info(f"✅ Created worksheet: {sheet_name} in {filepath}")
            return f"✓ Created worksheet: {sheet_name} in {filepath}"
        else:
            logger.error(f"✗ Failed to create worksheet: {result.get('error')}")
            return f"✗ Failed to create worksheet: {result.get('error', 'Unknown error')}"
    
    async def _arun(self, filepath: str, sheet_name: str) -> str:
        """Async version."""
        client = self.excel_client or ExcelMCPClient()
        result = await client.create_worksheet(filepath, sheet_name)
        
        if result["success"]:
            logger.info(f"✅ Created worksheet: {sheet_name} in {filepath}")
            return f"✓ Created worksheet: {sheet_name} in {filepath}"
        else:
            logger.error(f"✗ Failed to create worksheet: {result.get('error')}")
            return f"✗ Failed to create worksheet: {result.get('error', 'Unknown error')}"


class GetExcelMetadataTool(BaseTool):
    """Get Excel workbook metadata."""
    name: str = "get_excel_metadata"
    description: str = (
        "Get metadata about an Excel workbook (sheets, ranges, etc.). "
        "Use this to inspect the structure of an Excel file before reading/writing data."
    )
    args_schema: Type[BaseModel] = GetMetadataInput
    excel_client: Any = None
    
    def _run(self, filepath: str, include_ranges: bool = False) -> str:
        """Sync wrapper."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            client = self.excel_client or ExcelMCPClient()
            result = loop.run_until_complete(client.get_workbook_metadata(filepath, include_ranges))
        finally:
            loop.close()
        
        if result["success"]:
            logger.info(f"✅ Retrieved metadata for {filepath}")
            return json.dumps(result["data"], indent=2, ensure_ascii=False)
        else:
            logger.error(f"✗ Failed to get metadata: {result.get('error')}")
            return f"✗ Failed to get metadata: {result.get('error', 'Unknown error')}"
    
    async def _arun(self, filepath: str, include_ranges: bool = False) -> str:
        """Async version."""
        client = self.excel_client or ExcelMCPClient()
        result = await client.get_workbook_metadata(filepath, include_ranges)
        
        if result["success"]:
            logger.info(f"✅ Retrieved metadata for {filepath}")
            return json.dumps(result["data"], indent=2, ensure_ascii=False)
        else:
            logger.error(f"✗ Failed to get metadata: {result.get('error')}")
            return f"✗ Failed to get metadata: {result.get('error', 'Unknown error')}"


# ===== TOOL INSTANCES =====

# Create tool instances (can be instantiated with dependency injection if needed)
create_excel_workbook = CreateExcelWorkbookTool()
write_excel_data = WriteExcelDataTool()
read_excel_data = ReadExcelDataTool()
create_excel_chart = CreateExcelChartTool()
format_excel_range = FormatExcelRangeTool()
create_excel_worksheet = CreateExcelWorksheetTool()
get_excel_metadata = GetExcelMetadataTool()


# Export all Excel tools as a list for easy integration
EXCEL_TOOLS = [
    create_excel_workbook,
    write_excel_data,
    read_excel_data,
    create_excel_chart,
    format_excel_range,
    create_excel_worksheet,
    get_excel_metadata
]
