from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from .membership import STATE_APPROVED, STATE_BLOCKED, STATE_PENDING, STATE_UNKNOWN, MembershipService


BLOCKED_RESPONSE = "Your access to Bucherim is currently blocked."
NOT_APPROVED_RESPONSE = "You are not currently approved for Bucherim. Text join@bucherim to request access."
JOIN_ACK_RESPONSE = "Your request to join Bucherim has been received and will be reviewed."
UNKNOWN_ACCESS_RESPONSE = "Access restricted. Text join@bucherim to request access."


@dataclass
class RouteResult:
    reply: str
    state: str
    response_mode: str


class BucherimRouter:
    def __init__(self, membership: MembershipService):
        self.membership = membership

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
            return RouteResult(reply=BLOCKED_RESPONSE, state=STATE_BLOCKED, response_mode="blocked")

        if decision.state == STATE_APPROVED:
            reply = await approved_responder(decision.normalized_phone, body, media)
            return RouteResult(reply=reply, state=STATE_APPROVED, response_mode="approved_ai")

        if decision.state == STATE_PENDING:
            if command == "join@bucherim":
                return RouteResult(reply=JOIN_ACK_RESPONSE, state=STATE_PENDING, response_mode="join_pending")
            return RouteResult(reply=UNKNOWN_ACCESS_RESPONSE, state=STATE_PENDING, response_mode="pending_access_restricted")

        if command == "@bucherim":
            return RouteResult(reply=NOT_APPROVED_RESPONSE, state=STATE_UNKNOWN, response_mode="not_approved")

        if command == "join@bucherim":
            pending = self.membership.request_join(
                phone_number=from_number,
                recipient=to_number,
                body=body,
                request_id=request_id,
                message_sid=message_sid,
                media=media,
            )
            return RouteResult(reply=JOIN_ACK_RESPONSE, state=pending.state, response_mode="join_request_created")

        return RouteResult(reply=UNKNOWN_ACCESS_RESPONSE, state=STATE_UNKNOWN, response_mode="access_restricted")
