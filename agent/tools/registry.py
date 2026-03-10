"""Tool registry for managing and discovering tools"""

from typing import Dict, Optional, List
from .base import Tool


class ToolRegistry:
    """Registry for managing all available tools"""
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """Register a new tool"""
        if self.get(tool.name) is not None:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool
    
    def get(self, name: str) -> Optional[Tool]:
        """Get tool by name"""
        return self._tools.get(name)
    
    def exists(self, name: str) -> bool:
        """Check if tool is registered"""
        return name in self._tools
    
    def list_all(self) -> List[str]:
        """List all tool names"""
        return list(self._tools.keys())
    
    def get_all_info(self) -> Dict[str, dict]:
        """Get info for all tools"""
        return {name: tool.get_info() for name, tool in self._tools.items()}
    
    def get_info(self, name: str) -> Optional[dict]:
        """Get info for specific tool"""
        tool = self.get(name)
        return tool.get_info() if tool else None
