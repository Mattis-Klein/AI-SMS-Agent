"""Delete file tool - remove a file from a validated path."""

from pathlib import Path
from typing import Any, Dict, Optional

from ..base import Tool, ToolResult


class DeleteFileTool(Tool):
    def __init__(self):
        super().__init__(
            name="delete_file",
            description="Delete a file at a validated path",
            requires_args=True,
        )

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        has_path = bool(str(args.get("path", "")).strip())
        if not has_path:
            return False, "Provide 'path' — the file to delete"
        return True, ""

    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        try:
            workspace = context.get("workspace") if context else None
            allowed_dirs = context.get("allowed_directories", []) if context else []
            if not workspace:
                return ToolResult(success=False, output="", error="Workspace not configured", tool_name=self.name)

            raw_path = str(args.get("path", "")).strip()
            is_safe, resolved = self._validate_path(raw_path, workspace, allowed_dirs)
            if not is_safe:
                return ToolResult(
                    success=False,
                    output="",
                    error=resolved,
                    error_type="denied_action",
                    tool_name=self.name,
                    arguments=args,
                )

            target = Path(resolved)

            if not target.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"File not found: {target.name}",
                    error_type="validation_failure",
                    tool_name=self.name,
                    arguments=args,
                )

            if target.is_dir():
                return ToolResult(
                    success=False,
                    output="",
                    error="That path is a folder, not a file. Use a folder-removal command instead.",
                    error_type="validation_failure",
                    tool_name=self.name,
                    arguments=args,
                )

            target.unlink()

            # Post-deletion verification: confirm the file is actually gone.
            if target.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error="File deletion appeared to succeed but the file still exists.",
                    error_type="execution_failure",
                    tool_name=self.name,
                    arguments=args,
                )

            return ToolResult(
                success=True,
                output=f"File deleted: {target}",
                tool_name=self.name,
                arguments=args,
                data={
                    "deleted_path": str(target),
                    "fs_action": "delete_file",
                    "action_status": "success",
                },
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to delete file: {exc}",
                error_type="execution_failure",
                tool_name=self.name,
                arguments=args,
            )

    def _validate_path(self, user_path: str, workspace: Path, allowed_dirs: list) -> tuple[bool, str]:
        try:
            resolved_workspace = workspace.resolve()
            expanded = Path(user_path).expanduser().resolve()

            # Allow workspace-relative paths.
            resolved_relative = (resolved_workspace / user_path).resolve()
            if resolved_relative.is_relative_to(resolved_workspace):
                return True, str(resolved_relative)

            normalized_allowed = [
                Path(d).expanduser().resolve() if isinstance(d, str) else d.expanduser().resolve()
                for d in allowed_dirs
            ]
            if any(expanded.is_relative_to(a) for a in normalized_allowed):
                return True, str(expanded)

            return False, "Path is not in allowed directories"
        except Exception as exc:
            return False, f"Path validation error: {exc}"
