# Fleet API Client - FastAPI Implementation

Professional Python client for Fleet REST API, built with FastAPI, following SOLID principles, fully testable, and ready for LangGraph integration.

## 🎯 Features

- ✅ **FastAPI** framework for high-performance API
- ✅ **SOLID principles** implementation
- ✅ **Type-safe** with Pydantic models
- ✅ **Dependency Injection** for easy testing
- ✅ **Comprehensive error handling**
- ✅ **LangGraph integration** ready
- ✅ **Unit tests** with pytest
- ✅ **Async/await** support
- ✅ **Configuration management** with pydantic-settings

## 📁 Project Structure

```
.
├── main.py                      # FastAPI application entry point
├── config.py                    # Configuration management
├── models.py                    # Pydantic models
├── exceptions.py                # Custom exceptions
├── fleet_client.py              # Fleet API client service
├── langgraph_integration.py     # LangGraph tools and examples
├── conftest.py                  # Pytest configuration and fixtures
├── test_fleet_client.py         # Unit tests
├── requirements.txt             # Python dependencies
└── .env.example                 # Environment variables template

```

## 🚀 Quick Start

### 1. Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your Fleet API details
FLEET_API_BASE_URL=https://your-fleet-server.com
FLEET_API_TOKEN=your-api-token-here
```

### 3. Run the API

```bash
# Development mode with auto-reload
uvicorn main:app --reload

# Production mode
python main.py
```

The API will be available at: `http://localhost:8000`

API documentation:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest test_fleet_client.py

# Run only unit tests
pytest -m unit

# Run with verbose output
pytest -v
```

## 📚 Usage Examples

### Basic API Usage

```python
from fleet_client import create_fleet_client

# Create client
client = create_fleet_client(
    base_url="https://fleet.example.com",
    token="your-api-token"
)

# Authenticate
response = await client.login("user@example.com", "password")
print(f"Token: {response.token}")

# List hosts
hosts = await client.list_hosts(page=0, per_page=10)
for host in hosts:
    print(f"{host.hostname} - {host.platform} - {host.status}")

# Run a query
result = await client.run_query(
    query="SELECT * FROM processes",
    host_ids=[1, 2, 3]
)
print(f"Campaign ID: {result.campaign_id}")

# Create a label
from models import LabelCreate

label = LabelCreate(
    name="Ubuntu Hosts",
    query="SELECT 1 FROM os_version WHERE platform = 'ubuntu'",
    description="All Ubuntu hosts"
)
created_label = await client.create_label(label)
print(f"Created label: {created_label.name}")
```

### FastAPI Integration

```python
from fastapi import FastAPI, Depends
from fleet_client import FleetAPIClient, create_fleet_client

app = FastAPI()

async def get_fleet_client() -> FleetAPIClient:
    return create_fleet_client()

@app.get("/my-hosts")
async def list_my_hosts(client: FleetAPIClient = Depends(get_fleet_client)):
    return await client.list_hosts(per_page=5)
```

### LangGraph Integration

```python
from langgraph_integration import (
    list_fleet_hosts,
    get_fleet_host_details,
    run_fleet_query,
    FLEET_TOOLS
)

# Use as LangGraph tools
async def main():
    # List hosts
    result = await list_fleet_hosts(page=0, per_page=10)
    print(result)
    
    # Get specific host
    host_details = await get_fleet_host_details(host_id=1)
    print(host_details)
    
    # Run query
    query_result = await run_fleet_query(
        query="SELECT * FROM system_info",
        host_ids=[1, 2]
    )
    print(query_result)

# Run example
import asyncio
asyncio.run(main())
```

## 🏗️ Architecture & SOLID Principles

### Single Responsibility Principle (SRP)
- `FleetAPIClient`: Handles only Fleet API operations
- `HTTPXClient`: Handles only HTTP communication
- `Settings`: Handles only configuration

### Open/Closed Principle (OCP)
- `HTTPClientInterface`: Abstract interface for HTTP clients
- Easy to extend with new implementations without modifying existing code

### Liskov Substitution Principle (LSP)
- Any `HTTPClientInterface` implementation can be substituted
- `MockHTTPClient` in tests substitutes `HTTPXClient`

### Interface Segregation Principle (ISP)
- Focused interfaces for specific responsibilities
- Clients depend only on methods they use

### Dependency Inversion Principle (DIP)
- High-level modules (FleetAPIClient) depend on abstractions (HTTPClientInterface)
- Dependencies are injected, not hardcoded

## 🔧 Advanced Configuration

### Custom HTTP Client

```python
from fleet_client import FleetAPIClient, HTTPClientInterface

class CustomHTTPClient(HTTPClientInterface):
    async def get(self, url: str, **kwargs):
        # Custom implementation
        pass
    
    # Implement other methods...

# Use custom client
client = FleetAPIClient(
    http_client=CustomHTTPClient(),
    settings=my_settings
)
```

### Environment Variables

All configuration can be set via environment variables:

```bash
# Fleet Configuration
FLEET_API_BASE_URL=https://fleet.example.com
FLEET_API_TOKEN=your-token

# Application
APP_NAME="My Fleet App"
DEBUG=True
LOG_LEVEL=INFO

# Server
HOST=0.0.0.0
PORT=8000

# Security
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## 🔐 Security Best Practices

1. **Never commit** `.env` file with real credentials
2. **Use environment variables** in production
3. **Rotate API tokens** regularly
4. **Enable HTTPS** in production
5. **Implement rate limiting** (configured in settings)

## 📊 API Endpoints

### Authentication
- `POST /api/auth/login` - Login and get token
- `POST /api/auth/logout` - Logout
- `GET /api/auth/me` - Get current user
- `POST /api/auth/change-password` - Change password
- `POST /api/auth/forgot-password` - Request password reset

### Hosts
- `GET /api/hosts` - List hosts
- `GET /api/hosts/{id}` - Get host details
- `DELETE /api/hosts/{id}` - Delete host

### Queries
- `POST /api/queries/run` - Run live query

### Labels
- `GET /api/labels` - List labels
- `POST /api/labels` - Create label
- `DELETE /api/labels/{id}` - Delete label

### Policies
- `GET /api/policies` - List policies
- `POST /api/policies` - Create policy
- `DELETE /api/policies/{id}` - Delete policy

### Teams
- `GET /api/teams` - List teams
- `POST /api/teams` - Create team
- `DELETE /api/teams/{id}` - Delete team

### Custom Variables
- `GET /api/custom-variables` - List variables
- `POST /api/custom-variables` - Create variable
- `DELETE /api/custom-variables/{id}` - Delete variable

## 🤝 Contributing

1. Follow SOLID principles
2. Add tests for new features
3. Update documentation
4. Use type hints
5. Follow PEP 8 style guide

## 📝 License

MIT License - feel free to use in your projects!

## 🆘 Support

For issues or questions:
1. Check the Fleet API documentation
2. Review the test files for examples
3. Open an issue with detailed information

## 🎓 Learning Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Fleet API Documentation](https://fleetdm.com/docs/rest-api)

---

Built with ❤️ using FastAPI, following SOLID principles, and ready for AI agent integration!
