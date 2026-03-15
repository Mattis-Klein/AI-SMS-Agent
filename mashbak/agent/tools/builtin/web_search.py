"""Web search tool for retrieving current information from the internet."""

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

if __package__:
    from ..base import Tool, ToolResult
else:
    from ..base import Tool, ToolResult


class WebSearchTool(Tool):
    """
    Performs web searches to retrieve current information.
    Uses DuckDuckGo API which requires no authentication.
    Designed to ground responses in current facts to prevent hallucinations
    on time-sensitive topics like elections, news, statistics, etc.
    """

    def __init__(self):
        super().__init__(
            name="web_search",
            description="Search the internet for current information on a topic. Returns a list of relevant results "
            "with titles, snippets, and URLs. Useful for verifying time-sensitive facts like elections, news, "
            "statistics, schedules, public figures, and current events.",
            requires_args=True,
        )
        self.max_results = 5
        self.timeout_seconds = 10.0

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        """Validate that search query is provided."""
        if not isinstance(args, dict):
            return False, "Arguments must be a dictionary"
        
        query = (args.get("query") or "").strip()
        if not query:
            return False, "A search query is required"
        
        if len(query) > 200:
            return False, "Query must be 200 characters or less"
        
        return True, ""

    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        """
        Execute a web search and return structured results.
        
        Args:
            args: Dictionary with 'query' key containing the search string
            context: Optional context (not used but included for Tool interface)
        
        Returns:
            ToolResult with list of search results or error message
        """
        try:
            query = (args.get("query") or "").strip()
            is_valid, error_msg = self.validate_args(args)
            if not is_valid:
                return ToolResult(
                    success=False,
                    output=error_msg,
                    error=error_msg,
                    error_type="validation_error",
                    tool_name=self.name,
                    arguments=args,
                )

            results = await asyncio.to_thread(self._search_sync, query)
            
            if not results:
                return ToolResult(
                    success=False,
                    output="No search results found for that query.",
                    error="No results returned from search",
                    error_type="no_results",
                    tool_name=self.name,
                    arguments=args,
                )

            # Format results for display
            output_lines = [f"Found {len(results)} results for: {query}\n"]
            for i, result in enumerate(results, 1):
                output_lines.append(f"{i}. {result.get('title', 'Untitled')}")
                if result.get("snippet"):
                    output_lines.append(f"   {result['snippet'][:150]}...")
                if result.get("url"):
                    output_lines.append(f"   Source: {result['url']}")
                output_lines.append("")

            output = "\n".join(output_lines)
            
            return ToolResult(
                success=True,
                output=output,
                error=None,
                tool_name=self.name,
                arguments=args,
                data={
                    "query": query,
                    "result_count": len(results),
                    "results": results,
                },
            )

        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                output="Web search timed out. Unable to retrieve results.",
                error="Search operation timed out",
                error_type="timeout",
                tool_name=self.name,
                arguments=args,
            )
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            return ToolResult(
                success=False,
                output="Could not connect to search service. Check your internet connection.",
                error=f"Network error: {str(e)[:100]}",
                error_type="network_error",
                tool_name=self.name,
                arguments=args,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="An unexpected error occurred while searching.",
                error=f"Unexpected error: {str(e)[:100]}",
                error_type="unexpected_error",
                tool_name=self.name,
                arguments=args,
            )

    def _search_sync(self, query: str) -> list[Dict[str, Any]]:
        """
        Synchronous web search implementation using DuckDuckGo API.
        """
        try:
            results = self._duckduckgo_search(query)
            return results[:self.max_results]
        except Exception:
            # Fallback to alternative method if API fails
            try:
                results = self._fallback_google_search(query)
                return results[:self.max_results]
            except Exception:
                return []

    def _duckduckgo_search(self, query: str) -> list[Dict[str, Any]]:
        """Search using DuckDuckGo's API (no auth required)."""
        # DuckDuckGo has an instant answer API available at:
        # https://api.duckduckgo.com/?q=query&format=json
        
        # For better results, we'll use the HTML search results with parsing
        # since the instant answer API doesn't return traditional search results
        
        # Using a simple approach: fetch DuckDuckGo search results
        search_url = f"https://html.duckduckgo.com/html?q={urllib.parse.quote(query)}"
        
        # DuckDuckGo requires a proper User-Agent
        request = urllib.request.Request(
            search_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                html = response.read().decode("utf-8", errors="replace")
            
            # Parse basic HTML results
            results = self._parse_html_results(html)
            return results
        except Exception:
            # If HTML parsing fails, try JSON API
            return self._duckduckgo_instant_json(query)

    def _duckduckgo_instant_json(self, query: str) -> list[Dict[str, Any]]:
        """Fallback: Use DuckDuckGo instant answer API (limited but reliable)."""
        api_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_redirect=1&no_html=1"
        
        request = urllib.request.Request(
            api_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
            
            results = []
            
            # Add instant answer if available
            if data.get("AbstractText"):
                results.append({
                    "title": data.get("AbstractTitle", "Answer"),
                    "snippet": data.get("AbstractText", "")[:500],
                    "url": data.get("AbstractURL", ""),
                })
            
            # Add related topics
            if data.get("RelatedTopics"):
                for topic in data.get("RelatedTopics", [])[:4]:
                    if isinstance(topic, dict):
                        results.append({
                            "title": topic.get("Text", "Related")[:100],
                            "snippet": "",
                            "url": topic.get("FirstURL", ""),
                        })
            
            return results
        except Exception:
            return []

    def _parse_html_results(self, html: str) -> list[Dict[str, Any]]:
        """Simple HTML parsing for search results."""
        results = []
        
        # Look for result containers (DuckDuckGo uses specific HTML structure)
        # This is a simplified parser; more robust parsing could use BeautifulSoup
        import re
        
        # Pattern for DuckDuckGo result links
        link_pattern = r'<a class="result__url" href="([^"]+)"[^>]*>([^<]+)</a>'
        title_pattern = r'<a class="result__link" href="[^"]*">([^<]+)</a>'
        snippet_pattern = r'<a class="result__snippet" [^>]*>([^<]+)</a>'
        
        try:
            # Extract results using regex (simplified approach)
            links = re.findall(link_pattern, html)
            titles = re.findall(title_pattern, html)
            snippets = re.findall(snippet_pattern, html)
            
            for i, link_tuple in enumerate(links[:self.max_results]):
                url = link_tuple[0] if isinstance(link_tuple, tuple) else link_tuple
                # Clean up the URL (DuckDuckGo encodes it)
                url = urllib.parse.unquote(url.replace("/l/?kk=", "").split("&uddg=")[0])
                
                title = titles[i] if i < len(titles) else "Search Result"
                snippet = snippets[i] if i < len(snippets) else ""
                
                results.append({
                    "title": self._clean_html(title)[:100],
                    "snippet": self._clean_html(snippet)[:300],
                    "url": url,
                })
            
            return results if results else []
        except Exception:
            return []

    def _fallback_google_search(self, query: str) -> list[Dict[str, Any]]:
        """Fallback using Google's search (less reliable due to rate limiting)."""
        # This is a last-resort fallback using a simple query
        # In production, consider using SerpAPI or similar service
        search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        
        request = urllib.request.Request(
            search_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                html = response.read().decode("utf-8", errors="replace")
            
            # Very basic extraction
            results = []
            import re
            
            # Look for result items
            items = re.findall(
                r'<div class="g"[^>]*>.*?<a href="([^"]*)"[^>]*>([^<]+)</a>.*?<span class="st">([^<]+)</span>',
                html,
                re.DOTALL
            )
            
            for url, title, snippet in items[:self.max_results]:
                results.append({
                    "title": self._clean_html(title)[:100],
                    "snippet": self._clean_html(snippet)[:300],
                    "url": url,
                })
            
            return results
        except Exception:
            return []

    @staticmethod
    def _clean_html(text: str) -> str:
        """Remove HTML tags and entities from text."""
        import re
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        # Decode common HTML entities
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')
        text = text.replace("&#39;", "'")
        text = text.strip()
        return text


import urllib.parse
