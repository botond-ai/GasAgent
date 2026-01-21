"""
Infrastructure layer - External service client implementations.

Following SOLID principles:
- Single Responsibility: Each client handles one external service
- Open/Closed: Easy to add new clients without modifying existing ones
- Dependency Inversion: Implements domain interfaces
"""
import httpx
import logging
import uuid
from typing import Dict, Any, Optional, List
from domain.interfaces import IMCPClient, IExcelMCPClient

logger = logging.getLogger(__name__)


class MCPClient(IMCPClient):
    """Base MCP (Model Context Protocol) client implementation.
    
    Supports JSON-RPC 2.0 over HTTP/HTTPS.
    Handles both plain JSON and SSE (Server-Sent Events) responses.
    
    Protocol flow:
    1. connect() - Initialize session with MCP server
    2. list_tools() - Fetch available tools
    3. call_tool() - Execute tools with arguments
    4. disconnect() - Clean up session
    """
    
    def __init__(self):
        self.server_url: Optional[str] = None
        self.connected: bool = False
        self.session_id: Optional[str] = None
        self.capabilities: Dict[str, Any] = {}
    
    async def connect(self, server_url: str) -> None:
        """Connect to MCP server using JSON-RPC 2.0 initialization."""
        # Don't reconnect if already connected to the same server
        if self.connected and self.server_url == server_url:
            logger.info(f"Already connected to MCP server: {server_url}")
            return
            
        try:
            self.server_url = server_url
            self.session_id = str(uuid.uuid4())
            
            logger.info(f"[MCP] Connecting to server: {server_url}")
            
            # Initialize session with JSON-RPC 2.0
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    server_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2025-03-26",
                            "capabilities": {},
                            "clientInfo": {
                                "name": "knowledge-router-client",
                                "version": "1.0.0"
                            }
                        }
                    },
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream"
                    }
                )
                
                # CRITICAL: Extract session ID from response headers
                server_session_id = response.headers.get("mcp-session-id") or response.headers.get("Mcp-Session-Id")
                if server_session_id:
                    self.session_id = server_session_id
                    logger.info(f"[MCP] Session ID assigned: {self.session_id}")
                
                # Parse response (SSE or plain JSON)
                if "event:" in response.text:
                    # Server-Sent Events format
                    import json
                    for line in response.text.split('\n'):
                        if line.startswith('data: '):
                            data = line[6:]  # Remove 'data: ' prefix
                            if data and data != 'ping':
                                result = json.loads(data)
                                if "result" in result:
                                    self.capabilities = result["result"].get("capabilities", {})
                                    self.connected = True
                                    logger.info(f"[MCP] ✓ Connected (SSE mode): {server_url}")
                                    break
                else:
                    # Plain JSON response
                    result = response.json()
                    if "result" in result:
                        self.capabilities = result["result"].get("capabilities", {})
                        self.connected = True
                        logger.info(f"[MCP] ✓ Connected (JSON mode): {server_url}")
            
            # Send 'initialized' notification (no response expected)
            if self.connected:
                try:
                    async with httpx.AsyncClient(timeout=5.0) as notify_client:
                        await notify_client.post(
                            server_url,
                            json={
                                "jsonrpc": "2.0",
                                "method": "notifications/initialized"  # Corrected method name
                            },
                            headers={
                                "Content-Type": "application/json",
                                "Accept": "application/json, text/event-stream",
                                "Mcp-Session-Id": self.session_id
                            }
                        )
                        logger.info(f"[MCP] Sent 'initialized' notification")
                except Exception as notify_error:
                    # Notifications may not return response, this is expected
                    logger.debug(f"[MCP] Initialized notification: {notify_error}")
                    
        except Exception as e:
            logger.error(f"[MCP] ✗ Connection failed: {e}")
            self.connected = False
            raise ConnectionError(f"Failed to connect to MCP server: {e}")
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools from the MCP server using JSON-RPC 2.0."""
        if not self.connected:
            raise ConnectionError("MCP client not connected to server")
        
        try:
            logger.info("[MCP] Listing tools from server")
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                }
                if self.session_id:
                    headers["Mcp-Session-Id"] = self.session_id
                    
                response = await client.post(
                    self.server_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/list",
                        "params": {}
                    },
                    headers=headers
                )
                
                # Parse response
                import json
                result_data = None
                if "event:" in response.text:
                    # SSE format
                    for line in response.text.split('\n'):
                        if line.startswith('data: '):
                            data = line[6:]
                            if data and data != 'ping':
                                result_data = json.loads(data)
                                break
                else:
                    # Plain JSON
                    result_data = response.json()
                
                if result_data and "result" in result_data:
                    tools = result_data["result"].get("tools", [])
                    logger.info(f"[MCP] ✓ Fetched {len(tools)} tools")
                    return tools
                    
                return []
        except Exception as e:
            logger.error(f"[MCP] ✗ Failed to list tools: {e}")
            raise
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP server using JSON-RPC 2.0."""
        if not self.connected:
            raise ConnectionError("MCP client not connected to server")
        
        try:
            logger.info(f"[MCP] Calling tool: {name} with args: {arguments}")
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                }
                if self.session_id:
                    headers["Mcp-Session-Id"] = self.session_id
                
                response = await client.post(
                    self.server_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {
                            "name": name,
                            "arguments": arguments
                        }
                    },
                    headers=headers
                )
                
                # Parse response
                import json
                result_data = None
                if "event:" in response.text:
                    # SSE format
                    for line in response.text.split('\n'):
                        if line.startswith('data: '):
                            data = line[6:]
                            if data and data != 'ping':
                                result_data = json.loads(data)
                                break
                else:
                    # Plain JSON
                    result_data = response.json()
                
                if result_data and "result" in result_data:
                    # Return content or full result
                    return result_data["result"].get('content', result_data["result"])
                    
                return {"error": "No result from MCP server"}
        except Exception as e:
            logger.error(f"[MCP] ✗ Tool call failed: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from MCP server."""
        if self.connected:
            try:
                self.connected = False
                self.session_id = None
                logger.info(f"[MCP] Disconnected from server: {self.server_url}")
            except Exception as e:
                logger.warning(f"[MCP] Error during disconnect: {e}")


class ExcelMCPClient(IExcelMCPClient):
    """Excel MCP client implementation using generic MCPClient.
    
    Wraps MCP protocol calls with Excel-specific operations.
    Server URL configured via environment variable EXCEL_MCP_SERVER_URL.
    
    Example usage:
        client = ExcelMCPClient()
        await client.create_workbook("report.xlsx")
        await client.write_data("report.xlsx", "Sheet1", data)
    """
    
    def __init__(self, mcp_client: Optional[IMCPClient] = None, server_url: Optional[str] = None):
        """Initialize Excel MCP client.
        
        Args:
            mcp_client: Optional MCP client instance (creates new if None)
            server_url: Optional server URL (uses env var if None)
        """
        self.mcp_client = mcp_client or MCPClient()
        self._connected = False
        self._server_url = server_url
    
    async def _ensure_connected(self) -> None:
        """Ensure MCP client is connected to Excel server."""
        if not self._connected:
            try:
                # Get server URL from config or parameter
                if self._server_url is None:
                    from config.settings import get_settings
                    settings = get_settings()
                    self._server_url = settings.excel_mcp_server_url
                
                await self.mcp_client.connect(self._server_url)
                self._connected = True
                logger.info(f"[Excel MCP] Connected to server: {self._server_url}")
            except Exception as e:
                logger.error(f"[Excel MCP] Failed to connect: {e}")
                raise ConnectionError(f"Excel MCP server not reachable: {e}")
    
    async def create_workbook(self, filepath: str) -> Dict[str, Any]:
        """Create new Excel workbook."""
        await self._ensure_connected()
        try:
            result = await self.mcp_client.call_tool(
                name="create_workbook",
                arguments={"filepath": filepath}
            )
            return {
                "success": True,
                "data": result,
                "system_message": f"[Excel] Created workbook: {filepath}"
            }
        except Exception as e:
            logger.error(f"[Excel MCP] Failed to create workbook: {e}")
            return {
                "success": False,
                "error": str(e),
                "system_message": f"[Excel] Error creating workbook: {e}"
            }
    
    async def write_data(
        self, 
        filepath: str, 
        sheet_name: str, 
        data: List[List], 
        start_cell: str = "A1"
    ) -> Dict[str, Any]:
        """Write data to Excel worksheet."""
        await self._ensure_connected()
        try:
            result = await self.mcp_client.call_tool(
                name="write_data_to_excel",
                arguments={
                    "filepath": filepath,
                    "sheet_name": sheet_name,
                    "data": data,
                    "start_cell": start_cell
                }
            )
            return {
                "success": True,
                "data": result,
                "system_message": f"[Excel] Data written to {sheet_name}!{start_cell}"
            }
        except Exception as e:
            logger.error(f"[Excel MCP] Failed to write data: {e}")
            return {
                "success": False,
                "error": str(e),
                "system_message": f"[Excel] Error writing data: {e}"
            }
    
    async def read_data(
        self, 
        filepath: str, 
        sheet_name: str, 
        start_cell: str = "A1",
        end_cell: Optional[str] = None
    ) -> Dict[str, Any]:
        """Read data from Excel worksheet."""
        await self._ensure_connected()
        try:
            arguments = {
                "filepath": filepath,
                "sheet_name": sheet_name,
                "start_cell": start_cell
            }
            if end_cell:
                arguments["end_cell"] = end_cell
            
            result = await self.mcp_client.call_tool(
                name="read_data_from_excel",
                arguments=arguments
            )
            return {
                "success": True,
                "data": result,
                "system_message": f"[Excel] Data read from {sheet_name}!{start_cell}"
            }
        except Exception as e:
            logger.error(f"[Excel MCP] Failed to read data: {e}")
            return {
                "success": False,
                "error": str(e),
                "system_message": f"[Excel] Error reading data: {e}"
            }
    
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
        """Create chart in worksheet."""
        await self._ensure_connected()
        try:
            result = await self.mcp_client.call_tool(
                name="create_chart",
                arguments={
                    "filepath": filepath,
                    "sheet_name": sheet_name,
                    "data_range": data_range,
                    "chart_type": chart_type,
                    "target_cell": target_cell,
                    "title": title,
                    "x_axis": x_axis,
                    "y_axis": y_axis
                }
            )
            return {
                "success": True,
                "data": result,
                "system_message": f"[Excel] Created {chart_type} chart in {sheet_name}!{target_cell}"
            }
        except Exception as e:
            logger.error(f"[Excel MCP] Failed to create chart: {e}")
            return {
                "success": False,
                "error": str(e),
                "system_message": f"[Excel] Error creating chart: {e}"
            }
    
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
        """Apply formatting to a range of cells."""
        await self._ensure_connected()
        try:
            arguments = {
                "filepath": filepath,
                "sheet_name": sheet_name,
                "start_cell": start_cell
            }
            if end_cell:
                arguments["end_cell"] = end_cell
            if bold:
                arguments["bold"] = True
            if italic:
                arguments["italic"] = True
            if font_size:
                arguments["font_size"] = font_size
            if bg_color:
                arguments["bg_color"] = bg_color
            
            result = await self.mcp_client.call_tool(
                name="format_range",
                arguments=arguments
            )
            return {
                "success": True,
                "data": result,
                "system_message": f"[Excel] Formatted {sheet_name}!{start_cell}"
            }
        except Exception as e:
            logger.error(f"[Excel MCP] Failed to format range: {e}")
            return {
                "success": False,
                "error": str(e),
                "system_message": f"[Excel] Error formatting range: {e}"
            }
    
    async def create_worksheet(self, filepath: str, sheet_name: str) -> Dict[str, Any]:
        """Create new worksheet in workbook."""
        await self._ensure_connected()
        try:
            result = await self.mcp_client.call_tool(
                name="create_worksheet",
                arguments={
                    "filepath": filepath,
                    "sheet_name": sheet_name
                }
            )
            return {
                "success": True,
                "data": result,
                "system_message": f"[Excel] Created worksheet: {sheet_name}"
            }
        except Exception as e:
            logger.error(f"[Excel MCP] Failed to create worksheet: {e}")
            return {
                "success": False,
                "error": str(e),
                "system_message": f"[Excel] Error creating worksheet: {e}"
            }
    
    async def get_workbook_metadata(self, filepath: str, include_ranges: bool = False) -> Dict[str, Any]:
        """Get metadata about workbook."""
        await self._ensure_connected()
        try:
            result = await self.mcp_client.call_tool(
                name="get_workbook_metadata",
                arguments={
                    "filepath": filepath,
                    "include_ranges": include_ranges
                }
            )
            return {
                "success": True,
                "data": result,
                "system_message": f"[Excel] Retrieved metadata for {filepath}"
            }
        except Exception as e:
            logger.error(f"[Excel MCP] Failed to get metadata: {e}")
            return {
                "success": False,
                "error": str(e),
                "system_message": f"[Excel] Error getting metadata: {e}"
            }
