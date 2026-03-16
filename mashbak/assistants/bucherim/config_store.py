from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_RESPONSES = {
    "welcome": "Welcome to Bucherim. You are now connected and can start asking questions.",
    "not_approved": "You are not currently approved for Bucherim. Text join@bucherim to request access.",
    "join_ack": "Your request to join Bucherim has been received and will be reviewed.",
    "already_active": "You are already connected to Bucherim. Ask me anything.",
    "not_member": "Access restricted. Text join@bucherim to request access.",
    "blocked": "Your access to Bucherim is currently blocked. Text join@bucherim to request a review.",
    "media_unavailable": "I received your media, but image analysis is not enabled yet. Please describe what you need in text.",
    "image_generation_unavailable": "I can discuss images, but outbound image generation is not enabled yet.",
}


class BucherimConfigStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir.resolve()
        self.root = self.base_dir / "assistants" / "bucherim"
        self.config_path = self.root / "config.json"
        self._ensure_layout()

    def _ensure_layout(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            self.save({"assistant_number": "+18772683048", "responses": dict(DEFAULT_RESPONSES)})

    def load(self) -> dict[str, Any]:
        self._ensure_layout()
        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}

        if not isinstance(raw, dict):
            raw = {}

        responses = raw.get("responses") if isinstance(raw.get("responses"), dict) else {}
        return {
            "assistant_number": str(raw.get("assistant_number") or "+18772683048"),
            "responses": {**DEFAULT_RESPONSES, **responses},
        }

    def save(self, payload: dict[str, Any]) -> None:
        normalized = {
            "assistant_number": str(payload.get("assistant_number") or "+18772683048"),
            "responses": {**DEFAULT_RESPONSES, **(payload.get("responses") or {})},
        }
        self.config_path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")

    def responses(self) -> dict[str, str]:
        return self.load().get("responses") or dict(DEFAULT_RESPONSES)

    def assistant_number(self) -> str:
        return str(self.load().get("assistant_number") or "+18772683048")
