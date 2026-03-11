"""Email tools backed by IMAP."""

from __future__ import annotations

import os
import re
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from email import policy
from email.header import decode_header, make_header
from email.parser import BytesParser
from typing import Any, Dict, Iterator, Optional

from ..base import Tool, ToolResult

try:
    import imaplib
except ModuleNotFoundError:
    imaplib = None


@dataclass
class EmailMessageSummary:
    email_id: str
    subject: str
    sender: str
    date: str
    unread: bool
    snippet: str


class EmailToolBase(Tool):
    def __init__(self, name: str, description: str, requires_args: bool = False):
        super().__init__(name=name, description=description, requires_args=requires_args)
        self.host = os.getenv("EMAIL_IMAP_HOST", "").strip()
        self.port = int(os.getenv("EMAIL_IMAP_PORT", "993") or "993")
        self.username = os.getenv("EMAIL_USERNAME", "").strip()
        self.password = os.getenv("EMAIL_PASSWORD", "").strip()
        self.mailbox = os.getenv("EMAIL_MAILBOX", "INBOX").strip() or "INBOX"
        self.use_ssl = os.getenv("EMAIL_USE_SSL", "true").strip().lower() not in {"0", "false", "no"}

    def _ensure_configured(self) -> tuple[bool, str]:
        if imaplib is None:
            return False, "IMAP support is unavailable in this build. Rebuild Mashbak with Python email/imap libraries included."
        if self.host and self.username and self.password:
            return True, ""
        return False, (
            "Email is not configured. Set EMAIL_IMAP_HOST, EMAIL_USERNAME, and EMAIL_PASSWORD in mashbak/agent/.env."
        )

    @contextmanager
    def _connect(self) -> Iterator[imaplib.IMAP4]:
        ok, error = self._ensure_configured()
        if not ok:
            raise RuntimeError(error)

        client = imaplib.IMAP4_SSL(self.host, self.port) if self.use_ssl else imaplib.IMAP4(self.host, self.port)
        try:
            client.login(self.username, self.password)
            status, _ = client.select(self.mailbox, readonly=True)
            if status != "OK":
                raise RuntimeError(f"Could not open mailbox '{self.mailbox}'.")
            yield client
        finally:
            try:
                client.logout()
            except Exception:
                pass

    def _decode_header_value(self, value: str | None) -> str:
        if not value:
            return ""
        try:
            return str(make_header(decode_header(value)))
        except Exception:
            return value

    def _extract_snippet(self, message) -> str:
        if message.is_multipart():
            for part in message.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain" and part.get_content_disposition() != "attachment":
                    try:
                        text = part.get_content().strip()
                    except Exception:
                        payload = part.get_payload(decode=True) or b""
                        text = payload.decode(part.get_content_charset() or "utf-8", errors="replace").strip()
                    if text:
                        return self._compact(text)
            return ""

        try:
            return self._compact(message.get_content().strip())
        except Exception:
            payload = message.get_payload(decode=True) or b""
            return self._compact(payload.decode(message.get_content_charset() or "utf-8", errors="replace").strip())

    def _compact(self, value: str, max_length: int = 180) -> str:
        compact = " ".join(value.split())
        if len(compact) <= max_length:
            return compact
        return f"{compact[: max_length - 3]}..."

    def _normalize_subject(self, value: str) -> str:
        normalized = value.strip()
        while True:
            updated = re.sub(r"^(?:re|fw|fwd):\s*", "", normalized, flags=re.IGNORECASE)
            if updated == normalized:
                break
            normalized = updated.strip()
        return normalized

    def _fetch_message(self, client: imaplib.IMAP4, email_id: str) -> tuple[EmailMessageSummary, dict[str, Any]]:
        status, data = client.fetch(email_id, "(RFC822 FLAGS)")
        if status != "OK" or not data or not data[0]:
            raise RuntimeError(f"Could not fetch email {email_id}.")

        raw_bytes = data[0][1]
        message = BytesParser(policy=policy.default).parsebytes(raw_bytes)
        flags_blob = data[-1].decode("utf-8", errors="replace") if isinstance(data[-1], bytes) else str(data[-1])
        unread = "\\Seen" not in flags_blob
        subject = self._decode_header_value(message.get("Subject")) or "(no subject)"
        sender = self._decode_header_value(message.get("From")) or "unknown sender"
        date_value = self._decode_header_value(message.get("Date"))
        snippet = self._extract_snippet(message)

        summary = EmailMessageSummary(
            email_id=str(email_id),
            subject=subject,
            sender=sender,
            date=date_value,
            unread=unread,
            snippet=snippet,
        )
        return summary, {
            "email_id": str(email_id),
            "subject": subject,
            "from": sender,
            "date": date_value,
            "unread": unread,
            "snippet": snippet,
        }

    def _fetch_messages(self, client: imaplib.IMAP4, email_ids: list[str]) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for email_id in email_ids:
            _summary, message_data = self._fetch_message(client, email_id)
            messages.append(message_data)
        return messages

    def _search(self, client: imaplib.IMAP4, *criteria: str) -> list[str]:
        status, data = client.search(None, *criteria)
        if status != "OK" or not data:
            return []
        raw = data[0].decode("utf-8", errors="replace").strip()
        if not raw:
            return []
        return raw.split()


class ListRecentEmailsTool(EmailToolBase):
    def __init__(self):
        super().__init__(
            name="list_recent_emails",
            description="List recent emails from the configured inbox",
            requires_args=False,
        )

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        limit = args.get("limit", 5)
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            return False, "limit must be an integer"
        if limit < 1 or limit > 20:
            return False, "limit must be between 1 and 20"
        return True, ""

    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        ok, error = self._ensure_configured()
        if not ok:
            return ToolResult(success=False, output="", error=error, tool_name=self.name, arguments=args)

        limit = int(args.get("limit", 5))
        unread_only = bool(args.get("unread_only", False))
        try:
            with self._connect() as client:
                email_ids = self._search(client, "UNSEEN" if unread_only else "ALL")[-limit:]
                email_ids.reverse()
                messages = self._fetch_messages(client, email_ids)
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc), tool_name=self.name, arguments=args)

        lines = [
            f"{item['email_id']}: {item['from']} | {item['subject']} | {item['date']}"
            for item in messages
        ]
        data = {
            "count": len(messages),
            "messages": messages,
            "unread_only": unread_only,
        }
        return ToolResult(
            success=True,
            output="\n".join(lines) if lines else "No emails found.",
            tool_name=self.name,
            arguments=args,
            data=data,
        )


class SummarizeInboxTool(EmailToolBase):
    def __init__(self):
        super().__init__(
            name="summarize_inbox",
            description="Summarize unread or recent emails from the configured inbox",
            requires_args=False,
        )

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        limit = args.get("limit", 5)
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            return False, "limit must be an integer"
        if limit < 1 or limit > 20:
            return False, "limit must be between 1 and 20"
        return True, ""

    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        ok, error = self._ensure_configured()
        if not ok:
            return ToolResult(success=False, output="", error=error, tool_name=self.name, arguments=args)

        limit = int(args.get("limit", 5))
        unread_only = bool(args.get("unread_only", True))
        try:
            with self._connect() as client:
                unread_ids = self._search(client, "UNSEEN")
                email_ids = unread_ids[-limit:] if unread_only and unread_ids else self._search(client, "ALL")[-limit:]
                email_ids.reverse()
                messages = self._fetch_messages(client, email_ids)
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc), tool_name=self.name, arguments=args)

        unread_count = len(messages) if unread_only else len([item for item in messages if item.get("unread")])
        summary_lines = [
            f"{item['from']} about {item['subject']}"
            for item in messages[:5]
        ]
        data = {
            "count": len(messages),
            "unread_count": unread_count,
            "messages": messages,
        }
        output = " ; ".join(summary_lines) if summary_lines else "No recent emails found."
        return ToolResult(success=True, output=output, tool_name=self.name, arguments=args, data=data)


class SearchEmailsTool(EmailToolBase):
    def __init__(self):
        super().__init__(
            name="search_emails",
            description="Search email headers and message bodies for a query",
            requires_args=True,
        )

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        query = str(args.get("query", "")).strip()
        if not query:
            return False, "query is required"
        limit = args.get("limit", 5)
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            return False, "limit must be an integer"
        if limit < 1 or limit > 20:
            return False, "limit must be between 1 and 20"
        return True, ""

    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        ok, error = self._ensure_configured()
        if not ok:
            return ToolResult(success=False, output="", error=error, tool_name=self.name, arguments=args)

        query = str(args.get("query", "")).strip().replace('"', "")
        limit = int(args.get("limit", 5))

        try:
            with self._connect() as client:
                subject_matches = self._search(client, "TEXT", f'"{query}"')
                email_ids = subject_matches[-limit:]
                email_ids.reverse()
                messages = self._fetch_messages(client, email_ids)
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc), tool_name=self.name, arguments=args)

        data = {
            "count": len(messages),
            "query": query,
            "messages": messages,
        }
        lines = [f"{item['email_id']}: {item['from']} | {item['subject']}" for item in messages]
        return ToolResult(
            success=True,
            output="\n".join(lines) if lines else "No matching emails found.",
            tool_name=self.name,
            arguments=args,
            data=data,
        )


class ReadEmailThreadTool(EmailToolBase):
    def __init__(self):
        super().__init__(
            name="read_email_thread",
            description="Read a thread related to a specific email id",
            requires_args=True,
        )

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        email_id = str(args.get("email_id", "")).strip()
        if not email_id:
            return False, "email_id is required"
        return True, ""

    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        ok, error = self._ensure_configured()
        if not ok:
            return ToolResult(success=False, output="", error=error, tool_name=self.name, arguments=args)

        email_id = str(args.get("email_id", "")).strip()
        try:
            with self._connect() as client:
                _target, target_data = self._fetch_message(client, email_id)
                thread_subject = self._normalize_subject(target_data["subject"])
                related_ids = [email_id]
                if thread_subject:
                    related_ids = self._search(client, "SUBJECT", f'"{thread_subject.replace("\"", "")}"')[-10:]
                related_ids = list(dict.fromkeys(related_ids))
                related_ids.reverse()
                messages = self._fetch_messages(client, related_ids)
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc), tool_name=self.name, arguments=args)

        data = {
            "count": len(messages),
            "thread_subject": thread_subject or target_data["subject"],
            "messages": messages,
        }
        lines = [f"{item['date']} | {item['from']} | {item['subject']} | {item['snippet']}" for item in messages]
        return ToolResult(
            success=True,
            output="\n".join(lines) if lines else "No related thread messages found.",
            tool_name=self.name,
            arguments=args,
            data=data,
        )