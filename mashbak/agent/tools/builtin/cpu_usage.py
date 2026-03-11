"""CPU usage tool"""

from typing import Any, Dict, Optional

import psutil

from ..base import Tool, ToolResult


class CpuUsageTool(Tool):
    def __init__(self):
        super().__init__(
            name="cpu_usage",
            description="Check current CPU usage percentage",
            requires_args=False,
        )
    
    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        if args:
            return False, "cpu_usage does not accept arguments"
        return True, ""
    
    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        try:
            cpu_percent = round(psutil.cpu_percent(interval=0.35), 2)
            return ToolResult(
                success=True,
                output=f"CPU Usage: {cpu_percent}%",
                tool_name=self.name,
                arguments=args,
                data={"cpu_percent": cpu_percent},
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e), tool_name=self.name)
