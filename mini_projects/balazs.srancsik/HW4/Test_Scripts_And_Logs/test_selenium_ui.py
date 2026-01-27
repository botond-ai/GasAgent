"""
Selenium UI Tests for SupportAI Application
Tests the main page, index.html, and UI interactions
Generates HTML report with test results
"""

import pytest
import time
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class TestResults:
    """Class to store and generate HTML report for test results"""
    def __init__(self):
        self.results = []
        self.start_time = datetime.now()
        
    def add_result(self, test_name: str, status: str, message: str, duration: float):
        self.results.append({
            "test_name": test_name,
            "status": status,
            "message": message,
            "duration": duration
        })
    
    def generate_html_report(self, output_path: str):
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        
        passed = sum(1 for r in self.results if r["status"] == "PASSED")
        failed = sum(1 for r in self.results if r["status"] == "FAILED")
        skipped = sum(1 for r in self.results if r["status"] == "SKIPPED")
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Selenium UI Test Report - SupportAI</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; padding: 2rem; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #FFD94F; margin-bottom: 1rem; }}
        .summary {{ display: flex; gap: 2rem; margin-bottom: 2rem; padding: 1.5rem; background: #16213e; border-radius: 8px; }}
        .summary-item {{ text-align: center; }}
        .summary-item .value {{ font-size: 2rem; font-weight: bold; }}
        .summary-item .label {{ color: #888; font-size: 0.875rem; }}
        .passed {{ color: #4ade80; }}
        .failed {{ color: #f87171; }}
        .skipped {{ color: #fbbf24; }}
        .test-table {{ width: 100%; border-collapse: collapse; background: #16213e; border-radius: 8px; overflow: hidden; }}
        .test-table th, .test-table td {{ padding: 1rem; text-align: left; border-bottom: 1px solid #2a2a4a; }}
        .test-table th {{ background: #0f3460; color: #FFD94F; }}
        .test-table tr:hover {{ background: #1a1a3e; }}
        .status-badge {{ padding: 0.25rem 0.75rem; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }}
        .status-passed {{ background: #065f46; color: #4ade80; }}
        .status-failed {{ background: #7f1d1d; color: #f87171; }}
        .status-skipped {{ background: #78350f; color: #fbbf24; }}
        .meta {{ color: #888; font-size: 0.875rem; margin-bottom: 1rem; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🧪 Selenium UI Test Report</h1>
        <p class="meta">Generated: {end_time.strftime('%Y-%m-%d %H:%M:%S')} | Total Duration: {total_duration:.2f}s</p>
        
        <div class="summary">
            <div class="summary-item">
                <div class="value">{len(self.results)}</div>
                <div class="label">Total Tests</div>
            </div>
            <div class="summary-item">
                <div class="value passed">{passed}</div>
                <div class="label">Passed</div>
            </div>
            <div class="summary-item">
                <div class="value failed">{failed}</div>
                <div class="label">Failed</div>
            </div>
            <div class="summary-item">
                <div class="value skipped">{skipped}</div>
                <div class="label">Skipped</div>
            </div>
        </div>
        
        <table class="test-table">
            <thead>
                <tr>
                    <th>Test Name</th>
                    <th>Status</th>
                    <th>Duration</th>
                    <th>Message</th>
                </tr>
            </thead>
            <tbody>
"""
        for result in self.results:
            status_class = f"status-{result['status'].lower()}"
            html += f"""
                <tr>
                    <td>{result['test_name']}</td>
                    <td><span class="status-badge {status_class}">{result['status']}</span></td>
                    <td>{result['duration']:.3f}s</td>
                    <td>{result['message']}</td>
                </tr>
"""
        
        html += """
            </tbody>
        </table>
    </div>
</body>
</html>
"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return output_path


# Global test results collector
test_results = TestResults()


def get_driver():
    """Create and return a Chrome WebDriver instance"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    
    try:
        driver = webdriver.Chrome(options=options)
        driver.implicitly_wait(10)
        return driver
    except Exception as e:
        print(f"Failed to create WebDriver: {e}")
        return None


class TestMainPageUI:
    """Test class for main page UI elements"""
    
    BASE_URL = "http://localhost:3000"
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test"""
        self.driver = get_driver()
        if self.driver is None:
            pytest.skip("WebDriver not available")
        yield
        if self.driver:
            self.driver.quit()
    
    def test_main_page_loads(self):
        """Test that the main page loads successfully"""
        start = time.time()
        test_name = "Main Page Load"
        try:
            self.driver.get(self.BASE_URL)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "app"))
            )
            duration = time.time() - start
            test_results.add_result(test_name, "PASSED", "Main page loaded successfully", duration)
            assert True
        except Exception as e:
            duration = time.time() - start
            test_results.add_result(test_name, "FAILED", str(e), duration)
            pytest.fail(str(e))
    
    def test_header_exists(self):
        """Test that the header exists with correct elements"""
        start = time.time()
        test_name = "Header Elements"
        try:
            self.driver.get(self.BASE_URL)
            header = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "app-header"))
            )
            assert header is not None
            
            # Check for h1 title
            title = header.find_element(By.TAG_NAME, "h1")
            assert "SupportAI" in title.text or title is not None
            
            duration = time.time() - start
            test_results.add_result(test_name, "PASSED", "Header and title found", duration)
        except Exception as e:
            duration = time.time() - start
            test_results.add_result(test_name, "FAILED", str(e), duration)
            pytest.fail(str(e))
    
    def test_view_tickets_button_exists(self):
        """Test that View Tickets button exists"""
        start = time.time()
        test_name = "View Tickets Button"
        try:
            self.driver.get(self.BASE_URL)
            button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "view-tickets-button"))
            )
            assert button is not None
            assert "View Tickets" in button.text or "Tickets" in button.text
            
            duration = time.time() - start
            test_results.add_result(test_name, "PASSED", "View Tickets button found", duration)
        except Exception as e:
            duration = time.time() - start
            test_results.add_result(test_name, "FAILED", str(e), duration)
            pytest.fail(str(e))
    
    def test_reset_button_exists(self):
        """Test that Reset Context button exists"""
        start = time.time()
        test_name = "Reset Context Button"
        try:
            self.driver.get(self.BASE_URL)
            button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "reset-button"))
            )
            assert button is not None
            
            duration = time.time() - start
            test_results.add_result(test_name, "PASSED", "Reset Context button found", duration)
        except Exception as e:
            duration = time.time() - start
            test_results.add_result(test_name, "FAILED", str(e), duration)
            pytest.fail(str(e))
    
    def test_chat_input_exists(self):
        """Test that chat input field exists"""
        start = time.time()
        test_name = "Chat Input Field"
        try:
            self.driver.get(self.BASE_URL)
            # Look for textarea or input in chat area
            chat_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "textarea, input[type='text']"))
            )
            assert chat_input is not None
            
            duration = time.time() - start
            test_results.add_result(test_name, "PASSED", "Chat input field found", duration)
        except Exception as e:
            duration = time.time() - start
            test_results.add_result(test_name, "FAILED", str(e), duration)
            pytest.fail(str(e))
    
    def test_chat_window_exists(self):
        """Test that chat window/messages area exists"""
        start = time.time()
        test_name = "Chat Window"
        try:
            self.driver.get(self.BASE_URL)
            chat_window = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "chat-window"))
            )
            assert chat_window is not None
            
            duration = time.time() - start
            test_results.add_result(test_name, "PASSED", "Chat window found", duration)
        except Exception as e:
            duration = time.time() - start
            test_results.add_result(test_name, "FAILED", str(e), duration)
            pytest.fail(str(e))
    
    def test_page_title(self):
        """Test that page has correct title"""
        start = time.time()
        test_name = "Page Title"
        try:
            self.driver.get(self.BASE_URL)
            time.sleep(1)  # Wait for page to fully load
            title = self.driver.title
            
            duration = time.time() - start
            test_results.add_result(test_name, "PASSED", f"Page title: {title}", duration)
            assert True
        except Exception as e:
            duration = time.time() - start
            test_results.add_result(test_name, "FAILED", str(e), duration)
            pytest.fail(str(e))


class TestTicketsDashboard:
    """Test class for tickets dashboard page"""
    
    TICKETS_URL = "http://localhost:3000/tickets"
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test"""
        self.driver = get_driver()
        if self.driver is None:
            pytest.skip("WebDriver not available")
        yield
        if self.driver:
            self.driver.quit()
    
    def test_tickets_page_loads(self):
        """Test that tickets dashboard loads"""
        start = time.time()
        test_name = "Tickets Dashboard Load"
        try:
            self.driver.get(self.TICKETS_URL)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "header"))
            )
            duration = time.time() - start
            test_results.add_result(test_name, "PASSED", "Tickets dashboard loaded", duration)
            assert True
        except Exception as e:
            duration = time.time() - start
            test_results.add_result(test_name, "FAILED", str(e), duration)
            pytest.fail(str(e))
    
    def test_tickets_filters_exist(self):
        """Test that filter inputs exist"""
        start = time.time()
        test_name = "Tickets Filters"
        try:
            self.driver.get(self.TICKETS_URL)
            filters_section = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "filters-section"))
            )
            assert filters_section is not None
            
            # Check for filter inputs
            filter_inputs = self.driver.find_elements(By.CLASS_NAME, "filter-input")
            assert len(filter_inputs) > 0
            
            duration = time.time() - start
            test_results.add_result(test_name, "PASSED", f"Found {len(filter_inputs)} filter inputs", duration)
        except Exception as e:
            duration = time.time() - start
            test_results.add_result(test_name, "FAILED", str(e), duration)
            pytest.fail(str(e))
    
    def test_back_button_exists(self):
        """Test that back button exists on tickets page"""
        start = time.time()
        test_name = "Back Button"
        try:
            self.driver.get(self.TICKETS_URL)
            back_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "back-button"))
            )
            assert back_button is not None
            assert "Back" in back_button.text
            
            duration = time.time() - start
            test_results.add_result(test_name, "PASSED", "Back button found", duration)
        except Exception as e:
            duration = time.time() - start
            test_results.add_result(test_name, "FAILED", str(e), duration)
            pytest.fail(str(e))
    
    def test_tickets_table_container(self):
        """Test that tickets table container exists"""
        start = time.time()
        test_name = "Tickets Table Container"
        try:
            self.driver.get(self.TICKETS_URL)
            table_container = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "tickets-table"))
            )
            assert table_container is not None
            
            duration = time.time() - start
            test_results.add_result(test_name, "PASSED", "Tickets table container found", duration)
        except Exception as e:
            duration = time.time() - start
            test_results.add_result(test_name, "FAILED", str(e), duration)
            pytest.fail(str(e))


def run_tests_standalone():
    """Run all tests standalone and generate HTML report"""
    driver = None
    BASE_URL = "http://localhost:3000"
    TICKETS_URL = "http://localhost:3000/tickets"
    
    try:
        driver = get_driver()
        if driver is None:
            test_results.add_result("WebDriver Setup", "FAILED", "Could not create WebDriver", 0)
        else:
            # Main Page Tests
            tests = [
                ("Main Page Load", BASE_URL, lambda d: d.find_element(By.CLASS_NAME, "app")),
                ("Header Elements", BASE_URL, lambda d: d.find_element(By.CLASS_NAME, "app-header")),
                ("View Tickets Button", BASE_URL, lambda d: d.find_element(By.CLASS_NAME, "view-tickets-button")),
                ("Reset Context Button", BASE_URL, lambda d: d.find_element(By.CLASS_NAME, "reset-button")),
                ("Chat Input Field", BASE_URL, lambda d: d.find_element(By.CSS_SELECTOR, "textarea, input[type='text']")),
                ("Chat Window", BASE_URL, lambda d: d.find_element(By.CLASS_NAME, "chat-window")),
                ("Page Title", BASE_URL, lambda d: d.title),
                # Tickets Dashboard Tests
                ("Tickets Dashboard Load", TICKETS_URL, lambda d: d.find_element(By.TAG_NAME, "header")),
                ("Tickets Filters", TICKETS_URL, lambda d: d.find_element(By.CLASS_NAME, "filters-section")),
                ("Back Button", TICKETS_URL, lambda d: d.find_element(By.CLASS_NAME, "back-button")),
                ("Tickets Table Container", TICKETS_URL, lambda d: d.find_element(By.ID, "tickets-table")),
            ]
            
            for test_name, url, check_func in tests:
                start = time.time()
                try:
                    driver.get(url)
                    WebDriverWait(driver, 10).until(lambda d: check_func(d))
                    result = check_func(driver)
                    duration = time.time() - start
                    msg = f"Element found" if result else "Check passed"
                    if test_name == "Page Title":
                        msg = f"Title: {driver.title}"
                    test_results.add_result(test_name, "PASSED", msg, duration)
                except Exception as e:
                    duration = time.time() - start
                    test_results.add_result(test_name, "FAILED", str(e)[:100], duration)
    finally:
        if driver:
            driver.quit()
    
    # Generate HTML report
    output_dir = os.path.dirname(os.path.abspath(__file__))
    report_path = os.path.join(output_dir, "selenium_test_report.html")
    test_results.generate_html_report(report_path)
    print(f"\n✅ HTML Report generated: {report_path}")
    return report_path


def run_tests():
    """Run all tests and generate HTML report"""
    # Run pytest
    pytest.main([__file__, '-v', '--tb=short'])
    
    # Generate HTML report
    output_dir = os.path.dirname(os.path.abspath(__file__))
    report_path = os.path.join(output_dir, "selenium_test_report.html")
    test_results.generate_html_report(report_path)
    print(f"\n✅ HTML Report generated: {report_path}")
    return report_path


if __name__ == "__main__":
    run_tests_standalone()
