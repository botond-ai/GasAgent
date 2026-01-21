# Test Coverage

Test suite for the AI Weather Agent project.

## Test Structure

```
tests/
├── __init__.py
├── test_geocode.py      # Unit tests for geocoding tool
├── test_weather.py      # Unit tests for weather tool
├── test_agent.py        # Integration tests for agent graph
└── test_api.py          # API endpoint tests
```

## Running Tests

### Run all tests:
```bash
cd /opt/hw3
source venv/bin/activate
pytest
```

### Run specific test file:
```bash
pytest tests/test_geocode.py
pytest tests/test_weather.py
pytest tests/test_agent.py
pytest tests/test_api.py
```

### Run with verbose output:
```bash
pytest -v
```

### Run with coverage:
```bash
pip install pytest-cov
pytest --cov=src --cov-report=html
```

### Run specific test:
```bash
pytest tests/test_geocode.py::TestGeocodeCity::test_geocode_success
```

## Test Categories

### Unit Tests

**test_geocode.py** - Geocoding tool tests:
- ✅ Successful city geocoding
- ✅ City not found handling
- ✅ API error handling
- ✅ Timeout handling
- ✅ Country filter
- ✅ Pydantic model validation

**test_weather.py** - Weather tool tests:
- ✅ Successful weather retrieval
- ✅ Missing API key handling
- ✅ Invalid API key handling
- ✅ API error handling
- ✅ Timeout handling
- ✅ Different units support
- ✅ Pydantic model validation

### Integration Tests

**test_agent.py** - Agent graph tests:
- ✅ Read user prompt node
- ✅ Decision node (call tool / final answer)
- ✅ Tool node (geocode / weather execution)
- ✅ Answer node
- ✅ Router logic (should_continue)
- ✅ Max iterations handling
- ✅ Error handling and fallbacks

### API Tests

**test_api.py** - Flask API tests:
- ✅ Health check endpoint
- ✅ Ask endpoint success
- ✅ Missing/empty question validation
- ✅ Invalid JSON handling
- ✅ Agent error handling
- ✅ CORS headers
- ✅ HTTP method validation

## Test Features

- **Mocking**: External API calls mocked with `responses` library
- **Fixtures**: Test client fixtures for Flask app
- **Parametrization**: Multiple test cases with different inputs
- **Error handling**: Tests for all error scenarios
- **Edge cases**: Empty inputs, timeouts, invalid data

## Coverage Goals

Current test coverage includes:
- Tools: geocode.py, weather.py
- Agent: graph.py (nodes and routing)
- API: api.py (all endpoints)
- Models: state.py (Pydantic models)

## Writing New Tests

Example test structure:

```python
import pytest
from unittest.mock import patch

class TestMyFeature:
    """Test cases for my feature."""
    
    def test_success_case(self):
        """Test successful execution."""
        # Arrange
        input_data = "test"
        
        # Act
        result = my_function(input_data)
        
        # Assert
        assert result == expected
    
    @patch('module.external_api')
    def test_with_mock(self, mock_api):
        """Test with mocked dependency."""
        mock_api.return_value = "mocked response"
        
        result = my_function()
        
        assert result == "expected"
        mock_api.assert_called_once()
```

## Continuous Integration

Tests can be integrated into CI/CD pipelines:

```yaml
# .github/workflows/test.yml
- name: Run tests
  run: |
    pip install -r requirements.txt
    pytest --cov=src --cov-report=xml
```

## Debugging Tests

Run with debugging output:
```bash
pytest -vv -s  # -s shows print statements
pytest --pdb   # Drop into debugger on failure
```
