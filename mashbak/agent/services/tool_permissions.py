from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ToolPermissionsStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir.resolve()
        self.path = self.base_dir / "data" / "config" / "tool_permissions.json"

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"tools": {}}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            payload = {"tools": {}}
        if not isinstance(payload, dict):
            payload = {"tools": {}}
        payload.setdefault("tools", {})
        return payload

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def _default_for_tool(tool_name: str, description: str = "") -> dict[str, Any]:
        sensitive = {
            "delete_file",
            "move_file",
            "launch_program",
            "run_project_command",
            "send_email",
            "capture_screenshot",
        }
        risky_sources = ["desktop"] if tool_name in sensitive else ["desktop", "sms", "voice"]
        return {
            "enabled": True,
            "allowed_sources": risky_sources,
            "requires_approval": tool_name in sensitive,
            "requires_unlocked_desktop": tool_name in sensitive or tool_name in {"capture_screenshot"},
            "scope": "default",
            "description": description,
        }

    def ensure_registry(self, tool_info: dict[str, Any]) -> dict[str, Any]:
        payload = self._read()
        tools = payload.get("tools") or {}
        changed = False
        for tool_name, info in tool_info.items():
            if tool_name in tools:
                continue
            tools[tool_name] = self._default_for_tool(tool_name, str((info or {}).get("description") or ""))
            changed = True
        payload["tools"] = tools
        if changed:
            self._write(payload)
        return payload

    def list(self, tool_info: dict[str, Any]) -> dict[str, Any]:
        payload = self.ensure_registry(tool_info)
        return {"tools": payload.get("tools") or {}}

    def get(self, tool_name: str, tool_info: dict[str, Any]) -> dict[str, Any]:
        payload = self.ensure_registry(tool_info)
        tools = payload.get("tools") or {}
        return tools.get(tool_name) or self._default_for_tool(tool_name)

    def set_tool(self, tool_name: str, settings: dict[str, Any], tool_info: dict[str, Any]) -> dict[str, Any]:
        payload = self.ensure_registry(tool_info)
        tools = payload.get("tools") or {}
        current = dict(tools.get(tool_name) or self._default_for_tool(tool_name))
        for key in ("enabled", "allowed_sources", "requires_approval", "requires_unlocked_desktop", "scope", "description"):
            if key in settings:
                current[key] = settings[key]
        tools[tool_name] = current
        payload["tools"] = tools
        self._write(payload)
        return current
