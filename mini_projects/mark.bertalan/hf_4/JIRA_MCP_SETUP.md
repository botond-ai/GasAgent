# Jira MCP Integration Guide

This guide explains how to set up and use the **Jira MCP (Model Context Protocol)** integration for enhanced Jira operations with automatic duplicate detection.

## Table of Contents
- [What is MCP?](#what-is-mcp)
- [Benefits Over REST API](#benefits-over-rest-api)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Features](#features)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Fallback Mode](#fallback-mode)

---

## What is MCP?

**Model Context Protocol (MCP)** is a standardized protocol for integrating external services with AI applications. The Jira MCP server provides:

- Structured, typed access to Jira APIs
- Built-in error handling and retries
- Automatic rate limiting
- Duplicate detection
- Better logging and observability

Instead of making raw HTTP requests to Jira, MCP provides a clean, reliable interface.

---

## Benefits Over REST API

| Feature | REST API | MCP |
|---------|----------|-----|
| Duplicate Detection | ❌ Manual | ✅ Automatic |
| Error Handling | ❌ Manual | ✅ Built-in |
| Rate Limiting | ❌ Manual | ✅ Automatic |
| Retries | ❌ Manual | ✅ Built-in |
| Type Safety | ❌ None | ✅ Strong |
| Search Similar Issues | ❌ Manual JQL | ✅ One method call |
| Logging | ⚠️ Basic | ✅ Comprehensive |
| Authentication | ⚠️ Manual tokens | ✅ Handled |

### Example: Creating a Ticket

**REST API** (old way):
```python
# Manual HTTP request
headers = {"Authorization": f"Basic {base64_token}"}
payload = {"fields": {...}}
response = requests.post(url, headers=headers, json=payload)
# Manual error handling
if response.status_code != 200:
    # Handle error...
# No duplicate checking!
```

**MCP** (new way):
```python
# Simple, clean, with duplicate detection
async with JiraMCPClient(...) as client:
    result = await client.create_issue(
        project_key="DEV",
        summary=summary,
        check_duplicates=True  # Automatic!
    )
    # Errors handled automatically
    # Returns: {success, key, url, similar_issues}
```

---

## Prerequisites

1. **Node.js** (v18 or later) - Required for MCP server
2. **Python 3.11+** - For the RAG application
3. **Jira account** with API access
4. **Internet connection** - MCP downloads server on first run

### Check Node.js Installation

```bash
node --version
# Should show v18.0.0 or later
```

If not installed, download from: https://nodejs.org/

---

## Installation

### Step 1: Install Python Dependencies

```bash
cd mini_projects/mark.bertalan/hf_4
pip install -r requirements.txt
```

This installs the `mcp` Python package.

### Step 2: Install Jira MCP Server

The MCP server is automatically downloaded when first used via:
```bash
npx -y @modelcontextprotocol/server-atlassian
```

You don't need to run this manually - the application does it automatically.

To verify it works:
```bash
npx @modelcontextprotocol/server-atlassian --help
```

---

## Configuration

### Step 1: Update .env File

Add or update these settings in your `.env` file:

```env
# Jira Configuration (required)
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_EMAIL=your.email@company.com
JIRA_API_TOKEN=your_jira_api_token_here

# Department mapping
JIRA_DEPARTMENT_MAPPING=hr:HR,dev:DEV,support:SUP,management:MGT

# Enable MCP (recommended)
USE_JIRA_MCP=true
```

### Step 2: Get Jira API Token

1. Go to: https://id.atlassian.com/manage-profile/security/api-tokens
2. Click **Create API token**
3. Give it a name (e.g., "RAG System")
4. Copy the token
5. Paste into `.env` file

### Step 3: Test Configuration

```bash
python -c "from scripts.config import Config; c = Config.from_env(); print(f'✓ Jira enabled: {c.jira_enabled}, MCP: {c.use_jira_mcp}')"
```

Should output:
```
✓ Jira enabled: True, MCP: True
```

---

## Features

### 1. Automatic Duplicate Detection

When creating a Jira ticket, MCP automatically searches for similar existing tickets.

**How it works:**
- Extracts key terms from the summary
- Searches Jira using JQL
- Returns similar open tickets
- Still creates the ticket but warns the user

**Example Output:**
```
✓ Jira task created successfully!

Task Key: DEV-456
Department: DEV
Priority: High
Summary: Deployment process failing with permission errors

View task: https://your-company.atlassian.net/browse/DEV-456

⚠️  Warning: Found similar existing tickets:
  • DEV-123: Deployment failures in production (In Progress)
  • DEV-234: Permission errors during deploy (Open)
```

### 2. Smart Search

Search for issues using natural language or JQL:

```python
similar = await client.search_similar_issues(
    project_key="DEV",
    summary="API timeout errors",
    max_results=5
)
```

### 3. Structured Results

All operations return structured JSON with clear success/error states:

```json
{
  "success": true,
  "key": "DEV-456",
  "url": "https://...",
  "duplicate_warning": true,
  "similar_issues": [
    {
      "key": "DEV-123",
      "summary": "Similar issue",
      "status": "In Progress"
    }
  ]
}
```

### 4. Comprehensive Logging

Every operation is logged with structured information:

```
INFO - Creating Jira issue via MCP
INFO - Searching for similar issues: project = DEV AND summary ~ "deployment permission"
INFO - Found 2 similar issues
INFO - ✓ Created Jira issue: DEV-456
INFO - MCP result: success=True, duplicates=True
WARNING - Created ticket despite 2 similar issues found
INFO - ===== Jira task created: DEV-456 in 1234.56ms =====
```

---

## Testing

### Test 1: Create a Simple Ticket

```bash
python -m scripts.main
```

**User Query:**
```
The API is returning 500 errors in production
```

**Expected Behavior:**
1. System suggests creating Jira ticket
2. User confirms: "yes"
3. MCP searches for duplicates
4. Creates ticket (with warning if duplicates found)
5. Returns ticket URL

**Check Logs:**
```
INFO - Creating Jira issue via MCP
INFO - Searching for similar issues: ...
INFO - Found 0 similar issues  # Or more if duplicates exist
INFO - ✓ Created Jira issue: DEV-123
```

### Test 2: Test Duplicate Detection

**Setup:**
1. Create a ticket: "Deployment failing with timeout"
2. Create another ticket with similar summary: "Deploy times out frequently"

**Expected:**
```
⚠️  Warning: Found similar existing tickets:
  • DEV-123: Deployment failing with timeout (Open)
```

### Test 3: Test Fallback to REST API

**Disable MCP temporarily:**
```env
USE_JIRA_MCP=false
```

**Expected Behavior:**
- System uses REST API
- No duplicate detection
- Ticket created successfully
- Log shows: "Creating Jira issue via REST API"

---

## Troubleshooting

### Issue: "MCP not available: ..."

**Cause:** Node.js not installed or MCP server can't be downloaded

**Solution:**
1. Check Node.js: `node --version`
2. Install Node.js from https://nodejs.org/
3. Test MCP server: `npx @modelcontextprotocol/server-atlassian --help`

**Workaround:**
Set `USE_JIRA_MCP=false` to use REST API fallback

---

### Issue: "Failed to connect to Jira MCP server"

**Cause:** Network issues or incorrect credentials

**Solution:**
1. Check internet connection
2. Verify Jira credentials in `.env`
3. Test manually:
   ```bash
   npx @modelcontextprotocol/server-atlassian \
     https://your-company.atlassian.net \
     your.email@company.com \
     your_api_token
   ```

---

### Issue: Slow First Run

**Cause:** MCP server downloading on first use

**Behavior:** First ticket creation may take 10-30 seconds while `npx` downloads the server

**Solution:** This is normal! Subsequent runs will be fast (~1-2 seconds)

**To pre-download:**
```bash
npx @modelcontextprotocol/server-atlassian --help
```

---

### Issue: "Duplicate warning not showing"

**Cause:** No similar tickets exist, or search is too specific

**Debug:**
1. Check logs for: "Searching for similar issues: ..."
2. The search uses first 5 words of summary
3. Search only finds open/in-progress tickets

**Test manually:**
Create two tickets with similar summaries and verify the second shows a warning.

---

### Issue: Async Event Loop Errors

**Cause:** Running in Jupyter notebook or other async environment

**Solution:** The code uses `run_async_in_thread()` which handles this automatically.

If you see errors like "Event loop already running":
- The fallback to REST API will activate automatically
- Check logs for "MCP not available: ..."

---

## Fallback Mode

The system automatically falls back to REST API if:

1. MCP dependencies not installed
2. Node.js not available
3. MCP server fails to start
4. Network issues prevent MCP connection
5. User sets `USE_JIRA_MCP=false`

**Fallback Behavior:**
- ✅ Tickets still created successfully
- ❌ No duplicate detection
- ⚠️ Basic error handling only
- ⚠️ No retry logic

**How to Check Which Mode is Used:**

Look for these log messages:

**MCP Mode:**
```
INFO - Creating Jira issue via MCP
INFO - MCP result: success=True, duplicates=True
```

**Fallback Mode:**
```
WARNING - MCP not available: ..., falling back to REST API
INFO - Creating Jira issue via REST API
INFO - ✓ Created via REST API: DEV-456
```

---

## Advanced Usage

### Programmatic Access

Use the MCP client directly in your code:

```python
from scripts.mcp_client import JiraMCPClient, run_async_in_thread

async def my_function():
    async with JiraMCPClient(url, email, token) as client:
        # Search for issues
        issues = await client.search_similar_issues(
            project_key="DEV",
            summary="API errors",
            max_results=10
        )

        # Create issue
        result = await client.create_issue(
            project_key="DEV",
            summary="New bug report",
            description="Details here...",
            priority="High",
            check_duplicates=True
        )

        # Add comment
        await client.add_comment(
            issue_key="DEV-123",
            comment="Updated information..."
        )

        # Update issue
        await client.update_issue(
            issue_key="DEV-123",
            fields={"priority": "Critical"}
        )

# Run in sync context
run_async_in_thread(my_function())
```

### Custom Duplicate Logic

Modify `scripts/mcp_client.py` to customize duplicate detection:

```python
async def search_similar_issues(self, project_key, summary, max_results=5):
    # Customize search logic
    search_terms = extract_keywords(summary)  # Your logic
    jql = f'project = {project_key} AND summary ~ "{search_terms}"'
    # ...
```

---

## Performance

### Typical Latencies

| Operation | MCP | REST API |
|-----------|-----|----------|
| Create ticket (no duplicates) | 500-1500ms | 300-800ms |
| Create ticket (with duplicate check) | 1000-2000ms | N/A |
| Search issues | 300-800ms | 300-800ms |
| First run (download MCP) | 10-30s | N/A |

### Optimization Tips

1. **Pre-download MCP**: Run `npx @modelcontextprotocol/server-atlassian --help` during setup
2. **Adjust search results**: Set `max_results=3` for faster duplicate checking
3. **Disable duplicates**: Set `check_duplicates=False` if not needed
4. **Use REST fallback**: For simple use cases without duplicate detection

---

## MCP Architecture

```
┌─────────────────┐
│  RAG Application│
│   (Python)      │
└────────┬────────┘
         │
         │ MCP Protocol (JSON-RPC over stdio)
         │
         ↓
┌─────────────────┐
│  MCP Server     │
│   (Node.js)     │
│  @model...      │
│  /server-       │
│  atlassian      │
└────────┬────────┘
         │
         │ HTTPS (REST API)
         │
         ↓
┌─────────────────┐
│  Jira Cloud     │
│  (Atlassian)    │
└─────────────────┘
```

**Benefits of This Architecture:**
- Python app doesn't need to handle Jira API complexity
- MCP server manages connections, retries, rate limiting
- Easy to swap MCP servers without changing Python code
- Better error messages and logging

---

## Comparison: Before vs After

### Before (REST API Only)

```python
# Create ticket
try:
    headers = {"Authorization": f"Basic {token}"}
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    ticket = response.json()
    # No duplicate checking!
except Exception as e:
    # Basic error handling
    print(f"Error: {e}")
```

### After (MCP)

```python
# Create ticket with duplicate detection
async with JiraMCPClient(...) as client:
    result = await client.create_issue(
        project_key="DEV",
        summary=summary,
        check_duplicates=True  # Automatic!
    )

    if result["duplicate_warning"]:
        print(f"⚠️  {len(result['similar_issues'])} similar tickets found")

    print(f"✓ Created: {result['key']}")
```

**Result:**
- ✅ Duplicate detection automatic
- ✅ Better error messages
- ✅ Cleaner code
- ✅ Structured results

---

## FAQ

**Q: Is MCP required?**

No! The system works fine with REST API fallback. MCP is recommended for duplicate detection and better reliability.

**Q: Does MCP cost money?**

No, MCP is free and open-source.

**Q: Can I use MCP with Jira Server (on-premise)?**

The `@modelcontextprotocol/server-atlassian` package is designed for Jira Cloud. For Jira Server, you may need a different MCP server or use REST API fallback.

**Q: How do I disable duplicate warnings?**

In the code, change:
```python
result = await client.create_issue(
    ...,
    check_duplicates=False  # Disable
)
```

**Q: Can I customize the duplicate search?**

Yes! Edit `scripts/mcp_client.py` and modify the `search_similar_issues()` method.

**Q: What if my network blocks npx?**

Use REST API fallback by setting `USE_JIRA_MCP=false`.

---

## Next Steps

- ✅ Install and test MCP
- ✅ Create a test ticket
- ✅ Verify duplicate detection works
- 📚 Read `PLANNER_AND_TEAMS.md` for planner integration
- 🔧 Customize duplicate search logic if needed

---

## Support

For issues:
1. Check logs for error messages
2. Verify Node.js installation
3. Test MCP server manually
4. Use REST API fallback as workaround
5. Check GitHub issues for known problems

**Logs Location:** Console output when running `python -m scripts.main`

---

Built with reliability and intelligence in mind! 🎯
