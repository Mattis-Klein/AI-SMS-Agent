from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from ..base import Tool, ToolResult
from .path_utils import resolve_safe_path


class EditFileTool(Tool):
    def __init__(self):
        super().__init__(
            name="edit_file",
            description="Edit a text file by replacing its full content or appending text",
            requires_args=True,
            category="filesystem",
            safety={"destructive": False},
        )

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        path = str(args.get("path") or "").strip()
        if not path:
            return False, "path is required"
        mode = str(args.get("mode") or "replace").strip().lower()
        if mode not in {"replace", "append"}:
            return False, "mode must be 'replace' or 'append'"
        if "content" not in args:
            return False, "content is required"
        return True, ""

    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        workspace = context.get("workspace") if context else None
        allowed_dirs = context.get("allowed_directories", []) if context else []
        if not workspace:
            return ToolResult(success=False, output="", error="Workspace not configured", tool_name=self.name)

        ok, reason, target = resolve_safe_path(str(args.get("path") or ""), Path(workspace), allowed_dirs)
        if not ok or target is None:
            return ToolResult(success=False, output="", error=reason, error_type="denied_action", tool_name=self.name, arguments=args)

        if not target.exists() or target.is_dir():
            return ToolResult(success=False, output="", error="Target file does not exist", error_type="validation_failure", tool_name=self.name, arguments=args)

        mode = str(args.get("mode") or "replace").lower()
        content = str(args.get("content") or "")
        previous = target.read_text(encoding="utf-8", errors="replace")
        if mode == "append":
            updated = previous + content
        else:
            updated = content
        target.write_text(updated, encoding="utf-8")

        return ToolResult(
            success=True,
            output=f"File updated: {target}",
            tool_name=self.name,
            arguments=args,
            data={
                "path": str(target),
                "mode": mode,
                "previous_preview": previous[:300],
                "updated_preview": updated[:300],
                "bytes": len(updated.encode("utf-8")),
            },
        )
