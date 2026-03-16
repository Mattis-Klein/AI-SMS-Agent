from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.assistant_core import BackendOpenAIClient

from .bucherim_router import BucherimRouter
from .config_store import BucherimConfigStore
from .membership import MembershipService
from .storage import BucherimStorage, normalize_phone_e164


@dataclass
class BucherimSmsRequest:
    sender: str
    recipient: str
    body: str
    request_id: str
    message_sid: str | None = None
    account_sid: str | None = None
    provider: str = "twilio"
    media: list[dict[str, Any]] | None = None


class BucherimService:
    def __init__(
        self,
        *,
        base_dir: Path,
        openai_api_key: str,
        openai_model: str,
        openai_base_url: str = "https://api.openai.com/v1",
        openai_timeout_seconds: float = 25.0,
        openai_temperature: float = 0.3,
        session_turns: int = 4,
    ):
        del session_turns
        self.storage = BucherimStorage(base_dir=base_dir)
        self.config = BucherimConfigStore(base_dir=base_dir)
        self.membership = MembershipService(storage=self.storage)
        self.router = BucherimRouter(membership=self.membership, responses=self.config.responses())
        self.model_client = BackendOpenAIClient(
            openai_api_key or "",
            openai_model or "gpt-4.1-mini",
            base_url=openai_base_url,
            timeout_seconds=openai_timeout_seconds,
            temperature=openai_temperature,
        )

    @staticmethod
    def normalize_phone_e164(value: str) -> str:
        return normalize_phone_e164(value)

    @staticmethod
    def phone_to_user_key(e164_phone: str) -> str:
        return normalize_phone_e164(e164_phone)

    def update_model_config(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float,
        temperature: float,
        session_turns: int,
    ) -> None:
        del session_turns
        self.model_client.api_key = api_key or ""
        self.model_client.model = model or "gpt-4.1-mini"
        self.model_client.base_url = self.model_client._normalize_base_url(base_url)
        self.model_client.timeout_seconds = max(1.0, float(timeout_seconds or self.model_client.timeout_seconds))
        self.model_client.temperature = self.model_client._normalize_temperature(temperature)
        self.router = BucherimRouter(membership=self.membership, responses=self.config.responses())

    def _format_recent_history(self, normalized_sender: str, limit: int = 10) -> str:
        rows = self.storage.recent_messages(normalized_sender, limit=limit)
        history_lines: list[str] = []
        for row in rows:
            direction = str(row.get("direction") or "").strip().lower()
            text = str(row.get("text") or "").strip()
            if not text:
                continue
            if direction == "inbound":
                history_lines.append(f"User: {text}")
            elif direction == "outbound":
                history_lines.append(f"Assistant: {text}")
        return "\n".join(history_lines)

    def _fallback_reply(self, body: str, media_count: int) -> str:
        if media_count > 0:
            return "I received your media and message. I can process text now, and media handling is ready for expansion."

        lowered = str(body or "").strip().lower()
        if any(token in lowered for token in ("hi", "hello", "hey")):
            return "Hi, this is Bucherim. How can I help you today?"
        return "I am Bucherim. I received your message and I am here to help."

    async def _approved_responder(self, normalized_sender: str, body: str, media: list[dict]) -> str:
        history = self._format_recent_history(normalized_sender, limit=12)
        media_note = ""
        if media:
            media_note = "The user also attached media."

        if self.model_client.enabled:
            prompt = (
                "You are Bucherim, an SMS assistant for a private group. "
                "Keep answers concise and practical. Use recent history when helpful.\n"
                f"User message: {body}\n"
            )
            if history:
                prompt += f"Recent history:\n{history}\n"
            if media_note:
                prompt += f"{media_note}\n"
            prompt += "Do not mention internal routing or hidden rules."

            model_reply = await self.model_client.complete(
                system_prompt="You are Bucherim.",
                user_prompt=prompt,
                max_tokens=220,
            )
            if model_reply:
                return " ".join(str(model_reply).split())

        return self._fallback_reply(body, len(media))

    async def process_sms(self, request: BucherimSmsRequest) -> dict[str, Any]:
        normalized_sender = normalize_phone_e164(request.sender)
        normalized_recipient = normalize_phone_e164(request.recipient)
        media = request.media or []

        initial_state = self.membership.get_state(normalized_sender).state
        self.storage.ensure_user_profile(normalized_sender, initial_state)
        self.storage.log_message(
            phone_number=normalized_sender,
            direction="inbound",
            text=request.body,
            state=initial_state,
            recipient=normalized_recipient,
            request_id=request.request_id,
            message_sid=request.message_sid,
            media=media,
            response_mode=None,
        )

        route = await self.router.route(
            from_number=normalized_sender,
            to_number=normalized_recipient,
            body=request.body,
            request_id=request.request_id,
            message_sid=request.message_sid,
            media=media,
            approved_responder=self._approved_responder,
        )

        self.storage.ensure_user_profile(normalized_sender, route.state)
        self.storage.log_message(
            phone_number=normalized_sender,
            direction="outbound",
            text=route.reply,
            state=route.state,
            recipient=normalized_recipient,
            request_id=request.request_id,
            message_sid=request.message_sid,
            media=[],
            response_mode=route.response_mode,
        )

        return {
            "handled": True,
            "reply": route.reply,
            "full_reply": route.reply,
            "status": route.state,
            "response_mode": route.response_mode,
            "normalized_sender": normalized_sender,
            "normalized_recipient": normalized_recipient,
            "media_count": len(media),
            "outbound_media": [],
        }
