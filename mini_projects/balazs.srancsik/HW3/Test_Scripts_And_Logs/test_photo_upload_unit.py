"""
Unit Test Suite for Photo Upload Tool.
Tests individual components and methods of the PhotoUploadTool class.

This script tests:
1. Date parsing functionality
2. Folder name sanitization and capitalization
3. MIME type detection
4. Input validation
5. Response structure
"""

import pytest
import sys
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Application', 'backend'))


class MockPCloudClient:
    """Mock pCloud client for unit testing."""
    
    def __init__(self):
        self.folders_created = []
        self.files_uploaded = []
        self.folder_id_counter = 1000
        self.file_id_counter = 2000
        self._photo_memories_id = 100
    
    async def find_folder(self, folder_name: str, parent_folder_id: int = None) -> Dict[str, Any]:
        """Mock find folder."""
        if folder_name == "Photo_Memories":
            return {"found": True, "folder_id": self._photo_memories_id, "folder_name": "Photo_Memories"}
        return {"found": False}
    
    async def create_folder(self, folder_name: str, parent_folder_id: int = None) -> Dict[str, Any]:
        """Mock create folder."""
        self.folder_id_counter += 1
        self.folders_created.append({"name": folder_name, "parent_id": parent_folder_id})
        return {
            "success": True,
            "folder_id": self.folder_id_counter,
            "folder_name": folder_name,
            "created": True
        }
    
    async def upload_file(self, file_path: str, file_name: str, folder_id: int, mime_type: str) -> Dict[str, Any]:
        """Mock upload file from path."""
        self.file_id_counter += 1
        self.files_uploaded.append({"name": file_name, "folder_id": folder_id})
        return {
            "success": True,
            "file_id": self.file_id_counter,
            "file_name": file_name,
            "size": 1024
        }
    
    async def upload_file_from_bytes(self, file_bytes: bytes, file_name: str, folder_id: int, mime_type: str) -> Dict[str, Any]:
        """Mock upload file from bytes."""
        self.file_id_counter += 1
        self.files_uploaded.append({"name": file_name, "folder_id": folder_id, "size": len(file_bytes)})
        return {
            "success": True,
            "file_id": self.file_id_counter,
            "file_name": file_name,
            "size": len(file_bytes)
        }
    
    async def list_folder_contents(self, folder_id: int) -> Dict[str, Any]:
        """Mock list folder contents."""
        contents = [
            {"id": f, "name": f["name"], "type": "file", "size": 1024}
            for f in self.files_uploaded if f.get("folder_id") == folder_id
        ]
        return {"success": True, "folder_id": folder_id, "contents": contents, "count": len(contents)}
    
    async def get_folder_structure(self, folder_id: int) -> Dict[str, Any]:
        """Mock get folder structure."""
        subfolders = [
            {"id": i, "name": f["name"], "path": f"/Photo_Memories/{f['name']}"}
            for i, f in enumerate(self.folders_created)
        ]
        return {"success": True, "folder_id": folder_id, "subfolders": subfolders, "count": len(subfolders)}


@pytest.fixture
def mock_client():
    """Create a mock pCloud client."""
    return MockPCloudClient()


@pytest.fixture
def photo_upload_tool(mock_client):
    """Create PhotoUploadTool with mock client."""
    from services.tools import PhotoUploadTool
    return PhotoUploadTool(cloud_client=mock_client, photo_memories_folder_id=100)


class TestDateParsing:
    """Tests for date parsing functionality."""
    
    def test_parse_iso_date(self, photo_upload_tool):
        """Test parsing ISO format date."""
        result = photo_upload_tool._parse_date("2024-06-15")
        assert result == "2024.06.15"
    
    def test_parse_dot_date(self, photo_upload_tool):
        """Test parsing dot-separated date."""
        result = photo_upload_tool._parse_date("2024.06.15")
        assert result == "2024.06.15"
    
    def test_parse_slash_date(self, photo_upload_tool):
        """Test parsing slash-separated date."""
        result = photo_upload_tool._parse_date("2024/06/15")
        assert result == "2024.06.15"
    
    def test_parse_european_date(self, photo_upload_tool):
        """Test parsing European format date (DD-MM-YYYY)."""
        result = photo_upload_tool._parse_date("15-06-2024")
        assert result == "2024.06.15"
    
    def test_parse_long_month_date(self, photo_upload_tool):
        """Test parsing date with full month name."""
        result = photo_upload_tool._parse_date("June 15, 2024")
        assert result == "2024.06.15"
    
    def test_parse_european_long_date(self, photo_upload_tool):
        """Test parsing European long format date."""
        result = photo_upload_tool._parse_date("15 June 2024")
        assert result == "2024.06.15"
    
    def test_parse_short_month_date(self, photo_upload_tool):
        """Test parsing date with abbreviated month."""
        result = photo_upload_tool._parse_date("Jun 15, 2024")
        assert result == "2024.06.15"
    
    def test_parse_empty_date_returns_today(self, photo_upload_tool):
        """Test that empty date returns today's date."""
        result = photo_upload_tool._parse_date("")
        today = datetime.now().strftime("%Y.%m.%d")
        assert result == today
    
    def test_parse_none_date_returns_today(self, photo_upload_tool):
        """Test that None date returns today's date."""
        result = photo_upload_tool._parse_date(None)
        today = datetime.now().strftime("%Y.%m.%d")
        assert result == today
    
    def test_parse_invalid_date_returns_today(self, photo_upload_tool):
        """Test that invalid date returns today's date."""
        result = photo_upload_tool._parse_date("not a date")
        today = datetime.now().strftime("%Y.%m.%d")
        assert result == today


class TestFolderNameSanitization:
    """Tests for folder name sanitization."""
    
    def test_sanitize_basic_name(self, photo_upload_tool):
        """Test sanitizing a basic name."""
        result = photo_upload_tool._sanitize_folder_name("summer vacation")
        assert result == "Summer vacation"
    
    def test_sanitize_capitalizes_first_letter(self, photo_upload_tool):
        """Test that first letter is capitalized."""
        result = photo_upload_tool._sanitize_folder_name("barcelona")
        assert result == "Barcelona"
    
    def test_sanitize_preserves_rest_of_string(self, photo_upload_tool):
        """Test that rest of string is preserved."""
        result = photo_upload_tool._sanitize_folder_name("new york city")
        assert result == "New york city"
    
    def test_sanitize_removes_invalid_chars(self, photo_upload_tool):
        """Test removal of invalid characters."""
        result = photo_upload_tool._sanitize_folder_name("test<>file")
        assert "<" not in result
        assert ">" not in result
    
    def test_sanitize_replaces_colon(self, photo_upload_tool):
        """Test replacement of colon."""
        result = photo_upload_tool._sanitize_folder_name("test:file")
        assert ":" not in result
    
    def test_sanitize_replaces_quotes(self, photo_upload_tool):
        """Test replacement of quotes."""
        result = photo_upload_tool._sanitize_folder_name('test"file')
        assert '"' not in result
    
    def test_sanitize_strips_spaces(self, photo_upload_tool):
        """Test stripping of leading/trailing spaces."""
        result = photo_upload_tool._sanitize_folder_name("  test  ")
        assert result == "Test"
    
    def test_sanitize_strips_dots(self, photo_upload_tool):
        """Test stripping of leading/trailing dots."""
        result = photo_upload_tool._sanitize_folder_name("..test..")
        assert result == "Test"
    
    def test_sanitize_empty_string(self, photo_upload_tool):
        """Test sanitizing empty string."""
        result = photo_upload_tool._sanitize_folder_name("")
        assert result == ""
    
    def test_sanitize_already_capitalized(self, photo_upload_tool):
        """Test that already capitalized names stay capitalized."""
        result = photo_upload_tool._sanitize_folder_name("Budapest")
        assert result == "Budapest"


class TestMimeTypeDetection:
    """Tests for MIME type detection."""
    
    def test_detect_jpeg(self, photo_upload_tool):
        """Test JPEG detection."""
        assert photo_upload_tool._get_mime_type("photo.jpg") == "image/jpeg"
        assert photo_upload_tool._get_mime_type("photo.jpeg") == "image/jpeg"
    
    def test_detect_png(self, photo_upload_tool):
        """Test PNG detection."""
        assert photo_upload_tool._get_mime_type("image.png") == "image/png"
    
    def test_detect_gif(self, photo_upload_tool):
        """Test GIF detection."""
        assert photo_upload_tool._get_mime_type("animation.gif") == "image/gif"
    
    def test_detect_webp(self, photo_upload_tool):
        """Test WebP detection."""
        assert photo_upload_tool._get_mime_type("modern.webp") == "image/webp"
    
    def test_detect_bmp(self, photo_upload_tool):
        """Test BMP detection."""
        assert photo_upload_tool._get_mime_type("bitmap.bmp") == "image/bmp"
    
    def test_detect_heic(self, photo_upload_tool):
        """Test HEIC detection (iPhone photos)."""
        assert photo_upload_tool._get_mime_type("iphone.heic") == "image/heic"
    
    def test_detect_tiff(self, photo_upload_tool):
        """Test TIFF detection."""
        assert photo_upload_tool._get_mime_type("scan.tiff") == "image/tiff"
        assert photo_upload_tool._get_mime_type("scan.tif") == "image/tiff"
    
    def test_detect_svg(self, photo_upload_tool):
        """Test SVG detection."""
        assert photo_upload_tool._get_mime_type("vector.svg") == "image/svg+xml"
    
    def test_detect_unknown(self, photo_upload_tool):
        """Test unknown extension returns octet-stream."""
        assert photo_upload_tool._get_mime_type("file.xyz") == "application/octet-stream"
    
    def test_detect_no_extension(self, photo_upload_tool):
        """Test file without extension."""
        assert photo_upload_tool._get_mime_type("noextension") == "application/octet-stream"
    
    def test_detect_case_insensitive(self, photo_upload_tool):
        """Test case insensitive detection."""
        assert photo_upload_tool._get_mime_type("PHOTO.JPG") == "image/jpeg"
        assert photo_upload_tool._get_mime_type("Image.PNG") == "image/png"


class TestInputValidation:
    """Tests for input validation in execute method."""
    
    @pytest.mark.asyncio
    async def test_missing_date(self, photo_upload_tool):
        """Test that missing date is reported."""
        result = await photo_upload_tool.execute(
            action="upload",
            date=None,
            event_name="test event",
            location="test city",
            file_data=[b"test"]
        )
        
        assert result["success"] is False
        assert "needs_info" in result
        assert any("date" in info.lower() for info in result["needs_info"])
    
    @pytest.mark.asyncio
    async def test_missing_event_name(self, photo_upload_tool):
        """Test that missing event name is reported."""
        result = await photo_upload_tool.execute(
            action="upload",
            date="2024-06-15",
            event_name=None,
            location="test city",
            file_data=[b"test"]
        )
        
        assert result["success"] is False
        assert "needs_info" in result
        assert any("event" in info.lower() for info in result["needs_info"])
    
    @pytest.mark.asyncio
    async def test_missing_location(self, photo_upload_tool):
        """Test that missing location is reported."""
        result = await photo_upload_tool.execute(
            action="upload",
            date="2024-06-15",
            event_name="test event",
            location=None,
            file_data=[b"test"]
        )
        
        assert result["success"] is False
        assert "needs_info" in result
        assert any("location" in info.lower() for info in result["needs_info"])
    
    @pytest.mark.asyncio
    async def test_missing_all_info(self, photo_upload_tool):
        """Test that all missing fields are reported."""
        result = await photo_upload_tool.execute(
            action="upload",
            date=None,
            event_name=None,
            location=None,
            file_data=[b"test"]
        )
        
        assert result["success"] is False
        assert "needs_info" in result
        assert len(result["needs_info"]) == 3
    
    @pytest.mark.asyncio
    async def test_missing_files(self, photo_upload_tool):
        """Test that missing files is reported."""
        result = await photo_upload_tool.execute(
            action="upload",
            date="2024-06-15",
            event_name="test event",
            location="test city",
            file_paths=None,
            file_data=None
        )
        
        assert result["success"] is False
        assert "error" in result
        assert "file" in result["error"].lower() or "no" in result["error"].lower()


class TestListAction:
    """Tests for list action."""
    
    @pytest.mark.asyncio
    async def test_list_returns_success(self, photo_upload_tool):
        """Test that list action returns success."""
        result = await photo_upload_tool.execute(action="list")
        
        assert result["success"] is True
        assert "message" in result
    
    @pytest.mark.asyncio
    async def test_list_contains_folder_info(self, photo_upload_tool):
        """Test that list action contains folder information."""
        result = await photo_upload_tool.execute(action="list")
        
        assert "data" in result
        assert "subfolders" in result["data"] or "folders" in str(result)


class TestUploadAction:
    """Tests for upload action with mock client."""
    
    @pytest.mark.asyncio
    async def test_successful_upload(self, photo_upload_tool, mock_client):
        """Test successful file upload."""
        result = await photo_upload_tool.execute(
            action="upload",
            date="2024-06-15",
            event_name="summer vacation",
            location="barcelona",
            file_data=[b"fake image data"],
            file_names=["test.jpg"]
        )
        
        assert result["success"] is True
        assert "data" in result
        assert len(mock_client.files_uploaded) == 1
    
    @pytest.mark.asyncio
    async def test_upload_creates_folder(self, photo_upload_tool, mock_client):
        """Test that upload creates folder with correct name."""
        await photo_upload_tool.execute(
            action="upload",
            date="2024-06-15",
            event_name="summer vacation",
            location="barcelona",
            file_data=[b"fake image data"],
            file_names=["test.jpg"]
        )
        
        assert len(mock_client.folders_created) == 1
        folder_name = mock_client.folders_created[0]["name"]
        assert "2024.06.15" in folder_name
        assert "Summer vacation" in folder_name
        assert "Barcelona" in folder_name
    
    @pytest.mark.asyncio
    async def test_upload_multiple_files(self, photo_upload_tool, mock_client):
        """Test uploading multiple files."""
        result = await photo_upload_tool.execute(
            action="upload",
            date="2024-06-15",
            event_name="party",
            location="home",
            file_data=[b"image1", b"image2", b"image3"],
            file_names=["photo1.jpg", "photo2.jpg", "photo3.png"]
        )
        
        assert result["success"] is True
        assert len(mock_client.files_uploaded) == 3
    
    @pytest.mark.asyncio
    async def test_upload_response_contains_folder_name(self, photo_upload_tool):
        """Test that upload response contains folder name."""
        result = await photo_upload_tool.execute(
            action="upload",
            date="2024-06-15",
            event_name="wedding",
            location="church",
            file_data=[b"image"],
            file_names=["photo.jpg"]
        )
        
        assert result["success"] is True
        assert "folder_name" in result["data"]
        assert "Wedding" in result["data"]["folder_name"]
        assert "Church" in result["data"]["folder_name"]
    
    @pytest.mark.asyncio
    async def test_upload_response_contains_system_message(self, photo_upload_tool):
        """Test that upload response contains system message."""
        result = await photo_upload_tool.execute(
            action="upload",
            date="2024-06-15",
            event_name="birthday",
            location="restaurant",
            file_data=[b"image"],
            file_names=["photo.jpg"]
        )
        
        assert "system_message" in result
        assert "1" in result["system_message"]  # Should mention number of files


class TestUnknownAction:
    """Tests for unknown action handling."""
    
    @pytest.mark.asyncio
    async def test_unknown_action_returns_error(self, photo_upload_tool):
        """Test that unknown action returns error."""
        result = await photo_upload_tool.execute(action="invalid_action")
        
        assert result["success"] is False
        assert "error" in result


class TestResponseStructure:
    """Tests for response structure validation."""
    
    @pytest.mark.asyncio
    async def test_success_response_has_required_fields(self, photo_upload_tool):
        """Test that success response has all required fields."""
        result = await photo_upload_tool.execute(
            action="upload",
            date="2024-06-15",
            event_name="test",
            location="test",
            file_data=[b"image"],
            file_names=["test.jpg"]
        )
        
        assert "success" in result
        assert "message" in result or "system_message" in result
        assert "data" in result
    
    @pytest.mark.asyncio
    async def test_error_response_has_required_fields(self, photo_upload_tool):
        """Test that error response has all required fields."""
        result = await photo_upload_tool.execute(
            action="upload",
            date=None,
            event_name=None,
            location=None
        )
        
        assert "success" in result
        assert result["success"] is False
        assert "error" in result or "needs_info" in result


class TestFolderNamingConvention:
    """Tests for folder naming convention."""
    
    @pytest.mark.asyncio
    async def test_folder_name_format(self, photo_upload_tool, mock_client):
        """Test folder name follows YYYY.MM.DD - Event - Location format."""
        await photo_upload_tool.execute(
            action="upload",
            date="2024-06-15",
            event_name="summer trip",
            location="paris",
            file_data=[b"image"],
            file_names=["test.jpg"]
        )
        
        folder_name = mock_client.folders_created[0]["name"]
        parts = folder_name.split(" - ")
        
        assert len(parts) == 3
        assert parts[0] == "2024.06.15"
        assert parts[1] == "Summer trip"
        assert parts[2] == "Paris"
    
    @pytest.mark.asyncio
    async def test_folder_name_with_special_chars(self, photo_upload_tool, mock_client):
        """Test folder name with special characters in input."""
        await photo_upload_tool.execute(
            action="upload",
            date="2024-06-15",
            event_name="john's birthday",
            location="new york",
            file_data=[b"image"],
            file_names=["test.jpg"]
        )
        
        folder_name = mock_client.folders_created[0]["name"]
        
        # Should not contain invalid characters
        assert "<" not in folder_name
        assert ">" not in folder_name
        assert ":" not in folder_name


# Run tests with: pytest test_photo_upload_unit.py -v --html=test_photo_upload_unit_report.html
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--html=test_photo_upload_unit_report.html", "--self-contained-html"])
