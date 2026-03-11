"""Current time tool"""

import subprocess
from typing import Any, Dict, Optional
from ..base import Tool, ToolResult


class CurrentTimeTool(Tool):
    def __init__(self):
        super().__init__(
            name="current_time",
            description="Get current system date and time",
            requires_args=False,
        )
    
    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        if args:
            return False, "current_time does not accept arguments"
        return True, ""
    
    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        try:
            result = subprocess.run(
                ["cmd", "/c", "echo %date% %time%"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode != 0:
                return ToolResult(success=False, output="", error=result.stderr or "Failed to get time", tool_name=self.name)
            
            return ToolResult(success=True, output=result.stdout.strip(), tool_name=self.name, arguments=args)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error="Command timeout", tool_name=self.name)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e), tool_name=self.name)
