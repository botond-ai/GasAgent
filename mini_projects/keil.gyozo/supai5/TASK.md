# TASK: FleetDM Device Lookup Tool Node Integration

**Priority:** Medium  
**Type:** Feature - Backend Integration  
**Status:** Not Started  
**Estimated Time:** 4-6 hours

---

## 📝 Overview

Add FleetDM device lookup as a conditional tool node in the existing LangGraph support ticket triage workflow. This will enable the AI agent to automatically retrieve device information when processing technical support tickets.

---

## 🎯 Objective

Integrate FleetDM API as a new node in the LangGraph workflow that:
- Conditionally executes only for technical/hardware-related tickets
- Looks up device information based on customer email
- Enriches the answer draft with relevant device context
- Gracefully handles cases where device is not found or FleetDM is not configured

---

## 📋 Requirements

### Functional Requirements

1. **FleetDM Service**
   - Create async HTTP client for FleetDM API
   - Implement host search by email/hostname
   - Implement host details retrieval
   - Format device info for LLM context

2. **Workflow Integration**
   - Add `fleet_lookup` node to LangGraph
   - Implement conditional routing based on ticket category
   - Pass device context to answer draft generation
   - Update state schema with device fields

3. **Configuration**
   - Add FleetDM URL and API token to settings
   - Support optional configuration (skip if not configured)
   - Environment variable validation

4. **Error Handling**
   - Handle API timeouts (10 second limit)
   - Handle device not found gracefully
   - Handle missing/invalid configuration
   - Log all FleetDM operations

### Non-Functional Requirements

- No performance impact on non-technical tickets (conditional execution)
- Secure API token storage (environment variables only)
- Comprehensive logging for debugging
- Backwards compatible (works even if FleetDM not configured)

---

## 🏗️ Architecture

### Current Workflow
```
detect_intent → triage_classify → expand_queries → search_rag → 
rerank_docs → draft_answer → check_policy → validate_output
```

### New Workflow with FleetDM
```
detect_intent → triage_classify → [CONDITIONAL ROUTING]
                                       ↓
                          technical? → fleet_lookup → expand_queries → ...
                          other? → expand_queries → ...
```

### Conditional Logic
```python
def should_lookup_device(state: dict) -> str:
    problem_type = state.get("problem_type", "").lower()
    category = state.get("category", "").lower()
    
    # Trigger FleetDM lookup for technical issues
    if "technical" in problem_type or "hardware" in problem_type:
        return "fleet_lookup"
    if "technical" in category or "hardware" in category:
        return "fleet_lookup"
    
    # Skip FleetDM for other issues
    return "expand_queries"
```

---

## 📁 Files to Create/Modify

### Backend Files

#### Create New Files

1. **`backend/app/services/fleet_service.py`** (NEW)
   - FleetDM API client service
   - Methods: `search_host()`, `get_host_details()`, `format_device_context()`
   - Async HTTP requests with httpx
   - ~150 lines

2. **`backend/app/models/fleet.py`** (NEW - Optional)
   - Pydantic models for FleetDM responses
   - Models: `FleetHost`, `FleetHostDetail`, `FleetSearchResponse`
   - ~50 lines

#### Modify Existing Files

3. **`backend/app/workflows/nodes.py`** (MODIFY)
   - Add `fleet_lookup()` node method to `WorkflowNodes` class
   - Modify `draft_answer()` to include device context in prompt
   - ~40 new lines

4. **`backend/app/workflows/graph.py`** (MODIFY)
   - Add `device_info` and `device_context` to `SupportWorkflowState`
   - Add `fleet_lookup` node to graph
   - Implement conditional routing after `triage_classify`
   - ~30 new lines

5. **`backend/app/core/config.py`** (MODIFY)
   - Add `fleet_url: str` field
   - Add `fleet_api_token: str` field
   - ~2 new lines

6. **`backend/.env`** (MODIFY)
   - Add FLEET_URL=https://your-fleet-instance.com
   - Add FLEET_API_TOKEN=your_token_here
   - ~2 new lines

7. **`backend/.env.example`** (MODIFY)
   - Add FLEET_URL= (with comment: optional)
   - Add FLEET_API_TOKEN= (with comment: optional)
   - ~2 new lines

---

## 🔧 Implementation Details

### 1. FleetDM Service (`fleet_service.py`)

```python
"""FleetDM API integration service."""
import httpx
from typing import Optional, Dict, Any
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class FleetService:
    """Service for interacting with FleetDM API."""
    
    def __init__(self):
        self.base_url = settings.fleet_url.rstrip('/') if settings.fleet_url else ""
        self.api_token = settings.fleet_api_token or ""
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        self.enabled = bool(self.base_url and self.api_token)
    
    async def search_host(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Search for a host by hostname, email, or identifier.
        
        Args:
            query: Search query (hostname, email, etc.)
            
        Returns:
            Host details if found, None otherwise
        """
        if not self.enabled:
            logger.debug("FleetDM not configured, skipping search")
            return None
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/fleet/hosts",
                    headers=self.headers,
                    params={"query": query}
                )
                response.raise_for_status()
                
                data = response.json()
                hosts = data.get("hosts", [])
                
                if hosts:
                    logger.info(f"FleetDM found {len(hosts)} host(s) for query: {query}")
                    return hosts[0]  # Return first match
                
                logger.info(f"FleetDM found no hosts for query: {query}")
                return None
                
        except httpx.HTTPError as e:
            logger.error(f"FleetDM HTTP error: {e}")
            return None
        except Exception as e:
            logger.error(f"FleetDM search error: {e}")
            return None
    
    async def get_host_details(self, host_id: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a host.
        
        Args:
            host_id: FleetDM host ID
            
        Returns:
            Detailed host information if found, None otherwise
        """
        if not self.enabled:
            return None
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/fleet/hosts/{host_id}",
                    headers=self.headers
                )
                response.raise_for_status()
                
                data = response.json()
                logger.info(f"FleetDM retrieved details for host ID: {host_id}")
                return data.get("host")
                
        except httpx.HTTPError as e:
            logger.error(f"FleetDM HTTP error retrieving host {host_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"FleetDM error retrieving host {host_id}: {e}")
            return None
    
    def format_device_context(self, host: Dict[str, Any]) -> str:
        """
        Format host information for LLM context.
        
        Args:
            host: FleetDM host data
            
        Returns:
            Formatted string for LLM prompt
        """
        if not host:
            return ""
        
        # Extract relevant fields
        hostname = host.get("hostname", "Unknown")
        platform = host.get("platform", "Unknown")
        os_version = host.get("os_version", "Unknown")
        status = host.get("status", "Unknown")
        seen_time = host.get("seen_time", "Unknown")
        cpu_type = host.get("cpu_type", "Unknown")
        memory = host.get("memory", "Unknown")
        disk_space_available = host.get("gigs_disk_space_available", "Unknown")
        
        context = f"""Device Information (from FleetDM):
- Hostname: {hostname}
- Platform: {platform}
- OS Version: {os_version}
- Status: {status}
- Last Seen: {seen_time}
- CPU: {cpu_type}
- Memory: {memory} GB
- Disk Space Available: {disk_space_available} GB
"""
        
        return context.strip()
```

### 2. Add Node to Workflow (`nodes.py`)

Add this method to the `WorkflowNodes` class:

```python
async def fleet_lookup(self, state: dict) -> dict:
    """
    Node: Lookup device information from FleetDM.
    
    Only runs for technical/hardware issues when customer email is available.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with device_info and device_context
    """
    logger.info(f"Looking up device info for ticket: {state['ticket_id']}")
    
    from app.services.fleet_service import FleetService
    
    fleet = FleetService()
    device_info = None
    device_context = ""
    
    # Try to find device by customer email
    customer_email = state.get("customer_email")
    if customer_email:
        device_info = await fleet.search_host(customer_email)
        
        if device_info:
            # Get full details if we found a match
            host_id = device_info.get("id")
            if host_id:
                full_details = await fleet.get_host_details(host_id)
                if full_details:
                    device_info = full_details
            
            device_context = fleet.format_device_context(device_info)
            logger.info(f"Found device for {customer_email}: {device_info.get('hostname')}")
        else:
            logger.info(f"No device found for {customer_email}")
    else:
        logger.debug("No customer email provided, skipping FleetDM lookup")
    
    return {
        "device_info": device_info,
        "device_context": device_context
    }
```

Modify the `draft_answer` method:

```python
async def draft_answer(self, state: dict) -> dict:
    """Node: Generate answer draft with citations."""
    logger.info(f"Drafting answer for ticket: {state['ticket_id']}")
    
    llm_with_structure = self.llm.with_structured_output(AnswerDraft)
    
    # Format context from reranked docs
    context_docs = state.get("reranked_docs", [])
    context = "\n\n".join([
        f"[Source {i+1}] {doc['text']}"
        for i, doc in enumerate(context_docs)
    ])
    
    # Get device context if available
    device_context = state.get("device_context", "")
    
    # Determine tone based on sentiment
    sentiment = state.get("sentiment", "neutral")
    tone_map = {
        "frustrated": "empathetic_professional",
        "neutral": "formal",
        "satisfied": "casual"
    }
    tone = tone_map.get(sentiment, "empathetic_professional")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert customer support agent. Draft a response using:

Customer: {customer_name}
Problem: {problem_type}
Sentiment: {sentiment}
Tone: {tone}

{device_info}

Knowledge base context:
{context}

Create a response with:
1. Greeting (warm, personalized)
2. Body (address issue, provide solution, reference device specs if relevant, cite sources as [Source N])
3. Closing (helpful, encouraging)

Include citations list with relevant excerpts, source references, and relevance scores."""),
        ("user", "Customer message: {message}")
    ])
    
    chain = prompt | llm_with_structure
    
    try:
        result = await chain.ainvoke({
            "customer_name": state["customer_name"],
            "problem_type": state.get("problem_type", "support request"),
            "sentiment": sentiment,
            "tone": tone,
            "device_info": device_context if device_context else "No device information available.",
            "context": context or "No specific documentation found.",
            "message": state["raw_message"]
        })
        
        return {
            "answer_draft": {
                "greeting": result.greeting,
                "body": result.body,
                "closing": result.closing,
                "tone": result.tone
            },
            "citations": [citation.model_dump() for citation in result.citations]
        }
    except Exception as e:
        logger.error(f"Error drafting answer: {e}")
        return {
            "answer_draft": {
                "greeting": f"Hello {state['customer_name']},",
                "body": "Thank you for contacting us. We're looking into your request.",
                "closing": "Best regards,\nSupport Team",
                "tone": "formal"
            },
            "citations": []
        }
```

### 3. Update Graph (`graph.py`)

Update state definition:

```python
class SupportWorkflowState(TypedDict, total=False):
    # Input
    ticket_id: str
    raw_message: str
    customer_name: str
    customer_email: str

    # Intent
    problem_type: str
    sentiment: str

    # Triage
    category: str
    subcategory: str
    priority: str
    sla_hours: int
    suggested_team: str
    triage_confidence: float

    # FleetDM (NEW)
    device_info: dict | None
    device_context: str

    # RAG
    search_queries: list[str]
    retrieved_docs: list[dict]
    reranked_docs: list[dict]

    # Output
    answer_draft: dict
    citations: list[dict]
    policy_check: dict
    output: dict
```

Update graph building:

```python
def _build_graph(self) -> StateGraph:
    """Build the LangGraph workflow."""
    
    workflow = StateGraph(SupportWorkflowState)
    
    # Add nodes
    workflow.add_node("detect_intent", self.nodes.detect_intent)
    workflow.add_node("triage_classify", self.nodes.triage_classify)
    workflow.add_node("fleet_lookup", self.nodes.fleet_lookup)  # NEW
    workflow.add_node("expand_queries", self.nodes.expand_queries)
    workflow.add_node("search_rag", self.nodes.search_rag)
    workflow.add_node("rerank_docs", self.nodes.rerank_docs)
    workflow.add_node("draft_answer", self.nodes.draft_answer)
    workflow.add_node("check_policy", self.nodes.check_policy)
    workflow.add_node("validate_output", self.nodes.validate_output)
    
    # Define conditional routing
    def should_lookup_device(state: dict) -> str:
        """Decide if we need FleetDM lookup based on ticket type."""
        problem_type = state.get("problem_type", "").lower()
        category = state.get("category", "").lower()
        
        # Keywords that trigger device lookup
        technical_keywords = ["technical", "hardware", "device", "computer", "laptop", "desktop", "machine", "system"]
        
        # Check problem type
        for keyword in technical_keywords:
            if keyword in problem_type:
                logger.info(f"FleetDM lookup triggered by problem_type: {problem_type}")
                return "fleet_lookup"
        
        # Check category
        for keyword in technical_keywords:
            if keyword in category:
                logger.info(f"FleetDM lookup triggered by category: {category}")
                return "fleet_lookup"
        
        # Skip FleetDM for non-technical issues
        logger.info(f"Skipping FleetDM lookup for non-technical ticket")
        return "expand_queries"
    
    # Define edges (execution flow)
    workflow.set_entry_point("detect_intent")
    
    workflow.add_edge("detect_intent", "triage_classify")
    
    # Conditional routing after triage
    workflow.add_conditional_edges(
        "triage_classify",
        should_lookup_device,
        {
            "fleet_lookup": "fleet_lookup",
            "expand_queries": "expand_queries"
        }
    )
    
    # Continue from fleet_lookup
    workflow.add_edge("fleet_lookup", "expand_queries")
    
    # Rest of the pipeline
    workflow.add_edge("expand_queries", "search_rag")
    workflow.add_edge("search_rag", "rerank_docs")
    workflow.add_edge("rerank_docs", "draft_answer")
    workflow.add_edge("draft_answer", "check_policy")
    workflow.add_edge("check_policy", "validate_output")
    workflow.add_edge("validate_output", END)
    
    # Compile graph
    return workflow.compile()
```

### 4. Update Config (`config.py`)

```python
class Settings(BaseSettings):
    # ... existing fields ...
    
    # FleetDM Configuration (optional)
    fleet_url: str = Field(default="", env="FLEET_URL")
    fleet_api_token: str = Field(default="", env="FLEET_API_TOKEN")
```

---

## 🧪 Testing Plan

### Unit Tests

Create `backend/tests/test_fleet_service.py`:

```python
import pytest
from app.services.fleet_service import FleetService

@pytest.mark.asyncio
async def test_search_host_not_configured():
    """Test that service handles missing configuration gracefully."""
    # Test with empty config
    service = FleetService()
    result = await service.search_host("test@example.com")
    assert result is None

@pytest.mark.asyncio
async def test_format_device_context():
    """Test device context formatting."""
    service = FleetService()
    host_data = {
        "hostname": "test-laptop",
        "platform": "darwin",
        "os_version": "macOS 14.0",
        "status": "online",
        "memory": 16,
        "gigs_disk_space_available": 100
    }
    
    context = service.format_device_context(host_data)
    assert "test-laptop" in context
    assert "darwin" in context
    assert "16 GB" in context
```

### Integration Tests

1. **Test technical ticket with device:**
   ```bash
   # Create ticket
   POST /api/tickets/
   {
     "customer_name": "John Doe",
     "customer_email": "john@company.com",  # Must exist in FleetDM
     "subject": "Laptop running slow",
     "message": "My laptop has been very slow lately"
   }
   
   # Process ticket
   POST /api/tickets/{id}/process
   
   # Verify response includes device info
   ```

2. **Test non-technical ticket (skip FleetDM):**
   ```bash
   POST /api/tickets/
   {
     "customer_name": "Jane Doe",
     "customer_email": "jane@company.com",
     "subject": "Billing question",
     "message": "I was charged twice"
   }
   
   # Process ticket - should skip FleetDM lookup
   ```

3. **Test device not found:**
   ```bash
   POST /api/tickets/
   {
     "customer_email": "notfound@example.com",
     "subject": "Computer won't boot",
     "message": "My computer won't turn on"
   }
   
   # Should continue gracefully without device info
   ```

### Manual Testing Checklist

- [ ] FleetDM service initializes correctly with valid config
- [ ] FleetDM service handles missing config gracefully
- [ ] Technical ticket triggers FleetDM lookup
- [ ] Non-technical ticket skips FleetDM lookup
- [ ] Device found: context appears in answer draft
- [ ] Device not found: no errors, continues normally
- [ ] API timeout handling works (10 second limit)
- [ ] Logs show FleetDM operations correctly
- [ ] Environment variables load correctly

---

## 📊 Success Criteria

### Must Have
- [x] FleetService class created with async methods
- [x] Conditional routing in graph based on ticket type
- [x] Device context included in answer draft for technical tickets
- [x] Graceful handling when FleetDM not configured
- [x] Graceful handling when device not found
- [x] Logging for all FleetDM operations

### Nice to Have
- [ ] Pydantic models for FleetDM responses
- [ ] Unit tests for FleetService
- [ ] Integration tests for workflow
- [ ] Caching for device lookups (reduce API calls)
- [ ] Metrics for FleetDM usage

---

## 🔗 API Documentation

**FleetDM API Reference:**
- Main docs: https://fleetdm.com/docs/rest-api/rest-api
- GitHub: https://github.com/fleetdm/fleet/blob/main/docs/REST%20API/rest-api.md

**Key Endpoints Used:**
```
GET /api/v1/fleet/hosts?query={email}
GET /api/v1/fleet/hosts/{id}
```

**Authentication:**
```
Headers:
  Authorization: Bearer {api_token}
```

---

## 🐛 Known Issues / Edge Cases

1. **Multiple devices per email:** Currently returns first match only
2. **Device offline:** Shows last known state, may be outdated
3. **Rate limiting:** FleetDM may rate limit requests
4. **Timeout:** 10 second timeout may be too short for slow networks

---

## 🚀 Deployment Notes

### Environment Setup
```bash
# .env file
FLEET_URL=https://fleet.yourcompany.com
FLEET_API_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Verification
```bash
# Test FleetDM connectivity
curl -H "Authorization: Bearer $FLEET_API_TOKEN" \
     https://fleet.yourcompany.com/api/v1/fleet/hosts?query=test
```

### Rollback Plan
If issues occur:
1. Remove FleetDM environment variables
2. Service will automatically skip all lookups
3. Workflow continues normally without device info

---

## 📝 Notes

- FleetDM integration is **optional** - system works without it
- Device lookup adds ~1-2 seconds to technical ticket processing
- Logs all FleetDM operations for debugging
- No breaking changes to existing workflow

---

## ✅ Definition of Done

- [ ] Code implemented and tested locally
- [ ] Unit tests written and passing
- [ ] Integration tests passing
- [ ] Code reviewed
- [ ] Environment variables documented
- [ ] Deployment instructions added to README
- [ ] Works with and without FleetDM configured
- [ ] Logs are comprehensive and helpful
- [ ] No performance degradation for non-technical tickets

---

**Assignee:** GitHub Copilot / Claude Code  
**Reviewer:** TBD  
**Related Issues:** N/A  
**Documentation:** Update README.md with FleetDM setup instructions
