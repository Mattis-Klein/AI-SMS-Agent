from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .storage import BucherimStorage, normalize_phone_e164


STATE_APPROVED = "approved"
STATE_PENDING = "pending"
STATE_BLOCKED = "blocked"


@dataclass
class MembershipDecision:
    normalized_phone: str
    state: str
    has_pending_request: bool = False


class MembershipService:
    def __init__(self, storage: BucherimStorage):
        self.storage = storage

    def get_state(self, phone_number: str) -> MembershipDecision:
        normalized_phone = normalize_phone_e164(phone_number)
        if not normalized_phone:
            return MembershipDecision(normalized_phone="", state=STATE_PENDING, has_pending_request=False)

        if normalized_phone in self.storage.blocked_numbers():
            return MembershipDecision(normalized_phone=normalized_phone, state=STATE_BLOCKED, has_pending_request=False)

        approved = self.storage.approved_numbers()
        if normalized_phone in approved:
            return MembershipDecision(normalized_phone=normalized_phone, state=STATE_APPROVED, has_pending_request=False)

        return MembershipDecision(
            normalized_phone=normalized_phone,
            state=STATE_PENDING,
            has_pending_request=self.storage.is_pending(normalized_phone),
        )

    def request_join(
        self,
        *,
        phone_number: str,
        recipient: str,
        body: str,
        request_id: str,
        message_sid: str | None,
        media: list[dict[str, Any]] | None,
    ) -> MembershipDecision:
        decision = self.get_state(phone_number)
        if decision.state in {STATE_APPROVED, STATE_BLOCKED}:
            return decision

        self.storage.add_pending_request(
            phone_number=decision.normalized_phone,
            recipient=recipient,
            body=body,
            request_id=request_id,
            message_sid=message_sid,
            media=media,
        )
        return MembershipDecision(normalized_phone=decision.normalized_phone, state=STATE_PENDING, has_pending_request=True)
