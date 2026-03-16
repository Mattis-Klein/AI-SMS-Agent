from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from ...config_loader import ConfigLoader
from ..base import Tool, ToolResult
from .path_utils import resolve_safe_path


class RunProjectCommandTool(Tool):
    def __init__(self):
        super().__init__(
            name="run_project_command",
            description="Run an approved project command in a safe directory",
            requires_args=True,
            category="system",
            safety={"destructive": False, "sensitive": True},
        )

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        if not str(args.get("working_directory") or "").strip():
            return False, "working_directory is required"
        if not str(args.get("command") or "").strip():
            return False, "command is required"
        return True, ""

    def _allowed_prefixes(self) -> tuple[str, ...]:
        raw = str(ConfigLoader.get("APPROVED_PROJECT_COMMAND_PREFIXES", "") or "")
        parts = [p.strip().lower() for p in raw.split(",") if p.strip()]
        return tuple(parts) if parts else ("npm run", "npm test", "pytest", "python", "git status", "git diff")

    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        workspace = context.get("workspace") if context else None
        allowed_dirs = context.get("allowed_directories", []) if context else []
        if not workspace:
            return ToolResult(success=False, output="", error="Workspace not configured", tool_name=self.name)

        ok, reason, path = resolve_safe_path(str(args.get("working_directory") or ""), Path(workspace), allowed_dirs)
        if not ok or path is None:
            return ToolResult(success=False, output="", error=reason, error_type="denied_action", tool_name=self.name, arguments=args)

        command = str(args.get("command") or "").strip()
        allowed = self._allowed_prefixes()
        if not any(command.lower().startswith(prefix) for prefix in allowed):
            return ToolResult(success=False, output="", error="Command prefix is not approved", error_type="denied_action", tool_name=self.name, arguments=args)

        result = subprocess.run(command, cwd=str(path), shell=True, capture_output=True, text=True, timeout=45)
        text = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        return ToolResult(
            success=result.returncode == 0,
            output=text.strip() or f"Command exited with code {result.returncode}",
            error=None if result.returncode == 0 else f"Command failed with code {result.returncode}",
            error_type=None if result.returncode == 0 else "execution_failure",
            tool_name=self.name,
            arguments=args,
            data={"exit_code": result.returncode, "working_directory": str(path), "command": command},
        )
