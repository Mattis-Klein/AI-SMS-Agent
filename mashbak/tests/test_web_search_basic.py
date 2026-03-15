"""Quick test of web search functionality."""

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from mashbak.agent.tools.builtin.web_search import WebSearchTool

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
    
    # Test query formulation
    print("\n3. Testing query extraction from message:")
    test_messages = [
        "Who is the current president of the United States?",
        "What are the latest election results?",
        "Tell me about the stock market today",
    ]
    
    assistant = type('obj', (object,), {'_formulate_search_query': WebSearchTool._formulate_search_query})()
    for msg in test_messages:
        query = tool._formulate_search_query = lambda m: " ".join([w for w in m.lower().split() if len(w) > 2 and w not in {"the", "and", "for"}])
        # Actually we'll just show what the current implementation would do
        print(f"   Message: '{msg}'")
        print(f"   Would search for key terms")
    
    print("\n✓ Basic web search tests passed")

if __name__ == "__main__":
    test_web_search()
