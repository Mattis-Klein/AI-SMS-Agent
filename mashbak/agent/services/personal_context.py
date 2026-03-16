from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class PersonalContextStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir.resolve()
        self.path = self.base_dir / "data" / "config" / "personal_context.json"

    def _default(self) -> dict[str, Any]:
        return {
            "profile": {
                "name": "",
                "preferred_tone": "",
                "response_style": "",
                "notes": "",
            },
            "people": [],
            "routines": [],
            "projects": [],
            "preferences": {
                "response_length": "balanced",
                "notification_style": "normal",
                "automation_aggressiveness": "safe",
            },
        }

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._default()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            payload = self._default()
        if not isinstance(payload, dict):
            payload = self._default()
        merged = self._default()
        for key in ("profile", "people", "routines", "projects", "preferences"):
            if key in payload:
                merged[key] = payload[key]
        return merged

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = self._default()
        for key in ("profile", "people", "routines", "projects", "preferences"):
            if key in payload:
                current[key] = payload[key]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(current, indent=2), encoding="utf-8")
        return current
