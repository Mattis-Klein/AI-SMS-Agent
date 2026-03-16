from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Optional

from ...services.email_accounts import EmailAccountStore
from ..base import Tool, ToolResult


class SendEmailTool(Tool):
    def __init__(self):
        super().__init__(
            name="send_email",
            description="Send an email using a configured email account",
            requires_args=True,
            category="email",
            safety={"destructive": False, "sensitive": True},
        )
        self.account_store = EmailAccountStore(Path(__file__).resolve().parent.parent.parent.parent)

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        if not str(args.get("to") or "").strip():
            return False, "to is required"
        if not str(args.get("subject") or "").strip():
            return False, "subject is required"
        if not str(args.get("body") or "").strip():
            return False, "body is required"
        return True, ""

    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        account = self.account_store.get_account(str(args.get("account_id") or "").strip() or None)
        if not account:
            return ToolResult(success=False, output="", error="No email account configured", error_type="missing_configuration", tool_name=self.name, arguments=args)

        smtp_host = str(args.get("smtp_host") or account.imap_host.replace("imap", "smtp"))
        smtp_port = int(args.get("smtp_port") or 587)

        msg = EmailMessage()
        msg["From"] = account.email_address
        msg["To"] = str(args.get("to"))
        msg["Subject"] = str(args.get("subject"))
        msg.set_content(str(args.get("body")))

        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as smtp:
                smtp.starttls()
                smtp.login(account.email_address, account.password)
                smtp.send_message(msg)
        except Exception as exc:
            return ToolResult(success=False, output="", error=f"Failed to send email: {exc}", error_type="execution_failure", tool_name=self.name, arguments=args)

        return ToolResult(success=True, output=f"Email sent to {msg['To']}", tool_name=self.name, arguments=args, data={"to": msg["To"], "subject": msg["Subject"], "account_id": account.account_id})


class DraftReplyTool(Tool):
    def __init__(self):
        super().__init__(
            name="draft_email_reply",
            description="Create a draft email reply as a file in outbox/drafts",
            requires_args=True,
            category="email",
            safety={"destructive": False},
        )

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        if not str(args.get("to") or "").strip():
            return False, "to is required"
        if not str(args.get("subject") or "").strip():
            return False, "subject is required"
        if not str(args.get("body") or "").strip():
            return False, "body is required"
        return True, ""

    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        workspace = context.get("workspace") if context else None
        if not workspace:
            return ToolResult(success=False, output="", error="Workspace not configured", tool_name=self.name)

        drafts = Path(workspace) / "outbox" / "drafts"
        drafts.mkdir(parents=True, exist_ok=True)
        name = str(args.get("filename") or "draft-reply.txt").strip()
        target = drafts / name
        payload = "\n".join([
            f"To: {str(args.get('to'))}",
            f"Subject: {str(args.get('subject'))}",
            "",
            str(args.get("body")),
        ])
        target.write_text(payload, encoding="utf-8")
        return ToolResult(success=True, output=f"Draft saved: {target}", tool_name=self.name, arguments=args, data={"path": str(target)})
