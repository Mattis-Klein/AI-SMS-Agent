from __future__ import annotations

from pathlib import Path
from typing import Any

from .config_store import BucherimConfigStore
from .membership import MembershipService, STATE_APPROVED, STATE_BLOCKED
from .storage import BucherimStorage, normalize_phone_e164


class BucherimAdminService:
    def __init__(self, base_dir: Path):
        self.storage = BucherimStorage(base_dir=base_dir)
        self.membership = MembershipService(storage=self.storage)
        self.config = BucherimConfigStore(base_dir=base_dir)

    def routing_overview(self) -> dict[str, Any]:
        approved = sorted(self.storage.approved_numbers())
        blocked = sorted(self.storage.blocked_numbers())
        pending = self.storage.pending_requests()
        return {
            "assistant_number": self.config.assistant_number(),
            "approved_numbers": approved,
            "blocked_numbers": blocked,
            "pending_requests": pending,
            "counts": {
                "approved": len(approved),
                "pending": len(pending),
                "blocked": len(blocked),
            },
        }

    def assistants_summary(self) -> dict[str, Any]:
        overview = self.routing_overview()
        return {
            "assistant_number": overview["assistant_number"],
            "counts": overview["counts"],
            "responses": self.config.responses(),
        }

    def update_response_template(self, template_key: str, template_text: str) -> dict[str, Any]:
        key = str(template_key or "").strip()
        if not key:
            raise ValueError("Template key is required")
        payload = self.config.load()
        responses = payload.get("responses") if isinstance(payload.get("responses"), dict) else {}
        responses[key] = str(template_text or "")
        payload["responses"] = responses
        self.config.save(payload)
        return {
            "template_key": key,
            "template_text": responses.get(key, ""),
            "responses": self.config.responses(),
        }

    def approve_member(self, phone_number: str) -> dict[str, Any]:
        normalized = normalize_phone_e164(phone_number)
        if not normalized:
            raise ValueError("Invalid phone number")
        self.storage.add_approved_number(normalized)
        self.storage.ensure_user_profile(normalized, STATE_APPROVED)
        return self.member_detail(normalized)

    def block_member(self, phone_number: str) -> dict[str, Any]:
        normalized = normalize_phone_e164(phone_number)
        if not normalized:
            raise ValueError("Invalid phone number")
        self.storage.add_blocked_number(normalized)
        self.storage.ensure_user_profile(normalized, STATE_BLOCKED)
        return self.member_detail(normalized)

    def member_detail(self, phone_number: str) -> dict[str, Any]:
        normalized = normalize_phone_e164(phone_number)
        if not normalized:
            raise ValueError("Invalid phone number")
        decision = self.membership.get_state(normalized)
        return {
            "phone_number": normalized,
            "state": decision.state,
            "has_pending_request": decision.has_pending_request,
            "profile": self.storage.profile(normalized),
            "history": self.storage.recent_messages(normalized, limit=40),
        }
