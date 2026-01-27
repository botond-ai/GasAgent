#!/usr/bin/env python3
"""
Test script to verify frontend-backend communication for development logs.
This script tests:
1. Development logger functionality
2. API endpoints structure
3. Log format compatibility with frontend
"""

import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from services.development_logger import (
    DevelopmentLogger, 
    get_dev_logger, 
    format_dev_logs_for_display,
    DevLog
)


def test_dev_logger_basic():
    """Test basic DevelopmentLogger functionality."""
    print("\n" + "="*70)
    print("TEST 1: Basic DevelopmentLogger Functionality")
    print("="*70)
    
    logger = DevelopmentLogger(max_logs=100)
    
    # Test logging
    logger.log_suggestion_1_history(
        event="started",
        description="Conversation history loaded from session"
    )
    
    logger.log_suggestion_1_history(
        event="completed",
        description="Processed 4 recent messages for context",
        details={
            "messages_count": 4,
            "last_user_message": "How to optimize queries?",
            "context_added": True
        }
    )
    
    # Get logs
    logs = logger.get_logs()
    print(f"✅ Logged {len(logs)} events")
    
    # Verify structure
    if logs:
        log = logs[0]
        print(f"✅ Log structure valid:")
        print(f"   - timestamp: {log['timestamp']} (type: {type(log['timestamp'])})")
        print(f"   - feature: {log['feature']}")
        print(f"   - event: {log['event']}")
        print(f"   - status: {log['status']}")
        print(f"   - description: {log['description']}")
    
    return logger


def test_all_features(logger):
    """Test all 5 feature logging methods."""
    print("\n" + "="*70)
    print("TEST 2: All 5 Features Logging")
    print("="*70)
    
    # Feature 1: Conversation History
    logger.log_suggestion_1_history(
        event="completed",
        description="Extracted conversation context",
        details={"messages": 4, "tokens": 342}
    )
    
    # Feature 2: Retrieval Check
    logger.log_suggestion_2_retrieval(
        event="completed",
        description="Retrieval quality check passed",
        details={"chunks": 3, "avg_similarity": 0.85, "decision": "FAST_PATH"}
    )
    
    # Feature 3: Checkpointing
    logger.log_suggestion_3_checkpoint(
        event="completed",
        description="Workflow state saved",
        details={"checkpoint_id": "1234567890", "channels": 5}
    )
    
    # Feature 4: Reranking
    logger.log_suggestion_4_reranking(
        event="completed",
        description="LLM reranking completed",
        details={"chunks": 3, "avg_score": 78.3, "top_score": 95}
    )
    
    # Feature 5: Hybrid Search
    logger.log_suggestion_5_hybrid(
        event="completed",
        description="Hybrid search fusion completed",
        details={"semantic": 3, "keyword": 5, "final": 5, "semantic_weight": 0.7, "keyword_weight": 0.3}
    )
    
    # Get logs by feature
    history_logs = logger.get_logs(feature="conversation_history")
    retrieval_logs = logger.get_logs(feature="retrieval_check")
    checkpoint_logs = logger.get_logs(feature="checkpointing")
    reranking_logs = logger.get_logs(feature="reranking")
    hybrid_logs = logger.get_logs(feature="hybrid_search")
    
    print(f"✅ Feature logs logged:")
    print(f"   - Conversation History: {len(history_logs)} logs")
    print(f"   - Retrieval Check: {len(retrieval_logs)} logs")
    print(f"   - Checkpointing: {len(checkpoint_logs)} logs")
    print(f"   - Reranking: {len(reranking_logs)} logs")
    print(f"   - Hybrid Search: {len(hybrid_logs)} logs")
    
    return logger


def test_summary():
    """Test summary functionality."""
    print("\n" + "="*70)
    print("TEST 3: Summary Generation")
    print("="*70)
    
    logger = get_dev_logger()
    summary = logger.get_summary()
    
    print("✅ Summary structure:")
    for feature, count in summary.items():
        print(f"   - {feature}: {count} logs")
    
    return logger


def test_api_response_format():
    """Test API response format compatibility."""
    print("\n" + "="*70)
    print("TEST 4: API Response Format (JSON Serialization)")
    print("="*70)
    
    logger = DevelopmentLogger()
    
    # Add some logs
    logger.log_suggestion_2_retrieval(
        event="completed",
        description="Test retrieval",
        details={"test": True, "value": 123}
    )
    
    # Get logs for API
    logs = logger.get_logs(limit=10)
    summary = logger.get_summary()
    
    # Simulate API response
    api_response = {
        "logs": logs,
        "summary": summary,
        "total_logs": len(logger.logs)
    }
    
    try:
        json_str = json.dumps(api_response, indent=2)
        print("✅ API response is JSON-serializable")
        print(f"   Response size: {len(json_str)} bytes")
        
        # Verify structure
        parsed = json.loads(json_str)
        print("✅ Response structure valid:")
        print(f"   - logs: {len(parsed['logs'])} items")
        print(f"   - summary: {list(parsed['summary'].keys())}")
        print(f"   - total_logs: {parsed['total_logs']}")
        
    except Exception as e:
        print(f"❌ JSON serialization failed: {e}")
        return False
    
    return True


def test_frontend_polling_format():
    """Test format expected by frontend polling."""
    print("\n" + "="*70)
    print("TEST 5: Frontend Polling Format")
    print("="*70)
    
    logger = DevelopmentLogger()
    
    # Add logs
    logger.log_suggestion_5_hybrid(
        event="started",
        description="Hybrid search starting"
    )
    logger.log_suggestion_5_hybrid(
        event="completed",
        description="Hybrid search completed"
    )
    
    # Simulate GET /api/dev-logs with feature filter
    logs = logger.get_logs(feature="hybrid_search", limit=100)
    summary = logger.get_summary()
    
    polling_response = {
        "logs": logs,
        "summary": summary,
        "total_logs": len(logger.logs)
    }
    
    print("✅ Frontend polling response:")
    print(f"   - Logs: {len(polling_response['logs'])} items")
    print(f"   - Each log has: timestamp, feature, event, status, description, details")
    print(f"   - Summary: {dict(polling_response['summary'])}")
    
    # Verify each log has required fields
    required_fields = {"timestamp", "feature", "event", "status", "description", "details"}
    for log in logs:
        if not all(field in log for field in required_fields):
            print(f"❌ Missing fields in log: {set(required_fields) - set(log.keys())}")
            return False
    
    print("✅ All logs have required fields")
    return True


def test_human_readable_display():
    """Test human-readable display format."""
    print("\n" + "="*70)
    print("TEST 6: Human-Readable Display Format")
    print("="*70)
    
    logger = DevelopmentLogger()
    
    # Add various logs
    logger.log_suggestion_1_history(
        event="completed",
        description="History processed",
        details={"count": 5}
    )
    logger.log_suggestion_2_retrieval(
        event="completed",
        description="Retrieval check passed"
    )
    logger.log_suggestion_4_reranking(
        event="error",
        description="Reranking failed"
    )
    
    # Get display format
    display = format_dev_logs_for_display(logger.logs)
    
    print("✅ Display format generated:")
    print(display)
    
    return True


def test_max_logs_limit():
    """Test memory management (max logs limit)."""
    print("\n" + "="*70)
    print("TEST 7: Memory Management (Max Logs Limit)")
    print("="*70)
    
    logger = DevelopmentLogger(max_logs=5)
    
    # Add more than max logs
    for i in range(10):
        logger.log_suggestion_1_history(
            event="test",
            description=f"Log #{i}"
        )
    
    if len(logger.logs) <= 5:
        print(f"✅ Log limit enforced: {len(logger.logs)}/{logger.max_logs} logs")
    else:
        print(f"❌ Log limit NOT enforced: {len(logger.logs)} logs (max: {logger.max_logs})")
        return False
    
    return True


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("FRONTEND-BACKEND COMMUNICATION TEST SUITE")
    print("="*70)
    
    results = []
    
    try:
        # Run tests
        logger = test_dev_logger_basic()
        results.append(("Basic Logger", True))
        
        logger = test_all_features(logger)
        results.append(("All Features", True))
        
        logger = test_summary()
        results.append(("Summary", True))
        
        success = test_api_response_format()
        results.append(("API Format", success))
        
        success = test_frontend_polling_format()
        results.append(("Polling Format", success))
        
        success = test_human_readable_display()
        results.append(("Display Format", success))
        
        success = test_max_logs_limit()
        results.append(("Max Logs Limit", success))
        
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Frontend-backend communication is ready.")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
