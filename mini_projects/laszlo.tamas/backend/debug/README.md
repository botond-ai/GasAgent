# Debug & Diagnostic Scripts

This directory contains **debug-only** scripts used for development, testing, and diagnostics.

## 📋 **CONSTITUTION COMPLIANCE**

Per [`AGENT_CONSTITUTION.md`](../../docs/AGENT_CONSTITUTION.md) Section 6.4:
> "minden `test_` prefixú fájl [...] **KÖTELEZŐEN** a `debug/` könyvtárba kerül"

All `test_*.py` and `check_*.py` files are **NOT required for runtime** and exist here for:
- Database schema verification
- Qdrant connection testing
- Document processing diagnostics
- Manual data inspection

## 🚫 **DO NOT USE IN PRODUCTION**

These scripts:
- Are NOT imported by `main.py` or any service
- Do NOT run automatically in Docker containers
- Should be executed **manually** for troubleshooting only

## 📁 **File Inventory**

### Diagnostic Scripts (check_*.py)
| File | Purpose |
|------|---------|
| `check_db_structure.py` | Verify PostgreSQL schema structure |
| `check_di_syntax.py` | Validate DI configuration syntax |
| `check_docs_chunks.py` | List document chunks in DB |
| `check_document_chunks_encoding.py` | Verify chunk encoding/decoding |
| `check_document_content.py` | Inspect document content by ID |
| `check_encoding.py` | Check text encoding issues |
| `check_messages.py` | View messages in database |
| `check_qdrant_data.py` | Inspect Qdrant collection contents |
| `check_session.py` | View session chat history |
| `check_user.py` | Query user data from PostgreSQL |

### Service Verification
| File | Purpose |
|------|---------|
| `test_qdrant_connection.py` | Test Qdrant client connection |
| `test_postgres_timeout.py` | Test PostgreSQL timeout configuration |
| `test_di_implementation.py` | Verify DI container setup |
| `test_service_injection.py` | Test service injection patterns |

### Manual Testing Utilities
| File | Purpose |
|------|---------|
| `test_chat_sequence.py` | Sequential chat test runner with metrics |
| `test_questions.md` | Test questions for chat testing |
| `test_api_endpoints.py` | Comprehensive API endpoint tester |

### Load Testing
| File | Purpose |
|------|---------|
| `load_test_chat.py` | Locust load test for chat API |
| `run_load_test.ps1` | PowerShell script to run load tests |
| `README_LOAD_TESTING.md` | Load testing documentation |

## 🔧 **Usage**

Run scripts manually from backend directory:
```bash
# Example: Check Qdrant connection
docker-compose exec backend python debug/test_qdrant_connection.py

# Example: Verify database structure
docker-compose exec backend python debug/check_db_structure.py

# Example: Run sequential chat tests
python debug/test_chat_sequence.py -n 5
```

---

**Last Updated:** 2026-01-20
