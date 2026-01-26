"""
Structured logging configuration for KnowledgeRouter.

Provides JSON-formatted logs for Loki/ELK ingestion with context enrichment.
"""
import logging
import json
import sys
from typing import Any, Dict, Optional
from datetime import datetime
import traceback


class StructuredFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    
    Output format:
    {
        "timestamp": "2026-01-23T10:30:45.123456Z",
        "level": "INFO",
        "name": "services.agent",
        "message": "Intent detection completed",
        "node": "intent_detection",
        "domain": "it",
        "user_id": "user123",
        "session_id": "session456",
        "latency_ms": 1234.56,
        "exc_info": "Traceback..." (if exception)
    }
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add custom fields from extra (logger.info("msg", extra={...}))
        if hasattr(record, "node"):
            log_data["node"] = record.node
        if hasattr(record, "domain"):
            log_data["domain"] = record.domain
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "session_id"):
            log_data["session_id"] = record.session_id
        if hasattr(record, "latency_ms"):
            log_data["latency_ms"] = record.latency_ms
        if hasattr(record, "tokens"):
            log_data["tokens"] = record.tokens
        if hasattr(record, "cost"):
            log_data["cost"] = record.cost
        
        # Add exception info if present
        if record.exc_info:
            log_data["exc_info"] = self.formatException(record.exc_info)
            log_data["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        
        # Stack trace for errors
        if record.levelno >= logging.ERROR and record.exc_info:
            log_data["stack_trace"] = traceback.format_exc()
        
        return json.dumps(log_data, ensure_ascii=False)


def setup_structured_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    json_format: bool = True
) -> None:
    """
    Configure structured logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (if None, logs only to stdout)
        json_format: If True, use JSON formatter; else use standard formatter
    
    Example:
        setup_structured_logging(log_level="INFO", log_file="/var/log/backend/app.log")
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    if json_format:
        console_handler.setFormatter(StructuredFormatter())
    else:
        # Standard format for development
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
        )
    
    root_logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(file_handler)
    
    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)
    
    root_logger.info(
        "Structured logging configured",
        extra={
            "log_level": log_level,
            "log_file": log_file,
            "json_format": json_format
        }
    )


class LogContext:
    """
    Context manager for enriching logs with metadata.
    
    Usage:
        with LogContext(user_id="user123", session_id="session456"):
            logger.info("Processing query", extra={"node": "intent_detection"})
        
        # Output:
        # {"timestamp": "...", "message": "Processing query", "node": "intent_detection",
        #  "user_id": "user123", "session_id": "session456"}
    """
    
    def __init__(self, **context: Any):
        self.context = context
        self.old_factory = None
    
    def __enter__(self):
        old_factory = logging.getLogRecordFactory()
        
        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record
        
        logging.setLogRecordFactory(record_factory)
        self.old_factory = old_factory
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.old_factory:
            logging.setLogRecordFactory(self.old_factory)


# Convenience function for agent logging
def log_node_execution(
    logger: logging.Logger,
    node: str,
    message: str,
    level: str = "INFO",
    **extra: Any
) -> None:
    """
    Log node execution with structured metadata.
    
    Args:
        logger: Logger instance
        node: Node name (intent_detection, retrieval, generation, etc.)
        message: Log message
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        **extra: Additional fields (domain, user_id, latency_ms, etc.)
    
    Example:
        log_node_execution(
            logger, 
            node="generation",
            message="LLM response generated",
            level="INFO",
            domain="it",
            user_id="user123",
            latency_ms=12345.67,
            tokens=1234
        )
    """
    log_method = getattr(logger, level.lower())
    log_method(message, extra={"node": node, **extra})
