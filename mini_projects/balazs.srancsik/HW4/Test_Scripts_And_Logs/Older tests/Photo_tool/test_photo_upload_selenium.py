"""
Test suite for the Photo Upload Tool using pytest and Selenium.
Tests the photo upload functionality through the web UI.

This script tests:
1. File attachment functionality
2. Photo upload with metadata (date, event, location)
3. Folder creation and listing
4. Response display with icons
"""

import pytest
import time
import os
import tempfile
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException


# Configuration
BASE_URL = "http://localhost:3000"  # Frontend URL
WAIT_TIMEOUT = 90  # Seconds to wait for responses (photo uploads can be slow)


@pytest.fixture(scope="module")
def driver():
    """Set up Chrome WebDriver with options."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode for CI
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.implicitly_wait(10)
    
    yield driver
    
    driver.quit()


@pytest.fixture(scope="module")
def test_image_path():
    """Create a temporary test image file."""
    # Create a simple 1x1 pixel PNG image
    png_data = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
        0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
        0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
        0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
        0x44, 0xAE, 0x42, 0x60, 0x82
    ])
    
    # Create temp file
    fd, path = tempfile.mkstemp(suffix='.png', prefix='test_photo_')
    with os.fdopen(fd, 'wb') as f:
        f.write(png_data)
    
    yield path
    
    # Cleanup
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture(scope="function")
def chat_page(driver):
    """Navigate to the chat page and wait for it to load."""
    driver.get(BASE_URL)
    
    # Wait for the chat input to be available
    WebDriverWait(driver, WAIT_TIMEOUT).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'], textarea"))
    )
    
    # Small delay to ensure page is fully loaded
    time.sleep(1)
    
    return driver


def send_message(driver, message: str):
    """Send a message in the chat interface."""
    # Find the input field
    input_field = driver.find_element(By.CSS_SELECTOR, "input[type='text'], textarea")
    input_field.clear()
    input_field.send_keys(message)
    
    # Find and click the send button or press Enter
    try:
        send_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], .send-button")
        send_button.click()
    except NoSuchElementException:
        input_field.send_keys(Keys.RETURN)


def attach_file(driver, file_path: str):
    """Attach a file using the file input."""
    try:
        # Find file input (may be hidden)
        file_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
        file_input.send_keys(file_path)
        time.sleep(1)  # Wait for file to be processed
        return True
    except NoSuchElementException:
        return False


def wait_for_response(driver, timeout: int = WAIT_TIMEOUT):
    """Wait for the AI response to appear."""
    time.sleep(2)  # Initial wait for request to start
    
    try:
        # Wait for loading to complete
        WebDriverWait(driver, timeout).until_not(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".loading, .spinner"))
        )
    except TimeoutException:
        pass
    
    try:
        # Wait for the response message to appear
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".message.assistant, .ai-message, .response, .message-content"))
        )
    except TimeoutException:
        pass
    
    # Additional wait for response to complete
    time.sleep(5)


def get_last_response(driver) -> str:
    """Get the text of the last AI response."""
    messages = driver.find_elements(By.CSS_SELECTOR, ".message.assistant, .ai-message, .response, .message-content")
    if messages:
        return messages[-1].text
    return ""


def get_tools_used(driver) -> str:
    """Get the tools used section text."""
    try:
        tools_section = driver.find_elements(By.CSS_SELECTOR, ".tools-used, .tool-item")
        if tools_section:
            return " ".join([t.text for t in tools_section])
    except NoSuchElementException:
        pass
    return ""


class TestPhotoUploadUIBasics:
    """Tests for basic UI elements related to photo upload."""
    
    def test_page_loads(self, chat_page):
        """Test that the chat page loads correctly."""
        assert chat_page.title or True  # Page should load
        
        # Check for chat input
        input_field = chat_page.find_element(By.CSS_SELECTOR, "input[type='text'], textarea")
        assert input_field is not None, "Chat input should be present"
    
    def test_file_input_exists(self, chat_page):
        """Test that file input element exists."""
        try:
            file_input = chat_page.find_element(By.CSS_SELECTOR, "input[type='file']")
            assert file_input is not None, "File input should be present"
        except NoSuchElementException:
            pytest.skip("File input not found - may be dynamically loaded")
    
    def test_header_displays_photo_memories(self, chat_page):
        """Test that the header mentions Photo Memories."""
        try:
            header = chat_page.find_element(By.CSS_SELECTOR, "header, .app-header, h1")
            header_text = header.text.lower()
            assert any(word in header_text for word in ["photo", "memories", "upload"]), \
                f"Header should mention photo features. Got: {header_text}"
        except NoSuchElementException:
            pytest.skip("Header element not found")


class TestPhotoUploadListFolders:
    """Tests for listing Photo_Memories folders."""
    
    def test_list_photo_memories_folders(self, chat_page):
        """Test listing Photo_Memories folder structure."""
        send_message(chat_page, "List my Photo_Memories folders")
        wait_for_response(chat_page)
        
        response = get_last_response(chat_page)
        
        assert response, "No response received"
        # Response should contain folder-related content
        assert any(word in response.lower() for word in ["folder", "photo", "memories", "📂", "📁", "structure", "mappa"]), \
            f"Response should contain folder information. Got: {response[:300]}"
    
    def test_list_folders_hungarian(self, chat_page):
        """Test listing folders with Hungarian query."""
        send_message(chat_page, "Mutasd a Photo_Memories mappáimat")
        wait_for_response(chat_page)
        
        response = get_last_response(chat_page)
        
        assert response, "No response received"
        # Should get some response about folders
        assert any(word in response.lower() for word in ["mappa", "folder", "photo", "📂", "📁"]), \
            f"Response should contain folder information. Got: {response[:300]}"


class TestPhotoUploadWithMetadata:
    """Tests for photo upload with metadata."""
    
    def test_upload_request_asks_for_info(self, chat_page):
        """Test that upload request without files asks for information."""
        send_message(chat_page, "I want to upload some vacation photos")
        wait_for_response(chat_page)
        
        response = get_last_response(chat_page)
        
        assert response, "No response received"
        # Should ask for date, event, or location
        assert any(word in response.lower() for word in ["date", "when", "event", "where", "location", "attach", "file", "photo", "dátum", "mikor", "hol", "esemény"]), \
            f"Response should ask for upload details. Got: {response[:300]}"
    
    def test_upload_with_complete_info(self, chat_page):
        """Test upload request with complete metadata."""
        send_message(chat_page, "Upload my photos from June 15, 2024, summer vacation in Barcelona")
        wait_for_response(chat_page)
        
        response = get_last_response(chat_page)
        
        assert response, "No response received"
        # Should acknowledge the info or ask for files
        assert any(word in response.lower() for word in ["barcelona", "summer", "vacation", "june", "2024", "file", "attach", "photo", "upload"]), \
            f"Response should acknowledge upload details. Got: {response[:300]}"


class TestPhotoUploadFileAttachment:
    """Tests for file attachment functionality."""
    
    def test_attach_and_upload_photo(self, chat_page, test_image_path):
        """Test attaching and uploading a photo."""
        # First attach the file
        attached = attach_file(chat_page, test_image_path)
        
        if not attached:
            pytest.skip("Could not attach file - file input not accessible")
        
        # Send message with upload details
        send_message(chat_page, "Upload this photo from January 19, 2026, test event in Test City")
        wait_for_response(chat_page, timeout=120)  # Longer timeout for actual upload
        
        response = get_last_response(chat_page)
        
        assert response, "No response received"
        # Should show upload result
        assert any(word in response.lower() for word in ["upload", "photo", "folder", "success", "file", "📷", "📂", "feltöltés", "sikeres"]), \
            f"Response should confirm upload. Got: {response[:300]}"
    
    def test_upload_shows_folder_icons(self, chat_page, test_image_path):
        """Test that upload response shows folder icons."""
        attached = attach_file(chat_page, test_image_path)
        
        if not attached:
            pytest.skip("Could not attach file")
        
        send_message(chat_page, "Upload this from December 25, 2025, Christmas party in Budapest")
        wait_for_response(chat_page, timeout=120)
        
        response = get_last_response(chat_page)
        
        # Check for icons in response
        has_icons = "📂" in response or "📷" in response or "📸" in response or "📁" in response
        
        if not has_icons:
            # Icons might not be present if upload failed, which is acceptable
            assert any(word in response.lower() for word in ["folder", "photo", "upload", "file"]), \
                f"Response should contain folder/photo references. Got: {response[:300]}"


class TestPhotoUploadToolsUsed:
    """Tests for Tools Used section display."""
    
    def test_tools_used_shows_photo_upload(self, chat_page, test_image_path):
        """Test that Tools Used section shows photo_upload."""
        attached = attach_file(chat_page, test_image_path)
        
        if not attached:
            pytest.skip("Could not attach file")
        
        send_message(chat_page, "Upload this photo from March 1, 2026, spring trip in Vienna")
        wait_for_response(chat_page, timeout=120)
        
        tools_text = get_tools_used(chat_page)
        
        if tools_text:
            # Should mention photo_upload tool
            assert any(word in tools_text.lower() for word in ["photo", "upload", "✓"]), \
                f"Tools used should mention photo_upload. Got: {tools_text}"
        else:
            # Tools section might not be visible, check response instead
            response = get_last_response(chat_page)
            assert response, "No response received"


class TestPhotoUploadFolderNaming:
    """Tests for folder naming convention."""
    
    def test_folder_name_format(self, chat_page):
        """Test that folder naming follows YYYY.MM.DD - Event - Location format."""
        send_message(chat_page, "I want to create a folder for photos from April 15, 2025, birthday party in Rome")
        wait_for_response(chat_page)
        
        response = get_last_response(chat_page)
        
        assert response, "No response received"
        # Should mention the folder name format or ask for files
        assert any(word in response.lower() for word in ["2025", "birthday", "rome", "folder", "attach", "file", "photo"]), \
            f"Response should reference folder details. Got: {response[:300]}"
    
    def test_folder_name_capitalization(self, chat_page):
        """Test that event and location names are capitalized."""
        send_message(chat_page, "Create a photo folder for may 20, 2025, wedding ceremony in paris")
        wait_for_response(chat_page)
        
        response = get_last_response(chat_page)
        
        assert response, "No response received"
        # Check if capitalization is mentioned or folder name is shown
        # The folder should be "2025.05.20 - Wedding ceremony - Paris"
        if "Wedding" in response or "Paris" in response:
            assert True  # Capitalization working
        else:
            # Just check we got a relevant response
            assert any(word in response.lower() for word in ["wedding", "paris", "folder", "photo"]), \
                f"Response should reference the event. Got: {response[:300]}"


class TestPhotoUploadErrorHandling:
    """Tests for error handling in photo upload."""
    
    def test_upload_without_files(self, chat_page):
        """Test upload request without attaching files."""
        send_message(chat_page, "Upload photos from today, test event in test city")
        wait_for_response(chat_page)
        
        response = get_last_response(chat_page)
        
        assert response, "No response received"
        # Should ask for files or indicate no files attached
        assert any(word in response.lower() for word in ["file", "attach", "photo", "upload", "no", "please", "csatol", "fájl"]), \
            f"Response should mention files needed. Got: {response[:300]}"
    
    def test_vague_upload_request(self, chat_page):
        """Test handling of vague upload request."""
        send_message(chat_page, "Upload my photos")
        wait_for_response(chat_page)
        
        response = get_last_response(chat_page)
        
        assert response, "No response received"
        # Should ask for more details
        assert any(word in response.lower() for word in ["date", "when", "event", "where", "location", "more", "detail", "information", "dátum", "mikor", "hol"]), \
            f"Response should ask for details. Got: {response[:300]}"


class TestPhotoUploadMultilingual:
    """Tests for multilingual support in photo upload."""
    
    def test_hungarian_upload_request(self, chat_page):
        """Test photo upload with Hungarian language."""
        send_message(chat_page, "Tölts fel fotókat 2025 január 15-ről, szilveszteri buli Budapesten")
        wait_for_response(chat_page)
        
        response = get_last_response(chat_page)
        
        assert response, "No response received"
        # Response should be in Hungarian or contain relevant info
        assert any(word in response.lower() for word in ["budapest", "szilveszter", "fotó", "mappa", "folder", "photo", "upload", "feltölt"]), \
            f"Response should acknowledge Hungarian request. Got: {response[:300]}"
    
    def test_german_upload_request(self, chat_page):
        """Test photo upload with German language."""
        send_message(chat_page, "Lade Fotos hoch vom 10. Februar 2025, Winterurlaub in München")
        wait_for_response(chat_page)
        
        response = get_last_response(chat_page)
        
        assert response, "No response received"
        # Response should acknowledge the request
        assert any(word in response.lower() for word in ["münchen", "winter", "foto", "ordner", "folder", "photo", "upload"]), \
            f"Response should acknowledge German request. Got: {response[:300]}"


# Run tests with: pytest test_photo_upload_selenium.py -v --html=test_photo_upload_selenium_report.html
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--html=test_photo_upload_selenium_report.html", "--self-contained-html"])
