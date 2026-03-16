from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Any, Dict, Optional

from ..base import Tool, ToolResult
from .path_utils import resolve_safe_path


class OpenTargetTool(Tool):
    def __init__(self):
        super().__init__(
            name="open_target",
            description="Open a safe folder path or URL",
            requires_args=True,
            category="system",
            safety={"destructive": False},
        )

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        target = str(args.get("target") or "").strip()
        if not target:
            return False, "target is required"
        return True, ""

    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        target = str(args.get("target") or "").strip()
        if target.startswith("http://") or target.startswith("https://"):
            webbrowser.open(target)
            return ToolResult(success=True, output=f"Opened URL: {target}", tool_name=self.name, arguments=args, data={"target": target, "type": "url"})

        workspace = context.get("workspace") if context else None
        allowed_dirs = context.get("allowed_directories", []) if context else []
        if not workspace:
            return ToolResult(success=False, output="", error="Workspace not configured", tool_name=self.name)
        ok, reason, path = resolve_safe_path(target, Path(workspace), allowed_dirs)
        if not ok or path is None:
            return ToolResult(success=False, output="", error=reason, error_type="denied_action", tool_name=self.name, arguments=args)

        webbrowser.open(str(path))
        return ToolResult(success=True, output=f"Opened target: {path}", tool_name=self.name, arguments=args, data={"target": str(path), "type": "path"})
