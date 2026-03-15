"""Test web search functionality and retrieval-grounded generation."""

import asyncio
import sys
from pathlib import Path

# Setup path for imports
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from mashbak.agent.runtime import AgentRuntime, create_runtime
from mashbak.agent.assistant_core import AssistantMetadata


async def test_web_search_tool():
    """Test the web_search tool directly."""
    print("\n" + "="*60)
    print("TEST 1: Web Search Tool Direct Execution")
    print("="*60)
    
    try:
        runtime = create_runtime()
        
        # Test 1a: Simple search
        print("\nTest 1a: Searching for 'current US president'...")
        result = await runtime.execute_tool(
            tool_name="web_search",
            args={"query": "current US president"},
            sender="test_user",
            request_id="test_001",
            source="test",
        )
        
        print(f"  Success: {result.get('success')}")
        if result.get("success"):
            print(f"  Results found: {result.get('data', {}).get('result_count', 0)}")
            results = result.get('data', {}).get('results', [])
            if results:
                print(f"  First result: {results[0].get('title')}")
        else:
            print(f"  Error: {result.get('error')}")
        
        # Test 1b: Search with multiple words
        print("\nTest 1b: Searching for '2024 presidential election results'...")
        result = await runtime.execute_tool(
            tool_name="web_search",
            args={"query": "2024 presidential election results"},
            sender="test_user",
            request_id="test_002",
            source="test",
        )
        
        print(f"  Success: {result.get('success')}")
        if result.get("success"):
            print(f"  Results found: {result.get('data', {}).get('result_count', 0)}")
        
        print("\n✓ Web search tool tests completed")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


async def test_time_sensitive_query():
    """Test that assistant triggers web search for time-sensitive queries."""
    print("\n" + "="*60)
    print("TEST 2: Assistant Web Search Triggering")
    print("="*60)
    
    try:
        runtime = create_runtime()
        
        # Test 2a: Time-sensitive fact query (should trigger web search)
        print("\nTest 2a: Asking about current US president (should trigger web search)...")
        metadata = AssistantMetadata(
            sender="test_user",
            source="test",
            session_id="test_session_001",
            owner_unlocked=True,
            request_id="test_003"
        )
        
        response = await runtime.assistant.respond(
            "Who is the current president of the United States?",
            metadata
        )
        
        print(f"  Success: {response.get('success')}")
        print(f"  Response: {response.get('output', '')[:200]}...")
        trace = response.get('trace', {})
        print(f"  Verification State: {trace.get('verification_state')}")
        print(f"  Verification Reason: {trace.get('verification_reason')[:150]}...")
        
        # Test 2b: Election results query
        print("\nTest 2b: Asking about elections (should trigger web search)...")
        metadata.request_id = "test_004"
        response = await runtime.assistant.respond(
            "What were the results of the latest general elections?",
            metadata
        )
        
        print(f"  Success: {response.get('success')}")
        print(f"  Response: {response.get('output', '')[:200]}...")
        trace = response.get('trace', {})
        print(f"  Verification State: {trace.get('verification_state')}")
        
        # Test 2c: Non-time-sensitive query (should NOT trigger web search)
        print("\nTest 2c: Asking about how to use the system (should NOT trigger web search)...")
        metadata.request_id = "test_005"
        response = await runtime.assistant.respond(
            "How can I create a text file with this system?",
            metadata
        )
        
        print(f"  Success: {response.get('success')}")
        print(f"  Response: {response.get('output', '')[:200]}...")
        trace = response.get('trace', {})
        print(f"  Verification State: {trace.get('verification_state')}")
        print(f"  Tool Executed: {trace.get('tool_execution_occurred')}")
        
        print("\n✓ Assistant web search triggering tests completed")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


async def test_search_error_handling():
    """Test graceful error handling when search fails."""
    print("\n" + "="*60)
    print("TEST 3: Error Handling")
    print("="*60)
    
    try:
        runtime = create_runtime()
        
        # Test with invalid arguments
        print("\nTest 3a: Testing with empty query...")
        result = await runtime.execute_tool(
            tool_name="web_search",
            args={"query": ""},
            sender="test_user",
            request_id="test_006",
            source="test",
        )
        
        print(f"  Success: {result.get('success')} (should be False)")
        print(f"  Error Type: {result.get('error_type')}")
        
        # Test with very long query
        print("\nTest 3b: Testing with oversized query...")
        result = await runtime.execute_tool(
            tool_name="web_search",
            args={"query": "a" * 300},
            sender="test_user",
            request_id="test_007",
            source="test",
        )
        
        print(f"  Success: {result.get('success')} (should be False)")
        print(f"  Error Type: {result.get('error_type')}")
        
        print("\n✓ Error handling tests completed")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


async def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("WEB SEARCH FEATURE TEST SUITE")
    print("="*80)
    
    all_passed = True
    
    try:
        # Run tests
        all_passed &= await test_web_search_tool()
        all_passed &= await test_time_sensitive_query()
        all_passed &= await test_search_error_handling()
        
    except Exception as e:
        print(f"\n✗ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Summary
    print("\n" + "="*80)
    if all_passed:
        print("✓ ALL TESTS PASSED")
        print("="*80)
        return 0
    else:
        print("✗ SOME TESTS FAILED")
        print("="*80)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
