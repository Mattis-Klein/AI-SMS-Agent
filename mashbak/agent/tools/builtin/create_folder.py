"""Create folder tool - create a directory in a validated location."""

from pathlib import Path
from typing import Any, Dict, Optional

from ..base import Tool, ToolResult


class CreateFolderTool(Tool):
    def __init__(self):
        super().__init__(
            name="create_folder",
            description="Create a folder in a validated directory",
            requires_args=True,
        )

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        has_path = bool(str(args.get("path", "")).strip())
        has_name = bool(str(args.get("name", "")).strip())
        has_parent = bool(str(args.get("parent_path", "")).strip())

        if has_path:
            return True, ""
        if has_name and has_parent:
            return True, ""
        return False, "Provide either 'path' or both 'parent_path' and 'name'"

    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        try:
            workspace = context.get("workspace") if context else None
            allowed_dirs = context.get("allowed_directories", []) if context else []
            if not workspace:
                return ToolResult(success=False, output="", error="Workspace not configured", tool_name=self.name)

            target_text = self._resolve_target_text(args)
            is_safe, resolved = self._validate_path(target_text, workspace, allowed_dirs)
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
            if target.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Folder already exists: {target}",
                    error_type="validation_failure",
                    tool_name=self.name,
                    arguments=args,
                    data={"existing_path": str(target)},
                )

            target.mkdir(parents=True, exist_ok=False)
            return ToolResult(
                success=True,
                output=f"Folder created: {target}",
                tool_name=self.name,
                arguments=args,
                data={
                    "created_path": str(target),
                    "fs_action": "create_folder",
                    "action_status": "success",
                },
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to create folder: {exc}",
                error_type="execution_failure",
                tool_name=self.name,
                arguments=args,
            )

    def _resolve_target_text(self, args: Dict[str, Any]) -> str:
        path = str(args.get("path", "")).strip()
        if path:
            return path
        parent = str(args.get("parent_path", "")).strip()
        name = str(args.get("name", "")).strip()
        return str(Path(parent) / name)

    def _validate_path(self, user_path: str, workspace: Path, allowed_dirs: list) -> tuple[bool, str]:
        try:
            resolved_workspace = workspace.resolve()
            expanded = Path(user_path).expanduser().resolve()

            # Permit workspace-relative references.
            resolved_relative = (resolved_workspace / user_path).resolve()
            if resolved_relative.is_relative_to(resolved_workspace):
                return True, str(resolved_relative)

            normalized_allowed = [
                Path(allowed_dir).expanduser().resolve() if isinstance(allowed_dir, str) else allowed_dir.expanduser().resolve()
                for allowed_dir in allowed_dirs
            ]
            if any(expanded.is_relative_to(allowed) for allowed in normalized_allowed):
                return True, str(expanded)

            return False, "Path is not in allowed directories"
        except Exception as exc:
            return False, f"Path validation error: {exc}"
