from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from ..base import Tool, ToolResult
from .path_utils import resolve_safe_path


class MoveFileTool(Tool):
    def __init__(self):
        super().__init__(
            name="move_file",
            description="Move a file from source path to destination path",
            requires_args=True,
            category="filesystem",
            safety={"destructive": True},
        )

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        if not str(args.get("source_path") or "").strip():
            return False, "source_path is required"
        if not str(args.get("destination_path") or "").strip():
            return False, "destination_path is required"
        return True, ""

    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        workspace = context.get("workspace") if context else None
        allowed_dirs = context.get("allowed_directories", []) if context else []
        if not workspace:
            return ToolResult(success=False, output="", error="Workspace not configured", tool_name=self.name)

        ok_src, reason_src, src = resolve_safe_path(str(args.get("source_path") or ""), Path(workspace), allowed_dirs)
        ok_dst, reason_dst, dst = resolve_safe_path(str(args.get("destination_path") or ""), Path(workspace), allowed_dirs)
        if not ok_src or src is None:
            return ToolResult(success=False, output="", error=reason_src, error_type="denied_action", tool_name=self.name, arguments=args)
        if not ok_dst or dst is None:
            return ToolResult(success=False, output="", error=reason_dst, error_type="denied_action", tool_name=self.name, arguments=args)
        if not src.exists() or src.is_dir():
            return ToolResult(success=False, output="", error="Source file does not exist", error_type="validation_failure", tool_name=self.name, arguments=args)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return ToolResult(success=True, output=f"Moved file to: {dst}", tool_name=self.name, arguments=args, data={"source": str(src), "destination": str(dst)})
