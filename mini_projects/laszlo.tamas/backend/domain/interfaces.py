"""
Domain interfaces - Abstractions for external services.

Following SOLID principles:
- Dependency Inversion Principle: Depend on abstractions, not concrete implementations
- Interface Segregation Principle: Specific interfaces for different concerns
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class IMCPClient(ABC):
    """Base interface for MCP (Model Context Protocol) client.
    
    MCP is a JSON-RPC 2.0 based protocol for AI agents to interact with
    external tools and data sources.
    """
    
    @abstractmethod
    async def connect(self, server_url: str) -> None:
        """Connect to MCP server and initialize session.
        
        Args:
            server_url: URL of the MCP server (HTTP/HTTPS endpoint)
        
        Raises:
            ConnectionError: If connection fails
        """
        pass
    
    @abstractmethod
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools from the MCP server.
        
        Returns:
            List of tool definitions with name, description, and input schema
        
        Raises:
            ConnectionError: If not connected to server
        """
        pass
    
    @abstractmethod
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP server.
        
        Args:
            name: Tool name to execute
            arguments: Tool arguments as key-value pairs
        
        Returns:
            Tool execution result
        
        Raises:
            ConnectionError: If not connected to server
            ValueError: If tool not found or invalid arguments
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from MCP server and clean up resources."""
        pass


class IExcelMCPClient(ABC):
    """Interface for Excel MCP client operations.
    
    Provides high-level Excel manipulation through MCP protocol.
    All file paths are relative to the server's EXCEL_FILES_PATH.
    """
    
    @abstractmethod
    async def create_workbook(self, filepath: str) -> Dict[str, Any]:
        """Create a new Excel workbook.
        
        Args:
            filepath: Path where to create workbook (e.g., 'report.xlsx')
        
        Returns:
            Dictionary with success status, data, and system_message
        """
        pass
    
    @abstractmethod
    async def write_data(
        self, 
        filepath: str, 
        sheet_name: str, 
        data: List[List], 
        start_cell: str = "A1"
    ) -> Dict[str, Any]:
        """Write data to Excel worksheet.
        
        Args:
            filepath: Path to Excel file
            sheet_name: Name of the worksheet
            data: List of lists (rows) containing data to write
            start_cell: Starting cell (default: "A1")
        
        Returns:
            Dictionary with success status, data, and system_message
        """
        pass
    
    @abstractmethod
    async def read_data(
        self, 
        filepath: str, 
        sheet_name: str, 
        start_cell: str = "A1",
        end_cell: Optional[str] = None
    ) -> Dict[str, Any]:
        """Read data from Excel worksheet.
        
        Args:
            filepath: Path to Excel file
            sheet_name: Name of the worksheet
            start_cell: Starting cell (default: "A1")
            end_cell: Optional ending cell
        
        Returns:
            Dictionary with success status, cell data, and system_message
        """
        pass
    
    @abstractmethod
    async def create_chart(
        self,
        filepath: str,
        sheet_name: str,
        data_range: str,
        chart_type: str,
        target_cell: str,
        title: str = "",
        x_axis: str = "",
        y_axis: str = ""
    ) -> Dict[str, Any]:
        """Create a chart in Excel worksheet.
        
        Args:
            filepath: Path to Excel file
            sheet_name: Name of the worksheet
            data_range: Range containing chart data (e.g., "A1:C10")
            chart_type: Type of chart (line, bar, pie, scatter, area)
            target_cell: Cell where to place chart (e.g., "E2")
            title: Optional chart title
            x_axis: Optional X-axis label
            y_axis: Optional Y-axis label
        
        Returns:
            Dictionary with success status, data, and system_message
        """
        pass
    
    @abstractmethod
    async def format_range(
        self,
        filepath: str,
        sheet_name: str,
        start_cell: str,
        end_cell: Optional[str] = None,
        bold: bool = False,
        italic: bool = False,
        font_size: Optional[int] = None,
        bg_color: Optional[str] = None
    ) -> Dict[str, Any]:
        """Apply formatting to a range of cells.
        
        Args:
            filepath: Path to Excel file
            sheet_name: Name of the worksheet
            start_cell: Starting cell of range
            end_cell: Optional ending cell of range
            bold: Apply bold formatting
            italic: Apply italic formatting
            font_size: Font size (e.g., 12, 14)
            bg_color: Background color (e.g., "FFFF00" for yellow)
        
        Returns:
            Dictionary with success status, data, and system_message
        """
        pass
    
    @abstractmethod
    async def create_worksheet(self, filepath: str, sheet_name: str) -> Dict[str, Any]:
        """Create a new worksheet in existing workbook.
        
        Args:
            filepath: Path to Excel file
            sheet_name: Name for the new worksheet
        
        Returns:
            Dictionary with success status, data, and system_message
        """
        pass
    
    @abstractmethod
    async def get_workbook_metadata(self, filepath: str, include_ranges: bool = False) -> Dict[str, Any]:
        """Get metadata about workbook (sheets, ranges, etc.).
        
        Args:
            filepath: Path to Excel file
            include_ranges: Whether to include range information
        
        Returns:
            Dictionary with success status, metadata, and system_message
        """
        pass
