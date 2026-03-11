"""Natural language interpreter for SMS messages"""

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
    """Maps natural language SMS to tool calls"""
    
    # Known configuration variables for detection
    CONFIG_VARIABLES = {
        "OPENAI_API_KEY", "OPENAI_MODEL",
        "EMAIL_PROVIDER", "EMAIL_IMAP_HOST", "EMAIL_IMAP_PORT",
        "EMAIL_USERNAME", "EMAIL_PASSWORD", "EMAIL_MAILBOX", "EMAIL_USE_SSL",
        "IMAP_SERVER", "IMAP_PORT", "EMAIL_ADDRESS",
        "AGENT_API_KEY", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER",
        "LOCAL_APP_PIN", "AGENT_WORKSPACE",
    }
    
    def __init__(self):
        # Map patterns to (tool_name, args_extractor_fn)
        self.patterns = [
            # Email
            (r"(?:do i have|any|show|list|check).*(?:new|recent|latest|unread).*(?:emails?|mail|messages?)", "summarize_inbox", lambda m: {"limit": 5, "unread_only": True}),
            (r"(?:summari[sz]e|summary).*(?:emails?|mail|inbox)", "summarize_inbox", lambda m: {"limit": 5, "unread_only": True}),
            (r"(?:list|show|check).*(?:emails?|mail|messages?)", "list_recent_emails", lambda m: {"limit": 5}),
            (r"(?:search|find).*(?:emails?|mail).*(?:for|about|with)\s+(.+)", "search_emails", lambda m: {"query": m.group(1).strip(), "limit": 5}),
            (r"(?:read|open|show).*(?:thread|email).*(?:id|uid)?\s*([0-9]+)", "read_email_thread", lambda m: {"email_id": m.group(1).strip()}),

            # Inbox/outbox commands
            (r"(?:check|list|show).*inbox", "dir_inbox", lambda m: {}),
            (r"(?:check|list|show).*outbox", "dir_outbox", lambda m: {}),
            
            # File listing
            (r"(?:list|show|what.*files?).*(?:in|from)\s+(.+)", "list_files", self._extract_path),
            (r"files?\s+(?:in|from)\s+(.+)", "list_files", self._extract_path),
            
            # System info
            (r"(?:check|show|get).*(?:system|os|info)", "system_info", lambda m: {}),
            (r"system info", "system_info", lambda m: {}),
            
            # CPU
            (r"(?:check|show).*(?:cpu|processor)", "cpu_usage", lambda m: {}),
            (r"how busy is my (?:computer|pc)(?: right now)?", "cpu_usage", lambda m: {}),
            
            # Disk space
            (r"(?:check|show).*(?:disk|storage|space)", "disk_space", lambda m: {}),
            
            # Time
            (r"(?:what.*time|current.*time|tell.*time)", "current_time", lambda m: {}),
            (r"time\?", "current_time", lambda m: {}),
            
            # Network
            (r"(?:check|show).*(?:network|connection|ip)", "network_status", lambda m: {}),
            
            # Processes
            (r"(?:list|show).*(?:processes|running|tasks)", "list_processes", lambda m: {}),
            
            # Uptime
            (r"(?:check|show).*uptime", "uptime", lambda m: {}),
        ]

    def classify_intent(self, message: str) -> Optional[str]:
        """Stage 1: classify intent group from natural language."""
        msg = message.lower().strip()
        if any(phrase in msg for phrase in ["explain", "what does", "what is", "how does"]):
            return "explanation"
        if any(word in msg for word in ["email", "emails", "mail", "inbox message", "unread"]):
            return "email"
        if any(word in msg for word in ["inbox", "outbox", "files", "file", "folder", "directory"]):
            return "filesystem"
        if any(word in msg for word in ["system", "os", "cpu", "disk", "time", "network", "process", "uptime"]):
            return "system"
        return "conversation"

    def select_tool(self, message: str, intent: Optional[str]) -> tuple[Optional[str], Optional[re.Match], float]:
        """Stage 2: select tool based on message and intent."""
        message_lower = message.lower().strip()
        if intent == "explanation":
            return None, None, 0.35
        for pattern, tool_name, _extractor in self.patterns:
            match = re.search(pattern, message_lower)
            if match:
                confidence = 0.9 if intent else 0.8
                return tool_name, match, confidence
        return None, None, 0.0

    def extract_args(self, tool_name: Optional[str], match: Optional[re.Match]) -> dict:
        """Stage 3: extract arguments for selected tool."""
        if not tool_name or not match:
            return {}

        for pattern, known_tool, extractor in self.patterns:
            if known_tool == tool_name:
                try:
                    return extractor(match)
                except Exception:
                    return {}
        return {}

    def parse(self, message: str) -> ParsedRequest:
        """Two-stage parse result used by dispatcher and future model upgrades."""
        
        # Check for configuration variable assignment first
        config_result = self._detect_config_variable(message)
        if config_result[0]:  # Found config variable
            return ParsedRequest(
                intent="configuration",
                tool=config_result[0],
                args=config_result[1],
                confidence=config_result[2],
                mode="tool"
            )
        
        intent = self.classify_intent(message)
        tool_name, match, confidence = self.select_tool(message, intent)
        args = self.extract_args(tool_name, match)
        mode = "tool" if tool_name else ("explanation" if intent == "explanation" else "conversation")
        return ParsedRequest(intent=intent, tool=tool_name, args=args, confidence=confidence, mode=mode)

    def parse_to_dict(self, message: str, context: Optional[dict[str, Any]] = None) -> dict:
        """Return structured parse in tool/args format."""
        parsed = self.parse(message)
        context = context or {}
        followup_topic = self._infer_followup_topic(message, parsed, context)
        entities = self._extract_entities(parsed.tool, parsed.args)
        topic = self._infer_topic(parsed.intent, parsed.tool, parsed.args)
        if followup_topic and not topic:
            topic = followup_topic
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

    def _detect_config_variable(self, message: str) -> tuple[Optional[str], dict, float]:
        """
        Detect if message contains a configuration variable assignment.
        
        Recognizes patterns:
        - VARIABLE_NAME = value
        - VARIABLE_NAME: value
        - VARIABLE_NAME value (if variable name matches known config)
        
        Returns (tool_name, args, confidence) or (None, {}, 0)
        """
        msg = message.strip()
        
        # Pattern 1: VARIABLE = value or VARIABLE: value
        assign_pattern = r"^([A-Z_][A-Z0-9_]*)\s*[:=]\s*(.+)$"
        match = re.match(assign_pattern, msg, re.IGNORECASE)
        if match:
            var_name = match.group(1).upper()
            var_value = match.group(2).strip()
            
            if var_name in self.CONFIG_VARIABLES and var_value:
                return (
                    "set_config_variable",
                    {"variable_name": var_name, "variable_value": var_value},
                    0.95
                )
        
        # Pattern 2: Known variable at start of message followed by space and value
        # (only if it's clearly a config context)
        for var_name in self.CONFIG_VARIABLES:
            if msg.upper().startswith(var_name):
                remainder = msg[len(var_name):].strip()
                # Check if looks like value assignment
                if remainder and not remainder[0].isalpha():  # Not a continuation of variable name
                    var_value = remainder.lstrip(":= ").strip()
                    if var_value:
                        return (
                            "set_config_variable",
                            {"variable_name": var_name, "variable_value": var_value},
                            0.85
                        )
        
        return None, {}, 0.0

    def parse_to_dict(self, message: str, context: Optional[dict[str, Any]] = None) -> dict:
        """Return structured parse in tool/args format."""
        parsed = self.parse(message)
        context = context or {}
        followup_topic = self._infer_followup_topic(message, parsed, context)
        entities = self._extract_entities(parsed.tool, parsed.args)
        topic = self._infer_topic(parsed.intent, parsed.tool, parsed.args)
        if followup_topic and not topic:
            topic = followup_topic
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

    def _infer_followup_topic(self, message: str, parsed: ParsedRequest, context: dict[str, Any]) -> Optional[str]:
        msg = message.lower().strip()
        if parsed.tool:
            return None
        if not any(token in msg for token in ["it", "that", "this", "configure", "set up", "setup"]):
            return None
        return context.get("last_topic")

    def _infer_topic(self, intent: Optional[str], tool_name: Optional[str], args: dict[str, Any]) -> Optional[str]:
        if tool_name == "set_config_variable":
            return "configuration"
        if tool_name and "email" in tool_name:
            return "email"
        if intent == "email":
            return "email"
        if intent == "configuration":
            return "configuration"
        if "path" in args:
            return "filesystem"
        if intent == "system":
            return "system"
        return None

    def _extract_entities(self, tool_name: Optional[str], args: dict[str, Any]) -> dict[str, Any]:
        entities: dict[str, Any] = {}
        if tool_name:
            entities["tool"] = tool_name
        for key in ("query", "path", "email_id", "limit"):
            if key in args:
                entities[key] = args[key]
        return entities
    
    def interpret(self, message: str) -> Tuple[Optional[str], dict, float]:
        """
        Interpret natural language message.
        
        Returns:
            (tool_name, args, confidence)
            or (None, {}, 0) if no match
        """
        parsed = self.parse(message)
        if parsed.tool:
            return parsed.tool, parsed.args, parsed.confidence
        return None, {}, 0
    
    def _extract_path(self, match) -> dict:
        """Extract path from regex match group"""
        if match.groups() and match.group(1):
            return {"path": match.group(1).strip()}
        return {}
