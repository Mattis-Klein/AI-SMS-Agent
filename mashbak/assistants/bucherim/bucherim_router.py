from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from .membership import STATE_APPROVED, STATE_BLOCKED, STATE_PENDING, MembershipService


@dataclass
class RouteResult:
    reply: str
    state: str
    response_mode: str


class BucherimRouter:
    def __init__(self, membership: MembershipService, responses: dict[str, str]):
        self.membership = membership
        self.responses = responses

    async def route(
        self,
        *,
        from_number: str,
        to_number: str,
        body: str,
        request_id: str,
        message_sid: str | None,
        media: list[dict],
        approved_responder: Callable[[str, str, list[dict]], Awaitable[str]],
    ) -> RouteResult:
        command = str(body or "").strip().lower()
        decision = self.membership.get_state(from_number)

        if decision.state == STATE_BLOCKED:
            return RouteResult(reply=self.responses["blocked"], state=STATE_BLOCKED, response_mode="blocked")

        if decision.state == STATE_APPROVED:
            reply = await approved_responder(decision.normalized_phone, body, media)
            return RouteResult(reply=reply, state=STATE_APPROVED, response_mode="approved_ai")

        if decision.state == STATE_PENDING:
            if command == "join@bucherim":
                if not decision.has_pending_request:
                    pending = self.membership.request_join(
                        phone_number=from_number,
                        recipient=to_number,
                        body=body,
                        request_id=request_id,
                        message_sid=message_sid,
                        media=media,
                    )
                    return RouteResult(reply=self.responses["join_ack"], state=pending.state, response_mode="join_request_created")
                return RouteResult(reply=self.responses["join_ack"], state=STATE_PENDING, response_mode="join_pending")
            if command == "@bucherim":
                return RouteResult(reply=self.responses["not_approved"], state=STATE_PENDING, response_mode="not_approved")
            return RouteResult(reply=self.responses["not_member"], state=STATE_PENDING, response_mode="pending_access_restricted")

        return RouteResult(reply=self.responses["not_member"], state=STATE_PENDING, response_mode="access_restricted")
