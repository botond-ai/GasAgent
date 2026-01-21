"""
Verification test for service injection and connection pooling.

Tests:
1. Singleton service reuse verification
2. Connection pool initialization check
3. DI container consistency
4. Tool layer service injection

Run: docker exec knowledge_router_backend python debug/test_service_injection.py
"""

import sys
import os
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_singleton_services():
    """Test that DI container returns same singleton instances."""
    print("\n" + "="*70)
    print("TEST 1: Singleton Service Reuse")
    print("="*70)
    
    from core.dependencies import (
        get_config_service,
        get_embedding_service,
        get_qdrant_service
    )
    
    # Get services multiple times
    config1 = get_config_service()
    config2 = get_config_service()
    
    embedding1 = get_embedding_service()
    embedding2 = get_embedding_service()
    
    qdrant1 = get_qdrant_service()
    qdrant2 = get_qdrant_service()
    
    # Verify same instance (id comparison)
    config_same = id(config1) == id(config2)
    embedding_same = id(embedding1) == id(embedding2)
    qdrant_same = id(qdrant1) == id(qdrant2)
    
    print(f"  ConfigService singleton: {'✅ PASS' if config_same else '❌ FAIL'}")
    print(f"    - Instance 1 ID: {id(config1)}")
    print(f"    - Instance 2 ID: {id(config2)}")
    
    print(f"\n  EmbeddingService singleton: {'✅ PASS' if embedding_same else '❌ FAIL'}")
    print(f"    - Instance 1 ID: {id(embedding1)}")
    print(f"    - Instance 2 ID: {id(embedding2)}")
    
    print(f"\n  QdrantService singleton: {'✅ PASS' if qdrant_same else '❌ FAIL'}")
    print(f"    - Instance 1 ID: {id(qdrant1)}")
    print(f"    - Instance 2 ID: {id(qdrant2)}")
    
    all_pass = config_same and embedding_same and qdrant_same
    print(f"\n{'✅ TEST 1 PASSED' if all_pass else '❌ TEST 1 FAILED'}")
    
    return all_pass


def test_connection_pool():
    """Test that connection pool is initialized."""
    print("\n" + "="*70)
    print("TEST 2: Connection Pool Initialization")
    print("="*70)
    
    try:
        from database.pg_connection import get_connection_pool, get_db_connection
        
        # Get pool (should be initialized)
        pool = get_connection_pool()
        
        print(f"  Connection pool type: {type(pool).__name__}")
        print(f"  Pool minconn: {pool.minconn}")
        print(f"  Pool maxconn: {pool.maxconn}")
        
        # Test getting a connection
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 as test_value")
                result = cursor.fetchone()
                connection_works = result['test_value'] == 1
        
        print(f"\n  Connection pool functional: {'✅ PASS' if connection_works else '❌ FAIL'}")
        
        # Check pool stats (basic info)
        print(f"\n  Pool configuration:")
        print(f"    - Min connections: {pool.minconn}")
        print(f"    - Max connections: {pool.maxconn}")
        
        print(f"\n{'✅ TEST 2 PASSED' if connection_works else '❌ TEST 2 FAILED'}")
        
        return connection_works
    
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        logger.error(f"Connection pool test failed: {e}", exc_info=True)
        print("\n❌ TEST 2 FAILED")
        return False


def test_tool_layer_injection():
    """Test that tools use injected singleton services."""
    print("\n" + "="*70)
    print("TEST 3: Tool Layer Service Injection")
    print("="*70)
    
    try:
        from services.knowledge_tools import create_knowledge_tools
        from core.dependencies import get_embedding_service, get_qdrant_service
        
        # Get singleton services
        singleton_embedding = get_embedding_service()
        singleton_qdrant = get_qdrant_service()
        
        # Create tools
        tools = create_knowledge_tools()
        
        print(f"  Total tools created: {len(tools)}")
        
        # Find specific tools
        embedding_tool = next((t for t in tools if t.name == "generate_embedding"), None)
        vector_tool = next((t for t in tools if t.name == "search_vectors"), None)
        
        # Verify service injection (same instance)
        embedding_injected = id(embedding_tool.embedding_service) == id(singleton_embedding)
        qdrant_injected = id(vector_tool.qdrant_service) == id(singleton_qdrant)
        
        print(f"\n  GenerateEmbeddingTool uses singleton: {'✅ PASS' if embedding_injected else '❌ FAIL'}")
        print(f"    - Tool service ID: {id(embedding_tool.embedding_service)}")
        print(f"    - Singleton ID:    {id(singleton_embedding)}")
        
        print(f"\n  SearchVectorsTool uses singleton: {'✅ PASS' if qdrant_injected else '❌ FAIL'}")
        print(f"    - Tool service ID: {id(vector_tool.qdrant_service)}")
        print(f"    - Singleton ID:    {id(singleton_qdrant)}")
        
        all_pass = embedding_injected and qdrant_injected
        print(f"\n{'✅ TEST 3 PASSED' if all_pass else '❌ TEST 3 FAILED'}")
        
        return all_pass
    
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        logger.error(f"Tool injection test failed: {e}", exc_info=True)
        print("\n❌ TEST 3 FAILED")
        return False


def test_workflow_di_usage():
    """Test that workflow uses DI container."""
    print("\n" + "="*70)
    print("TEST 4: Workflow Layer DI Usage")
    print("="*70)
    
    try:
        import os
        from services.unified_chat_workflow import UnifiedChatWorkflow
        from core.dependencies import get_embedding_service, get_qdrant_service
        
        # Get singletons
        singleton_embedding = get_embedding_service()
        singleton_qdrant = get_qdrant_service()
        
        # Create workflow
        api_key = os.getenv("OPENAI_API_KEY")
        workflow = UnifiedChatWorkflow(openai_api_key=api_key)
        
        # Verify workflow uses same singleton instances
        embedding_same = id(workflow.embedding_service) == id(singleton_embedding)
        qdrant_same = id(workflow.qdrant_service) == id(singleton_qdrant)
        
        print(f"  Workflow uses singleton EmbeddingService: {'✅ PASS' if embedding_same else '❌ FAIL'}")
        print(f"    - Workflow service ID: {id(workflow.embedding_service)}")
        print(f"    - Singleton ID:        {id(singleton_embedding)}")
        
        print(f"\n  Workflow uses singleton QdrantService: {'✅ PASS' if qdrant_same else '❌ FAIL'}")
        print(f"    - Workflow service ID: {id(workflow.qdrant_service)}")
        print(f"    - Singleton ID:        {id(singleton_qdrant)}")
        
        all_pass = embedding_same and qdrant_same
        print(f"\n{'✅ TEST 4 PASSED' if all_pass else '❌ TEST 4 FAILED'}")
        
        return all_pass
    
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        logger.error(f"Workflow DI test failed: {e}", exc_info=True)
        print("\n❌ TEST 4 FAILED")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("SERVICE INJECTION & CONNECTION POOLING VERIFICATION")
    print("="*70)
    
    results = {
        "Singleton Service Reuse": test_singleton_services(),
        "Connection Pool Init": test_connection_pool(),
        "Tool Layer Injection": test_tool_layer_injection(),
        "Workflow DI Usage": test_workflow_di_usage()
    }
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test_name}: {status}")
    
    total = len(results)
    passed_count = sum(results.values())
    
    print(f"\nTotal: {total} | Passed: {passed_count} | Failed: {total - passed_count}")
    
    if all(results.values()):
        print("\n✅ ALL TESTS PASSED - Service injection working correctly!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED - Check implementation!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
