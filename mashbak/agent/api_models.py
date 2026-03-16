from __future__ import annotations

from pydantic import BaseModel, Field


class ExecuteToolRequest(BaseModel):
    tool_name: str
    args: dict = {}
    owner_unlocked: bool | None = None


class ExecuteNaturalLanguageRequest(BaseModel):
    message: str
    owner_unlocked: bool | None = None


class BucherimMediaItem(BaseModel):
    url: str
    content_type: str | None = None
    filename: str | None = None


class BucherimSmsRequest(BaseModel):
    from_number: str
    to_number: str
    body: str = ""
    message_sid: str | None = None
    account_sid: str | None = None
    media: list[BucherimMediaItem] = Field(default_factory=list)


class EmailAccountSaveRequest(BaseModel):
    account_id: str | None = None
    label: str = ""
    email_address: str = ""
    password: str = ""
    imap_host: str = ""
    imap_port: int = 993
    use_ssl: bool = True
    mailbox: str = "INBOX"
    provider: str = "imap"
    make_default: bool = False


class EmailAccountActionRequest(BaseModel):
    account_id: str


class FilesPolicySaveRequest(BaseModel):
    allowed_directories: list[str] = Field(default_factory=list)


class PathTestRequest(BaseModel):
    path: str


class RoutingApproveRequest(BaseModel):
    phone_number: str


class RoutingDeactivateRequest(BaseModel):
    phone_number: str


class ToolPermissionUpdateRequest(BaseModel):
    tool_name: str
    enabled: bool | None = None
    allowed_sources: list[str] | None = None
    requires_approval: bool | None = None
    requires_unlocked_desktop: bool | None = None
    scope: str | None = None


class ApprovalActionRequest(BaseModel):
    approval_id: str
    reviewer: str = "operator"


class PersonalContextSaveRequest(BaseModel):
    profile: dict = Field(default_factory=dict)
    people: list[dict] = Field(default_factory=list)
    routines: list[dict] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
    preferences: dict = Field(default_factory=dict)