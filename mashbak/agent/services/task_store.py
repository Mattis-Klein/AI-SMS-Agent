from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class AgentTask:
    task_id: str
    title: str
    status: str
    source: str
    sender: str
    created_at: str
    updated_at: str
    steps: list[dict[str, Any]]
    result: dict[str, Any]


class TaskStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir.resolve()
        self.path = self.base_dir / "data" / "state" / "tasks.json"

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"tasks": []}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            payload = {"tasks": []}
        if not isinstance(payload, dict):
            payload = {"tasks": []}
        payload.setdefault("tasks", [])
        return payload

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def create_task(self, title: str, source: str, sender: str, steps: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        payload = self._read()
        now = self._now()
        task = {
            "task_id": uuid.uuid4().hex[:12],
            "title": str(title or "Task"),
            "status": "running",
            "source": str(source or "unknown"),
            "sender": str(sender or "unknown"),
            "created_at": now,
            "updated_at": now,
            "steps": list(steps or []),
            "result": {},
        }
        payload["tasks"].insert(0, task)
        payload["tasks"] = payload["tasks"][:300]
        self._write(payload)
        return task

    def update_task(self, task_id: str, **updates: Any) -> dict[str, Any] | None:
        payload = self._read()
        rows = payload.get("tasks") or []
        for row in rows:
            if str(row.get("task_id")) != str(task_id):
                continue
            row.update({k: v for k, v in updates.items() if k in {"status", "steps", "result", "title"}})
            row["updated_at"] = self._now()
            self._write(payload)
            return row
        return None

    def list_tasks(self, limit: int = 100, status: str = "") -> dict[str, Any]:
        payload = self._read()
        rows = payload.get("tasks") or []
        state = str(status or "").strip().lower()
        if state:
            rows = [row for row in rows if str(row.get("status") or "").lower() == state]
        cap = max(1, min(int(limit or 100), 300))
        items = rows[:cap]
        return {"tasks": items, "count": len(items)}
