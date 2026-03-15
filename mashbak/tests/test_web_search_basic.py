"""Quick test of web search functionality."""

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from agent.tools.builtin.web_search import WebSearchTool

def test_web_search():
    """Test web search tool."""
    print("\nTesting WebSearchTool...")
    print("="*60)
    
    tool = WebSearchTool()
    print(f"Tool name: {tool.name}")
    print(f"Tool description: {tool.description}")
    
    # Test validation
    print("\n1. Testing argument validation:")
    is_valid, msg = tool.validate_args({"query": "current US president"})
    print(f"   Valid query 'current US president': {is_valid}")
    
    is_valid, msg = tool.validate_args({"query": ""})
    print(f"   Empty query validation: {is_valid} (should be False)")
    print(f"   Error message: {msg}")
    
    # Test sync search (synchronous version)
    print("\n2. Testing synchronous search:")
    try:
        results = tool._search_sync("current events today")
        print(f"   Search for 'current events today': {len(results)} results")
        if results:
            print(f"   First result: {results[0].get('title')[:80]}...")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test text cleanup helper for basic parsing behavior
    print("\n3. Testing HTML cleanup helper:")
    cleaned = tool._clean_html("<b>Current &amp; Verified</b>")
    print(f"   Cleaned text: {cleaned}")
    assert cleaned == "Current & Verified"
    
    print("\n✓ Basic web search tests passed")

if __name__ == "__main__":
    test_web_search()
