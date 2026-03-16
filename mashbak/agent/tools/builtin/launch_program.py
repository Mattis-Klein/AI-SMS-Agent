from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from ...config_loader import ConfigLoader
from ..base import Tool, ToolResult


class LaunchProgramTool(Tool):
    def __init__(self):
        super().__init__(
            name="launch_program",
            description="Launch an approved local program",
            requires_args=True,
            category="system",
            safety={"destructive": False, "sensitive": True},
        )

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        if not str(args.get("program") or "").strip():
            return False, "program is required"
        return True, ""

    def _allowed_programs(self) -> set[str]:
        raw = str(ConfigLoader.get("APPROVED_PROGRAMS", "") or "")
        parts = [p.strip().lower() for p in raw.split(",") if p.strip()]
        default = {"notepad", "calc", "mspaint", "explorer"}
        return set(parts) if parts else default

    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        program = str(args.get("program") or "").strip()
        allowed = self._allowed_programs()
        token = Path(program).stem.lower()
        if token not in allowed:
            return ToolResult(success=False, output="", error=f"Program '{program}' is not in approved list", error_type="denied_action", tool_name=self.name, arguments=args)
        subprocess.Popen([program], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return ToolResult(success=True, output=f"Launched {program}", tool_name=self.name, arguments=args, data={"program": program})
