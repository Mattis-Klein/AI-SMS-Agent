from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from .config_store import BucherimConfigStore


def iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def normalize_phone_e164(value: str) -> str:
    text = str(value or "").strip()
    digits = re.sub(r"\D", "", text)
    if not digits:
        return ""
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return f"+{digits}"


class BucherimStorage:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir.resolve()
        self.root = self.base_dir / "assistants" / "bucherim"
        self.config_dir = self.root / "config"
        self.logs_users_dir = self.root / "logs" / "users"
        self.config_store = BucherimConfigStore(base_dir=self.base_dir)

        self.approved_numbers_path = self.config_dir / "approved_numbers.json"
        self.pending_requests_path = self.config_dir / "pending_requests.json"
        self.blocked_numbers_path = self.config_dir / "blocked_numbers.json"

        self._ensure_layout()

    def _ensure_layout(self) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.logs_users_dir.mkdir(parents=True, exist_ok=True)

        self._ensure_json(self.approved_numbers_path, {"numbers": []})
        self._ensure_json(self.pending_requests_path, {"requests": []})
        self._ensure_json(self.blocked_numbers_path, {"numbers": []})
        self._migrate_legacy_membership_config()

    def _migrate_legacy_membership_config(self) -> None:
        legacy_path = self.root / "config.json"
        if not legacy_path.exists():
            return

        raw = self._read_json(legacy_path, {})
        if not raw:
            return

        legacy_approved = {
            normalize_phone_e164(str(item))
            for item in (raw.get("allowlist") or [])
            if normalize_phone_e164(str(item))
        }
        legacy_blocked = {
            normalize_phone_e164(str(item))
            for item in (raw.get("blocked_numbers") or [])
            if normalize_phone_e164(str(item))
        }

        if legacy_approved:
            self._save_numbers(self.approved_numbers_path, self.approved_numbers() | legacy_approved)
        if legacy_blocked:
            self._save_numbers(self.blocked_numbers_path, self.blocked_numbers() | legacy_blocked)

        if "allowlist" in raw or "blocked_numbers" in raw:
            raw.pop("allowlist", None)
            raw.pop("blocked_numbers", None)
            self.config_store.save(raw)

    def _ensure_json(self, path: Path, payload: dict[str, Any]) -> None:
        if not path.exists():
            self._write_json(path, payload)

    @staticmethod
    def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return dict(default)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
        except (OSError, json.JSONDecodeError):
            pass
        return dict(default)

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")

    def _load_numbers(self, path: Path, key: str = "numbers") -> set[str]:
        raw = self._read_json(path, {key: []})
        values = raw.get(key)
        if not isinstance(values, list):
            values = []
        normalized = {
            normalize_phone_e164(str(item))
            for item in values
            if normalize_phone_e164(str(item))
        }
        return normalized

    def _save_numbers(self, path: Path, values: set[str], key: str = "numbers") -> None:
        self._write_json(path, {key: sorted(values)})

    def approved_numbers(self) -> set[str]:
        return self._load_numbers(self.approved_numbers_path, "numbers")

    def blocked_numbers(self) -> set[str]:
        return self._load_numbers(self.blocked_numbers_path, "numbers")

    def pending_requests(self) -> list[dict[str, Any]]:
        raw = self._read_json(self.pending_requests_path, {"requests": []})
        requests = raw.get("requests")
        if not isinstance(requests, list):
            return []
        clean: list[dict[str, Any]] = []
        for item in requests:
            if isinstance(item, dict):
                clean.append(item)
        return clean

    def add_pending_request(
        self,
        *,
        phone_number: str,
        recipient: str,
        body: str,
        request_id: str,
        message_sid: str | None,
        media: list[dict[str, Any]] | None,
    ) -> None:
        normalized_phone = normalize_phone_e164(phone_number)
        normalized_recipient = normalize_phone_e164(recipient)
        rows = self.pending_requests()
        existing = {normalize_phone_e164(str(row.get("phone_number") or "")) for row in rows}
        if normalized_phone not in existing:
            rows.append(
                {
                    "timestamp": iso_now(),
                    "phone_number": normalized_phone,
                    "recipient": normalized_recipient,
                    "request_id": request_id,
                    "message_sid": message_sid,
                    "body": str(body or ""),
                    "media_count": len(media or []),
                    "review_state": "pending",
                }
            )
            self._write_json(self.pending_requests_path, {"requests": rows})

    def remove_pending_request(self, phone_number: str) -> None:
        normalized_phone = normalize_phone_e164(phone_number)
        rows = self.pending_requests()
        kept = [
            row
            for row in rows
            if normalize_phone_e164(str(row.get("phone_number") or "")) != normalized_phone
        ]
        self._write_json(self.pending_requests_path, {"requests": kept})

    def add_approved_number(self, phone_number: str) -> None:
        normalized_phone = normalize_phone_e164(phone_number)
        approved = self.approved_numbers()
        blocked = self.blocked_numbers()

        approved.add(normalized_phone)
        if normalized_phone in blocked:
            blocked.remove(normalized_phone)

        self.remove_pending_request(normalized_phone)
        self._save_numbers(self.approved_numbers_path, approved)
        self._save_numbers(self.blocked_numbers_path, blocked)

    def add_blocked_number(self, phone_number: str) -> None:
        normalized_phone = normalize_phone_e164(phone_number)
        approved = self.approved_numbers()
        blocked = self.blocked_numbers()

        blocked.add(normalized_phone)
        if normalized_phone in approved:
            approved.remove(normalized_phone)

        self.remove_pending_request(normalized_phone)
        self._save_numbers(self.approved_numbers_path, approved)
        self._save_numbers(self.blocked_numbers_path, blocked)

    def is_pending(self, phone_number: str) -> bool:
        normalized_phone = normalize_phone_e164(phone_number)
        return any(
            normalize_phone_e164(str(row.get("phone_number") or "")) == normalized_phone
            for row in self.pending_requests()
        )

    def user_dir(self, phone_number: str) -> Path:
        normalized_phone = normalize_phone_e164(phone_number)
        return self.logs_users_dir / normalized_phone

    def ensure_user_profile(self, phone_number: str, state: str) -> Path:
        normalized_phone = normalize_phone_e164(phone_number)
        user_dir = self.user_dir(normalized_phone)
        user_dir.mkdir(parents=True, exist_ok=True)

        profile_path = user_dir / "profile.json"
        profile = self._read_json(profile_path, {})
        now = iso_now()

        if not profile:
            profile = {
                "phone_number": normalized_phone,
                "first_seen_at": now,
                "state": state,
            }

        profile["phone_number"] = normalized_phone
        profile["state"] = state
        profile["updated_at"] = now
        self._write_json(profile_path, profile)
        return profile_path

    def log_message(
        self,
        *,
        phone_number: str,
        direction: str,
        text: str,
        state: str,
        recipient: str,
        request_id: str,
        message_sid: str | None,
        media: list[dict[str, Any]] | None = None,
        response_mode: str | None = None,
    ) -> Path:
        normalized_phone = normalize_phone_e164(phone_number)
        normalized_recipient = normalize_phone_e164(recipient)
        user_dir = self.user_dir(normalized_phone)
        user_dir.mkdir(parents=True, exist_ok=True)

        messages_path = user_dir / "messages.jsonl"
        payload = {
            "timestamp": iso_now(),
            "direction": direction,
            "phone_number": normalized_phone,
            "recipient": normalized_recipient,
            "state": state,
            "text": str(text or ""),
            "request_id": request_id,
            "message_sid": message_sid,
            "media_count": len(media or []),
            "media": media or [],
            "response_mode": response_mode,
        }
        self._append_jsonl(messages_path, payload)
        return messages_path

    def recent_messages(self, phone_number: str, limit: int = 8) -> list[dict[str, Any]]:
        normalized_phone = normalize_phone_e164(phone_number)
        messages_path = self.user_dir(normalized_phone) / "messages.jsonl"
        if not messages_path.exists():
            return []

        rows: list[dict[str, Any]] = []
        for raw_line in messages_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
                if isinstance(payload, dict):
                    rows.append(payload)
            except json.JSONDecodeError:
                continue

        if limit <= 0:
            return rows
        return rows[-limit:]

    def profile(self, phone_number: str) -> dict[str, Any]:
        profile_path = self.user_dir(phone_number) / "profile.json"
        return self._read_json(profile_path, {})
