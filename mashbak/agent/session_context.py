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
    # Rolling window of recent user+assistant turns (bounded by max_recent_turns).
    # Each turn dict includes: role, message, assistant_reply, intent, tool,
    # success, topic, created_path.
    recent_turns: list[dict[str, Any]] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    # --- Structured task state ---
    # The tool the user appeared to be asking for but hasn't executed yet
    # (e.g. asked for a file operation and we're collecting parameters).
    pending_task: str | None = None
    # Parameters collected so far for the pending task.
    pending_parameters: dict[str, Any] = field(default_factory=dict)
    # Parameters still required before the pending task can run.
    missing_parameters: list[str] = field(default_factory=list)
    # The last task that was fully executed (tool name).
    last_task: str | None = None
    # "success" | "failure" | None — outcome of the last tool execution.
    last_result: str | None = None
    # Arguments that were sent to the last executed tool.
    last_args: dict[str, Any] = field(default_factory=dict)
    # Path of the last file or folder created/written by a tool, if any.
    last_created_path: str | None = None

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
            # task state
            "pending_task": self.pending_task,
            "pending_parameters": dict(self.pending_parameters),
            "missing_parameters": list(self.missing_parameters),
            "last_task": self.last_task,
            "last_result": self.last_result,
            "last_args": dict(self.last_args),
            "last_created_path": self.last_created_path,
        }


class SessionContextManager:
    """Stores lightweight context in memory only; resets when process restarts."""

    def __init__(self, max_recent_turns: int = 10):
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

    def record_assistant_reply(self, *, session_id: str, assistant_reply: str) -> None:
        """Append the assistant's reply text to the most recent turn in this session."""
        with self._lock:
            context = self._ensure_session_unlocked(session_id)
            if context.recent_turns:
                context.recent_turns[-1]["assistant_reply"] = assistant_reply
            context.updated_at = time.time()

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
            tool_name = result.get("tool_name") or parsed.get("tool")
            succeeded = bool(result.get("success"))

            context.last_intent = parsed.get("intent") or context.last_intent
            context.last_tool = tool_name or context.last_tool
            context.last_failure_type = result.get("error_type") or context.last_failure_type

            topic = parsed.get("topic") or parsed.get("followup_topic")
            if topic:
                context.last_topic = topic
            elif context.last_tool and "email" in context.last_tool:
                context.last_topic = "email_access"

            entities = dict(parsed.get("entities") or {})
            if entities:
                context.last_entities = entities

            # --- Task state updates ---
            # Track the last completed tool and its args/outcome.
            if tool_name and succeeded:
                context.last_task = tool_name
                context.last_result = "success"
                context.last_args = dict(parsed.get("args") or {})
                # Extract any file/folder path the tool created.
                result_data = result.get("data") if isinstance(result.get("data"), dict) else {}
                created_path = result_data.get("created_path") or result_data.get("path") or result_data.get("file_path")
                if created_path:
                    context.last_created_path = str(created_path)
            elif tool_name and not succeeded:
                context.last_result = "failure"

            # Clear pending task once executed (success or failure).
            if tool_name and context.pending_task == tool_name:
                context.pending_task = None
                context.pending_parameters = {}
                context.missing_parameters = []

            # Capture missing parameters surfaced by failed tool execution.
            tool_missing_params = result.get("missing_parameters")
            if isinstance(tool_missing_params, list):
                context.missing_parameters = list(tool_missing_params)

            # --- Config-specific updates ---
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

            # Build and append the turn record.  assistant_reply is filled later
            # via record_assistant_reply() once the response text is finalized.
            turn: dict[str, Any] = {
                "role": "user",
                "message": user_message,
                "assistant_reply": None,
                "intent": parsed.get("intent"),
                "tool": tool_name,
                "success": result.get("success"),
                "error_type": result.get("error_type"),
                "topic": context.last_topic,
                "created_path": context.last_created_path,
                "missing_config_fields": list(context.missing_config_fields),
                "missing_parameters": list(context.missing_parameters),
                "config_progress_state": context.config_progress_state,
            }
            context.recent_turns.append(turn)
            context.recent_turns = context.recent_turns[-self.max_recent_turns :]
            context.updated_at = time.time()
            return context.snapshot()

    def public_summary(self, session_id: str) -> dict[str, Any]:
        """Return a debug-safe summary that omits sensitive values."""
        snap = self.get_snapshot(session_id)
        safe_turns = []
        for t in snap.get("recent_turns", []):
            # Truncate long messages; drop raw assistant_reply if bulky.
            safe_turns.append({
                "intent": t.get("intent"),
                "tool": t.get("tool"),
                "success": t.get("success"),
                "topic": t.get("topic"),
                "created_path": t.get("created_path"),
                "has_reply": t.get("assistant_reply") is not None,
            })
        return {
            "session_id": snap["session_id"],
            "last_topic": snap["last_topic"],
            "last_intent": snap["last_intent"],
            "last_tool": snap["last_tool"],
            "last_failure_type": snap["last_failure_type"],
            "config_progress_state": snap["config_progress_state"],
            "missing_config_fields": snap["missing_config_fields"],
            "pending_task": snap["pending_task"],
            "missing_parameters": snap["missing_parameters"],
            "last_task": snap["last_task"],
            "last_result": snap["last_result"],
            "last_created_path": snap["last_created_path"],
            "recent_turns_count": len(snap["recent_turns"]),
            "recent_turns": safe_turns,
        }
