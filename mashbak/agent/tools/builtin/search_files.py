from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from ..base import Tool, ToolResult
from .path_utils import resolve_safe_path


class SearchFilesTool(Tool):
    def __init__(self):
        super().__init__(
            name="search_files",
            description="Search for files by glob/name under a safe directory",
            requires_args=True,
            category="filesystem",
            safety={"destructive": False},
        )

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        if not str(args.get("root_path") or "").strip():
            return False, "root_path is required"
        if not str(args.get("pattern") or "").strip():
            return False, "pattern is required"
        return True, ""

    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        workspace = context.get("workspace") if context else None
        allowed_dirs = context.get("allowed_directories", []) if context else []
        if not workspace:
            return ToolResult(success=False, output="", error="Workspace not configured", tool_name=self.name)

        ok, reason, root = resolve_safe_path(str(args.get("root_path") or ""), Path(workspace), allowed_dirs)
        if not ok or root is None:
            return ToolResult(success=False, output="", error=reason, error_type="denied_action", tool_name=self.name, arguments=args)
        if not root.exists() or not root.is_dir():
            return ToolResult(success=False, output="", error="root_path must be an existing directory", error_type="validation_failure", tool_name=self.name, arguments=args)

        pattern = str(args.get("pattern") or "*").strip()
        limit = max(1, min(int(args.get("limit") or 50), 200))
        matches = [str(path) for path in root.rglob(pattern)][:limit]

        return ToolResult(
            success=True,
            output="\n".join(matches) if matches else "No matches found.",
            tool_name=self.name,
            arguments=args,
            data={"matches": matches, "count": len(matches), "root": str(root), "pattern": pattern},
        )
