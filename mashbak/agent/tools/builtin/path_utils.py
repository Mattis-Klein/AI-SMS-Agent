from __future__ import annotations

from pathlib import Path
from typing import Iterable


def resolve_safe_path(user_path: str, workspace: Path, allowed_dirs: Iterable[Path | str]) -> tuple[bool, str, Path | None]:
    try:
        raw = str(user_path or "").strip()
        if not raw:
            return False, "Path is required", None

        resolved_workspace = workspace.resolve()
        expanded = Path(raw).expanduser()
        if expanded.is_absolute():
            candidate = expanded.resolve()
        else:
            candidate = (resolved_workspace / expanded).resolve()

        if candidate.is_relative_to(resolved_workspace):
            return True, "", candidate

        normalized_allowed = [
            Path(value).expanduser().resolve() if isinstance(value, str) else value.expanduser().resolve()
            for value in allowed_dirs
        ]
        if any(candidate.is_relative_to(base) for base in normalized_allowed):
            return True, "", candidate

        return False, "Path is not in allowed directories", None
    except Exception as exc:
        return False, f"Path validation error: {exc}", None
