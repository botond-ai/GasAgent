"""
Structured JSON Logging with Correlation ID Injection.

Provides JSON formatter that automatically injects correlation IDs
(request_id, trace_id, session_id, tenant_id, user_id) from ContextVars
into every log record.

Usage:
    from observability.structured_logger import JSONFormatter
    
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
"""
import json
import logging
import sys
import traceback
from datetime import datetime
from typing import Optional

from api.middleware.request_context import (
    request_id_ctx_var,
    session_id_ctx_var,
    tenant_id_ctx_var,
    user_id_ctx_var,
    trace_id_ctx_var,
)


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter with automatic correlation ID injection.
    
    Features:
    - ISO 8601 timestamp
    - Structured fields (level, message, logger, module, function, line)
    - Automatic correlation ID injection from ContextVars
    - Exception stack trace formatting
    - Custom extra fields support
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON string.
        
        Args:
            record: LogRecord instance
            
        Returns:
            JSON string with structured log data
        """
        # Base log data
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Inject correlation IDs from ContextVars
        request_id = request_id_ctx_var.get()
        trace_id = trace_id_ctx_var.get()
        session_id = session_id_ctx_var.get()
        tenant_id = tenant_id_ctx_var.get()
        user_id = user_id_ctx_var.get()
        
        if request_id:
            log_data["request_id"] = request_id
        if trace_id:
            log_data["trace_id"] = trace_id
        if session_id:
            log_data["session_id"] = session_id
        if tenant_id:
            log_data["tenant_id"] = tenant_id
        if user_id:
            log_data["user_id"] = user_id
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }
        
        # Add custom extra fields (if any)
        # Skip standard LogRecord attributes
        skip_keys = {
            "name", "msg", "args", "created", "filename", "funcName", "levelname",
            "levelno", "lineno", "module", "msecs", "message", "pathname", "process",
            "processName", "relativeCreated", "thread", "threadName", "exc_info",
            "exc_text", "stack_info", "getMessage", "taskName",
        }
        
        extra = {
            key: value
            for key, value in record.__dict__.items()
            if key not in skip_keys and not key.startswith("_")
        }
        
        if extra:
            log_data["extra"] = extra
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


def get_json_formatter() -> JSONFormatter:
    """
    Factory function for JSON formatter.
    
    Returns:
        Configured JSONFormatter instance
    """
    return JSONFormatter()


def configure_json_logging(logger: Optional[logging.Logger] = None) -> None:
    """
    Configure JSON logging for a specific logger or root logger.
    
    Args:
        logger: Logger instance to configure. If None, configures root logger.
    """
    target_logger = logger or logging.getLogger()
    
    # Remove existing handlers
    target_logger.handlers.clear()
    
    # Add JSON handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    target_logger.addHandler(handler)
    
    # Preserve log level
    if not target_logger.level:
        target_logger.setLevel(logging.INFO)
