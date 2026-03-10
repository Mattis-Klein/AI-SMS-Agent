"""List files tool - list files in a specified directory"""

import subprocess
from pathlib import Path
from typing import Any, Dict, Optional
from ..base import Tool, ToolResult


class ListFilesTool(Tool):
    def __init__(self):
        super().__init__(
            name="list_files",
            description="List files in a specified directory",
            requires_args=True,
        )
    
    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        if "path" not in args:
            return False, "Missing required argument: path"
        if not isinstance(args["path"], str):
            return False, "path must be a string"
        return True, ""
    
    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        try:
            user_path = args.get("path", "")
            workspace = context.get("workspace") if context else None
            allowed_dirs = context.get("allowed_directories", []) if context else []
            
            if not workspace:
                return ToolResult(success=False, output="", error="Workspace not configured")
            
            # Validate path
            is_safe, resolved_path = self._validate_path(user_path, workspace, allowed_dirs)
            if not is_safe:
                return ToolResult(success=False, output="", error=resolved_path, tool_name=self.name)
            
            result = subprocess.run(
                ["cmd", "/c", f"dir \"{resolved_path}\""],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode != 0:
                return ToolResult(success=False, output="", error=result.stderr or "Failed to list directory", tool_name=self.name)
            
            return ToolResult(success=True, output=result.stdout, tool_name=self.name, arguments=args)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error="Command timeout", tool_name=self.name)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e), tool_name=self.name)
    
    def _validate_path(self, user_path: str, workspace: Path, allowed_dirs: list) -> tuple[bool, str]:
        """Validate path is within safe directories"""
        try:
            # Check workspace-relative path first
            resolved = (workspace / user_path).resolve()
            if workspace in resolved.parents or resolved == workspace:
                return True, str(resolved)
            
            # Check allowed directories
            resolved = Path(user_path).resolve()
            for allowed_dir in allowed_dirs:
                allowed = Path(allowed_dir).resolve() if isinstance(allowed_dir, str) else allowed_dir
                if allowed in resolved.parents or resolved == allowed:
                    return True, str(resolved)
            
            return False, "Path is not in allowed directories"
        except Exception as e:
            return False, f"Path validation error: {str(e)}"
