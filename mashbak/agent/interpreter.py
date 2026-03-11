"""Natural language interpreter for Mashbak requests."""

import re
from dataclasses import dataclass
from typing import Any, Optional, Tuple


@dataclass
class ParsedRequest:
    intent: Optional[str]
    tool: Optional[str]
    args: dict
    confidence: float
    mode: str


class NaturalLanguageInterpreter:
    """Maps natural language requests to tool calls."""

    CONFIG_VARIABLES = {
        "OPENAI_API_KEY", "OPENAI_MODEL",
        "EMAIL_PROVIDER", "EMAIL_IMAP_HOST", "EMAIL_IMAP_PORT",
        "EMAIL_USERNAME", "EMAIL_PASSWORD", "EMAIL_MAILBOX", "EMAIL_USE_SSL",
        "IMAP_SERVER", "IMAP_PORT", "EMAIL_ADDRESS",
        "SMS_OWNER_NUMBER", "SMS_ACCESS_REQUEST_NUMBERS", "SMS_ACCESS_REQUEST_RESPONSE",
        "SMS_ACCESS_REQUEST_KEYWORD", "HERSHY_NUMBER", "HERSHY_RESPONSE",
        "REJECTED_NUMBERS", "REJECTED_RESPONSE", "SMS_DENIAL_RESPONSE",
        "SMS_PHONE_NORMALIZATION_DIGITS",
        "AGENT_API_KEY", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER",
        "BRIDGE_PORT", "PUBLIC_BASE_URL", "AGENT_URL",
        "LOG_LEVEL", "DEBUG_MODE", "SESSION_CONTEXT_MAX_TURNS", "TOOL_EXECUTION_TIMEOUT",
        "MODEL_RESPONSE_MAX_TOKENS",
        "LOCAL_APP_PIN", "AGENT_WORKSPACE",
    }

    FOLLOWUP_PHRASES = {
        "so", "so?", "and now", "what else", "what do i still need", "did that fix it",
        "do you need my password", "do u have access", "do u need my password", "what now",
    }

    def __init__(self):
        self.patterns = [
            (r"(?:do i have|any|show|list|check).*(?:new|recent|latest|unread).*(?:emails?|mail|messages?)", "summarize_inbox", lambda m: {"limit": 5, "unread_only": True}),
            (r"(?:summari[sz]e|summary).*(?:emails?|mail|inbox)", "summarize_inbox", lambda m: {"limit": 5, "unread_only": True}),
            (r"(?:list|show|check).*(?:emails?|mail|messages?)", "list_recent_emails", lambda m: {"limit": 5}),
            (r"(?:search|find).*(?:emails?|mail).*(?:for|about|with)\s+(.+)", "search_emails", lambda m: {"query": m.group(1).strip(), "limit": 5}),
            (r"(?:read|open|show).*(?:thread|email).*(?:id|uid)?\s*([0-9]+)", "read_email_thread", lambda m: {"email_id": m.group(1).strip()}),
            (r"(?:check|list|show).*inbox", "dir_inbox", lambda m: {}),
            (r"(?:check|list|show).*outbox", "dir_outbox", lambda m: {}),
            (r"(?:list|show|what.*files?).*(?:in|from)\s+(.+)", "list_files", self._extract_path),
            (r"files?\s+(?:in|from)\s+(.+)", "list_files", self._extract_path),
            (r"(?:check|show|get).*(?:system|os|info)", "system_info", lambda m: {}),
            (r"system info", "system_info", lambda m: {}),
            (r"(?:check|show).*(?:cpu|processor)", "cpu_usage", lambda m: {}),
            (r"how busy is my (?:computer|pc)(?: right now)?", "cpu_usage", lambda m: {}),
            (r"(?:check|show).*(?:disk|storage|space)", "disk_space", lambda m: {}),
            (r"(?:what.*time|current.*time|tell.*time)", "current_time", lambda m: {}),
            (r"time\?", "current_time", lambda m: {}),
            (r"(?:check|show).*(?:network|connection|ip)", "network_status", lambda m: {}),
            (r"(?:list|show).*(?:processes|running|tasks)", "list_processes", lambda m: {}),
            (r"(?:check|show).*uptime", "uptime", lambda m: {}),
        ]

    def parse(self, message: str) -> ParsedRequest:
        tool_name, args, confidence = self._detect_config_assignment(message)
        if tool_name:
            return ParsedRequest(intent="config_update", tool=tool_name, args=args, confidence=confidence, mode="tool")

        intent = self._classify_intent(message)
        tool_name, match, confidence = self._select_tool(message, intent)
        args = self._extract_args(tool_name, match)
        mode = "tool" if tool_name else ("explanation" if intent == "explanation" else "conversation")
        return ParsedRequest(intent=intent, tool=tool_name, args=args, confidence=confidence, mode=mode)

    def parse_to_dict(self, message: str, context: Optional[dict[str, Any]] = None) -> dict:
        context = context or {}
        parsed = self.parse(message)

        followup_topic = self._resolve_followup_topic(message, parsed, context)
        topic = self._infer_topic(message, parsed, followup_topic)
        entities = self._extract_entities(parsed.tool, parsed.args)

        if followup_topic:
            entities["followup_topic"] = followup_topic
        if context.get("missing_config_fields"):
            entities["missing_config_fields"] = list(context.get("missing_config_fields") or [])

        return {
            "tool": parsed.tool,
            "args": parsed.args,
            "intent": parsed.intent,
            "confidence": parsed.confidence,
            "mode": parsed.mode,
            "topic": topic,
            "followup_topic": followup_topic,
            "entities": entities,
        }

    def interpret(self, message: str) -> Tuple[Optional[str], dict, float]:
        parsed = self.parse(message)
        if parsed.tool:
            return parsed.tool, parsed.args, parsed.confidence
        return None, {}, 0.0

    def _detect_config_assignment(self, message: str) -> tuple[Optional[str], dict[str, Any], float]:
        msg = message.strip()
        assign_pattern = r"^([A-Z_][A-Z0-9_]*)\s*[:=]\s*(.+)$"
        match = re.match(assign_pattern, msg, re.IGNORECASE)
        if match:
            var_name = match.group(1).upper()
            var_value = match.group(2).strip()
            if var_name in self.CONFIG_VARIABLES and var_value:
                return "set_config_variable", {"variable_name": var_name, "variable_value": var_value}, 0.96

        for var_name in self.CONFIG_VARIABLES:
            if msg.upper().startswith(var_name):
                remainder = msg[len(var_name):].strip()
                if remainder and not remainder[0].isalpha():
                    var_value = remainder.lstrip(":= ").strip()
                    if var_value:
                        return "set_config_variable", {"variable_name": var_name, "variable_value": var_value}, 0.86

        return None, {}, 0.0

    def _classify_intent(self, message: str) -> Optional[str]:
        msg = message.lower().strip()
        if any(phrase in msg for phrase in ["explain", "what does", "what is", "how does"]):
            return "explanation"
        if any(word in msg for word in ["email", "emails", "mail", "inbox message", "unread"]):
            return "email_access"
        if any(word in msg for word in ["inbox", "outbox", "files", "file", "folder", "directory"]):
            return "filesystem"
        if any(word in msg for word in ["system", "os", "cpu", "disk", "time", "network", "process", "uptime"]):
            return "system"
        return "conversation"

    def _select_tool(self, message: str, intent: Optional[str]) -> tuple[Optional[str], Optional[re.Match[str]], float]:
        msg = message.lower().strip()
        if intent == "explanation":
            return None, None, 0.35

        for pattern, tool_name, _extractor in self.patterns:
            match = re.search(pattern, msg)
            if match:
                return tool_name, match, (0.9 if intent else 0.8)
        return None, None, 0.0

    def _extract_args(self, tool_name: Optional[str], match: Optional[re.Match[str]]) -> dict[str, Any]:
        if not tool_name or not match:
            return {}

        for _pattern, known_tool, extractor in self.patterns:
            if known_tool == tool_name:
                try:
                    return extractor(match)
                except Exception:
                    return {}
        return {}

    def _resolve_followup_topic(self, message: str, parsed: ParsedRequest, context: dict[str, Any]) -> Optional[str]:
        if parsed.tool:
            return None

        msg = message.lower().strip()
        if context.get("last_topic") in {"email_setup", "email_access", "config_update"}:
            if self._is_elliptical_followup(msg) or self._is_config_followup(msg):
                return context.get("last_topic")

        if context.get("last_failure_type") == "missing_configuration":
            if self._is_elliptical_followup(msg) or self._is_config_followup(msg):
                return "email_setup"

        return None

    def _is_config_followup(self, message: str) -> bool:
        tokens = message.split()
        if message in self.FOLLOWUP_PHRASES:
            return True
        return any(
            key in message
            for key in ["password", "still need", "what else", "did that fix", "and now", "do you need", "setup", "configure"]
        ) or len(tokens) <= 2

    def _is_elliptical_followup(self, message: str) -> bool:
        if message in self.FOLLOWUP_PHRASES:
            return True
        tokens = [token for token in re.split(r"\s+", message) if token]
        if len(tokens) <= 3 and any(token in {"so", "now", "what", "else", "and", "did", "fix"} for token in tokens):
            return True
        return any(token in message for token in ["so?", "what else", "and now", "did that", "what now"])

    def _infer_topic(self, message: str, parsed: ParsedRequest, followup_topic: Optional[str]) -> Optional[str]:
        msg = message.lower().strip()
        if parsed.tool == "set_config_variable":
            return "config_update"
        if parsed.tool and "email" in parsed.tool:
            return "email_access"
        if parsed.intent == "email_access" and any(token in msg for token in ["configure", "setup", "set up", "password"]):
            return "email_setup"
        if parsed.intent == "email_access":
            return "email_access"
        if parsed.intent == "system":
            return "system"
        if parsed.intent == "filesystem":
            return "filesystem"
        if followup_topic:
            return followup_topic
        return None

    def _extract_entities(self, tool_name: Optional[str], args: dict[str, Any]) -> dict[str, Any]:
        entities: dict[str, Any] = {}
        if tool_name:
            entities["tool"] = tool_name
        for key in ("query", "path", "email_id", "limit", "variable_name"):
            if key in args:
                entities[key] = args[key]
        return entities

    def _extract_path(self, match: re.Match[str]) -> dict[str, Any]:
        if match.groups() and match.group(1):
            return {"path": match.group(1).strip()}
        return {}
