"""Disk space tool"""

import subprocess
from typing import Any, Dict, Optional
from ..base import Tool, ToolResult


class DiskSpaceTool(Tool):
    def __init__(self):
        super().__init__(
            name="disk_space",
            description="Check disk space on C: drive",
            requires_args=False,
        )
    
    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        if args:
            return False, "disk_space does not accept arguments"
        return True, ""
    
    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        try:
            result = subprocess.run(
                ["cmd", "/c", 'wmic logicaldisk where "DeviceID=\'C:\'" get FreeSpace,Size'],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode != 0:
                return ToolResult(success=False, output="", error=result.stderr or "Failed to get disk space", tool_name=self.name)
            
            return ToolResult(success=True, output=result.stdout, tool_name=self.name, arguments=args)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error="Command timeout", tool_name=self.name)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e), tool_name=self.name)
