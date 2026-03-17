from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import imaplib
except ModuleNotFoundError:  # pragma: no cover
    imaplib = None

try:
    from ..config_loader import ConfigLoader
except ImportError:  # pragma: no cover - script-mode fallback
    from config_loader import ConfigLoader


@dataclass
class EmailAccount:
    account_id: str
    label: str
    email_address: str
    password: str
    imap_host: str
    imap_port: int
    use_ssl: bool
    mailbox: str
    provider: str = "imap"
    categories: list[str] | None = None
    default_category: str = "Primary"
    is_default: bool = False

    def public_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "label": self.label,
            "email_address": self.email_address,
            "imap_host": self.imap_host,
            "imap_port": self.imap_port,
            "use_ssl": self.use_ssl,
            "mailbox": self.mailbox,
            "provider": self.provider,
            "categories": list(self.categories or []),
            "default_category": self.default_category or "Primary",
            "is_default": self.is_default,
            "password_set": bool(self.password),
        }


class EmailAccountStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir.resolve()
        self.path = self.base_dir / "data" / "config" / "email_accounts.json"

    def _default_payload(self) -> dict[str, Any]:
        return {"default_account_id": None, "accounts": []}

    def _legacy_account(self) -> EmailAccount | None:
        ConfigLoader.load(reload=True)
        host = (ConfigLoader.get("EMAIL_IMAP_HOST") or ConfigLoader.get("IMAP_SERVER") or "").strip()
        username = (ConfigLoader.get("EMAIL_USERNAME") or ConfigLoader.get("EMAIL_ADDRESS") or "").strip()
        password = (ConfigLoader.get("EMAIL_PASSWORD") or "").strip()
        if not (host and username and password):
            return None
        port = ConfigLoader.get_int("EMAIL_IMAP_PORT", ConfigLoader.get_int("IMAP_PORT", 993))
        mailbox = (ConfigLoader.get("EMAIL_MAILBOX", "INBOX") or "INBOX").strip() or "INBOX"
        use_ssl = ConfigLoader.get_bool("EMAIL_USE_SSL", True)
        provider = (ConfigLoader.get("EMAIL_PROVIDER") or "imap").strip() or "imap"
        return EmailAccount(
            account_id="legacy-default",
            label="Primary",
            email_address=username,
            password=password,
            imap_host=host,
            imap_port=port,
            use_ssl=use_ssl,
            mailbox=mailbox,
            provider=provider,
            categories=["Primary"],
            default_category="Primary",
            is_default=True,
        )

    def _read_payload(self) -> dict[str, Any]:
        if not self.path.exists():
            legacy = self._legacy_account()
            if legacy is None:
                return self._default_payload()
            return {
                "default_account_id": legacy.account_id,
                "accounts": [legacy.public_dict() | {"password": legacy.password}],
            }
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = self._default_payload()
        if not isinstance(raw, dict):
            raw = self._default_payload()
        raw.setdefault("default_account_id", None)
        raw.setdefault("accounts", [])
        return raw

    def _write_payload(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list_accounts(self) -> list[EmailAccount]:
        payload = self._read_payload()
        default_id = payload.get("default_account_id")
        accounts: list[EmailAccount] = []
        for row in payload.get("accounts") or []:
            if not isinstance(row, dict):
                continue
            accounts.append(
                EmailAccount(
                    account_id=str(row.get("account_id") or uuid.uuid4().hex[:12]),
                    label=str(row.get("label") or row.get("email_address") or "Email account"),
                    email_address=str(row.get("email_address") or ""),
                    password=str(row.get("password") or ""),
                    imap_host=str(row.get("imap_host") or ""),
                    imap_port=int(row.get("imap_port") or 993),
                    use_ssl=bool(row.get("use_ssl", True)),
                    mailbox=str(row.get("mailbox") or "INBOX"),
                    provider=str(row.get("provider") or "imap"),
                    categories=[str(item) for item in (row.get("categories") or []) if str(item).strip()],
                    default_category=str(row.get("default_category") or "Primary"),
                    is_default=str(row.get("account_id")) == str(default_id),
                )
            )
        if not accounts:
            legacy = self._legacy_account()
            if legacy:
                accounts.append(legacy)
        if accounts and not any(account.is_default for account in accounts):
            accounts[0].is_default = True
        return accounts

    def list_public_accounts(self) -> dict[str, Any]:
        accounts = self.list_accounts()
        return {
            "accounts": [account.public_dict() for account in accounts],
            "default_account_id": next((account.account_id for account in accounts if account.is_default), None),
        }

    def get_account(self, account_id: str | None = None) -> EmailAccount | None:
        accounts = self.list_accounts()
        if not accounts:
            return None
        if account_id:
            for account in accounts:
                if account.account_id == account_id:
                    return account
        for account in accounts:
            if account.is_default:
                return account
        return accounts[0]

    def save_account(
        self,
        *,
        account_id: str | None,
        label: str,
        email_address: str,
        password: str,
        imap_host: str,
        imap_port: int,
        use_ssl: bool,
        mailbox: str,
        provider: str = "imap",
        make_default: bool = False,
        categories: list[str] | None = None,
        default_category: str | None = None,
    ) -> dict[str, Any]:
        payload = self._read_payload()
        rows = [row for row in payload.get("accounts") or [] if isinstance(row, dict)]
        normalized_id = account_id or uuid.uuid4().hex[:12]
        existing = next((row for row in rows if str(row.get("account_id")) == normalized_id), None)
        if existing is None:
            existing = {"account_id": normalized_id}
            rows.append(existing)
        existing["label"] = label.strip() or email_address.strip() or "Email account"
        existing["email_address"] = email_address.strip()
        existing["imap_host"] = imap_host.strip()
        existing["imap_port"] = int(imap_port)
        existing["use_ssl"] = bool(use_ssl)
        existing["mailbox"] = mailbox.strip() or "INBOX"
        existing["provider"] = provider.strip() or "imap"
        normalized_categories = [str(item).strip() for item in (categories or []) if str(item).strip()]
        existing["categories"] = normalized_categories or ["Primary"]
        existing["default_category"] = str(default_category or existing.get("default_category") or "Primary").strip() or "Primary"
        if str(password or "").strip():
            existing["password"] = str(password).strip()
        else:
            existing["password"] = str(existing.get("password") or "")
        payload["accounts"] = rows
        if make_default or not payload.get("default_account_id"):
            payload["default_account_id"] = normalized_id
        self._write_payload(payload)
        return self.list_public_accounts()

    def delete_account(self, account_id: str) -> dict[str, Any]:
        payload = self._read_payload()
        rows = [row for row in payload.get("accounts") or [] if isinstance(row, dict)]
        rows = [row for row in rows if str(row.get("account_id")) != str(account_id)]
        payload["accounts"] = rows
        if str(payload.get("default_account_id")) == str(account_id):
            payload["default_account_id"] = rows[0].get("account_id") if rows else None
        self._write_payload(payload)
        return self.list_public_accounts()

    def set_default(self, account_id: str) -> dict[str, Any]:
        payload = self._read_payload()
        payload["default_account_id"] = account_id
        self._write_payload(payload)
        return self.list_public_accounts()

    def is_configured(self) -> bool:
        return bool(self.list_accounts())

    def test_account(self, account_id: str | None = None) -> tuple[bool, str]:
        account = self.get_account(account_id)
        if account is None:
            return False, "No email account is configured."
        if imaplib is None:
            return False, "IMAP support is unavailable in this build."

        client = None
        try:
            client = imaplib.IMAP4_SSL(account.imap_host, account.imap_port) if account.use_ssl else imaplib.IMAP4(account.imap_host, account.imap_port)
            client.login(account.email_address, account.password)
            status, _ = client.select(account.mailbox, readonly=True)
            if status != "OK":
                return False, f"Could not open mailbox '{account.mailbox}'."
            return True, f"Connected to {account.label} successfully."
        except Exception as exc:
            return False, str(exc)
        finally:
            if client is not None:
                try:
                    client.logout()
                except Exception:
                    pass
