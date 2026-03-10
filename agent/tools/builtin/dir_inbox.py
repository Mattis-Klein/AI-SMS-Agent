"""Dir inbox tool - list files in inbox directory"""

import subprocess
from typing import Any, Dict, Optional
from ..base import Tool, ToolResult


class DirInboxTool(Tool):
    def __init__(self):
        super().__init__(
            name="dir_inbox",
            description="List files in the inbox directory",
            requires_args=False,
        )
    
    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        if args:
            return False, "dir_inbox does not accept arguments"
        return True, ""
    
    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        try:
            workspace = context.get("workspace") if context else None
            if not workspace:
                return ToolResult(success=False, output="", error="Workspace not configured")
            
            inbox_path = str(workspace / "inbox")
            result = subprocess.run(
                ["cmd", "/c", "dir", inbox_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode != 0:
                return ToolResult(success=False, output="", error=result.stderr or "Failed to list inbox")
            
            return ToolResult(success=True, output=result.stdout, tool_name=self.name, arguments=args)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error="Command timeout", tool_name=self.name)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e), tool_name=self.name)
