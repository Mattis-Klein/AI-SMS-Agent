"""System info tool"""

import subprocess
from typing import Any, Dict, Optional
from ..base import Tool, ToolResult


class SystemInfoTool(Tool):
    def __init__(self):
        super().__init__(
            name="system_info",
            description="Get basic system information (OS, version, memory)",
            requires_args=False,
        )
    
    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        if args:
            return False, "system_info does not accept arguments"
        return True, ""
    
    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        try:
            ps_script = (
                "$os = Get-CimInstance Win32_OperatingSystem; "
                "$memoryGb = [math]::Round(($os.TotalVisibleMemorySize / 1MB), 2); "
                "Write-Output ('OS Name: ' + $os.Caption); "
                "Write-Output ('OS Version: ' + $os.Version); "
                "Write-Output ('System Type: ' + $os.OSArchitecture); "
                "Write-Output ('Total Physical Memory: ' + $memoryGb + ' GB')"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode != 0:
                return ToolResult(success=False, output="", error=result.stderr or "Failed to get system info", tool_name=self.name)
            
            return ToolResult(success=True, output=result.stdout, tool_name=self.name, arguments=args)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error="Command timeout", tool_name=self.name)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e), tool_name=self.name)
