from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


class ApprovalStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir.resolve()
        self.path = self.base_dir / "data" / "state" / "approvals.json"

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"items": []}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            payload = {"items": []}
        if not isinstance(payload, dict):
            payload = {"items": []}
        payload.setdefault("items", [])
        return payload

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def create(self, *, tool_name: str, args: dict[str, Any], source: str, sender: str, reason: str) -> dict[str, Any]:
        payload = self._read()
        now = self._now()
        item = {
            "approval_id": uuid.uuid4().hex[:12],
            "status": "pending",
            "tool_name": tool_name,
            "args": args,
            "source": source,
            "sender": sender,
            "reason": reason,
            "created_at": now,
            "updated_at": now,
        }
        payload["items"].insert(0, item)
        payload["items"] = payload["items"][:500]
        self._write(payload)
        return item

    def set_status(self, approval_id: str, status: str, reviewer: str = "operator") -> dict[str, Any] | None:
        payload = self._read()
        for row in payload.get("items") or []:
            if str(row.get("approval_id")) != str(approval_id):
                continue
            row["status"] = status
            row["reviewer"] = reviewer
            row["updated_at"] = self._now()
            self._write(payload)
            return row
        return None

    def get(self, approval_id: str) -> dict[str, Any] | None:
        for row in self._read().get("items") or []:
            if str(row.get("approval_id")) == str(approval_id):
                return row
        return None

    def list(self, limit: int = 100, status: str = "") -> dict[str, Any]:
        rows = self._read().get("items") or []
        state = str(status or "").strip().lower()
        if state:
            rows = [row for row in rows if str(row.get("status") or "").lower() == state]
        cap = max(1, min(int(limit or 100), 300))
        items = rows[:cap]
        return {"approvals": items, "count": len(items)}
