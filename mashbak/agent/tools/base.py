"""Base tool class and types"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ToolResult:
    """Result of tool execution"""
    success: bool
    output: str
    error: Optional[str] = None
    tool_name: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
    data: Optional[Any] = None
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "data": self.data,
        }


@dataclass
class ComparisonContext:
    """Context for tool-selection comparison"""
    user_message: str
    workspace_path: str
    allowed_directories: list


class Tool(ABC):
    """Base class for all tools"""
    
    def __init__(self, name: str, description: str, requires_args: bool = False):
        self.name = name
        self.description = description
        self.requires_args = requires_args
    
    @abstractmethod
    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate input arguments.
        Returns (is_valid, error_message)
        """
        pass
    
    @abstractmethod
    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        """
        Execute the tool.
        Args:
            args: Validated input arguments
            context: Additional context (workspace, allowed_dirs, request_id, sender, etc.)
        Returns:
            ToolResult with success/output/error
        """
        pass
    
    def get_info(self) -> dict:
        """Return tool metadata"""
        return {
            "name": self.name,
            "description": self.description,
            "requires_args": self.requires_args,
        }
