"""
Pydantic-based API Test Script for Photo Upload Tool.
Tests the pCloud API connections and photo upload functionality.

This script validates:
1. pCloud client initialization and authentication
2. Folder creation and listing operations
3. File upload functionality
4. Response schema validation using Pydantic models
"""

import os
import sys
import asyncio
import tempfile
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field, validator
import json

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Application', 'backend'))


# ============================================================================
# PYDANTIC MODELS FOR RESPONSE VALIDATION
# ============================================================================

class FolderInfo(BaseModel):
    """Model for folder information from pCloud."""
    id: Optional[int] = Field(None, alias='folder_id')
    name: str
    path: Optional[str] = None
    
    class Config:
        populate_by_name = True


class FileInfo(BaseModel):
    """Model for file information from pCloud."""
    id: Optional[int] = Field(None, alias='file_id')
    name: str
    path: Optional[str] = None
    size: Optional[int] = None
    
    class Config:
        populate_by_name = True


class FolderCreateResponse(BaseModel):
    """Model for folder creation response."""
    success: bool
    folder_id: Optional[int] = None
    folder_name: Optional[str] = None
    path: Optional[str] = None
    created: Optional[bool] = None
    error: Optional[str] = None


class FolderFindResponse(BaseModel):
    """Model for folder find response."""
    found: bool = False
    folder_id: Optional[int] = None
    folder_name: Optional[str] = None
    path: Optional[str] = None
    error: Optional[str] = None


class FolderContentsItem(BaseModel):
    """Model for individual item in folder contents."""
    id: Optional[int] = None
    name: str
    type: str  # 'file' or 'folder'
    path: Optional[str] = None
    size: Optional[int] = None
    created_time: Optional[str] = None


class FolderContentsResponse(BaseModel):
    """Model for folder contents listing response."""
    success: bool = False
    folder_id: Optional[int] = None
    contents: List[FolderContentsItem] = []
    count: int = 0
    error: Optional[str] = None


class FolderStructureResponse(BaseModel):
    """Model for folder structure response."""
    success: bool = False
    folder_id: Optional[int] = None
    subfolders: List[Dict[str, Any]] = []
    count: int = 0
    error: Optional[str] = None


class FileUploadResponse(BaseModel):
    """Model for file upload response."""
    success: bool
    file_id: Optional[int] = None
    file_name: Optional[str] = None
    path: Optional[str] = None
    size: Optional[int] = None
    error: Optional[str] = None


class PhotoUploadToolResponse(BaseModel):
    """Model for PhotoUploadTool execute response."""
    success: bool
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    system_message: Optional[str] = None
    error: Optional[str] = None
    needs_info: Optional[List[str]] = None


# ============================================================================
# TEST RESULT TRACKING
# ============================================================================

class TestResult(BaseModel):
    """Model for individual test result."""
    test_name: str
    status: str  # 'PASSED', 'FAILED', 'SKIPPED', 'ERROR'
    duration_ms: float
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class TestReport(BaseModel):
    """Model for complete test report."""
    title: str = "Photo Upload Tool API Test Report"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_ms: float = 0
    results: List[TestResult] = []
    environment: Dict[str, str] = {}


# ============================================================================
# TEST RUNNER CLASS
# ============================================================================

class PhotoUploadAPITester:
    """Test runner for Photo Upload Tool API."""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.pcloud_client = None
        self.photo_upload_tool = None
        self.test_folder_id = None
        self.test_folder_name = None
        
    def _record_result(self, test_name: str, status: str, duration_ms: float, 
                       message: str = None, details: Dict = None):
        """Record a test result."""
        self.results.append(TestResult(
            test_name=test_name,
            status=status,
            duration_ms=duration_ms,
            message=message,
            details=details
        ))
        print(f"  [{status}] {test_name}" + (f" - {message}" if message else ""))
    
    async def test_pcloud_client_initialization(self) -> bool:
        """Test 1: Initialize pCloud client."""
        start = datetime.now()
        test_name = "pCloud Client Initialization"
        
        try:
            from infrastructure.tool_clients import PCloudClient
            
            # Try username/password authentication first (Option 1)
            username = os.getenv("PCLOUD_USERNAME")
            password = os.getenv("PCLOUD_PASSWORD")
            endpoint = os.getenv("PCLOUD_ENDPOINT", "eapi")
            
            # Fall back to access token if username/password not available
            access_token = os.getenv("PCLOUD_ACCESS_TOKEN")
            
            if not username or not password:
                if not access_token:
                    self._record_result(test_name, "SKIPPED", 0, 
                                       "Neither PCLOUD_USERNAME/PASSWORD nor PCLOUD_ACCESS_TOKEN set")
                    return False
                # Use access token
                self.pcloud_client = PCloudClient(
                    access_token=access_token,
                    endpoint=endpoint
                )
            else:
                # Use username/password
                self.pcloud_client = PCloudClient(
                    username=username,
                    password=password,
                    endpoint=endpoint
                )
            
            # Force initialization
            self.pcloud_client._initialize()
            
            duration = (datetime.now() - start).total_seconds() * 1000
            auth_method = "username/password" if username and password else "access token"
            self._record_result(test_name, "PASSED", duration, 
                               f"Client initialized successfully using {auth_method}")
            return True
            
        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            self._record_result(test_name, "ERROR", duration, str(e))
            return False
    
    async def test_photo_upload_tool_initialization(self) -> bool:
        """Test 2: Initialize PhotoUploadTool."""
        start = datetime.now()
        test_name = "PhotoUploadTool Initialization"
        
        try:
            from services.tools import PhotoUploadTool
            
            if not self.pcloud_client:
                self._record_result(test_name, "SKIPPED", 0, 
                                   "pCloud client not available")
                return False
            
            folder_id = os.getenv("PCLOUD_PHOTO_MEMORIES_FOLDER_ID")
            folder_id = int(folder_id) if folder_id else None
            
            self.photo_upload_tool = PhotoUploadTool(
                cloud_client=self.pcloud_client,
                photo_memories_folder_id=folder_id
            )
            
            duration = (datetime.now() - start).total_seconds() * 1000
            self._record_result(test_name, "PASSED", duration,
                               f"Tool initialized with folder_id={folder_id}")
            return True
            
        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            self._record_result(test_name, "ERROR", duration, str(e))
            return False
    
    async def test_list_photo_memories_folders(self) -> bool:
        """Test 3: List Photo_Memories folder structure."""
        start = datetime.now()
        test_name = "List Photo_Memories Folders"
        
        try:
            if not self.photo_upload_tool:
                self._record_result(test_name, "SKIPPED", 0,
                                   "PhotoUploadTool not available")
                return False
            
            result = await self.photo_upload_tool.execute(action="list")
            
            # Validate response with Pydantic
            response = PhotoUploadToolResponse(**result)
            
            duration = (datetime.now() - start).total_seconds() * 1000
            
            if response.success:
                folder_count = len(response.data.get("subfolders", [])) if response.data else 0
                self._record_result(test_name, "PASSED", duration,
                                   f"Found {folder_count} folders",
                                   {"folders": response.data.get("subfolders", [])[:5]})
                return True
            else:
                self._record_result(test_name, "FAILED", duration,
                                   response.error or "Unknown error")
                return False
                
        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            self._record_result(test_name, "ERROR", duration, str(e))
            return False
    
    async def test_find_folder(self) -> bool:
        """Test 4: Find a folder by name."""
        start = datetime.now()
        test_name = "Find Folder by Name"
        
        try:
            if not self.pcloud_client:
                self._record_result(test_name, "SKIPPED", 0,
                                   "pCloud client not available")
                return False
            
            # Try to find Photo_Memories folder
            result = await self.pcloud_client.find_folder("Photo_Memories", parent_folder_id=0)
            
            # Validate with Pydantic
            response = FolderFindResponse(**result)
            
            duration = (datetime.now() - start).total_seconds() * 1000
            
            if response.found:
                self._record_result(test_name, "PASSED", duration,
                                   f"Found Photo_Memories folder (ID: {response.folder_id})")
                return True
            else:
                self._record_result(test_name, "PASSED", duration,
                                   "Photo_Memories folder not found (expected if new account)")
                return True
                
        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            self._record_result(test_name, "ERROR", duration, str(e))
            return False
    
    async def test_create_test_folder(self) -> bool:
        """Test 5: Create a test folder."""
        start = datetime.now()
        test_name = "Create Test Folder"
        
        try:
            if not self.pcloud_client:
                self._record_result(test_name, "SKIPPED", 0,
                                   "pCloud client not available")
                return False
            
            # Create a unique test folder name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.test_folder_name = f"_TEST_FOLDER_{timestamp}"
            
            result = await self.pcloud_client.create_folder(self.test_folder_name, parent_folder_id=0)
            
            # Validate with Pydantic
            response = FolderCreateResponse(**result)
            
            duration = (datetime.now() - start).total_seconds() * 1000
            
            if response.success:
                self.test_folder_id = response.folder_id
                self._record_result(test_name, "PASSED", duration,
                                   f"Created folder '{self.test_folder_name}' (ID: {self.test_folder_id})")
                return True
            else:
                self._record_result(test_name, "FAILED", duration,
                                   response.error or "Unknown error")
                return False
                
        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            self._record_result(test_name, "ERROR", duration, str(e))
            return False
    
    async def test_list_folder_contents(self) -> bool:
        """Test 6: List folder contents."""
        start = datetime.now()
        test_name = "List Folder Contents"
        
        try:
            if not self.pcloud_client or not self.test_folder_id:
                self._record_result(test_name, "SKIPPED", 0,
                                   "Test folder not available")
                return False
            
            result = await self.pcloud_client.list_folder_contents(self.test_folder_id)
            
            # Validate with Pydantic
            response = FolderContentsResponse(**result)
            
            duration = (datetime.now() - start).total_seconds() * 1000
            
            if response.success:
                self._record_result(test_name, "PASSED", duration,
                                   f"Listed {response.count} items in folder")
                return True
            else:
                self._record_result(test_name, "FAILED", duration,
                                   response.error or "Unknown error")
                return False
                
        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            self._record_result(test_name, "ERROR", duration, str(e))
            return False
    
    async def test_upload_file_from_bytes(self) -> bool:
        """Test 7: Upload a file from bytes."""
        start = datetime.now()
        test_name = "Upload File from Bytes"
        
        try:
            if not self.pcloud_client or not self.test_folder_id:
                self._record_result(test_name, "SKIPPED", 0,
                                   "Test folder not available")
                return False
            
            # Create a simple test image (1x1 pixel PNG)
            test_image_bytes = bytes([
                0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
                0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
                0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1 dimensions
                0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
                0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
                0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
                0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
                0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
                0x44, 0xAE, 0x42, 0x60, 0x82
            ])
            
            test_filename = f"test_image_{datetime.now().strftime('%H%M%S')}.png"
            
            result = await self.pcloud_client.upload_file_from_bytes(
                file_bytes=test_image_bytes,
                file_name=test_filename,
                folder_id=self.test_folder_id,
                mime_type="image/png"
            )
            
            # Validate with Pydantic
            response = FileUploadResponse(**result)
            
            duration = (datetime.now() - start).total_seconds() * 1000
            
            if response.success:
                self._record_result(test_name, "PASSED", duration,
                                   f"Uploaded '{test_filename}' (ID: {response.file_id}, Size: {response.size} bytes)")
                return True
            else:
                self._record_result(test_name, "FAILED", duration,
                                   response.error or "Unknown error")
                return False
                
        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            self._record_result(test_name, "ERROR", duration, str(e))
            return False
    
    async def test_photo_upload_tool_validation(self) -> bool:
        """Test 8: Test PhotoUploadTool input validation."""
        start = datetime.now()
        test_name = "PhotoUploadTool Input Validation"
        
        try:
            if not self.photo_upload_tool:
                self._record_result(test_name, "SKIPPED", 0,
                                   "PhotoUploadTool not available")
                return False
            
            # Test with missing required fields
            result = await self.photo_upload_tool.execute(
                action="upload",
                date=None,
                event_name=None,
                location=None
            )
            
            response = PhotoUploadToolResponse(**result)
            
            duration = (datetime.now() - start).total_seconds() * 1000
            
            # Should fail with needs_info
            if not response.success and response.needs_info:
                self._record_result(test_name, "PASSED", duration,
                                   f"Correctly identified missing fields: {response.needs_info}")
                return True
            else:
                self._record_result(test_name, "FAILED", duration,
                                   "Should have returned needs_info for missing fields")
                return False
                
        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            self._record_result(test_name, "ERROR", duration, str(e))
            return False
    
    async def test_date_parsing(self) -> bool:
        """Test 9: Test date parsing functionality."""
        start = datetime.now()
        test_name = "Date Parsing"
        
        try:
            if not self.photo_upload_tool:
                self._record_result(test_name, "SKIPPED", 0,
                                   "PhotoUploadTool not available")
                return False
            
            test_dates = [
                ("2024-06-15", "2024.06.15"),
                ("15-06-2024", "2024.06.15"),
                ("June 15, 2024", "2024.06.15"),
                ("15 June 2024", "2024.06.15"),
            ]
            
            all_passed = True
            results = []
            
            for input_date, expected in test_dates:
                parsed = self.photo_upload_tool._parse_date(input_date)
                passed = parsed == expected
                results.append(f"{input_date} -> {parsed} ({'✓' if passed else '✗'})")
                if not passed:
                    all_passed = False
            
            duration = (datetime.now() - start).total_seconds() * 1000
            
            if all_passed:
                self._record_result(test_name, "PASSED", duration,
                                   "All date formats parsed correctly",
                                   {"results": results})
                return True
            else:
                self._record_result(test_name, "FAILED", duration,
                                   "Some date formats failed",
                                   {"results": results})
                return False
                
        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            self._record_result(test_name, "ERROR", duration, str(e))
            return False
    
    async def test_folder_name_sanitization(self) -> bool:
        """Test 10: Test folder name sanitization and capitalization."""
        start = datetime.now()
        test_name = "Folder Name Sanitization"
        
        try:
            if not self.photo_upload_tool:
                self._record_result(test_name, "SKIPPED", 0,
                                   "PhotoUploadTool not available")
                return False
            
            test_cases = [
                ("summer vacation", "Summer vacation"),
                ("barcelona", "Barcelona"),
                ("new york", "New york"),
                ("test<>file", "Test__file"),
            ]
            
            all_passed = True
            results = []
            
            for input_name, expected in test_cases:
                sanitized = self.photo_upload_tool._sanitize_folder_name(input_name)
                passed = sanitized == expected
                results.append(f"'{input_name}' -> '{sanitized}' ({'✓' if passed else '✗'})")
                if not passed:
                    all_passed = False
            
            duration = (datetime.now() - start).total_seconds() * 1000
            
            if all_passed:
                self._record_result(test_name, "PASSED", duration,
                                   "All names sanitized correctly",
                                   {"results": results})
                return True
            else:
                self._record_result(test_name, "FAILED", duration,
                                   "Some sanitization failed",
                                   {"results": results})
                return False
                
        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            self._record_result(test_name, "ERROR", duration, str(e))
            return False
    
    async def test_mime_type_detection(self) -> bool:
        """Test 11: Test MIME type detection."""
        start = datetime.now()
        test_name = "MIME Type Detection"
        
        try:
            if not self.photo_upload_tool:
                self._record_result(test_name, "SKIPPED", 0,
                                   "PhotoUploadTool not available")
                return False
            
            test_cases = [
                ("photo.jpg", "image/jpeg"),
                ("image.png", "image/png"),
                ("picture.gif", "image/gif"),
                ("file.webp", "image/webp"),
                ("unknown.xyz", "application/octet-stream"),
            ]
            
            all_passed = True
            results = []
            
            for filename, expected in test_cases:
                mime_type = self.photo_upload_tool._get_mime_type(filename)
                passed = mime_type == expected
                results.append(f"'{filename}' -> '{mime_type}' ({'✓' if passed else '✗'})")
                if not passed:
                    all_passed = False
            
            duration = (datetime.now() - start).total_seconds() * 1000
            
            if all_passed:
                self._record_result(test_name, "PASSED", duration,
                                   "All MIME types detected correctly",
                                   {"results": results})
                return True
            else:
                self._record_result(test_name, "FAILED", duration,
                                   "Some MIME types incorrect",
                                   {"results": results})
                return False
                
        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            self._record_result(test_name, "ERROR", duration, str(e))
            return False
    
    async def cleanup_test_folder(self):
        """Cleanup: Delete test folder (informational only)."""
        if self.test_folder_id:
            print(f"\n  [INFO] Test folder '{self.test_folder_name}' (ID: {self.test_folder_id}) was created.")
            print(f"  [INFO] Please delete it manually from pCloud if needed.")
    
    async def run_all_tests(self) -> TestReport:
        """Run all tests and generate report."""
        print("\n" + "="*70)
        print("PHOTO UPLOAD TOOL - PYDANTIC API TEST SUITE")
        print("="*70 + "\n")
        
        start_time = datetime.now()
        
        # Run tests in order
        await self.test_pcloud_client_initialization()
        await self.test_photo_upload_tool_initialization()
        await self.test_list_photo_memories_folders()
        await self.test_find_folder()
        await self.test_create_test_folder()
        await self.test_list_folder_contents()
        await self.test_upload_file_from_bytes()
        await self.test_photo_upload_tool_validation()
        await self.test_date_parsing()
        await self.test_folder_name_sanitization()
        await self.test_mime_type_detection()
        
        # Cleanup
        await self.cleanup_test_folder()
        
        total_duration = (datetime.now() - start_time).total_seconds() * 1000
        
        # Generate report
        report = TestReport(
            total_tests=len(self.results),
            passed=sum(1 for r in self.results if r.status == "PASSED"),
            failed=sum(1 for r in self.results if r.status == "FAILED"),
            skipped=sum(1 for r in self.results if r.status == "SKIPPED"),
            errors=sum(1 for r in self.results if r.status == "ERROR"),
            duration_ms=total_duration,
            results=self.results,
            environment={
                "python_version": sys.version,
                "pcloud_username_set": "Yes" if os.getenv("PCLOUD_USERNAME") else "No",
                "pcloud_password_set": "Yes" if os.getenv("PCLOUD_PASSWORD") else "No",
                "pcloud_token_set": "Yes" if os.getenv("PCLOUD_ACCESS_TOKEN") else "No",
                "pcloud_endpoint": os.getenv("PCLOUD_ENDPOINT", "eapi"),
                "folder_id_set": "Yes" if os.getenv("PCLOUD_PHOTO_MEMORIES_FOLDER_ID") else "No"
            }
        )
        
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"  Total:   {report.total_tests}")
        print(f"  Passed:  {report.passed}")
        print(f"  Failed:  {report.failed}")
        print(f"  Skipped: {report.skipped}")
        print(f"  Errors:  {report.errors}")
        print(f"  Duration: {report.duration_ms:.2f}ms")
        print("="*70 + "\n")
        
        return report


def generate_html_report(report: TestReport, output_path: str):
    """Generate HTML report from test results."""
    
    status_colors = {
        "PASSED": "#28a745",
        "FAILED": "#dc3545",
        "SKIPPED": "#ffc107",
        "ERROR": "#dc3545"
    }
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report.title}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 20px; }}
        .header h1 {{ font-size: 24px; margin-bottom: 10px; }}
        .header .timestamp {{ opacity: 0.8; font-size: 14px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 20px; }}
        .summary-card {{ background: white; padding: 20px; border-radius: 10px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .summary-card .number {{ font-size: 36px; font-weight: bold; }}
        .summary-card .label {{ color: #666; font-size: 14px; margin-top: 5px; }}
        .passed .number {{ color: #28a745; }}
        .failed .number {{ color: #dc3545; }}
        .skipped .number {{ color: #ffc107; }}
        .errors .number {{ color: #dc3545; }}
        .results {{ background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden; }}
        .results h2 {{ background: #f8f9fa; padding: 15px 20px; border-bottom: 1px solid #dee2e6; }}
        .test-item {{ padding: 15px 20px; border-bottom: 1px solid #eee; display: flex; align-items: center; gap: 15px; }}
        .test-item:last-child {{ border-bottom: none; }}
        .status-badge {{ padding: 5px 12px; border-radius: 20px; color: white; font-size: 12px; font-weight: bold; min-width: 70px; text-align: center; }}
        .test-name {{ flex: 1; font-weight: 500; }}
        .test-duration {{ color: #666; font-size: 14px; }}
        .test-message {{ color: #666; font-size: 14px; margin-top: 5px; }}
        .test-details {{ background: #f8f9fa; padding: 10px; border-radius: 5px; margin-top: 10px; font-family: monospace; font-size: 12px; white-space: pre-wrap; }}
        .environment {{ background: white; border-radius: 10px; padding: 20px; margin-top: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .environment h2 {{ margin-bottom: 15px; }}
        .env-item {{ display: flex; gap: 10px; padding: 5px 0; }}
        .env-key {{ font-weight: bold; min-width: 200px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📷 {report.title}</h1>
            <div class="timestamp">Generated: {report.timestamp}</div>
        </div>
        
        <div class="summary">
            <div class="summary-card">
                <div class="number">{report.total_tests}</div>
                <div class="label">Total Tests</div>
            </div>
            <div class="summary-card passed">
                <div class="number">{report.passed}</div>
                <div class="label">Passed</div>
            </div>
            <div class="summary-card failed">
                <div class="number">{report.failed}</div>
                <div class="label">Failed</div>
            </div>
            <div class="summary-card skipped">
                <div class="number">{report.skipped}</div>
                <div class="label">Skipped</div>
            </div>
            <div class="summary-card errors">
                <div class="number">{report.errors}</div>
                <div class="label">Errors</div>
            </div>
            <div class="summary-card">
                <div class="number">{report.duration_ms:.0f}ms</div>
                <div class="label">Duration</div>
            </div>
        </div>
        
        <div class="results">
            <h2>Test Results</h2>
"""
    
    for result in report.results:
        color = status_colors.get(result.status, "#666")
        details_html = ""
        if result.details:
            details_html = f'<div class="test-details">{json.dumps(result.details, indent=2)}</div>'
        
        html += f"""
            <div class="test-item">
                <span class="status-badge" style="background: {color}">{result.status}</span>
                <div style="flex: 1">
                    <div class="test-name">{result.test_name}</div>
                    {f'<div class="test-message">{result.message}</div>' if result.message else ''}
                    {details_html}
                </div>
                <div class="test-duration">{result.duration_ms:.2f}ms</div>
            </div>
"""
    
    html += """
        </div>
        
        <div class="environment">
            <h2>Environment</h2>
"""
    
    for key, value in report.environment.items():
        html += f"""
            <div class="env-item">
                <span class="env-key">{key}:</span>
                <span>{value[:100]}{'...' if len(str(value)) > 100 else ''}</span>
            </div>
"""
    
    html += """
        </div>
    </div>
</body>
</html>
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"HTML report saved to: {output_path}")


async def main():
    """Main entry point."""
    # Load environment variables from .env file
    env_path = os.path.join(os.path.dirname(__file__), '..', 'Application', '.env')
    if os.path.exists(env_path):
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    
    tester = PhotoUploadAPITester()
    report = await tester.run_all_tests()
    
    # Generate HTML report
    output_dir = os.path.dirname(__file__)
    html_path = os.path.join(output_dir, 'test_photo_upload_api_report.html')
    generate_html_report(report, html_path)
    
    # Return exit code based on results
    if report.failed > 0 or report.errors > 0:
        return 1
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
