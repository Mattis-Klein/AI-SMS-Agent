"""Email tools backed by IMAP."""

from __future__ import annotations

import re
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from email import policy
from email.header import decode_header, make_header
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from ...services.email_accounts import EmailAccount, EmailAccountStore
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
        self.account_store = EmailAccountStore(Path(__file__).resolve().parent.parent.parent.parent)

    def _required_config(self, account: EmailAccount | None) -> tuple[bool, list[str]]:
        missing: list[str] = []
        if account is None:
            missing.append("email_account")
            return False, missing
        if not account.imap_host:
            missing.append("imap_host")
        if not account.email_address:
            missing.append("email_address")
        if not account.password:
            missing.append("password")
        if not account.imap_port:
            missing.append("imap_port")
        return len(missing) == 0, missing

    def _resolve_account(self, args: Dict[str, Any]) -> EmailAccount | None:
        account_id = str(args.get("account_id") or "").strip() or None
        if account_id:
            return self.account_store.get_account(account_id)
        query = str(args.get("account_query") or "").strip().lower()
        if not query:
            return self.account_store.get_account(None)
        accounts = self.account_store.list_accounts()
        for account in accounts:
            label = str(account.label or "").strip().lower()
            email = str(account.email_address or "").strip().lower()
            if query == label or query in label or query in email:
                return account
        return self.account_store.get_account(None)

    def _resolve_accounts(self, args: Dict[str, Any]) -> list[EmailAccount]:
        if bool(args.get("all_accounts")):
            return self.account_store.list_accounts()
        account = self._resolve_account(args)
        return [account] if account is not None else []

    def _normalize_category(self, value: str | None) -> str:
        raw = str(value or "").strip().lower()
        if not raw:
            return "Primary"
        if raw in {"all", "all tabs", "all categories", "everywhere"}:
            return "All"
        if raw.startswith("promo"):
            return "Promotions"
        if raw.startswith("social"):
            return "Social"
        if raw.startswith("update"):
            return "Updates"
        if raw.startswith("forum"):
            return "Forums"
        if raw.startswith("primary"):
            return "Primary"
        return raw.title()

    def _resolve_categories(self, account: EmailAccount, args: Dict[str, Any]) -> list[str]:
        standard = ["Primary", "Promotions", "Social", "Updates", "Forums"]
        account_categories = [self._normalize_category(item) for item in (account.categories or []) if str(item).strip()]
        if not account_categories:
            account_categories = ["Primary"]

        requested = self._normalize_category(args.get("category")) if args.get("category") is not None else ""
        if bool(args.get("all_categories")) or requested == "All":
            merged: list[str] = []
            for item in account_categories + standard:
                if item not in merged:
                    merged.append(item)
            return merged
        if requested:
            return [requested]
        default_category = self._normalize_category(account.default_category or "Primary")
        return [default_category]

    def _classify_email_exception(self, exc: Exception) -> tuple[str, str]:
        """Map low-level IMAP/network exceptions to stable error categories/messages."""
        message = str(exc or "").strip()
        lowered = message.lower()

        if isinstance(exc, TimeoutError) or "timed out" in lowered:
            return "connection_failure", "Email server connection timed out."

        if imaplib is not None:
            try:
                if isinstance(exc, imaplib.IMAP4.error):
                    if any(token in lowered for token in ["auth", "login", "invalid", "credentials", "authenticationfailed"]):
                        return "authentication_failure", "Email authentication failed."
                    return "execution_failure", message or "Email operation failed."
            except Exception:
                pass

        if any(token in lowered for token in ["connection refused", "name or service not known", "network is unreachable", "nodename nor servname", "temporary failure in name resolution"]):
            return "connection_failure", "Email server could not be reached."

        if any(token in lowered for token in ["auth", "login", "invalid credentials", "authenticationfailed", "password"]):
            return "authentication_failure", "Email authentication failed."

        return "execution_failure", (message or "Email operation failed.")

    def _ensure_configured(self, args: Dict[str, Any]) -> tuple[bool, str, list[str], EmailAccount | None]:
        account = self._resolve_account(args)
        if imaplib is None:
            return False, "IMAP support is unavailable in this build. Rebuild Mashbak with Python email/imap libraries included.", [], account
        ok, missing = self._required_config(account)
        if ok:
            return True, "", [], account
        return False, (
            "Email is not configured. Add an email account profile in the Mashbak control board or provide a configured account_id."
        ), missing, account

    @contextmanager
    def _connect(self, account: EmailAccount, args: Dict[str, Any]) -> Iterator[imaplib.IMAP4]:
        ok, error, _missing, _resolved = self._ensure_configured(args)
        if not ok:
            raise RuntimeError(error)

        client = imaplib.IMAP4_SSL(account.imap_host, account.imap_port) if account.use_ssl else imaplib.IMAP4(account.imap_host, account.imap_port)
        try:
            client.login(account.email_address, account.password)
            yield client
        finally:
            try:
                client.logout()
            except Exception:
                pass

    def _list_mailboxes(self, client: imaplib.IMAP4) -> list[str]:
        status, data = client.list()
        if status != "OK" or not data:
            return []
        names: list[str] = []
        for raw in data:
            line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
            match = re.search(r'"([^"]+)"\s*$', line)
            name = match.group(1) if match else line.split()[-1].strip('"')
            if name:
                names.append(name)
        return names

    def _select_mailbox(self, client: imaplib.IMAP4, mailbox_name: str) -> bool:
        status, _ = client.select(mailbox_name, readonly=True)
        return status == "OK"

    def _resolve_mailbox_for_category(self, client: imaplib.IMAP4, account: EmailAccount, category: str) -> str | None:
        base = str(account.mailbox or "INBOX").strip() or "INBOX"
        if category == "Primary":
            return base if self._select_mailbox(client, base) else None

        known = self._list_mailboxes(client)
        canonical = category.lower()
        for mailbox in known:
            lower = mailbox.lower()
            if lower.endswith("/" + canonical) or lower.endswith("." + canonical) or lower == canonical:
                if self._select_mailbox(client, mailbox):
                    return mailbox

        candidates = [
            f"{base}/{category}",
            f"{base}.{category}",
            f"[Gmail]/{category}",
            category,
        ]
        for mailbox in candidates:
            if self._select_mailbox(client, mailbox):
                return mailbox
        return None

    def _fetch_category_messages(
        self,
        client: imaplib.IMAP4,
        account: EmailAccount,
        category: str,
        limit: int,
        unread_only: bool,
    ) -> dict[str, Any]:
        mailbox = self._resolve_mailbox_for_category(client, account, category)
        if not mailbox:
            return {
                "category": category,
                "mailbox": None,
                "available": False,
                "unread_count": 0,
                "count": 0,
                "messages": [],
            }

        unread_ids = self._search(client, "UNSEEN")
        if unread_only and unread_ids:
            email_ids = unread_ids[-limit:]
        elif unread_only:
            email_ids = []
        else:
            email_ids = self._search(client, "ALL")[-limit:]
        email_ids.reverse()
        messages = self._fetch_messages(client, email_ids)
        return {
            "category": category,
            "mailbox": mailbox,
            "available": True,
            "unread_count": len(unread_ids),
            "count": len(messages),
            "messages": messages,
        }

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
        accounts = self._resolve_accounts(args)
        if not accounts:
            return ToolResult(
                success=False,
                output="",
                error="No matching email account is configured.",
                error_type="missing_configuration",
                tool_name=self.name,
                arguments=args,
            )

        for account in accounts:
            ok, error, missing, _ = self._ensure_configured({"account_id": account.account_id})
            if ok:
                continue
            return ToolResult(
                success=False,
                output="",
                error=error,
                error_type="missing_configuration",
                tool_name=self.name,
                arguments=args,
                missing_config_fields=missing,
                remediation="Add the missing email variables in mashbak/.env.master and retry.",
            )

        limit = int(args.get("limit", 5))
        unread_only = bool(args.get("unread_only", False))
        all_rows: list[dict[str, Any]] = []
        requested_scope = {
            "all_accounts": bool(args.get("all_accounts")),
            "all_categories": bool(args.get("all_categories")),
            "account_query": str(args.get("account_query") or "").strip() or None,
            "category": self._normalize_category(args.get("category")) if args.get("category") else None,
        }
        try:
            for account in accounts:
                with self._connect(account, {"account_id": account.account_id}) as client:
                    for category in self._resolve_categories(account, args):
                        bucket = self._fetch_category_messages(client, account, category, limit, unread_only)
                        for message in bucket.get("messages") or []:
                            row = dict(message)
                            row["account_id"] = account.account_id
                            row["account_label"] = account.label
                            row["category"] = category
                            row["mailbox"] = bucket.get("mailbox")
                            all_rows.append(row)
        except Exception as exc:
            error_type, error_text = self._classify_email_exception(exc)
            return ToolResult(
                success=False,
                output="",
                error=error_text,
                error_type=error_type,
                tool_name=self.name,
                arguments=args,
            )

        all_rows.sort(key=lambda item: str(item.get("date") or ""), reverse=True)
        messages = all_rows[: max(1, limit)]
        lines = [
            f"[{item.get('account_label')}/{item.get('category')}] {item['email_id']}: {item['from']} | {item['subject']} | {item['date']}"
            for item in messages
        ]
        data = {
            "count": len(messages),
            "messages": messages,
            "unread_only": unread_only,
            "accounts": [{"account_id": item.account_id, "label": item.label} for item in accounts],
            "scope": requested_scope,
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
        accounts = self._resolve_accounts(args)
        if not accounts:
            return ToolResult(
                success=False,
                output="",
                error="No matching email account is configured.",
                error_type="missing_configuration",
                tool_name=self.name,
                arguments=args,
            )

        for account in accounts:
            ok, error, missing, _ = self._ensure_configured({"account_id": account.account_id})
            if ok:
                continue
            return ToolResult(
                success=False,
                output="",
                error=error,
                error_type="missing_configuration",
                tool_name=self.name,
                arguments=args,
                missing_config_fields=missing,
                remediation="Add the missing email variables in mashbak/.env.master and retry.",
            )

        limit = int(args.get("limit", 5))
        unread_only = bool(args.get("unread_only", True))
        account_summaries: list[dict[str, Any]] = []
        try:
            for account in accounts:
                with self._connect(account, {"account_id": account.account_id}) as client:
                    categories = self._resolve_categories(account, args)
                    category_summaries: list[dict[str, Any]] = []
                    for category in categories:
                        category_summaries.append(
                            self._fetch_category_messages(
                                client=client,
                                account=account,
                                category=category,
                                limit=limit,
                                unread_only=unread_only,
                            )
                        )
                    account_summaries.append(
                        {
                            "account_id": account.account_id,
                            "account_label": account.label,
                            "categories": category_summaries,
                        }
                    )
        except Exception as exc:
            error_type, error_text = self._classify_email_exception(exc)
            return ToolResult(
                success=False,
                output="",
                error=error_text,
                error_type=error_type,
                tool_name=self.name,
                arguments=args,
            )

        flat_messages: list[dict[str, Any]] = []
        for account in account_summaries:
            for bucket in account.get("categories") or []:
                for message in bucket.get("messages") or []:
                    enriched = dict(message)
                    enriched["account_id"] = account.get("account_id")
                    enriched["account_label"] = account.get("account_label")
                    enriched["category"] = bucket.get("category")
                    flat_messages.append(enriched)

        summary_lines: list[str] = ["Email Summary"]
        for account_idx, account in enumerate(account_summaries):
            if len(account_summaries) > 1:
                if account_idx > 0:
                    summary_lines.append("")
                summary_lines.append(f"{account.get('account_label')}")
            for bucket in account.get("categories") or []:
                category = str(bucket.get("category") or "Primary")
                summary_lines.append(category)
                if not bucket.get("available"):
                    summary_lines.append("Category not available in this mailbox")
                    continue
                unread_count = int(bucket.get("unread_count") or 0)
                summary_lines.append(f"{unread_count} unread messages")

        unread_count = sum(int((bucket or {}).get("unread_count") or 0) for account in account_summaries for bucket in (account.get("categories") or []))
        data = {
            "count": len(flat_messages),
            "unread_count": unread_count,
            "messages": flat_messages,
            "accounts": account_summaries,
            "scope": {
                "all_accounts": bool(args.get("all_accounts")),
                "all_categories": bool(args.get("all_categories")),
                "account_query": str(args.get("account_query") or "").strip() or None,
                "category": self._normalize_category(args.get("category")) if args.get("category") else None,
            },
        }
        output = "\n".join(summary_lines) if len(summary_lines) > 1 else "No recent emails found."
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
        ok, error, missing, account = self._ensure_configured(args)
        if not ok:
            return ToolResult(
                success=False,
                output="",
                error=error,
                error_type="missing_configuration",
                tool_name=self.name,
                arguments=args,
                missing_config_fields=missing,
                remediation="Add the missing email variables in mashbak/.env.master and retry.",
            )

        query = str(args.get("query", "")).strip().replace('"', "")
        limit = int(args.get("limit", 5))

        try:
            with self._connect(account, args) as client:
                if not self._select_mailbox(client, str(account.mailbox or "INBOX")):
                    raise RuntimeError(f"Could not open mailbox '{account.mailbox}'.")
                subject_matches = self._search(client, "TEXT", f'"{query}"')
                email_ids = subject_matches[-limit:]
                email_ids.reverse()
                messages = self._fetch_messages(client, email_ids)
        except Exception as exc:
            error_type, error_text = self._classify_email_exception(exc)
            return ToolResult(
                success=False,
                output="",
                error=error_text,
                error_type=error_type,
                tool_name=self.name,
                arguments=args,
            )

        data = {
            "count": len(messages),
            "query": query,
            "messages": messages,
            "account_id": account.account_id if account else None,
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
        ok, error, missing, account = self._ensure_configured(args)
        if not ok:
            return ToolResult(
                success=False,
                output="",
                error=error,
                error_type="missing_configuration",
                tool_name=self.name,
                arguments=args,
                missing_config_fields=missing,
                remediation="Add the missing email variables in mashbak/.env.master and retry.",
            )

        email_id = str(args.get("email_id", "")).strip()
        try:
            with self._connect(account, args) as client:
                if not self._select_mailbox(client, str(account.mailbox or "INBOX")):
                    raise RuntimeError(f"Could not open mailbox '{account.mailbox}'.")
                _target, target_data = self._fetch_message(client, email_id)
                thread_subject = self._normalize_subject(target_data["subject"])
                related_ids = [email_id]
                if thread_subject:
                    related_ids = self._search(client, "SUBJECT", f'"{thread_subject.replace("\"", "")}"')[-10:]
                related_ids = list(dict.fromkeys(related_ids))
                related_ids.reverse()
                messages = self._fetch_messages(client, related_ids)
        except Exception as exc:
            error_type, error_text = self._classify_email_exception(exc)
            return ToolResult(
                success=False,
                output="",
                error=error_text,
                error_type=error_type,
                tool_name=self.name,
                arguments=args,
            )

        data = {
            "count": len(messages),
            "thread_subject": thread_subject or target_data["subject"],
            "messages": messages,
            "account_id": account.account_id if account else None,
        }
        lines = [f"{item['date']} | {item['from']} | {item['subject']} | {item['snippet']}" for item in messages]
        return ToolResult(
            success=True,
            output="\n".join(lines) if lines else "No related thread messages found.",
            tool_name=self.name,
            arguments=args,
            data=data,
        )