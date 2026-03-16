from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from .email_accounts import EmailAccountStore
from assistants.bucherim.admin import BucherimAdminService


class ControlBoardService:
    def __init__(self, runtime):
        self.runtime = runtime
        self.email_accounts = EmailAccountStore(runtime.base_dir)
        self.bucherim_admin = BucherimAdminService(runtime.base_dir)

    def _agent_log_path(self) -> Path:
        return self.runtime.base_dir / "data" / "logs" / "agent.log"

    def _agent_config_path(self) -> Path:
        return self.runtime.base_dir / "agent" / "config.json"

    def _load_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _save_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _read_jsonl(self, path: Path, limit: int = 200) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                rows.append({"raw": line})
        return rows[-limit:]

    def _tail_events(self, limit: int = 120) -> list[dict[str, Any]]:
        rows = self._read_jsonl(self._agent_log_path(), limit=limit)
        return [row for row in rows if isinstance(row, dict)]

    def recent_tool_actions(self, limit: int = 25) -> list[dict[str, Any]]:
        events = self._tail_events(limit=400)
        actions: list[dict[str, Any]] = []
        for ev in reversed(events):
            if ev.get("event_type") != "tool_execution":
                continue
            arguments = ev.get("arguments") if isinstance(ev.get("arguments"), dict) else {}
            actions.append(
                {
                    "timestamp": ev.get("time"),
                    "assistant": ev.get("sender") or ev.get("source") or "desktop",
                    "requested_action": ev.get("interpreted_intent") or ev.get("tool_name"),
                    "selected_tool": ev.get("tool_name"),
                    "result": "success" if ev.get("success") else "failure",
                    "state": "blocked" if "allowed" in str(ev.get("error") or "").lower() else ("success" if ev.get("success") else "failure"),
                    "target": arguments.get("path") or arguments.get("parent_path"),
                    "details": ev.get("error") or ev.get("output"),
                    "source": ev.get("source") or "desktop",
                }
            )
            if len(actions) >= limit:
                break
        return actions

    def recent_failures(self, limit: int = 10) -> list[dict[str, Any]]:
        events = self._tail_events(limit=400)
        failures: list[dict[str, Any]] = []
        for ev in reversed(events):
            if ev.get("event_type") == "tool_execution" and not ev.get("success"):
                failures.append(
                    {
                        "timestamp": ev.get("time"),
                        "assistant": ev.get("sender") or ev.get("source") or "backend",
                        "tool": ev.get("tool_name"),
                        "state": "failure",
                        "error": ev.get("error"),
                    }
                )
            elif ev.get("event_type") == "error":
                failures.append(
                    {
                        "timestamp": ev.get("time"),
                        "assistant": ev.get("sender") or ev.get("source") or "backend",
                        "tool": ev.get("tool_name"),
                        "state": "failure",
                        "error": ev.get("error_message") or ev.get("error_type"),
                    }
                )
            if len(failures) >= limit:
                break
        return failures

    def bridge_health(self) -> dict[str, Any]:
        try:
            with urllib.request.urlopen("http://127.0.0.1:34567/health", timeout=1.2) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
            return {"connected": True, "detail": payload}
        except Exception as exc:
            return {"connected": False, "detail": str(exc)}

    def overview(self) -> dict[str, Any]:
        summary = self.runtime.summary()
        return {
            "backend": {
                "connected": True,
                "workspace": summary.get("workspace"),
                "model": summary.get("assistant_model"),
                "ai_enabled": summary.get("assistant_ai_enabled"),
            },
            "bridge": self.bridge_health(),
            "email": {
                "configured": self.email_accounts.is_configured(),
                "accounts": len(self.email_accounts.list_accounts()),
            },
            "active_assistant": "mashbak",
            "recent_failures": self.recent_failures(limit=10),
            "recent_actions": self.recent_tool_actions(limit=12),
        }

    def activity(self, limit: int = 100) -> dict[str, Any]:
        cap = max(10, min(int(limit or 100), 500))
        return {"items": self.recent_tool_actions(limit=cap), "count": cap}

    def email_accounts_summary(self) -> dict[str, Any]:
        return self.email_accounts.list_public_accounts()

    def save_email_account(self, **kwargs: Any) -> dict[str, Any]:
        return self.email_accounts.save_account(**kwargs)

    def delete_email_account(self, account_id: str) -> dict[str, Any]:
        return self.email_accounts.delete_account(account_id)

    def set_default_email_account(self, account_id: str) -> dict[str, Any]:
        return self.email_accounts.set_default(account_id)

    def test_email_account(self, account_id: str | None) -> dict[str, Any]:
        success, message = self.email_accounts.test_account(account_id)
        return {"success": success, "message": message}

    def files_policy(self) -> dict[str, Any]:
        allowed = [str(item) for item in self.runtime.config.get_allowed_directories()]
        blocked_attempts = []
        for ev in self._tail_events(limit=250):
            if ev.get("event_type") != "tool_execution" or ev.get("success"):
                continue
            err = str(ev.get("error") or "")
            if "allowed" in err.lower() or "path is not in allowed directories" in err.lower():
                args = ev.get("arguments") if isinstance(ev.get("arguments"), dict) else {}
                blocked_attempts.append(
                    {
                        "timestamp": ev.get("time"),
                        "tool": ev.get("tool_name"),
                        "path": args.get("path") or args.get("parent_path"),
                        "error": err,
                    }
                )
        return {"allowed_directories": allowed, "blocked_attempts": blocked_attempts[-60:]}

    def save_files_policy(self, allowed_directories: list[str]) -> dict[str, Any]:
        normalized = [str(Path(p).expanduser().resolve()) for p in allowed_directories if str(p).strip()]
        payload = self._load_json(self._agent_config_path(), default={})
        payload["allowed_directories"] = normalized
        self._save_json(self._agent_config_path(), payload)
        self.runtime.config.load()
        return {"success": True, "allowed_directories": normalized}

    def test_path_allowed(self, path_text: str) -> dict[str, Any]:
        path_value = str(path_text or "").strip()
        if not path_value:
            return {"allowed": False, "reason": "Path is empty"}
        requested = Path(path_value).expanduser().resolve()
        workspace = self.runtime.workspace.resolve()
        if requested.is_relative_to(workspace):
            return {"allowed": True, "reason": f"Allowed: workspace-relative ({requested})"}
        for allowed in self.runtime.config.get_allowed_directories():
            base = Path(allowed).expanduser().resolve()
            if requested.is_relative_to(base):
                return {"allowed": True, "reason": f"Allowed: within {base}"}
        return {"allowed": False, "reason": "Blocked: path is not in allowed directories"}

    def assistants(self) -> dict[str, Any]:
        bucherim = self.bucherim_admin.assistants_summary()
        return {
            "mashbak": {
                "model": self.runtime.openai_model,
                "base_url": self.runtime.openai_base_url,
                "temperature": self.runtime.openai_temperature,
                "max_tokens": self.runtime.model_response_max_tokens,
                "ai_enabled": bool(self.runtime.openai_api_key),
            },
            "bucherim": bucherim,
        }

    def routing(self) -> dict[str, Any]:
        return self.bucherim_admin.routing_overview()

    def approve_member(self, phone_number: str) -> dict[str, Any]:
        return self.bucherim_admin.approve_member(phone_number)

    def block_member(self, phone_number: str) -> dict[str, Any]:
        return self.bucherim_admin.block_member(phone_number)

    def routing_member(self, phone_number: str) -> dict[str, Any]:
        return self.bucherim_admin.member_detail(phone_number)