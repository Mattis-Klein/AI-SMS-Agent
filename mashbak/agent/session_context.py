"""In-memory per-session conversation context for Mashbak backend."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class SessionContext:
    session_id: str
    last_topic: str | None = None
    last_intent: str | None = None
    last_tool: str | None = None
    last_failure_type: str | None = None
    last_entities: dict[str, Any] = field(default_factory=dict)
    missing_config_fields: list[str] = field(default_factory=list)
    config_progress_state: str | None = None
    pending_restart_components: list[str] = field(default_factory=list)
    recent_turns: list[dict[str, Any]] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    def snapshot(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "last_topic": self.last_topic,
            "last_intent": self.last_intent,
            "last_tool": self.last_tool,
            "last_failure_type": self.last_failure_type,
            "last_entities": dict(self.last_entities),
            "missing_config_fields": list(self.missing_config_fields),
            "config_progress_state": self.config_progress_state,
            "pending_restart_components": list(self.pending_restart_components),
            "recent_turns": list(self.recent_turns),
            "updated_at": self.updated_at,
        }


class SessionContextManager:
    """Stores lightweight context in memory only; resets when process restarts."""

    def __init__(self, max_recent_turns: int = 4):
        self.max_recent_turns = max(1, int(max_recent_turns))
        self._sessions: dict[str, SessionContext] = {}
        self._lock = Lock()

    def get(self, session_id: str) -> SessionContext:
        with self._lock:
            return self._ensure_session_unlocked(session_id)

    def _ensure_session_unlocked(self, session_id: str) -> SessionContext:
        context = self._sessions.get(session_id)
        if context is None:
            context = SessionContext(session_id=session_id)
            self._sessions[session_id] = context
        return context

    def get_snapshot(self, session_id: str) -> dict[str, Any]:
        return self.get(session_id).snapshot()

    def update(
        self,
        *,
        session_id: str,
        user_message: str,
        parsed: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            context = self._ensure_session_unlocked(session_id)
            context.last_intent = parsed.get("intent") or context.last_intent
            context.last_tool = result.get("tool_name") or parsed.get("tool") or context.last_tool
            context.last_failure_type = result.get("error_type") or context.last_failure_type

            topic = parsed.get("topic") or parsed.get("followup_topic")
            if topic:
                context.last_topic = topic
            elif context.last_tool and "email" in context.last_tool:
                context.last_topic = "email_access"

            entities = dict(parsed.get("entities") or {})
            if entities:
                context.last_entities = entities

            explicit_missing = result.get("missing_config_fields")
            if explicit_missing is not None:
                context.missing_config_fields = list(explicit_missing)

            config_data = result.get("data") if isinstance(result.get("data"), dict) else {}
            restart_required = config_data.get("restart_required")
            if isinstance(restart_required, list):
                context.pending_restart_components = list(restart_required)

            if parsed.get("tool") == "set_config_variable":
                variable_name = str((parsed.get("args") or {}).get("variable_name", "")).strip().upper()
                if variable_name and context.missing_config_fields:
                    next_missing: list[str] = []
                    for item in context.missing_config_fields:
                        options = [part.strip().upper() for part in str(item).split("|") if part.strip()]
                        if variable_name in options:
                            continue
                        next_missing.append(item)
                    context.missing_config_fields = next_missing

            if context.missing_config_fields:
                context.config_progress_state = "in_progress"
            elif parsed.get("tool") == "set_config_variable":
                context.config_progress_state = "complete"
            elif context.config_progress_state is None:
                context.config_progress_state = "idle"

            turn = {
                "message": user_message,
                "intent": parsed.get("intent"),
                "tool": result.get("tool_name") or parsed.get("tool"),
                "success": result.get("success"),
                "error_type": result.get("error_type"),
                "topic": context.last_topic,
                "missing_config_fields": list(context.missing_config_fields),
                "config_progress_state": context.config_progress_state,
            }
            context.recent_turns.append(turn)
            context.recent_turns = context.recent_turns[-self.max_recent_turns :]
            context.updated_at = time.time()
            return context.snapshot()
