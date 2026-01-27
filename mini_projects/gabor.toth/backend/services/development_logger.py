"""Development Logger for today's features (5 Advanced RAG Suggestions)."""

from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, asdict
import json


@dataclass
class DevLog:
    """Single development log entry."""
    timestamp: float  # milliseconds for JS compatibility
    feature: str  # Which of the 5 suggestions this log is for
    event: str  # What happened (e.g., "started", "completed", "error")
    description: str  # Human-readable description
    status: str  # "processing", "success", "error"
    details: Dict[str, Any]  # Additional metadata
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class DevelopmentLogger:
    """Logger for today's 5 Advanced RAG Suggestions features."""
    
    FEATURES = {
        "conversation_history": "#1: Conversation History",
        "retrieval_check": "#2: Retrieval Before Tools",
        "checkpointing": "#3: Workflow Checkpointing",
        "reranking": "#4: Semantic Reranking",
        "hybrid_search": "#5: Hybrid Search",
    }
    
    def __init__(self, max_logs: int = 500):
        self.max_logs = max_logs
        self.logs: List[DevLog] = []
    
    def log(
        self,
        feature: str,
        event: str,
        description: str,
        status: str = "info",
        details: Optional[Dict[str, Any]] = None
    ) -> DevLog:
        """Add a log entry for a development feature.
        
        Args:
            feature: One of: "conversation_history", "retrieval_check", "checkpointing", "reranking", "hybrid_search"
            event: What happened (e.g., "started", "completed", "error")
            description: Human-readable description
            status: "processing", "success", "error"
            details: Additional metadata (will be displayed to user)
        
        Returns:
            The created DevLog entry
        """
        now_ms = datetime.now().timestamp() * 1000
        
        dev_log = DevLog(
            timestamp=now_ms,
            feature=feature,
            event=event,
            description=description,
            status=status,
            details=details or {}
        )
        
        self.logs.append(dev_log)
        
        # Keep only the last max_logs entries
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]
        
        return dev_log
    
    def log_suggestion_1_history(
        self,
        event: str,
        description: str,
        details: Optional[Dict[str, Any]] = None
    ) -> DevLog:
        """Log Suggestion #1: Conversation History."""
        return self.log("conversation_history", event, description, "success", details)
    
    def log_suggestion_2_retrieval(
        self,
        event: str,
        description: str,
        details: Optional[Dict[str, Any]] = None
    ) -> DevLog:
        """Log Suggestion #2: Retrieval Before Tools."""
        return self.log("retrieval_check", event, description, "success", details)
    
    def log_suggestion_3_checkpoint(
        self,
        event: str,
        description: str,
        details: Optional[Dict[str, Any]] = None
    ) -> DevLog:
        """Log Suggestion #3: Workflow Checkpointing."""
        return self.log("checkpointing", event, description, "success", details)
    
    def log_suggestion_4_reranking(
        self,
        event: str,
        description: str,
        details: Optional[Dict[str, Any]] = None
    ) -> DevLog:
        """Log Suggestion #4: Semantic Reranking."""
        return self.log("reranking", event, description, "success", details)
    
    def log_suggestion_5_hybrid(
        self,
        event: str,
        description: str,
        details: Optional[Dict[str, Any]] = None
    ) -> DevLog:
        """Log Suggestion #5: Hybrid Search."""
        return self.log("hybrid_search", event, description, "success", details)
    
    def get_logs(self, feature: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get logs as dictionaries for frontend.
        
        Args:
            feature: Filter by feature (optional)
            limit: Maximum number of logs to return
        
        Returns:
            List of log dictionaries (newest first)
        """
        filtered = self.logs
        
        if feature:
            filtered = [log for log in filtered if log.feature == feature]
        
        # Return newest first, limited to 'limit'
        result = [log.to_dict() for log in reversed(filtered)]
        return result[:limit]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all logged features."""
        summary = {}
        
        for feature_key, feature_name in self.FEATURES.items():
            feature_logs = [log for log in self.logs if log.feature == feature_key]
            summary[feature_key] = {
                "name": feature_name,
                "total_events": len(feature_logs),
                "success_count": len([log for log in feature_logs if log.status == "success"]),
                "error_count": len([log for log in feature_logs if log.status == "error"]),
                "last_event": feature_logs[-1].event if feature_logs else None,
            }
        
        return summary
    
    def clear(self):
        """Clear all logs."""
        self.logs = []


# Format logs for human-readable display (for terminal/IDE output)
def format_dev_logs_for_display(logs: List[Dict[str, Any]]) -> str:
    """Format logs for human-readable terminal/IDE display."""
    if not logs:
        return "No logs yet."
    
    lines = []
    lines.append("\n" + "="*80)
    lines.append("📊 DEVELOPMENT LOGS (Today's Features)")
    lines.append("="*80 + "\n")
    
    # Group by feature
    by_feature = {}
    for log in logs:
        # Handle both dict and DevLog object
        feature = log["feature"] if isinstance(log, dict) else log.feature
        if feature not in by_feature:
            by_feature[feature] = []
        by_feature[feature].append(log)
    
    # Display by feature
    for feature_key in ["conversation_history", "retrieval_check", "checkpointing", "reranking", "hybrid_search"]:
        if feature_key not in by_feature:
            continue
        
        feature_logs = by_feature[feature_key]
        feature_name = DevelopmentLogger.FEATURES[feature_key]
        
        lines.append(f"\n🔹 {feature_name}")
        lines.append("-" * 80)
        
        for log in feature_logs:
            # Handle both dict and DevLog object
            status = log["status"] if isinstance(log, dict) else log.status
            
            # Status emoji
            status_emoji = {
                "success": "✅",
                "error": "❌",
                "processing": "🔄",
                "info": "ℹ️"
            }.get(status, "•")
            
            # Extract fields - handle both dict and DevLog object
            if isinstance(log, dict):
                ts = datetime.fromtimestamp(log["timestamp"] / 1000).strftime("%H:%M:%S")
                event = log["event"]
                description = log["description"]
                details = log.get("details")
            else:
                ts = datetime.fromtimestamp(log.timestamp / 1000).strftime("%H:%M:%S")
                event = log.event
                description = log.description
                details = log.details
            
            lines.append(f"  {status_emoji} [{ts}] {event.upper()}: {description}")
            
            # Details if present
            if details:
                if isinstance(details, dict):
                    for key, value in details.items():
                        lines.append(f"      └─ {key}: {value}")
                else:
                    lines.append(f"      └─ {details}")
    
    lines.append("\n" + "="*80)
    return "\n".join(lines)


# Global development logger instance
_dev_logger_instance: Optional[DevelopmentLogger] = None


def get_dev_logger() -> DevelopmentLogger:
    """Get or create the global development logger instance."""
    global _dev_logger_instance
    if _dev_logger_instance is None:
        _dev_logger_instance = DevelopmentLogger()
    return _dev_logger_instance
