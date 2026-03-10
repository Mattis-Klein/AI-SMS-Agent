"""Uptime tool"""

import subprocess
from typing import Any, Dict, Optional
from ..base import Tool, ToolResult


class UptimeTool(Tool):
    def __init__(self):
        super().__init__(
            name="uptime",
            description="Get system uptime in hours",
            requires_args=False,
        )
    
    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        if args:
            return False, "uptime does not accept arguments"
        return True, ""
    
    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        try:
            result = subprocess.run(
                ["powershell", "-Command", 
                 "(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime | Select-Object -ExpandProperty TotalHours | ForEach-Object { [math]::Round($_, 2) }"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode != 0:
                return ToolResult(success=False, output="", error=result.stderr or "Failed to get uptime", tool_name=self.name)
            
            hours = result.stdout.strip()
            return ToolResult(success=True, output=f"System uptime: {hours} hours", tool_name=self.name, arguments=args)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error="Command timeout", tool_name=self.name)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e), tool_name=self.name)
