"""
Mashbak FastAPI application

Tool-based architecture for executing safe commands via SMS.
All requests are routed through the tool dispatcher, which validates
inputs and logs all activities.
"""

import asyncio
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

if __package__:
    from .runtime import create_runtime
else:
    from runtime import create_runtime


# ============================================================================
# Initialization
# ============================================================================

app = FastAPI(title="Mashbak", version="2.0.0")
runtime = create_runtime()


# ============================================================================
# Request Models
# ============================================================================

class ExecuteToolRequest(BaseModel):
    """Request to execute a tool by name"""
    tool_name: str
    args: dict = {}


class ExecuteNaturalLanguageRequest(BaseModel):
    """Request to execute a natural language message"""
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


class EmailConfigSaveRequest(BaseModel):
    provider: str = "imap"
    email_address: str = ""
    password: str = ""
    imap_host: str = ""
    imap_port: int = 993
    use_ssl: bool = True
    mailbox: str = "INBOX"


class FilesPolicySaveRequest(BaseModel):
    allowed_directories: list[str] = Field(default_factory=list)


class PathTestRequest(BaseModel):
    path: str


class RoutingApproveRequest(BaseModel):
    phone_number: str
    activate_now: bool = False


class RoutingDeactivateRequest(BaseModel):
    phone_number: str


def _platform_root() -> Path:
    return runtime.base_dir


def _agent_log_path() -> Path:
    return _platform_root() / "data" / "logs" / "agent.log"


def _bridge_log_path() -> Path:
    return _platform_root() / "data" / "logs" / "bridge.log"


def _agent_config_path() -> Path:
    return _platform_root() / "agent" / "config.json"


def _bucherim_config_path() -> Path:
    return _platform_root() / "assistants" / "bucherim" / "config.json"


def _bucherim_users_root() -> Path:
    return _platform_root() / "data" / "users" / "bucherim"


def _pending_requests_path() -> Path:
    return _bucherim_users_root() / "pending_requests.jsonl"


def _normalize_phone(value: str) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if not digits:
        return ""
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return f"+{digits}"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_jsonl(path: Path, limit: int = 200) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            rows.append({"raw": line})
    return rows[-limit:]


def _tail_events(path: Path, limit: int = 120) -> list[dict[str, Any]]:
    rows = _read_jsonl(path, limit=limit)
    return [r for r in rows if isinstance(r, dict)]


def _recent_tool_actions(limit: int = 25) -> list[dict[str, Any]]:
    events = _tail_events(_agent_log_path(), limit=400)
    actions: list[dict[str, Any]] = []
    for ev in reversed(events):
        if ev.get("event_type") != "tool_execution":
            continue
        actions.append({
            "timestamp": ev.get("time"),
            "assistant": ev.get("sender") or "desktop",
            "requested_action": ev.get("interpreted_intent") or ev.get("tool_name"),
            "selected_tool": ev.get("tool_name"),
            "result": "success" if ev.get("success") else "failure",
            "state": "blocked" if str(ev.get("error") or "").lower().find("allowed") >= 0 else ("success" if ev.get("success") else "failure"),
            "target": (ev.get("arguments") or {}).get("path") if isinstance(ev.get("arguments"), dict) else None,
            "details": ev.get("error") or ev.get("output"),
        })
        if len(actions) >= limit:
            break
    return actions


def _recent_failures(limit: int = 10) -> list[dict[str, Any]]:
    events = _tail_events(_agent_log_path(), limit=400)
    failures: list[dict[str, Any]] = []
    for ev in reversed(events):
        if ev.get("event_type") == "tool_execution" and not ev.get("success"):
            failures.append({
                "timestamp": ev.get("time"),
                "tool": ev.get("tool_name"),
                "error": ev.get("error"),
            })
        elif ev.get("event_type") == "error":
            failures.append({
                "timestamp": ev.get("time"),
                "tool": ev.get("tool_name"),
                "error": ev.get("error_message") or ev.get("error_type"),
            })
        if len(failures) >= limit:
            break
    return failures


def _bridge_health() -> dict[str, Any]:
    url = "http://127.0.0.1:34567/health"
    try:
        with urllib.request.urlopen(url, timeout=1.2) as response:
            payload = response.read().decode("utf-8", errors="replace")
        parsed = json.loads(payload)
        return {"connected": True, "detail": parsed}
    except Exception as exc:
        return {"connected": False, "detail": str(exc)}


def _test_path_allowed(path_text: str) -> tuple[bool, str]:
    path_value = str(path_text or "").strip()
    if not path_value:
        return False, "Path is empty"
    requested = Path(path_value).expanduser().resolve()
    workspace = runtime.workspace.resolve()
    if requested.is_relative_to(workspace):
        return True, f"Allowed: workspace-relative ({requested})"
    for allowed in runtime.config.get_allowed_directories():
        base = Path(allowed).expanduser().resolve()
        if requested.is_relative_to(base):
            return True, f"Allowed: within {base}"
    return False, "Blocked: path is not in allowed directories"


# ============================================================================
# Authentication & Middleware
# ============================================================================

def authenticate(api_key: Optional[str], request_id: Optional[str] = None) -> None:
    """Authenticate API request"""
    if api_key != runtime.api_key:
        runtime.logger.log_error(
            request_id=request_id or "unknown",
            error_type="auth_failed",
            error_message="Invalid API key",
        )
        raise HTTPException(status_code=401, detail="Unauthorized")


# ============================================================================
# Health & Info Endpoints
# ============================================================================

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "workspace": str(runtime.workspace),
        "tools_loaded": len(runtime.registry.list_all()),
        "assistant_ai_enabled": bool(runtime.openai_api_key),
        "assistant_model": runtime.openai_model,
        "model_response_max_tokens": runtime.model_response_max_tokens,
        "session_context_max_turns": runtime.session_context_turns,
        "tool_timeout_seconds": runtime.default_tool_timeout_seconds,
        "email_configured": bool(runtime.summary().get("email_configured")),
        "version": "2.0.0",
    }


@app.get("/tools")
def list_tools(x_api_key: str = Header(None)):
    """List all available tools with descriptions"""
    authenticate(x_api_key)
    
    return {
        "tools": runtime.registry.get_all_info(),
        "count": len(runtime.registry.list_all()),
    }


@app.get("/tools/{tool_name}")
def get_tool_info(tool_name: str, x_api_key: str = Header(None)):
    """Get information about a specific tool"""
    authenticate(x_api_key)
    
    info = runtime.registry.get_info(tool_name)
    if not info:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    
    return info


# ============================================================================
# Session Debug Endpoint
# ============================================================================

@app.get("/session/{session_id}")
def get_session_context(session_id: str, x_api_key: str = Header(None)):
    """
    Return a debug-safe summary of the current session context.

    Shows recent context summary, pending task, missing parameters, last task,
    last result, and last created path.  Sensitive config values are never
    exposed here.

    session_id format:  desktop:<sender_key>  or  sms:<digits>
    """
    authenticate(x_api_key)
    return runtime.session_context.public_summary(session_id)


# ============================================================================
# Tool Execution Endpoints
# ============================================================================

@app.post("/execute")
async def execute_tool(
    req: ExecuteToolRequest,
    x_api_key: str = Header(None),
    x_request_id: str = Header(None),
    x_sender: str = Header(None),
    x_source: str = Header(None),
):
    """
    Execute a tool directly by name with structured arguments.
    
    Example:
        POST /execute
        {
            "tool_name": "list_files",
            "args": {"path": "C:\\Users\\owner\\Documents"}
        }
    """
    authenticate(x_api_key, x_request_id)

    result = await runtime.execute_tool(
        tool_name=req.tool_name,
        args=req.args,
        sender=x_sender or "unknown",
        request_id=x_request_id,
        source=x_source,
    )

    if result["tool_name"] is None and "not found" in (result.get("error") or ""):
        raise HTTPException(status_code=404, detail=result["error"])

    if not result["success"] and "not allowed" in (result.get("error") or ""):
        raise HTTPException(status_code=403, detail=result["error"])

    trace = result.get("trace") or {}
    if not result["success"] and trace.get("validation_status") == "failed":
        raise HTTPException(status_code=400, detail=result["error"])

    return {
        "success": result["success"],
        "tool_name": result["tool_name"],
        "output": result["output"],
        "error": result["error"],
        "error_type": result.get("error_type"),
        "missing_config_fields": result.get("missing_config_fields"),
        "remediation": result.get("remediation"),
        "request_id": result["request_id"],
        "source": result.get("source", x_source or "unknown"),
        "trace": result.get("trace"),
    }


@app.post("/execute-nl")
async def execute_natural_language(
    req: ExecuteNaturalLanguageRequest,
    x_api_key: str = Header(None),
    x_request_id: str = Header(None),
    x_sender: str = Header(None),
    x_source: str = Header(None),
):
    """
    Execute a natural language request. The system interprets the message,
    selects an appropriate tool, validates inputs, and executes the tool.
    
    Example:
        POST /execute-nl
        {"message": "list files in my documents"}
    """
    authenticate(x_api_key, x_request_id)

    result = await runtime.execute_nl(
        message=req.message,
        sender=x_sender or "unknown",
        request_id=x_request_id,
        source=x_source,
        owner_unlocked=req.owner_unlocked,
    )
    
    # Format response
    return {
        "success": result["success"],
        "tool_name": result["tool_name"],
        "output": result["output"],
        "error": result["error"],
        "error_type": result.get("error_type"),
        "missing_config_fields": result.get("missing_config_fields"),
        "remediation": result.get("remediation"),
        "request_id": result["request_id"],
        "sender": x_sender or "unknown",
        "source": result.get("source", x_source or "unknown"),
        "data": result.get("data"),
        "trace": result.get("trace"),
    }


@app.post("/bucherim/sms")
async def execute_bucherim_sms(
    req: BucherimSmsRequest,
    x_api_key: str = Header(None),
    x_request_id: str = Header(None),
):
    """Dedicated Bucherim SMS entrypoint for bridge transport routing."""
    authenticate(x_api_key, x_request_id)

    result = await runtime.execute_bucherim_sms(
        sender=req.from_number,
        recipient=req.to_number,
        body=req.body,
        request_id=x_request_id or "unknown",
        message_sid=req.message_sid,
        account_sid=req.account_sid,
        media=[item.model_dump() for item in req.media],
    )

    return {
        "success": True,
        "reply": result.get("reply", ""),
        "full_reply": result.get("full_reply", result.get("reply", "")),
        "status": result.get("status"),
        "response_mode": result.get("response_mode"),
        "normalized_sender": result.get("normalized_sender"),
        "normalized_recipient": result.get("normalized_recipient"),
        "media_count": result.get("media_count", 0),
        "outbound_media": result.get("outbound_media", []),
        "request_id": x_request_id or "unknown",
    }


# ============================================================================
# Control Board Endpoints
# ============================================================================

@app.get("/control-board/overview")
def control_board_overview(x_api_key: str = Header(None)):
    authenticate(x_api_key)
    summary = runtime.summary()
    return {
        "backend": {
            "connected": True,
            "workspace": summary.get("workspace"),
            "model": summary.get("assistant_model"),
            "ai_enabled": summary.get("assistant_ai_enabled"),
        },
        "bridge": _bridge_health(),
        "email": {
            "configured": summary.get("email_configured"),
        },
        "active_assistant": "mashbak",
        "recent_failures": _recent_failures(limit=10),
        "recent_actions": _recent_tool_actions(limit=12),
        "quick_actions": [
            "check system info",
            "list recent emails",
            "create file in workspace",
            "show blocked path attempts",
        ],
    }


@app.get("/control-board/activity")
def control_board_activity(limit: int = 100, x_api_key: str = Header(None)):
    authenticate(x_api_key)
    cap = max(10, min(int(limit or 100), 500))
    return {
        "items": _recent_tool_actions(limit=cap),
        "count": cap,
    }


@app.get("/control-board/email-config")
def control_board_email_config(x_api_key: str = Header(None)):
    authenticate(x_api_key)
    from .config_loader import ConfigLoader

    host = (ConfigLoader.get("EMAIL_IMAP_HOST") or ConfigLoader.get("IMAP_SERVER") or "").strip()
    port = int(ConfigLoader.get("EMAIL_IMAP_PORT") or ConfigLoader.get("IMAP_PORT") or 993)
    username = (ConfigLoader.get("EMAIL_USERNAME") or ConfigLoader.get("EMAIL_ADDRESS") or "").strip()
    mailbox = (ConfigLoader.get("EMAIL_MAILBOX") or "INBOX").strip() or "INBOX"
    use_ssl = ConfigLoader.get_bool("EMAIL_USE_SSL", True)
    provider = (ConfigLoader.get("EMAIL_PROVIDER") or "imap").strip() or "imap"

    return {
        "provider": provider,
        "email_address": username,
        "password_set": bool((ConfigLoader.get("EMAIL_PASSWORD") or "").strip()),
        "imap_host": host,
        "imap_port": port,
        "use_ssl": use_ssl,
        "mailbox": mailbox,
    }


@app.post("/control-board/email-config/save")
async def control_board_email_save(req: EmailConfigSaveRequest, x_api_key: str = Header(None)):
    authenticate(x_api_key)

    updates = {
        "EMAIL_PROVIDER": req.provider,
        "EMAIL_USERNAME": req.email_address,
        "EMAIL_IMAP_HOST": req.imap_host,
        "EMAIL_IMAP_PORT": str(req.imap_port),
        "EMAIL_USE_SSL": "true" if req.use_ssl else "false",
        "EMAIL_MAILBOX": req.mailbox,
    }
    if str(req.password or "").strip():
        updates["EMAIL_PASSWORD"] = req.password

    results = []
    for key, value in updates.items():
        if not str(value or "").strip():
            continue
        result = await runtime.execute_tool(
            tool_name="set_config_variable",
            args={"variable_name": key, "variable_value": str(value)},
            sender="desktop-control-board",
            source="desktop",
        )
        results.append({"variable": key, "success": bool(result.get("success")), "error": result.get("error")})

    return {
        "success": all(item["success"] for item in results) if results else False,
        "updates": results,
    }


@app.post("/control-board/email-config/test")
async def control_board_email_test(x_api_key: str = Header(None)):
    authenticate(x_api_key)
    result = await runtime.execute_tool(
        tool_name="list_recent_emails",
        args={"limit": 1},
        sender="desktop-control-board",
        source="desktop",
    )
    return {
        "success": bool(result.get("success")),
        "error_type": result.get("error_type"),
        "message": result.get("output") if result.get("success") else result.get("error"),
    }


@app.get("/control-board/files-policy")
def control_board_files_policy(x_api_key: str = Header(None)):
    authenticate(x_api_key)
    allowed = [str(item) for item in runtime.config.get_allowed_directories()]
    blocked_attempts = []
    for ev in _tail_events(_agent_log_path(), limit=250):
        if ev.get("event_type") != "tool_execution":
            continue
        if ev.get("success"):
            continue
        err = str(ev.get("error") or "")
        if "allowed" in err.lower() or "path is not in allowed directories" in err.lower():
            args = ev.get("arguments") if isinstance(ev.get("arguments"), dict) else {}
            blocked_attempts.append({
                "timestamp": ev.get("time"),
                "tool": ev.get("tool_name"),
                "path": args.get("path") or args.get("parent_path"),
                "error": err,
            })
    blocked_attempts = blocked_attempts[-60:]
    return {
        "allowed_directories": allowed,
        "blocked_attempts": blocked_attempts,
    }


@app.post("/control-board/files-policy/save")
def control_board_files_policy_save(req: FilesPolicySaveRequest, x_api_key: str = Header(None)):
    authenticate(x_api_key)
    normalized = [str(Path(p).expanduser().resolve()) for p in req.allowed_directories if str(p).strip()]
    payload = _load_json(_agent_config_path(), default={})
    payload["allowed_directories"] = normalized
    _save_json(_agent_config_path(), payload)
    runtime.config.load()
    return {"success": True, "allowed_directories": normalized}


@app.post("/control-board/files-policy/test-path")
def control_board_files_policy_test_path(req: PathTestRequest, x_api_key: str = Header(None)):
    authenticate(x_api_key)
    allowed, reason = _test_path_allowed(req.path)
    return {
        "allowed": allowed,
        "reason": reason,
    }


@app.get("/control-board/assistants")
def control_board_assistants(x_api_key: str = Header(None)):
    authenticate(x_api_key)
    bucherim = _load_json(_bucherim_config_path(), default={})
    return {
        "mashbak": {
            "model": runtime.openai_model,
            "base_url": runtime.openai_base_url,
            "temperature": runtime.openai_temperature,
            "max_tokens": runtime.model_response_max_tokens,
            "ai_enabled": bool(runtime.openai_api_key),
        },
        "bucherim": {
            "assistant_number": bucherim.get("assistant_number"),
            "allowlist_count": len(bucherim.get("allowlist") or []),
            "blocked_numbers_count": len(bucherim.get("blocked_numbers") or []),
            "responses": bucherim.get("responses") or {},
        },
    }


@app.get("/control-board/routing")
def control_board_routing(x_api_key: str = Header(None)):
    authenticate(x_api_key)
    bucherim = _load_json(_bucherim_config_path(), default={})
    pending = _read_jsonl(_pending_requests_path(), limit=200)
    pending = [item for item in pending if isinstance(item, dict)]
    return {
        "assistant_number": bucherim.get("assistant_number"),
        "allowlist": bucherim.get("allowlist") or [],
        "blocked_numbers": bucherim.get("blocked_numbers") or [],
        "pending_join_requests": pending,
    }


@app.post("/control-board/routing/approve")
def control_board_routing_approve(req: RoutingApproveRequest, x_api_key: str = Header(None)):
    authenticate(x_api_key)
    normalized = _normalize_phone(req.phone_number)
    if not normalized:
        raise HTTPException(status_code=400, detail="Invalid phone number")

    config = _load_json(_bucherim_config_path(), default={})
    allowlist = list(config.get("allowlist") or [])
    if normalized not in allowlist:
        allowlist.append(normalized)
    config["allowlist"] = allowlist
    _save_json(_bucherim_config_path(), config)

    user_key = "p" + "".join(ch for ch in normalized if ch.isdigit())
    user_dir = _bucherim_users_root() / user_key
    membership_path = user_dir / "membership.json"
    membership = _load_json(membership_path, default={})
    membership["phone_number"] = normalized
    membership["status"] = "active" if req.activate_now else "allowlisted"
    membership["source"] = "control_board_approve"
    _save_json(membership_path, membership)

    return {"success": True, "phone_number": normalized, "status": membership.get("status")}


@app.post("/control-board/routing/deactivate")
def control_board_routing_deactivate(req: RoutingDeactivateRequest, x_api_key: str = Header(None)):
    authenticate(x_api_key)
    normalized = _normalize_phone(req.phone_number)
    if not normalized:
        raise HTTPException(status_code=400, detail="Invalid phone number")

    config = _load_json(_bucherim_config_path(), default={})
    allowlist = [item for item in list(config.get("allowlist") or []) if str(item) != normalized]
    blocked = list(config.get("blocked_numbers") or [])
    if normalized not in blocked:
        blocked.append(normalized)
    config["allowlist"] = allowlist
    config["blocked_numbers"] = blocked
    _save_json(_bucherim_config_path(), config)

    user_key = "p" + "".join(ch for ch in normalized if ch.isdigit())
    membership_path = _bucherim_users_root() / user_key / "membership.json"
    membership = _load_json(membership_path, default={})
    if membership:
        membership["status"] = "blocked"
        membership["source"] = "control_board_deactivate"
        _save_json(membership_path, membership)

    return {"success": True, "phone_number": normalized, "status": "blocked"}


# ============================================================================
# Legacy Compatibility Endpoints
# ============================================================================

@app.post("/run")
async def run_legacy_command(
    tool_name: str = None,
    args: dict = None,
    x_api_key: str = Header(None),
    x_request_id: str = Header(None),
    x_sender: str = Header(None),
    x_source: str = Header(None),
):
    """
    Legacy compatibility endpoint. Forwards to new /execute endpoint.
    """
    authenticate(x_api_key, x_request_id)
    
    req = ExecuteToolRequest(tool_name=tool_name, args=args or {})
    return await execute_tool(
        req,
        x_api_key=x_api_key,
        x_request_id=x_request_id,
        x_sender=x_sender,
        x_source=x_source,
    )


# ============================================================================
# Startup/Shutdown
# ============================================================================

@app.on_event("startup")
def startup():
    """Log startup"""
    runtime.logger.log(
        event_type="startup",
        tools_loaded=len(runtime.registry.list_all()),
        workspace=str(runtime.workspace),
    )


@app.on_event("shutdown")
def shutdown():
    """Log shutdown"""
    runtime.logger.log(event_type="shutdown")