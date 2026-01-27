"""
Unit tests for structured logging (Loki integration).
Tests JSON formatting, context enrichment, and log_node_execution helper.
"""
import logging
import json
from infrastructure.structured_logging import (
    StructuredFormatter,
    setup_structured_logging,
    LogContext,
    log_node_execution
)


class TestStructuredFormatter:
    """Test JSON log formatter."""
    
    def test_basic_json_format(self):
        """Test basic log record is formatted as JSON."""
        formatter = StructuredFormatter()
        logger = logging.getLogger("test")
        
        # Create log record
        record = logger.makeRecord(
            name="test.module",
            level=logging.INFO,
            fn="test.py",
            lno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert log_data["level"] == "INFO"
        assert log_data["name"] == "test.module"
        assert log_data["message"] == "Test message"
        assert log_data["line"] == 42
        assert "timestamp" in log_data
        assert log_data["timestamp"].endswith("Z")  # UTC format
    
    def test_json_with_extra_fields(self):
        """Test custom fields from extra parameter."""
        formatter = StructuredFormatter()
        logger = logging.getLogger("test")
        
        record = logger.makeRecord(
            name="test",
            level=logging.INFO,
            fn="test.py",
            lno=10,
            msg="Query processed",
            args=(),
            exc_info=None
        )
        
        # Add custom fields
        record.node = "generation"
        record.domain = "it"
        record.user_id = "user123"
        record.session_id = "session456"
        record.latency_ms = 1234.56
        record.tokens = 512
        record.cost = 0.0012
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert log_data["node"] == "generation"
        assert log_data["domain"] == "it"
        assert log_data["user_id"] == "user123"
        assert log_data["session_id"] == "session456"
        assert log_data["latency_ms"] == 1234.56
        assert log_data["tokens"] == 512
        assert log_data["cost"] == 0.0012
    
    def test_json_with_exception(self):
        """Test exception info is included in JSON."""
        formatter = StructuredFormatter()
        logger = logging.getLogger("test")
        
        exc_info = None
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        
        record = logger.makeRecord(
            name="test",
            level=logging.ERROR,
            fn="test.py",
            lno=10,
            msg="Error occurred",
            args=(),
            exc_info=exc_info
        )
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert log_data["level"] == "ERROR"
        assert "exc_info" in log_data
        assert "ValueError" in log_data["exc_info"]
        assert "Test error" in log_data["exc_info"]


class TestSetupStructuredLogging:
    """Test logging setup function."""
    
    def test_setup_json_logging(self, capsys):
        """Test setup with JSON format enabled."""
        setup_structured_logging(log_level="INFO", json_format=True)
        
        logger = logging.getLogger()
        logger.info("Test message", extra={"node": "test_node"})
        
        captured = capsys.readouterr()
        
        # Should be valid JSON
        log_line = captured.out.strip().split("\n")[-1]
        log_data = json.loads(log_line)
        
        assert log_data["level"] == "INFO"
        assert log_data["message"] == "Test message"
        assert log_data["node"] == "test_node"
    
    def test_setup_standard_logging(self, capsys):
        """Test setup with standard text format."""
        setup_structured_logging(log_level="INFO", json_format=False)
        
        logger = logging.getLogger()
        logger.info("Test message")
        
        captured = capsys.readouterr()
        
        # Should NOT be JSON (plain text)
        assert "Test message" in captured.out
        assert "{" not in captured.out  # No JSON braces
    
    def test_log_levels(self, capsys):
        """Test different log levels."""
        setup_structured_logging(log_level="DEBUG", json_format=True)
        
        logger = logging.getLogger("test")
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        
        captured = capsys.readouterr()
        
        assert "DEBUG" in captured.out
        assert "INFO" in captured.out
        assert "WARNING" in captured.out
        assert "ERROR" in captured.out
    
    def test_log_level_filtering(self, capsys):
        """Test that log level filtering works."""
        setup_structured_logging(log_level="WARNING", json_format=True)
        
        logger = logging.getLogger("test")
        logger.debug("Debug message - should not appear")
        logger.info("Info message - should not appear")
        logger.warning("Warning message - should appear")
        
        captured = capsys.readouterr()
        
        assert "Debug message" not in captured.out
        assert "Info message" not in captured.out
        assert "Warning message" in captured.out


class TestLogContext:
    """Test LogContext context manager."""
    
    def test_context_enrichment(self, capsys):
        """Test logs are enriched with context metadata."""
        setup_structured_logging(log_level="INFO", json_format=True)
        logger = logging.getLogger("test")
        
        with LogContext(user_id="user123", session_id="session456"):
            logger.info("Processing query", extra={"node": "intent_detection"})
        
        captured = capsys.readouterr()
        log_line = captured.out.strip().split("\n")[-1]
        log_data = json.loads(log_line)
        
        assert log_data["user_id"] == "user123"
        assert log_data["session_id"] == "session456"
        assert log_data["node"] == "intent_detection"
    
    def test_context_cleanup(self, capsys):
        """Test context is cleaned up after exiting."""
        setup_structured_logging(log_level="INFO", json_format=True)
        logger = logging.getLogger("test")
        
        # Log inside context
        with LogContext(user_id="user123"):
            logger.info("Inside context")
        
        # Log outside context
        logger.info("Outside context")
        
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        
        # First log should have user_id
        log1 = json.loads(lines[-2])
        assert "user_id" in log1
        assert log1["user_id"] == "user123"
        
        # Second log should NOT have user_id
        log2 = json.loads(lines[-1])
        assert "user_id" not in log2
    
    def test_nested_context(self, capsys):
        """Test nested LogContext managers."""
        setup_structured_logging(log_level="INFO", json_format=True)
        logger = logging.getLogger("test")
        
        with LogContext(user_id="user123"):
            with LogContext(session_id="session456"):
                logger.info("Nested context")
        
        captured = capsys.readouterr()
        log_line = captured.out.strip().split("\n")[-1]
        log_data = json.loads(log_line)
        
        # Both context values should be present
        assert log_data["user_id"] == "user123"
        assert log_data["session_id"] == "session456"


class TestLogNodeExecution:
    """Test log_node_execution helper function."""
    
    def test_basic_node_logging(self, capsys):
        """Test basic node execution logging."""
        setup_structured_logging(log_level="INFO", json_format=True)
        logger = logging.getLogger("test")
        
        log_node_execution(
            logger,
            node="generation",
            message="LLM response generated",
            level="INFO"
        )
        
        captured = capsys.readouterr()
        log_line = captured.out.strip().split("\n")[-1]
        log_data = json.loads(log_line)
        
        assert log_data["level"] == "INFO"
        assert log_data["node"] == "generation"
        assert log_data["message"] == "LLM response generated"
    
    def test_node_logging_with_metadata(self, capsys):
        """Test node logging with additional metadata."""
        setup_structured_logging(log_level="INFO", json_format=True)
        logger = logging.getLogger("test")
        
        log_node_execution(
            logger,
            node="generation",
            message="Processing completed",
            level="INFO",
            domain="it",
            user_id="user123",
            session_id="session456",
            latency_ms=1234.56,
            tokens=512,
            cost=0.0012
        )
        
        captured = capsys.readouterr()
        log_line = captured.out.strip().split("\n")[-1]
        log_data = json.loads(log_line)
        
        assert log_data["node"] == "generation"
        assert log_data["domain"] == "it"
        assert log_data["user_id"] == "user123"
        assert log_data["session_id"] == "session456"
        assert log_data["latency_ms"] == 1234.56
        assert log_data["tokens"] == 512
        assert log_data["cost"] == 0.0012
    
    def test_node_logging_error_level(self, capsys):
        """Test node logging with ERROR level."""
        setup_structured_logging(log_level="INFO", json_format=True)
        logger = logging.getLogger("test")
        
        log_node_execution(
            logger,
            node="retrieval",
            message="Qdrant query failed",
            level="ERROR",
            domain="it"
        )
        
        captured = capsys.readouterr()
        log_line = captured.out.strip().split("\n")[-1]
        log_data = json.loads(log_line)
        
        assert log_data["level"] == "ERROR"
        assert log_data["node"] == "retrieval"
        assert log_data["message"] == "Qdrant query failed"


class TestLokiIntegration:
    """Test Loki-specific logging patterns."""
    
    def test_json_parseable_output(self, capsys):
        """Test all output is valid JSON for Loki ingestion."""
        setup_structured_logging(log_level="INFO", json_format=True)
        logger = logging.getLogger("test")
        
        # Simulate agent workflow
        with LogContext(user_id="user123", session_id="session456"):
            log_node_execution(logger, "intent_detection", "Intent detected", domain="it")
            log_node_execution(logger, "plan", "Plan created", domain="it")
            log_node_execution(logger, "retrieval", "Documents retrieved", domain="it", latency_ms=234.5)
            log_node_execution(logger, "generation", "Response generated", domain="it", tokens=1024, cost=0.002)
        
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        
        # All lines should be valid JSON
        for line in lines:
            if line.strip():  # Skip empty lines
                log_data = json.loads(line)
                assert "timestamp" in log_data
                assert "level" in log_data
                assert "message" in log_data
    
    def test_logql_queryable_fields(self, capsys):
        """Test logs contain fields queryable by LogQL."""
        setup_structured_logging(log_level="INFO", json_format=True)
        logger = logging.getLogger("test")
        
        log_node_execution(
            logger,
            node="generation",
            message="Query processed",
            domain="it",
            user_id="user123",
            session_id="session456",
            latency_ms=1234.56
        )
        
        captured = capsys.readouterr()
        log_line = captured.out.strip().split("\n")[-1]
        log_data = json.loads(log_line)
        
        # Verify all critical fields for LogQL queries
        assert "node" in log_data  # {container="backend"} | json | node="generation"
        assert "domain" in log_data  # {container="backend"} | json | domain="it"
        assert "user_id" in log_data  # {container="backend"} | json | user_id="user123"
        assert "session_id" in log_data  # {container="backend"} | json | session_id="session456"
        assert "latency_ms" in log_data  # {container="backend"} | json | latency_ms > 1000
        assert "level" in log_data  # {container="backend"} | json | level="ERROR"
    
    def test_timestamp_format(self, capsys):
        """Test timestamp is in ISO8601 UTC format for Loki."""
        setup_structured_logging(log_level="INFO", json_format=True)
        logger = logging.getLogger("test")
        
        logger.info("Test message")
        
        captured = capsys.readouterr()
        log_line = captured.out.strip().split("\n")[-1]
        log_data = json.loads(log_line)
        
        # Timestamp should be ISO8601 with Z suffix
        assert log_data["timestamp"].endswith("Z")
        assert "T" in log_data["timestamp"]
        
        # Should be parseable as datetime
        from datetime import datetime
        parsed = datetime.fromisoformat(log_data["timestamp"].replace("Z", "+00:00"))
        assert parsed is not None
