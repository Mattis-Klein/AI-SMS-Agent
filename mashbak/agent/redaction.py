"""Central redaction helpers for Mashbak logging and debug surfaces."""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[REDACTED]"

SENSITIVE_VARIABLES = {
    "OPENAI_API_KEY",
    "EMAIL_PASSWORD",
    "EMAIL_PASS",
    "TWILIO_AUTH_TOKEN",
    "AGENT_API_KEY",
    "LOCAL_APP_PIN",
}

SENSITIVE_KEYS = {
    "password",
    "token",
    "api_key",
    "authorization",
    "auth",
    "secret",
    "variable_value",
}

_CONFIG_ASSIGNMENT_PATTERN = re.compile(
    r"(?P<var>\b[A-Z_][A-Z0-9_]*\b)\s*(?P<sep>[:=])\s*(?P<value>.*?)(?=(?:\s+\b[A-Z_][A-Z0-9_]*\b\s*[:=])|$|\r|\n)"
)


def _is_sensitive_key(key: str | None) -> bool:
    if not key:
        return False
    lowered = key.lower()
    if lowered in SENSITIVE_KEYS:
        return True
    return any(token in lowered for token in ("password", "token", "api_key", "secret"))


def _is_sensitive_variable_name(name: str | None) -> bool:
    if not name:
        return False
    return name.strip().upper() in SENSITIVE_VARIABLES


def redact_config_assignments(text: str) -> str:
    """Redact values for config-like assignments in free text."""

    def _replace(match: re.Match[str]) -> str:
        var = match.group("var")
        sep = match.group("sep")
        return f"{var}{sep}{REDACTED}"

    return _CONFIG_ASSIGNMENT_PATTERN.sub(_replace, text)


def sanitize_for_logging(value: Any, *, key: str | None = None) -> Any:
    """Recursively sanitize objects for logs/debug traces without removing structure."""
    if value is None:
        return None

    if isinstance(value, str):
        if _is_sensitive_key(key):
            return REDACTED
        return redact_config_assignments(value)

    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        variable_name = str(value.get("variable_name", "")).upper() if "variable_name" in value else ""
        for inner_key, inner_value in value.items():
            if inner_key == "variable_value":
                sanitized[inner_key] = REDACTED
                continue
            if _is_sensitive_key(inner_key):
                sanitized[inner_key] = REDACTED
                continue
            if inner_key == "variable_name" and _is_sensitive_variable_name(str(inner_value)):
                sanitized[inner_key] = str(inner_value)
                continue
            if variable_name and _is_sensitive_variable_name(variable_name) and inner_key in {"output", "raw_message", "raw_request", "message", "reply"}:
                sanitized[inner_key] = redact_config_assignments(str(inner_value))
                continue
            sanitized[inner_key] = sanitize_for_logging(inner_value, key=str(inner_key))
        return sanitized

    if isinstance(value, (list, tuple, set)):
        return [sanitize_for_logging(item, key=key) for item in value]

    return value


def sanitize_trace(trace: dict[str, Any]) -> dict[str, Any]:
    return sanitize_for_logging(trace) if isinstance(trace, dict) else {}
