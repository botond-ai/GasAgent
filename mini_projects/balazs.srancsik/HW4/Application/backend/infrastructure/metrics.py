"""
Prometheus metrics collection for SupportAI application.
Tracks request counts, latencies, tool usage, costs, and ticket statistics.
"""
import time
from functools import wraps
from typing import Callable, Any
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# REQUEST METRICS
# ============================================================================

# HTTP request counter
http_requests_total = Counter(
    'supportai_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

# HTTP request latency
http_request_duration_seconds = Histogram(
    'supportai_http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'endpoint'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
)

# Active requests gauge
http_requests_in_progress = Gauge(
    'supportai_http_requests_in_progress',
    'Number of HTTP requests currently being processed',
    ['method', 'endpoint']
)

# ============================================================================
# CHAT & AI METRICS
# ============================================================================

# Chat messages counter
chat_messages_total = Counter(
    'supportai_chat_messages_total',
    'Total chat messages processed',
    ['user_id', 'has_files']
)

# Chat response time
chat_response_duration_seconds = Histogram(
    'supportai_chat_response_duration_seconds',
    'Chat response generation time in seconds',
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0]
)

# Support feedback detection
support_feedback_detected_total = Counter(
    'supportai_support_feedback_detected_total',
    'Total support feedback messages detected',
    ['language']
)

# ============================================================================
# TOOL METRICS
# ============================================================================

# Tool invocations counter
tool_invocations_total = Counter(
    'supportai_tool_invocations_total',
    'Total tool invocations',
    ['tool_name', 'success']
)

# Tool execution time
tool_execution_duration_seconds = Histogram(
    'supportai_tool_execution_duration_seconds',
    'Tool execution time in seconds',
    ['tool_name'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
)

# Tools per request
tools_per_request = Histogram(
    'supportai_tools_per_request',
    'Number of tools called per chat request',
    buckets=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20]
)

# ============================================================================
# TICKET METRICS
# ============================================================================

# Tickets created counter
tickets_created_total = Counter(
    'supportai_tickets_created_total',
    'Total tickets created',
    ['priority', 'sentiment', 'issue_type']
)

# Current ticket count gauge
tickets_total = Gauge(
    'supportai_tickets_total',
    'Total number of tickets in database'
)

# Tickets by priority gauge
tickets_by_priority = Gauge(
    'supportai_tickets_by_priority',
    'Number of tickets by priority',
    ['priority']
)

# Tickets by sentiment gauge
tickets_by_sentiment = Gauge(
    'supportai_tickets_by_sentiment',
    'Number of tickets by sentiment',
    ['sentiment']
)

# Tickets by issue type gauge
tickets_by_issue_type = Gauge(
    'supportai_tickets_by_issue_type',
    'Number of tickets by issue type',
    ['issue_type']
)

# ============================================================================
# COST METRICS
# ============================================================================

# OpenAI API cost tracking (estimated)
openai_api_cost_usd = Counter(
    'supportai_openai_api_cost_usd_total',
    'Estimated OpenAI API cost in USD',
    ['model', 'operation']
)

# OpenAI tokens used
openai_tokens_total = Counter(
    'supportai_openai_tokens_total',
    'Total OpenAI tokens used',
    ['model', 'token_type']
)

# Ticket cost to customer
ticket_cost_usd_total = Counter(
    'supportai_ticket_cost_usd_total',
    'Total ticket cost to customers in USD'
)

# Average ticket cost gauge
ticket_cost_average_usd = Gauge(
    'supportai_ticket_cost_average_usd',
    'Average ticket cost to customers in USD'
)

# ============================================================================
# FILE UPLOAD METRICS
# ============================================================================

# Files uploaded counter
files_uploaded_total = Counter(
    'supportai_files_uploaded_total',
    'Total files uploaded',
    ['status']
)

# File upload size
file_upload_size_bytes = Histogram(
    'supportai_file_upload_size_bytes',
    'File upload size in bytes',
    buckets=[1024, 10240, 102400, 1048576, 5242880, 10485760, 52428800]
)

# ============================================================================
# EMAIL METRICS
# ============================================================================

# Emails sent counter
emails_sent_total = Counter(
    'supportai_emails_sent_total',
    'Total emails sent',
    ['status']
)

# ============================================================================
# LANGUAGE METRICS
# ============================================================================

# Messages by language
messages_by_language = Counter(
    'supportai_messages_by_language_total',
    'Total messages by detected language',
    ['language']
)

# Translations performed
translations_total = Counter(
    'supportai_translations_total',
    'Total translations performed',
    ['source_language', 'target_language']
)

# ============================================================================
# SENTIMENT METRICS
# ============================================================================

# Sentiment analysis results
sentiment_analysis_total = Counter(
    'supportai_sentiment_analysis_total',
    'Total sentiment analysis results',
    ['sentiment']
)

# Sentiment confidence histogram
sentiment_confidence = Histogram(
    'supportai_sentiment_confidence',
    'Sentiment analysis confidence scores',
    ['sentiment'],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

# ============================================================================
# SYSTEM METRICS
# ============================================================================

# Application info
app_info = Info('supportai_app', 'SupportAI application information')
app_info.info({
    'version': '1.1.0',
    'name': 'SupportAI',
    'framework': 'FastAPI'
})

# ============================================================================
# MIDDLEWARE
# ============================================================================

class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP request metrics."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        method = request.method
        path = request.url.path
        
        # Normalize path for metrics (avoid high cardinality)
        endpoint = self._normalize_path(path)
        
        # Track in-progress requests
        http_requests_in_progress.labels(method=method, endpoint=endpoint).inc()
        
        start_time = time.time()
        
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            raise
        finally:
            # Record metrics
            duration = time.time() - start_time
            
            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code
            ).inc()
            
            http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
            
            http_requests_in_progress.labels(method=method, endpoint=endpoint).dec()
        
        return response
    
    def _normalize_path(self, path: str) -> str:
        """Normalize path to avoid high cardinality metrics."""
        # Map specific paths to generic labels
        if path.startswith('/api/chat'):
            return '/api/chat'
        elif path.startswith('/api/session/'):
            return '/api/session/{id}'
        elif path.startswith('/api/profile/'):
            return '/api/profile/{id}'
        elif path.startswith('/api/tickets'):
            return '/api/tickets'
        elif path == '/metrics':
            return '/metrics'
        elif path == '/':
            return '/'
        elif path == '/tickets':
            return '/tickets'
        else:
            return '/other'


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def track_tool_execution(tool_name: str):
    """Decorator to track tool execution metrics."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            success = "true"
            
            try:
                result = await func(*args, **kwargs)
                if isinstance(result, dict) and not result.get("success", True):
                    success = "false"
                return result
            except Exception as e:
                success = "false"
                raise
            finally:
                duration = time.time() - start_time
                tool_invocations_total.labels(tool_name=tool_name, success=success).inc()
                tool_execution_duration_seconds.labels(tool_name=tool_name).observe(duration)
        
        return wrapper
    return decorator


def record_chat_metrics(
    user_id: str,
    has_files: bool,
    duration: float,
    tools_called: int,
    is_support_feedback: bool = False,
    language: str = "en"
):
    """Record metrics for a chat request."""
    chat_messages_total.labels(
        user_id=user_id[:8] if user_id else "unknown",  # Truncate for privacy
        has_files=str(has_files).lower()
    ).inc()
    
    chat_response_duration_seconds.observe(duration)
    tools_per_request.observe(tools_called)
    
    if is_support_feedback:
        support_feedback_detected_total.labels(language=language).inc()


def record_ticket_created(
    priority: str,
    sentiment: str,
    issue_type: str,
    cost_usd: float = 0.0
):
    """Record metrics when a ticket is created."""
    tickets_created_total.labels(
        priority=priority or "unknown",
        sentiment=sentiment or "neutral",
        issue_type=issue_type or "unknown"
    ).inc()
    
    if cost_usd > 0:
        ticket_cost_usd_total.inc(cost_usd)


def record_openai_usage(
    model: str,
    operation: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost_usd: float = 0.0
):
    """Record OpenAI API usage metrics."""
    if prompt_tokens > 0:
        openai_tokens_total.labels(model=model, token_type="prompt").inc(prompt_tokens)
    if completion_tokens > 0:
        openai_tokens_total.labels(model=model, token_type="completion").inc(completion_tokens)
    if cost_usd > 0:
        openai_api_cost_usd.labels(model=model, operation=operation).inc(cost_usd)


def record_sentiment(sentiment: str, confidence: float):
    """Record sentiment analysis metrics."""
    sentiment_analysis_total.labels(sentiment=sentiment).inc()
    sentiment_confidence.labels(sentiment=sentiment).observe(confidence)


def record_translation(source_language: str, target_language: str):
    """Record translation metrics."""
    translations_total.labels(
        source_language=source_language,
        target_language=target_language
    ).inc()


def record_file_upload(success: bool, size_bytes: int = 0):
    """Record file upload metrics."""
    status = "success" if success else "failed"
    files_uploaded_total.labels(status=status).inc()
    if size_bytes > 0:
        file_upload_size_bytes.observe(size_bytes)


def record_email_sent(success: bool):
    """Record email sent metrics."""
    status = "success" if success else "failed"
    emails_sent_total.labels(status=status).inc()


def record_language_detected(language: str):
    """Record language detection metrics."""
    messages_by_language.labels(language=language).inc()


def update_ticket_gauges(db_path: str = "data/tickets.db"):
    """Update ticket gauge metrics from database."""
    import sqlite3
    import os
    
    if not os.path.exists(db_path):
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Total tickets
        cursor.execute("SELECT COUNT(*) FROM tickets")
        total = cursor.fetchone()[0]
        tickets_total.set(total)
        
        # By priority
        cursor.execute("SELECT priority, COUNT(*) FROM tickets GROUP BY priority")
        for row in cursor.fetchall():
            priority = row[0] or "unknown"
            count = row[1]
            tickets_by_priority.labels(priority=priority).set(count)
        
        # By sentiment
        cursor.execute("SELECT sentiment, COUNT(*) FROM tickets GROUP BY sentiment")
        for row in cursor.fetchall():
            sentiment = row[0] or "neutral"
            count = row[1]
            tickets_by_sentiment.labels(sentiment=sentiment).set(count)
        
        # By issue type
        cursor.execute("SELECT issue_type, COUNT(*) FROM tickets GROUP BY issue_type")
        for row in cursor.fetchall():
            issue_type = row[0] or "unknown"
            count = row[1]
            tickets_by_issue_type.labels(issue_type=issue_type).set(count)
        
        # Average cost
        cursor.execute("SELECT AVG(CAST(cost_usd AS REAL)) FROM tickets WHERE cost_usd IS NOT NULL AND cost_usd != ''")
        avg_cost = cursor.fetchone()[0]
        if avg_cost:
            ticket_cost_average_usd.set(avg_cost)
        
        conn.close()
    except Exception as e:
        logger.error(f"Error updating ticket gauges: {e}")


def get_metrics() -> bytes:
    """Generate Prometheus metrics output."""
    # Update ticket gauges before generating metrics
    update_ticket_gauges()
    return generate_latest()


def get_metrics_content_type() -> str:
    """Get the content type for Prometheus metrics."""
    return CONTENT_TYPE_LATEST
