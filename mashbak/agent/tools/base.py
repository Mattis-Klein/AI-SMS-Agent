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
    error_type: Optional[str] = None
    tool_name: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
    data: Optional[Any] = None
    missing_config_fields: Optional[list[str]] = None
    remediation: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "error_type": self.error_type,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "data": self.data,
            "missing_config_fields": self.missing_config_fields,
            "remediation": self.remediation,
        }


@dataclass
class ComparisonContext:
    """Context for tool-selection comparison"""
    user_message: str
    workspace_path: str
    allowed_directories: list


class Tool(ABC):
    """Base class for all tools"""
    
    def __init__(
        self,
        name: str,
        description: str,
        requires_args: bool = False,
        category: str = "general",
        input_schema: Optional[Dict[str, Any]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        safety: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.description = description
        self.requires_args = requires_args
        self.category = category
        self.input_schema = input_schema or {}
        self.output_schema = output_schema or {}
        self.safety = safety or {}
    
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
            "category": self.category,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "safety": self.safety,
        }
