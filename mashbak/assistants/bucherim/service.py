"""Bucherim assistant backend service.

This module owns Bucherim membership gating, per-user persistence, audit logs,
and conversational handling for SMS users.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__:
    from agent.assistant_core import BackendOpenAIClient
    from agent.session_context import SessionContextManager
else:
    from agent.assistant_core import BackendOpenAIClient
    from agent.session_context import SessionContextManager


ACTIVE_STATUS = "active"
PENDING_STATUS = "pending_request"
ALLOWLISTED_STATUS = "allowlisted"
REJECTED_STATUS = "rejected"
BLOCKED_STATUS = "blocked"
UNKNOWN_STATUS = "unknown"


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
    """Backend intelligence and membership flow for Bucherim SMS assistant."""

    def __init__(
        self,
        *,
        base_dir: Path,
        openai_api_key: str,
        openai_model: str,
        session_turns: int = 4,
    ):
        self.base_dir = base_dir.resolve()
        self.config_path = self.base_dir / "assistants" / "bucherim" / "config.json"
        self.data_root = self.base_dir / "data"
        self.users_root = self.data_root / "users" / "bucherim"
        self.media_root = self.data_root / "media" / "bucherim"
        self.audit_root = self.data_root / "logs" / "bucherim"
        self.audit_log_file = self.audit_root / "events.jsonl"
        self.pending_requests_file = self.users_root / "pending_requests.jsonl"

        self.users_root.mkdir(parents=True, exist_ok=True)
        self.media_root.mkdir(parents=True, exist_ok=True)
        self.audit_root.mkdir(parents=True, exist_ok=True)
        self.pending_requests_file.parent.mkdir(parents=True, exist_ok=True)

        self.model_client = BackendOpenAIClient(openai_api_key or "", openai_model or "gpt-4.1-mini")
        self.session_context = SessionContextManager(max_recent_turns=max(1, int(session_turns or 4)))

    def update_model_config(self, *, api_key: str, model: str, session_turns: int) -> None:
        self.model_client.api_key = api_key or ""
        self.model_client.model = model or "gpt-4.1-mini"
        self.session_context.max_recent_turns = max(1, int(session_turns or self.session_context.max_recent_turns))

    @staticmethod
    def normalize_phone_e164(value: str) -> str:
        """Normalize number to E.164-like form for matching and identity."""
        text = str(value or "").strip()
        digits = re.sub(r"\D", "", text)

        if not digits:
            return ""

        # North America default normalization for 10-digit SMS numbers.
        if len(digits) == 10:
            return f"+1{digits}"
        if len(digits) == 11 and digits.startswith("1"):
            return f"+{digits}"

        return f"+{digits}"

    @staticmethod
    def phone_to_user_key(e164_phone: str) -> str:
        """Convert normalized phone to filesystem-safe deterministic key."""
        digits = re.sub(r"\D", "", str(e164_phone or ""))
        if not digits:
            return "unknown"
        return f"p{digits}"

    @staticmethod
    def _iso_now() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    @staticmethod
    def _command(body: str) -> str:
        return str(body or "").strip().lower()

    @staticmethod
    def _load_json(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")

    def _load_config(self) -> dict[str, Any]:
        default_config = {
            "assistant_number": "+18772683048",
            "allowlist": [],
            "blocked_numbers": [],
            "responses": {
                "welcome": "Welcome to Bucherim. You are now connected and can start asking questions.",
                "not_approved": "You are not currently approved for Bucherim. Text join@bucherim to request access.",
                "join_ack": "Your request to join Bucherim has been received and will be reviewed.",
                "already_active": "You are already connected to Bucherim. Ask me anything.",
                "not_member": "You are not currently a Bucherim member. Text @bucherim if approved, or join@bucherim to request access.",
                "blocked": "Your access to Bucherim is currently blocked. Text join@bucherim to request a review.",
                "media_unavailable": "I received your media, but image analysis is not enabled yet. Please describe what you need in text.",
                "image_generation_unavailable": "I can discuss images, but outbound image generation is not enabled yet.",
            },
        }

        raw_config = self._load_json(self.config_path, default_config)
        if not isinstance(raw_config, dict):
            raw_config = default_config

        responses = raw_config.get("responses") if isinstance(raw_config.get("responses"), dict) else {}

        allowlist_raw = raw_config.get("allowlist") if isinstance(raw_config.get("allowlist"), list) else []
        blocked_raw = raw_config.get("blocked_numbers") if isinstance(raw_config.get("blocked_numbers"), list) else []

        allowlist = {
            self.normalize_phone_e164(str(number))
            for number in allowlist_raw
            if self.normalize_phone_e164(str(number))
        }
        blocked_numbers = {
            self.normalize_phone_e164(str(number))
            for number in blocked_raw
            if self.normalize_phone_e164(str(number))
        }

        return {
            "assistant_number": self.normalize_phone_e164(str(raw_config.get("assistant_number") or "+18772683048")) or "+18772683048",
            "allowlist": allowlist,
            "blocked_numbers": blocked_numbers,
            "responses": {
                **default_config["responses"],
                **responses,
            },
        }

    def _user_paths(self, normalized_sender: str) -> dict[str, Path]:
        user_key = self.phone_to_user_key(normalized_sender)
        user_dir = self.users_root / user_key
        media_dir = self.media_root / user_key
        media_index = media_dir / "index.jsonl"

        return {
            "user_key": Path(user_key),
            "user_dir": user_dir,
            "profile": user_dir / "profile.json",
            "membership": user_dir / "membership.json",
            "conversation": user_dir / "conversation.jsonl",
            "requests": user_dir / "requests.jsonl",
            "user_media_dir": user_dir / "media",
            "media_dir": media_dir,
            "media_index": media_index,
        }

    def _ensure_user_files(self, normalized_sender: str, config: dict[str, Any]) -> dict[str, Any]:
        paths = self._user_paths(normalized_sender)
        user_dir = paths["user_dir"]
        user_media_dir = paths["user_media_dir"]
        media_dir = paths["media_dir"]

        user_dir.mkdir(parents=True, exist_ok=True)
        user_media_dir.mkdir(parents=True, exist_ok=True)
        media_dir.mkdir(parents=True, exist_ok=True)

        profile_path = paths["profile"]
        if not profile_path.exists():
            profile = {
                "phone_number": normalized_sender,
                "user_key": self.phone_to_user_key(normalized_sender),
                "first_seen_at": self._iso_now(),
                "assistant_number": config["assistant_number"],
            }
            self._write_json(profile_path, profile)

        membership_path = paths["membership"]
        membership = self._load_json(membership_path, {})
        if not isinstance(membership, dict) or not membership:
            initial_status = UNKNOWN_STATUS
            if normalized_sender in config["blocked_numbers"]:
                initial_status = BLOCKED_STATUS
            elif normalized_sender in config["allowlist"]:
                initial_status = ALLOWLISTED_STATUS

            membership = {
                "phone_number": normalized_sender,
                "status": initial_status,
                "source": "allowlist" if initial_status == ALLOWLISTED_STATUS else ("blocked_list" if initial_status == BLOCKED_STATUS else "none"),
                "joined_at": None,
                "updated_at": self._iso_now(),
                "history": [],
            }
            self._write_json(membership_path, membership)

        return {
            "paths": paths,
            "membership": membership,
        }

    def _save_membership(self, membership_path: Path, membership: dict[str, Any]) -> None:
        membership["updated_at"] = self._iso_now()
        self._write_json(membership_path, membership)

    def _record_membership_event(
        self,
        *,
        paths: dict[str, Path],
        membership: dict[str, Any],
        event: str,
        request: BucherimSmsRequest,
        details: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "timestamp": self._iso_now(),
            "event": event,
            "status": membership.get("status"),
            "phone_number": membership.get("phone_number"),
            "request_id": request.request_id,
            "message_sid": request.message_sid,
            "details": details or {},
        }
        history = membership.get("history")
        if not isinstance(history, list):
            history = []
        history.append(payload)
        membership["history"] = history[-50:]

        self._append_jsonl(paths["conversation"], {
            "timestamp": payload["timestamp"],
            "direction": "event",
            "event_type": "membership",
            "event": event,
            "status": membership.get("status"),
            "request_id": request.request_id,
            "message_sid": request.message_sid,
            "details": details or {},
        })

        self._append_jsonl(self.audit_log_file, {
            "timestamp": payload["timestamp"],
            "event_type": "membership",
            "event": event,
            "phone_number": membership.get("phone_number"),
            "status": membership.get("status"),
            "request_id": request.request_id,
            "message_sid": request.message_sid,
            "details": details or {},
        })

    def _record_inbound(
        self,
        *,
        paths: dict[str, Path],
        membership: dict[str, Any],
        request: BucherimSmsRequest,
        media: list[dict[str, Any]],
    ) -> None:
        payload = {
            "timestamp": self._iso_now(),
            "direction": "inbound",
            "phone_number": membership.get("phone_number"),
            "status": membership.get("status"),
            "request_id": request.request_id,
            "provider": request.provider,
            "message_sid": request.message_sid,
            "account_sid": request.account_sid,
            "text_body": request.body,
            "contains_media": bool(media),
            "media_count": len(media),
            "media": media,
            "media_processing": "logged_only" if media else "none",
            "response_mode": None,
            "assistant_response": None,
        }
        self._append_jsonl(paths["conversation"], payload)

        self._append_jsonl(self.audit_log_file, {
            "timestamp": payload["timestamp"],
            "event_type": "inbound_message",
            "phone_number": membership.get("phone_number"),
            "status": membership.get("status"),
            "request_id": request.request_id,
            "message_sid": request.message_sid,
            "contains_media": bool(media),
            "media_count": len(media),
            "media_processing": payload["media_processing"],
        })

        if media:
            for index, item in enumerate(media):
                self._append_jsonl(paths["media_index"], {
                    "timestamp": self._iso_now(),
                    "direction": "inbound",
                    "request_id": request.request_id,
                    "message_sid": request.message_sid,
                    "media_index": index,
                    "media_url": item.get("url"),
                    "content_type": item.get("content_type"),
                    "download_status": "referenced_only",
                    "stored_filename": None,
                    "processed_by_assistant": False,
                })

    def _record_outbound(
        self,
        *,
        paths: dict[str, Path],
        membership: dict[str, Any],
        request: BucherimSmsRequest,
        reply: str,
        full_reply: str,
        response_mode: str,
        response_media: list[dict[str, Any]] | None = None,
    ) -> None:
        payload = {
            "timestamp": self._iso_now(),
            "direction": "outbound",
            "phone_number": membership.get("phone_number"),
            "status": membership.get("status"),
            "request_id": request.request_id,
            "provider": request.provider,
            "message_sid": request.message_sid,
            "text_body": reply,
            "assistant_response": full_reply,
            "response_mode": response_mode,
            "contains_media": bool(response_media),
            "media_count": len(response_media or []),
            "media": response_media or [],
        }
        self._append_jsonl(paths["conversation"], payload)

        self._append_jsonl(self.audit_log_file, {
            "timestamp": payload["timestamp"],
            "event_type": "outbound_message",
            "phone_number": membership.get("phone_number"),
            "status": membership.get("status"),
            "request_id": request.request_id,
            "message_sid": request.message_sid,
            "response_mode": response_mode,
            "contains_media": bool(response_media),
            "media_count": len(response_media or []),
        })

    def _append_join_request(
        self,
        *,
        paths: dict[str, Path],
        normalized_sender: str,
        request: BucherimSmsRequest,
    ) -> None:
        payload = {
            "timestamp": self._iso_now(),
            "phone_number": normalized_sender,
            "request_id": request.request_id,
            "message_sid": request.message_sid,
            "recipient": request.recipient,
            "status": PENDING_STATUS,
            "review_state": "pending",
        }
        self._append_jsonl(paths["requests"], payload)
        self._append_jsonl(self.pending_requests_file, payload)

    def _shorten_for_sms(self, text: str, max_chars: int = 480) -> str:
        compact = " ".join(str(text or "").split())
        if len(compact) <= max_chars:
            return compact
        return f"{compact[: max_chars - 3]}..."

    def _is_image_request(self, body: str) -> bool:
        text = self._command(body)
        return any(token in text for token in ("image", "picture", "photo", "draw", "generate"))

    def _session_id_for_sender(self, normalized_sender: str) -> str:
        return f"bucherim:{re.sub(r'\D', '', normalized_sender)}"

    def _update_session_context(
        self,
        *,
        normalized_sender: str,
        user_message: str,
        assistant_reply: str,
        membership_status: str,
        intent: str,
        response_mode: str,
        has_media: bool,
        topic: str,
    ) -> None:
        session_id = self._session_id_for_sender(normalized_sender)
        parsed = {
            "mode": "bucherim",
            "intent": intent,
            "topic": topic,
            "entities": {
                "has_media": has_media,
                "membership_status": membership_status,
                "last_response_type": response_mode,
                "last_media_presence": has_media,
            },
            "args": {},
            "confidence": 0.9,
        }
        result = {
            "success": True,
            "tool_name": None,
            "output": assistant_reply,
            "error": None,
            "data": {
                "response_mode": response_mode,
                "membership_status": membership_status,
                "last_media_presence": has_media,
                "last_response_type": response_mode,
            },
        }
        self.session_context.update(
            session_id=session_id,
            user_message=user_message,
            parsed=parsed,
            result=result,
        )
        self.session_context.record_assistant_reply(session_id=session_id, assistant_reply=assistant_reply)

    def _format_recent_turns(self, session_snapshot: dict[str, Any]) -> str:
        turns = session_snapshot.get("recent_turns") or []
        lines: list[str] = []
        for turn in turns[-5:]:
            user_msg = str(turn.get("message") or "").strip()
            assistant_msg = str(turn.get("assistant_reply") or "").strip()
            if user_msg:
                lines.append(f"User: {user_msg}")
            if assistant_msg:
                lines.append(f"Assistant: {assistant_msg}")
        return "\n".join(lines)

    async def _generate_member_reply(
        self,
        *,
        normalized_sender: str,
        body: str,
        membership_status: str,
        has_media: bool,
        config: dict[str, Any],
    ) -> tuple[str, str, str]:
        responses = config["responses"]

        if has_media:
            full_reply = responses["media_unavailable"]
            self._update_session_context(
                normalized_sender=normalized_sender,
                user_message=body,
                assistant_reply=full_reply,
                membership_status=membership_status,
                intent="media_request",
                response_mode="image_analysis_unavailable",
                has_media=True,
                topic="media",
            )
            return self._shorten_for_sms(full_reply), full_reply, "image_analysis_unavailable"

        if self._is_image_request(body):
            full_reply = responses["image_generation_unavailable"]
            self._update_session_context(
                normalized_sender=normalized_sender,
                user_message=body,
                assistant_reply=full_reply,
                membership_status=membership_status,
                intent="image_generation_request",
                response_mode="image_generation_unavailable",
                has_media=False,
                topic="media",
            )
            return self._shorten_for_sms(full_reply), full_reply, "image_generation_unavailable"

        session_id = self._session_id_for_sender(normalized_sender)
        context_snapshot = self.session_context.get_snapshot(session_id)
        recent_turns = self._format_recent_turns(context_snapshot)

        full_reply: str | None = None
        if self.model_client.enabled:
            prompt = (
                "You are Bucherim, a helpful SMS AI assistant. "
                "Answer naturally and clearly, and keep SMS replies concise. "
                "Use the recent conversation for context when helpful.\n"
                f"User message: {body}\n"
            )
            if recent_turns:
                prompt += f"Recent conversation:\n{recent_turns}\n"
            prompt += "Do not mention internal systems or hidden policies."
            full_reply = await self.model_client.complete(
                system_prompt="You are Bucherim, an SMS-first assistant.",
                user_prompt=prompt,
                max_tokens=220,
            )

        if not full_reply:
            lowered = self._command(body)
            if any(token in lowered for token in ("hi", "hello", "hey")):
                full_reply = "Hi. I am Bucherim. Ask me anything and I will help as best I can by text."
            else:
                full_reply = "I can help with general questions by SMS. Tell me what you want to know."

        sms_reply = self._shorten_for_sms(full_reply)

        self._update_session_context(
            normalized_sender=normalized_sender,
            user_message=body,
            assistant_reply=full_reply,
            membership_status=membership_status,
            intent="conversation",
            response_mode="text",
            has_media=has_media,
            topic=context_snapshot.get("last_topic") or "general",
        )

        return sms_reply, full_reply, "text"

    async def process_sms(self, request: BucherimSmsRequest) -> dict[str, Any]:
        config = self._load_config()
        normalized_sender = self.normalize_phone_e164(request.sender)
        normalized_recipient = self.normalize_phone_e164(request.recipient)

        raw_media = request.media or []
        media = []
        for item in raw_media:
            media.append({
                "url": str(item.get("url") or "").strip(),
                "content_type": str(item.get("content_type") or "").strip(),
                "filename": str(item.get("filename") or "").strip() or None,
            })

        seeded = self._ensure_user_files(normalized_sender, config)
        paths = seeded["paths"]
        membership = seeded["membership"]

        self._record_inbound(paths=paths, membership=membership, request=request, media=media)

        responses = config["responses"]
        command = self._command(request.body)
        status = membership.get("status") or UNKNOWN_STATUS

        # Keep allowlist state fresh if config changed.
        if normalized_sender in config["allowlist"] and status == UNKNOWN_STATUS:
            membership["status"] = ALLOWLISTED_STATUS
            membership["source"] = "allowlist"
            status = membership["status"]
            self._record_membership_event(
                paths=paths,
                membership=membership,
                event="allowlist_detected",
                request=request,
                details={"source": "allowlist"},
            )

        if normalized_sender in config["blocked_numbers"]:
            membership["status"] = BLOCKED_STATUS
            membership["source"] = "blocked_list"
            status = BLOCKED_STATUS

        if command == "@bucherim":
            if membership.get("status") == BLOCKED_STATUS:
                full_reply = responses["blocked"]
                reply = self._shorten_for_sms(full_reply)
                response_mode = "membership_blocked"
                self._record_membership_event(
                    paths=paths,
                    membership=membership,
                    event="admission_blocked",
                    request=request,
                    details={"reason": "blocked_number"},
                )
            elif normalized_sender in config["allowlist"]:
                if membership.get("status") != ACTIVE_STATUS:
                    membership["status"] = ACTIVE_STATUS
                    membership["source"] = "allowlist"
                    membership["joined_at"] = membership.get("joined_at") or self._iso_now()
                    self._record_membership_event(
                        paths=paths,
                        membership=membership,
                        event="admitted",
                        request=request,
                        details={"source": "allowlist"},
                    )
                full_reply = responses["welcome"]
                reply = self._shorten_for_sms(full_reply)
                response_mode = "membership_welcome"
            else:
                membership["status"] = REJECTED_STATUS
                self._record_membership_event(
                    paths=paths,
                    membership=membership,
                    event="admission_rejected",
                    request=request,
                    details={"reason": "not_allowlisted", "instruction": "join@bucherim"},
                )
                full_reply = responses["not_approved"]
                reply = self._shorten_for_sms(full_reply)
                response_mode = "membership_rejected"

            self._update_session_context(
                normalized_sender=normalized_sender,
                user_message=request.body,
                assistant_reply=full_reply,
                membership_status=str(membership.get("status") or UNKNOWN_STATUS),
                intent="membership_command",
                response_mode=response_mode,
                has_media=bool(media),
                topic="membership",
            )

            self._save_membership(paths["membership"], membership)
            self._record_outbound(
                paths=paths,
                membership=membership,
                request=request,
                reply=reply,
                full_reply=full_reply,
                response_mode=response_mode,
            )
            return {
                "handled": True,
                "reply": reply,
                "full_reply": full_reply,
                "status": membership.get("status"),
                "response_mode": response_mode,
                "normalized_sender": normalized_sender,
                "normalized_recipient": normalized_recipient,
                "media_count": len(media),
                "outbound_media": [],
            }

        if command == "join@bucherim":
            if membership.get("status") == ACTIVE_STATUS:
                full_reply = responses["already_active"]
                reply = self._shorten_for_sms(full_reply)
                response_mode = "already_active"
            elif membership.get("status") == BLOCKED_STATUS:
                full_reply = responses["blocked"]
                reply = self._shorten_for_sms(full_reply)
                response_mode = "membership_blocked"
            elif normalized_sender in config["allowlist"]:
                # Keep deterministic flow: allowlisted users should send @bucherim to activate.
                membership["status"] = ALLOWLISTED_STATUS
                full_reply = "You are pre-approved. Text @bucherim to activate your Bucherim membership."
                reply = self._shorten_for_sms(full_reply)
                response_mode = "allowlisted_not_active"
            else:
                membership["status"] = PENDING_STATUS
                membership["source"] = "request"
                self._append_join_request(paths=paths, normalized_sender=normalized_sender, request=request)
                self._record_membership_event(
                    paths=paths,
                    membership=membership,
                    event="join_requested",
                    request=request,
                    details={"review_state": "pending"},
                )
                full_reply = responses["join_ack"]
                reply = self._shorten_for_sms(full_reply)
                response_mode = "join_request_ack"

            self._update_session_context(
                normalized_sender=normalized_sender,
                user_message=request.body,
                assistant_reply=full_reply,
                membership_status=str(membership.get("status") or UNKNOWN_STATUS),
                intent="join_request",
                response_mode=response_mode,
                has_media=bool(media),
                topic="membership",
            )

            self._save_membership(paths["membership"], membership)
            self._record_outbound(
                paths=paths,
                membership=membership,
                request=request,
                reply=reply,
                full_reply=full_reply,
                response_mode=response_mode,
            )
            return {
                "handled": True,
                "reply": reply,
                "full_reply": full_reply,
                "status": membership.get("status"),
                "response_mode": response_mode,
                "normalized_sender": normalized_sender,
                "normalized_recipient": normalized_recipient,
                "media_count": len(media),
                "outbound_media": [],
            }

        if membership.get("status") != ACTIVE_STATUS:
            full_reply = responses["blocked"] if membership.get("status") == BLOCKED_STATUS else responses["not_member"]
            reply = self._shorten_for_sms(full_reply)
            response_mode = "not_authorized"

            self._record_membership_event(
                paths=paths,
                membership=membership,
                event="non_member_message_blocked",
                request=request,
                details={"status": membership.get("status")},
            )
            self._update_session_context(
                normalized_sender=normalized_sender,
                user_message=request.body,
                assistant_reply=full_reply,
                membership_status=str(membership.get("status") or UNKNOWN_STATUS),
                intent="non_member_message",
                response_mode=response_mode,
                has_media=bool(media),
                topic="membership",
            )
            self._save_membership(paths["membership"], membership)
            self._record_outbound(
                paths=paths,
                membership=membership,
                request=request,
                reply=reply,
                full_reply=full_reply,
                response_mode=response_mode,
            )
            return {
                "handled": True,
                "reply": reply,
                "full_reply": full_reply,
                "status": membership.get("status"),
                "response_mode": response_mode,
                "normalized_sender": normalized_sender,
                "normalized_recipient": normalized_recipient,
                "media_count": len(media),
                "outbound_media": [],
            }

        reply, full_reply, response_mode = await self._generate_member_reply(
            normalized_sender=normalized_sender,
            body=request.body,
            membership_status=str(membership.get("status") or ACTIVE_STATUS),
            has_media=bool(media),
            config=config,
        )

        self._save_membership(paths["membership"], membership)
        self._record_outbound(
            paths=paths,
            membership=membership,
            request=request,
            reply=reply,
            full_reply=full_reply,
            response_mode=response_mode,
        )

        return {
            "handled": True,
            "reply": reply,
            "full_reply": full_reply,
            "status": membership.get("status"),
            "response_mode": response_mode,
            "normalized_sender": normalized_sender,
            "normalized_recipient": normalized_recipient,
            "media_count": len(media),
            "outbound_media": [],
        }
