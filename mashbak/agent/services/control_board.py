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

    @staticmethod
    def _csv_values(raw: str | None) -> set[str]:
        text = str(raw or "").strip()
        if not text:
            return set()
        return {part.strip().lower() for part in text.split(",") if part.strip()}

    @staticmethod
    def _to_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=True)
        except Exception:
            return str(value)

    def _event_to_activity(self, ev: dict[str, Any]) -> dict[str, Any] | None:
        event_type = str(ev.get("event_type") or "").strip()
        if not event_type:
            return None

        args = ev.get("arguments") if isinstance(ev.get("arguments"), dict) else {}
        source = str(ev.get("source") or ev.get("sender") or "backend")
        tool_name = str(ev.get("tool_name") or ev.get("selected_tool") or "")
        action = ""
        state = "info"
        details = ""

        if event_type == "tool_execution":
            action = str(ev.get("interpreted_intent") or tool_name or "tool execution")
            if ev.get("success"):
                state = "success"
                details = str(ev.get("output") or "")
            else:
                err = str(ev.get("error") or "")
                state = "blocked" if "allowed" in err.lower() else "failure"
                details = err
        elif event_type == "request":
            action = str(ev.get("interpreted_intent") or "request")
            tool_name = tool_name or str(ev.get("selected_tool") or "")
            details = str(ev.get("raw_message") or "")
            state = "received"
        elif event_type == "response":
            action = "response"
            state = str(ev.get("status") or "completed").lower()
            details = str(ev.get("response_message") or "")
        elif event_type == "error":
            action = str(ev.get("error_type") or "error")
            state = "failure"
            details = str(ev.get("error_message") or "")
        elif event_type == "voice_inbound_call":
            action = "voice call received"
            state = "received"
            details = str(ev.get("from_number") or "")
            source = "voice"
        elif event_type == "voice_access_denied":
            action = "voice access denied"
            state = "blocked"
            details = str(ev.get("from_number") or "")
            source = "voice"
        elif event_type == "voice_speech_received":
            action = "voice speech"
            state = "received"
            details = str(ev.get("speech_result") or "")
            source = "voice"
        elif event_type == "voice_assistant_reply":
            action = "voice assistant reply"
            state = "success"
            details = str(ev.get("reply_text") or "")
            source = "voice"
        else:
            action = event_type.replace("_", " ")
            details = self._to_text(ev)

        target = args.get("path") or args.get("parent_path") or args.get("target") or ""
        searchable = " ".join(
            [
                self._to_text(ev.get("request_id")),
                self._to_text(action),
                self._to_text(tool_name),
                self._to_text(source),
                self._to_text(state),
                self._to_text(target),
                self._to_text(details),
            ]
        ).lower()

        return {
            "timestamp": ev.get("time"),
            "event_type": event_type,
            "assistant": ev.get("sender") or source,
            "requested_action": action,
            "selected_tool": tool_name,
            "result": "success" if state == "success" else ("failure" if state == "failure" else state),
            "state": state,
            "target": self._to_text(target),
            "details": details,
            "source": source,
            "request_id": ev.get("request_id"),
            "searchable": searchable,
            "raw_event": ev,
        }

    def recent_tool_actions(self, limit: int = 25) -> list[dict[str, Any]]:
        events = self._tail_events(limit=400)
        actions: list[dict[str, Any]] = []
        for ev in reversed(events):
            if ev.get("event_type") != "tool_execution":
                continue
            item = self._event_to_activity(ev)
            if item:
                item.pop("searchable", None)
                item.pop("raw_event", None)
                actions.append(item)
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
        pending_approvals = self.runtime.approval_store.list(limit=500, status="pending").get("count", 0)
        running_tasks = self.runtime.task_store.list_tasks(limit=500, status="running").get("count", 0)
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
            "pending_approvals": pending_approvals,
            "running_tasks": running_tasks,
            "recent_failures": self.recent_failures(limit=10),
            "recent_actions": self.recent_tool_actions(limit=12),
        }

    def activity(
        self,
        limit: int = 100,
        event_types: str = "",
        sources: str = "",
        tool_name: str = "",
        state: str = "",
        query: str = "",
    ) -> dict[str, Any]:
        cap = max(10, min(int(limit or 100), 500))
        event_filter = self._csv_values(event_types)
        source_filter = self._csv_values(sources)
        tool_filter = str(tool_name or "").strip().lower()
        state_filter = str(state or "").strip().lower()
        query_filter = str(query or "").strip().lower()

        items: list[dict[str, Any]] = []
        for ev in reversed(self._tail_events(limit=1000)):
            item = self._event_to_activity(ev)
            if not item:
                continue
            if event_filter and str(item.get("event_type") or "").lower() not in event_filter:
                continue
            if source_filter and str(item.get("source") or "").lower() not in source_filter:
                continue
            if tool_filter and tool_filter not in str(item.get("selected_tool") or "").lower():
                continue
            if state_filter and state_filter != str(item.get("state") or "").lower():
                continue
            if query_filter and query_filter not in str(item.get("searchable") or ""):
                continue

            item.pop("searchable", None)
            if len(items) < cap:
                items.append(item)

        return {
            "items": items,
            "count": len(items),
            "limit": cap,
            "filters": {
                "event_types": sorted(event_filter),
                "sources": sorted(source_filter),
                "tool_name": tool_filter,
                "state": state_filter,
                "query": query_filter,
            },
        }

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
            return {"success": True, "allowed": False, "normalized_path": "", "reason": "Path is empty"}
        requested = Path(path_value).expanduser().resolve()
        workspace = self.runtime.workspace.resolve()
        if requested.is_relative_to(workspace):
            return {
                "success": True,
                "allowed": True,
                "normalized_path": str(requested),
                "reason": "Allowed: workspace-relative path",
            }
        for allowed in self.runtime.config.get_allowed_directories():
            base = Path(allowed).expanduser().resolve()
            if requested.is_relative_to(base):
                return {
                    "success": True,
                    "allowed": True,
                    "normalized_path": str(requested),
                    "reason": f"Allowed: within {base}",
                }
        return {
            "success": True,
            "allowed": False,
            "normalized_path": str(requested),
            "reason": "Blocked: path is not in allowed directories",
        }

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

    def update_assistant_template(self, template_key: str, template_text: str) -> dict[str, Any]:
        updated = self.bucherim_admin.update_response_template(template_key, template_text)
        return {"success": True, **updated}

    def routing(self) -> dict[str, Any]:
        return self.bucherim_admin.routing_overview()

    def approve_member(self, phone_number: str) -> dict[str, Any]:
        return self.bucherim_admin.approve_member(phone_number)

    def block_member(self, phone_number: str) -> dict[str, Any]:
        return self.bucherim_admin.block_member(phone_number)

    def routing_member(self, phone_number: str) -> dict[str, Any]:
        return self.bucherim_admin.member_detail(phone_number)

    def tools_permissions(self) -> dict[str, Any]:
        info = self.runtime.registry.get_all_info()
        payload = self.runtime.tool_permissions.list(info)
        return {
            "success": True,
            "tools": payload.get("tools") or {},
            "tool_info": info,
            "count": len(info),
        }

    def update_tool_permission(self, tool_name: str, settings: dict[str, Any]) -> dict[str, Any]:
        info = self.runtime.registry.get_all_info()
        updated = self.runtime.tool_permissions.set_tool(tool_name, settings, info)
        return {"success": True, "tool_name": tool_name, "settings": updated}

    def approvals(self, limit: int = 80, status: str = "") -> dict[str, Any]:
        return self.runtime.approval_store.list(limit=limit, status=status)

    async def approve_and_run(self, approval_id: str, reviewer: str = "operator") -> dict[str, Any]:
        approval = self.runtime.approval_store.get(approval_id)
        if not approval:
            return {"success": False, "error": "Approval not found"}
        self.runtime.approval_store.set_status(approval_id, "approved", reviewer=reviewer)
        result = await self.runtime.execute_tool(
            tool_name=str(approval.get("tool_name") or ""),
            args=approval.get("args") if isinstance(approval.get("args"), dict) else {},
            sender=str(approval.get("sender") or "operator"),
            source="desktop",
            owner_unlocked=True,
            approval_id=approval_id,
            approved_by=reviewer,
        )
        return {"success": True, "approval_id": approval_id, "result": result}

    def approve_approval(self, approval_id: str, reviewer: str = "operator") -> dict[str, Any]:
        approval = self.runtime.approval_store.get(approval_id)
        if not approval:
            return {"success": False, "error": "Approval not found"}
        row = self.runtime.approval_store.set_status(approval_id, "approved", reviewer=reviewer)
        if not row:
            return {"success": False, "error": "Approval not found"}
        return {"success": True, "approval": row}

    async def run_approved(self, approval_id: str, reviewer: str = "operator") -> dict[str, Any]:
        approval = self.runtime.approval_store.get(approval_id)
        if not approval:
            return {"success": False, "error": "Approval not found"}
        if str(approval.get("status") or "").lower() != "approved":
            return {"success": False, "error": "Approval must be approved before running"}
        result = await self.runtime.execute_tool(
            tool_name=str(approval.get("tool_name") or ""),
            args=approval.get("args") if isinstance(approval.get("args"), dict) else {},
            sender=str(approval.get("sender") or "operator"),
            source="desktop",
            owner_unlocked=True,
            approval_id=approval_id,
            approved_by=reviewer,
        )
        return {"success": bool(result.get("success", True)), "approval_id": approval_id, "result": result}

    def reject_approval(self, approval_id: str, reviewer: str = "operator") -> dict[str, Any]:
        row = self.runtime.approval_store.set_status(approval_id, "rejected", reviewer=reviewer)
        if not row:
            return {"success": False, "error": "Approval not found"}
        return {"success": True, "approval": row}

    def tasks(self, limit: int = 80, status: str = "") -> dict[str, Any]:
        return self.runtime.task_store.list_tasks(limit=limit, status=status)

    def get_personal_context(self) -> dict[str, Any]:
        payload = self.runtime.personal_context.read()
        return {
            "success": True,
            "profile": payload.get("profile") or {},
            "people": payload.get("people") or [],
            "routines": payload.get("routines") or [],
            "projects": payload.get("projects") or [],
            "preferences": payload.get("preferences") or {},
        }

    def save_personal_context(self, payload: dict[str, Any]) -> dict[str, Any]:
        saved = self.runtime.personal_context.save(payload)
        return {
            "success": True,
            "profile": saved.get("profile") or {},
            "people": saved.get("people") or [],
            "routines": saved.get("routines") or [],
            "projects": saved.get("projects") or [],
            "preferences": saved.get("preferences") or {},
        }