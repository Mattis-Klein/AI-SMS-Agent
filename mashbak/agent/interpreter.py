"""Natural language interpreter for Mashbak requests."""

from pathlib import Path
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
        "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL", "OPENAI_TIMEOUT_SECONDS", "OPENAI_TEMPERATURE",
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

    CONFIG_NAME_ALIASES = {
        "email": "EMAIL_USERNAME",
        "email address": "EMAIL_USERNAME",
        "email user": "EMAIL_USERNAME",
        "email username": "EMAIL_USERNAME",
        "username": "EMAIL_USERNAME",
        "email password": "EMAIL_PASSWORD",
        "imap server": "EMAIL_IMAP_HOST",
        "imap host": "EMAIL_IMAP_HOST",
        "imap port": "EMAIL_IMAP_PORT",
        "model response max tokens": "MODEL_RESPONSE_MAX_TOKENS",
        "session context max turns": "SESSION_CONTEXT_MAX_TURNS",
        "tool execution timeout": "TOOL_EXECUTION_TIMEOUT",
        "openai base url": "OPENAI_BASE_URL",
        "openai timeout": "OPENAI_TIMEOUT_SECONDS",
        "openai timeout seconds": "OPENAI_TIMEOUT_SECONDS",
        "openai temperature": "OPENAI_TEMPERATURE",
    }

    def __init__(self):
        self.patterns = [
            (r"(?:check|show|list|summari[sz]e)\s+all\s+emails\s+everywhere", "summarize_inbox", lambda m: {"limit": 5, "unread_only": True, "all_accounts": True, "all_categories": True}),
            (r"(?:check|show|list|summari[sz]e)\s+all\s+inbox\s+tabs", "summarize_inbox", lambda m: {"limit": 5, "unread_only": True, "all_categories": True}),
            (r"(?:check|show|list|summari[sz]e)\s+(primary|promotions?|social|updates?|forums?)(?:\s+(?:emails?|mail))?\s+in\s+(.+?)\s+email$", "summarize_inbox", lambda m: {"limit": 5, "unread_only": True, "category": m.group(1).strip(), "account_query": m.group(2).strip()}),
            (r"(?:check|show|list|summari[sz]e)\s+(primary|promotions?|social|updates?|forums?)(?:\s+(?:emails?|mail))?$", "summarize_inbox", lambda m: {"limit": 5, "unread_only": True, "category": m.group(1).strip()}),
            (r"(?:check|show|list|summari[sz]e)\s+(?:my\s+)?emails?$", "summarize_inbox", lambda m: {"limit": 5, "unread_only": True}),
            (r"(?:check|show|list|summari[sz]e)\s+(.+?)\s+email", "summarize_inbox", lambda m: {"limit": 5, "unread_only": True, "account_query": m.group(1).strip()}),
            (r"(?:do i have|any|show|list|check).*(?:new|recent|latest|unread).*(?:emails?|mail|messages?)", "summarize_inbox", lambda m: {"limit": 5, "unread_only": True}),
            (r"(?:summari[sz]e|summary).*(?:emails?|mail|inbox)", "summarize_inbox", lambda m: {"limit": 5, "unread_only": True}),
            (r"(?:list|show|check).*(?:emails?|mail|messages?)", "list_recent_emails", lambda m: {"limit": 5}),
            (r"(?:search|find).*(?:emails?|mail).*(?:for|about|with)\s+(.+)", "search_emails", lambda m: {"query": m.group(1).strip(), "limit": 5}),
            (r"(?:read|open|show).*(?:thread|email).*(?:id|uid)?\s*([0-9]+)", "read_email_thread", lambda m: {"email_id": m.group(1).strip()}),
            (r"(?:check|list|show).*inbox", "dir_inbox", lambda m: {}),
            (r"(?:check|list|show).*outbox", "dir_outbox", lambda m: {}),
            (r"(?:list|show|what.*files?).*(?:in|from)\s+(.+)", "list_files", self._extract_path),
            (r"files?\s+(?:in|from)\s+(.+)", "list_files", self._extract_path),
            (r"(?:create|make)\s+(?:a\s+)?(?:folder|directory)\s+(?:on\s+my\s+desktop|in\s+my\s+desktop|on\s+desktop)\s+(?:called|named)\s+(.+)", "create_folder", self._extract_desktop_named_target),
            (r"(?:create|make)\s+(?:a\s+)?(?:new\s+)?file\s+(?:on\s+my\s+desktop|on\s+the\s+desktop|in\s+my\s+desktop|on\s+desktop)\s+(?:called|named)\s+(.+)", "create_file", self._extract_desktop_named_file_target),
            (r"(?:create|make)\s+(?:a\s+)?(?:folder|directory)\s+(?:called|named)\s+(.+)", "create_folder", self._extract_named_target),
            (r"(?:create|make)\s+(?:a\s+)?(?:folder|directory)\s+(?:in|at|under)\s+(.+)", "create_folder", self._extract_path),
            (r"(?:create|make)\s+(?:a\s+)?file\s+(?:named|called)\s+(.+?)\s+(?:in|at|under)\s+(.+)", "create_file", self._extract_named_file_target),
            (r"(?:create|make)\s+(?:a\s+)?file\s+(?:named|called)\s+(.+)", "create_file", self._extract_named_file_default_path),
            (r"(?:create|make)\s+(?:a\s+)?file\s+(?:in|at|under)\s+(.+)", "create_file", self._extract_path),
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
            (r"(?:delete|remove|erase)\s+(?:the\s+)?file\s+(?:called|named)\s+(.+)", "delete_file", lambda m: {"path": m.group(1).strip()}),
            (r"(?:delete|remove|erase)\s+(?:the\s+file\s+at|file)\s+(.+)", "delete_file", lambda m: {"path": m.group(1).strip()}),
            (r"(?:edit|update|rewrite)\s+file\s+(.+?)\s+(?:with|to)\s+(.+)", "edit_file", lambda m: {"path": m.group(1).strip(), "content": m.group(2).strip(), "mode": "replace"}),
            (r"(?:append|add)\s+to\s+file\s+(.+?)\s*:\s*(.+)", "edit_file", lambda m: {"path": m.group(1).strip(), "content": m.group(2).strip(), "mode": "append"}),
            (r"(?:copy)\s+file\s+(.+?)\s+(?:to|into)\s+(.+)", "copy_file", lambda m: {"source_path": m.group(1).strip(), "destination_path": m.group(2).strip()}),
            (r"(?:move)\s+file\s+(.+?)\s+(?:to|into)\s+(.+)", "move_file", lambda m: {"source_path": m.group(1).strip(), "destination_path": m.group(2).strip()}),
            (r"(?:search|find)\s+files\s+(?:in|under)\s+(.+?)\s+(?:for|matching)\s+(.+)", "search_files", lambda m: {"root_path": m.group(1).strip(), "pattern": m.group(2).strip()}),
            (r"(?:launch|start|open app)\s+(.+)", "launch_program", lambda m: {"program": m.group(1).strip()}),
            (r"(?:open url|open website|open link)\s+(.+)", "open_target", lambda m: {"target": m.group(1).strip()}),
            (r"(?:open folder|open path)\s+(.+)", "open_target", lambda m: {"target": m.group(1).strip()}),
            (r"(?:run command|run project command)\s+(.+?)\s+(?:in|under)\s+(.+)", "run_project_command", lambda m: {"command": m.group(1).strip(), "working_directory": m.group(2).strip()}),
            (r"(?:take|capture).*(?:screenshot)", "capture_screenshot", lambda m: {}),
            (r"(?:send email)\s+to\s+(.+?)\s+subject\s+(.+?)\s+body\s+(.+)", "send_email", lambda m: {"to": m.group(1).strip(), "subject": m.group(2).strip(), "body": m.group(3).strip()}),
            (r"(?:draft email|draft reply)\s+to\s+(.+?)\s+subject\s+(.+?)\s+body\s+(.+)", "draft_email_reply", lambda m: {"to": m.group(1).strip(), "subject": m.group(2).strip(), "body": m.group(3).strip()}),
            (r"(?:create|generate|make).*(?:html|homepage|website).*(?:for|about)\s+(.+)", "generate_homepage", lambda m: {"project_path": "workspace/generated-site", "title": "Generated Homepage", "prompt": m.group(1).strip()}),
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
        """
        Parse a user message into a structured intent dict, using session context
        to resolve references from recent turns and task state.

        Context fields consumed:
          recent_turns         — rolling window of prior user+assistant turns
          last_topic           — last conversation topic
          last_failure_type    — last error category
          last_task / last_result / last_args / last_created_path — task state
          pending_task / missing_parameters   — pending task state
          missing_config_fields               — outstanding config requirements
        """
        context = context or {}

        unresolved_file_ref = self._detect_unresolved_file_reference(message, context)
        if unresolved_file_ref:
            return unresolved_file_ref

        unresolved_folder_ref = self._detect_unresolved_folder_reference(message, context)
        if unresolved_folder_ref:
            return unresolved_folder_ref

        # --- 1a. Try contextual delete resolution before reference-query parsing ---
        del_tool, del_args, del_confidence = self._detect_contextual_delete_action(message, context)
        if del_tool:
            del_entities = self._extract_entities(del_tool, del_args)
            return {
                "tool": del_tool,
                "args": del_args,
                "intent": "filesystem",
                "confidence": del_confidence,
                "mode": "tool",
                "topic": "filesystem",
                "followup_topic": None,
                "entities": del_entities,
            }

        # --- 1. Try context-reference resolution first (elliptical queries) ---
        ref_result = self._resolve_context_reference(message, context)
        if ref_result is not None:
            return ref_result

        # --- 1b. Try context-aware filesystem follow-ups before generic parse ---
        fs_tool, fs_args, fs_confidence = self._detect_contextual_filesystem_action(message, context)
        if fs_tool:
            fs_entities = self._extract_entities(fs_tool, fs_args)
            return {
                "tool": fs_tool,
                "args": fs_args,
                "intent": "filesystem",
                "confidence": fs_confidence,
                "mode": "tool",
                "topic": "filesystem",
                "followup_topic": None,
                "entities": fs_entities,
            }

        # --- 2. Standard parse ---
        parsed = self.parse(message)

        followup_topic = self._resolve_followup_topic(message, parsed, context)

        if not parsed.tool:
            followup_tool, followup_args, followup_confidence = self._detect_followup_config_assignment(message, followup_topic)
            if followup_tool:
                parsed = ParsedRequest(
                    intent="config_update",
                    tool=followup_tool,
                    args=followup_args,
                    confidence=followup_confidence,
                    mode="tool",
                )
                followup_topic = None

        topic = self._infer_topic(message, parsed, followup_topic)
        entities = self._extract_entities(parsed.tool, parsed.args)

        if followup_topic:
            entities["followup_topic"] = followup_topic
        if context.get("missing_config_fields"):
            entities["missing_config_fields"] = list(context.get("missing_config_fields") or [])
        if context.get("missing_parameters"):
            entities["missing_parameters"] = list(context.get("missing_parameters") or [])
        entities["action_requested"] = self._is_action_request(message, parsed.intent)

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

    def _detect_contextual_filesystem_action(
        self,
        message: str,
        context: dict[str, Any],
    ) -> tuple[Optional[str], dict[str, Any], float]:
        msg = message.strip().lower()
        target_dir = self._resolve_last_real_folder_path(context)
        if not target_dir:
            return None, {}, 0.0

        if "50 states" in msg and self._contains_folder_reference_phrase(msg):
            return "create_file", {
                "parent_path": str(target_dir),
                "name": "states.txt",
                "content": self._all_states_text(),
            }, 0.93

        named_file_match = re.search(
            r"(?:create|make|add|put)\s+(?:a\s+)?file\s+(?:named|called)\s+(.+?)\s+(?:in|inside|under|at)\s+(?:that\s+folder|the\s+folder|it|inside\s+it|inside\s+that\s+folder|the\s+folder\s+we\s+just\s+made)",
            msg,
        )
        if named_file_match:
            file_name = self._sanitize_filename(named_file_match.group(1))
            if file_name:
                return "create_file", {
                    "parent_path": str(target_dir),
                    "name": file_name,
                }, 0.92

        if any(token in msg for token in [
            "put a file in it",
            "put file in it",
            "add a file in it",
            "put a file in that folder",
            "add a file in that folder",
            "add a file inside that folder",
            "create a file in the folder we just made",
            "create a file in that folder",
            "create a file inside that folder",
            "add a file inside it",
        ]):
            return "create_file", {
                "parent_path": str(target_dir),
                "name": "note.txt",
            }, 0.9

        if "add states to that folder" in msg or "add states in that folder" in msg:
            return "create_file", {
                "parent_path": str(target_dir),
                "name": "states.txt",
                "content": self._all_states_text(),
            }, 0.92

        return None, {}, 0.0

    def _detect_contextual_delete_action(
        self,
        message: str,
        context: dict[str, Any],
    ) -> tuple[Optional[str], dict[str, Any], float]:
        """Resolve 'delete that file' / 'delete it' against the last created file in context."""
        msg = message.strip().lower()

        delete_triggers = [
            "delete that file",
            "delete it",
            "delete that",
            "remove that file",
            "remove it",
            "erase that file",
            "delete the file you just created",
            "delete the file you made",
            "delete the file you created",
            "get rid of it",
            "get rid of that file",
        ]
        if not any(t in msg for t in delete_triggers):
            # Also check regex for "delete/remove/erase" + pronoun/that
            if not re.search(r"(?:delete|remove|erase)\s+(?:that|it|the\s+(?:file|one))\b", msg):
                return None, {}, 0.0

        # Only resolve if there is a verified last_created_path from a successful action.
        last_path = self._resolve_last_real_file_path(context)
        if not last_path:
            return None, {}, 0.0

        return "delete_file", {"path": str(last_path)}, 0.93

    def _resolve_last_real_file_path(self, context: dict[str, Any]) -> Optional[Path]:
        """Return the last successfully created FILE path from context (not a folder)."""
        if not isinstance(context, dict):
            return None

        if context.get("last_task") == "create_file" and context.get("last_result") == "success":
            last_path = str(context.get("last_created_path") or "").strip()
            if last_path:
                p = Path(last_path)
                if not p.is_dir():
                    return p

        for turn in reversed(context.get("recent_turns") or []):
            if turn.get("tool") == "create_file" and bool(turn.get("success")):
                created_path = str(turn.get("created_path") or "").strip()
                if created_path:
                    p = Path(created_path)
                    if not p.is_dir():
                        return p

        return None

    # ------------------------------------------------------------------
    # Context-reference resolution
    #
    # Detects elliptical or pronoun-heavy follow-ups and resolves them
    # against the session's recent turns and task state without requiring
    # the user to repeat themselves.
    # ------------------------------------------------------------------

    # Patterns that signal the user is referring to something already in context.
    _REF_LOCATION_PATTERNS = [
        r"\bwhere(?:\s+was|\s+is|\s+did)?\s+it\b",
        r"\bwhere(?:\s+was|\s+is)?\s+(?:that|the\s+\w+)\s+(?:added|created|saved|put|written)\b",
        r"\bdid\s+(?:you|it)\s+(?:create|save|add|write|put)\s+it\b",
        r"\bis\s+it\s+(?:there|saved|created|done|added)\b",
    ]
    _REF_THAT_FILE_PATTERNS = [
        r"\bthat\s+file\b",
        r"\bthe\s+(?:file|folder|path)\s+(?:we\s+(?:are|were)\s+talking\s+about|you\s+mentioned|i\s+mentioned)\b",
        r"\bthe\s+one\s+(?:we\s+(?:are|were|just)\s+talking\s+about|you\s+(?:created|made|mentioned))\b",
        r"\bit\s+(?:was|is)\s+(?:that\s+file|the\s+file)\b",
    ]
    _REF_WHAT_ELSE_PATTERNS = [
        r"\bwhat\s+(?:else\s+)?do\s+you\s+need\b",
        r"\bwhat\s+(?:else\s+)?(?:is\s+)?(?:still\s+)?(?:missing|needed|required)\b",
        r"\bwhat\s+(?:other\s+)?(?:info(?:rmation)?|details?)\s+(?:do\s+you\s+need|are\s+(?:you\s+)?missing)\b",
        r"\bdo\s+you\s+(?:still\s+)?need\s+(?:anything|my|more)\b",
    ]
    _REF_PASSWORD_PATTERNS = [
        r"\bso\s+do\s+you\s+need\s+my\s+password\b",
        r"\bdo\s+(?:you|u)\s+need\s+(?:my\s+)?password\b",
        r"\bdo\s+(?:you|u)\s+(?:have\s+)?(?:(?:my|the)\s+)?password\b",
    ]

    def _resolve_context_reference(
        self,
        message: str,
        context: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """
        Check if the message is an elliptical reference to prior conversation.

        Returns a parse_to_dict-shaped dict when the reference is resolved, or
        None when the message should go through normal parsing.
        """
        msg = message.strip()
        lower = msg.lower()

        # --- "where was it added?" / "did you create it?" ---
        if any(re.search(p, lower) for p in self._REF_LOCATION_PATTERNS):
            return self._build_reference_response(
                message=message,
                context=context,
                reference_target="location",
                intent="reference_query",
            )

        # --- "that file" / "the one we are talking about" ---
        if any(re.search(p, lower) for p in self._REF_THAT_FILE_PATTERNS):
            return self._build_reference_response(
                message=message,
                context=context,
                reference_target="file_subject",
                intent="reference_query",
            )

        # --- "what else do you need?" / "what's still missing?" ---
        if any(re.search(p, lower) for p in self._REF_WHAT_ELSE_PATTERNS):
            return self._build_reference_response(
                message=message,
                context=context,
                reference_target="missing_requirements",
                intent="status_query",
            )

        # --- "so do you need my password?" ---
        if any(re.search(p, lower) for p in self._REF_PASSWORD_PATTERNS):
            return self._build_reference_response(
                message=message,
                context=context,
                reference_target="password_prompt",
                intent="config_followup",
            )

        return None

    def _build_reference_response(
        self,
        message: str,
        context: dict[str, Any],
        reference_target: str,
        intent: str,
    ) -> dict[str, Any]:
        """
        Construct the parse_to_dict result for a resolved context reference.
        The entities dict carries the resolved values so assistant_core can
        build an accurate reply without executing a new tool.
        """
        entities: dict[str, Any] = {
            "reference_target": reference_target,
        }

        # Resolve the most relevant path from session task state or recent turns.
        created_path = context.get("last_created_path") or self._find_path_in_recent_turns(context)
        if created_path:
            entities["resolved_path"] = created_path

        # Carry forward what the last action was.
        last_task = context.get("last_task")
        last_result = context.get("last_result")
        if last_task:
            entities["last_task"] = last_task
            entities["last_result"] = last_result

        # What the system still requires from the user.
        missing_params = list(context.get("missing_parameters") or [])
        missing_config = list(context.get("missing_config_fields") or [])
        if missing_params:
            entities["missing_parameters"] = missing_params
        if missing_config:
            entities["missing_config_fields"] = missing_config

        # Derive topic: when there is a missing_configuration error context,
        # promote to "email_setup" regardless of the raw last_topic so that
        # downstream reply builders apply the right guidance.
        last_topic = context.get("last_topic")
        if context.get("last_failure_type") == "missing_configuration" and missing_config:
            last_topic = "email_setup"

        return {
            "tool": None,
            "args": {},
            "intent": intent,
            "confidence": 0.92,
            "mode": "conversation",
            "topic": last_topic,
            "followup_topic": last_topic,
            "entities": entities,
        }

    def _find_path_in_recent_turns(self, context: dict[str, Any]) -> Optional[str]:
        """Walk recent turns in reverse to find the most recent file/folder path."""
        for turn in reversed(context.get("recent_turns") or []):
            if turn.get("created_path"):
                return turn["created_path"]
            # Also check args of file/folder tools.
            tool = turn.get("tool") or ""
            if "file" in tool or "dir" in tool or "inbox" in tool or "outbox" in tool:
                # The turn doesn't store raw args but last_args does via context.
                pass
        # Try last_args from context.
        last_args = context.get("last_args") or {}
        return last_args.get("path") or last_args.get("file_path")

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

        natural_pattern = r"^(?:set|update|change)\s+([A-Za-z_][A-Za-z0-9_\-\s]*)\s+(?:to|=|:)\s*(.+)$"
        natural_match = re.match(natural_pattern, msg, re.IGNORECASE)
        if natural_match:
            variable_candidate = natural_match.group(1).strip()
            variable_value = natural_match.group(2).strip()
            variable_name = self._resolve_config_variable_name(variable_candidate)
            if variable_name and variable_value:
                return "set_config_variable", {"variable_name": variable_name, "variable_value": variable_value}, 0.93

        return None, {}, 0.0

    def _detect_followup_config_assignment(
        self,
        message: str,
        followup_topic: Optional[str],
    ) -> tuple[Optional[str], dict[str, Any], float]:
        if followup_topic not in {"email_setup", "email_access", "config_update"}:
            return None, {}, 0.0

        msg = message.strip()
        lower = msg.lower()

        password_match = re.match(r"^(?:and\s+)?password\s*(?:is|=|:|to)\s+(.+)$", lower, re.IGNORECASE)
        if password_match:
            return "set_config_variable", {
                "variable_name": "EMAIL_PASSWORD",
                "variable_value": msg[password_match.start(1):].strip(),
            }, 0.9

        username_match = re.match(r"^(?:and\s+)?(?:email\s+)?(?:username|user|address|email)\s*(?:is|=|:|to)\s+(.+)$", lower, re.IGNORECASE)
        if username_match:
            return "set_config_variable", {
                "variable_name": "EMAIL_USERNAME",
                "variable_value": msg[username_match.start(1):].strip(),
            }, 0.88

        return None, {}, 0.0

    def _resolve_config_variable_name(self, candidate: str) -> Optional[str]:
        normalized_key = re.sub(r"\s+", " ", candidate.strip().lower())
        if normalized_key in self.CONFIG_NAME_ALIASES:
            return self.CONFIG_NAME_ALIASES[normalized_key]

        normalized_var = re.sub(r"[^A-Za-z0-9]+", "_", candidate.strip()).upper().strip("_")
        if normalized_var in self.CONFIG_VARIABLES:
            return normalized_var

        return None

    def _classify_intent(self, message: str) -> Optional[str]:
        msg = message.lower().strip()
        if any(phrase in msg for phrase in ["explain", "what does", "what is", "how does"]):
            return "explanation"
        if any(word in msg for word in ["email", "emails", "mail", "inbox message", "unread", "primary", "promotions", "social", "updates", "forums"]):
            return "email_access"
        if any(word in msg for word in ["inbox", "outbox", "files", "file", "folder", "directory"]):
            return "filesystem"
        if any(word in msg for word in ["delete", "remove", "erase"]):
            return "filesystem"
        if any(word in msg for word in ["system", "os", "cpu", "disk", "time", "network", "process", "uptime"]):
            return "system"
        return "conversation"

    def _select_tool(self, message: str, intent: Optional[str]) -> tuple[Optional[str], Optional[re.Match[str]], float]:
        raw = message.strip()
        msg = raw.lower()
        if intent == "explanation":
            return None, None, 0.35

        action_verb_present = any(token in msg for token in ["create", "make", "add", "save", "delete", "move", "put", "write"])

        for pattern, tool_name, _extractor in self.patterns:
            match = re.search(pattern, raw, flags=re.IGNORECASE)
            if match:
                # Action-verb requests should not be misclassified as read-only list_files.
                if tool_name in {"list_files", "dir_inbox", "dir_outbox"} and action_verb_present:
                    continue
                return tool_name, match, (0.9 if intent else 0.8)
        return None, None, 0.0

    def _extract_args(self, tool_name: Optional[str], match: Optional[re.Match[str]]) -> dict[str, Any]:
        if not tool_name or not match:
            return {}

        matched_pattern = getattr(match.re, "pattern", None)
        for pattern, known_tool, extractor in self.patterns:
            if known_tool == tool_name and pattern == matched_pattern:
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
        ) or any(
            key in message
            for key in ["username", "user", "email", "address", "imap", "server", "port"]
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
        for key in (
            "query",
            "path",
            "parent_path",
            "name",
            "email_id",
            "limit",
            "variable_name",
            "path_reference_unresolved",
            "account_id",
            "account_query",
            "category",
            "all_accounts",
            "all_categories",
        ):
            if key in args:
                entities[key] = args[key]
        return entities

    def _extract_path(self, match: re.Match[str]) -> dict[str, Any]:
        if match.groups() and match.group(1):
            return {"path": match.group(1).strip()}
        return {}

    def _extract_desktop_named_target(self, match: re.Match[str]) -> dict[str, Any]:
        folder_name = self._sanitize_filename(match.group(1)) if match.groups() else ""
        return {"path": str(Path.home() / "Desktop" / folder_name)} if folder_name else {}

    def _extract_desktop_named_file_target(self, match: re.Match[str]) -> dict[str, Any]:
        file_name = self._sanitize_filename(match.group(1)) if match.groups() else ""
        return {"path": str(Path.home() / "Desktop" / file_name)} if file_name else {}

    def _extract_named_target(self, match: re.Match[str]) -> dict[str, Any]:
        target_name = self._sanitize_filename(match.group(1)) if match.groups() else ""
        if not target_name:
            return {}
        return {"path": target_name}

    def _extract_named_file_target(self, match: re.Match[str]) -> dict[str, Any]:
        if not match.groups() or len(match.groups()) < 2:
            return {}
        file_name = self._sanitize_filename(match.group(1))
        parent_path = match.group(2).strip()
        if not file_name or not parent_path:
            return {}
        return {"parent_path": parent_path, "name": file_name}

    def _extract_named_file_default_path(self, match: re.Match[str]) -> dict[str, Any]:
        file_name = self._sanitize_filename(match.group(1)) if match.groups() else ""
        if not file_name:
            return {}
        return {"path": file_name}

    def _sanitize_filename(self, value: str) -> str:
        cleaned = value.strip().strip("\"'` ")
        cleaned = re.sub(r"[<>:\\|?*]", "_", cleaned)
        return cleaned[:120]

    def _is_action_request(self, message: str, intent: Optional[str]) -> bool:
        if intent != "filesystem":
            return False
        msg = message.lower()
        return any(token in msg for token in ["create", "make", "add", "save", "delete", "remove", "erase", "move", "put", "write"])

    def _contains_folder_reference_phrase(self, message: str) -> bool:
        lowered = str(message or "").lower()
        return any(token in lowered for token in [
            "that folder",
            "the folder",
            "in it",
            "inside it",
            "inside that folder",
            "the folder we just made",
        ])

    def _resolve_last_real_folder_path(self, context: dict[str, Any]) -> Optional[Path]:
        if not isinstance(context, dict):
            return None

        if context.get("last_task") == "create_folder" and context.get("last_result") == "success":
            last_path = str(context.get("last_created_path") or "").strip()
            if last_path:
                return Path(last_path)

        for turn in reversed(context.get("recent_turns") or []):
            if turn.get("tool") == "create_folder" and bool(turn.get("success")):
                created_path = str(turn.get("created_path") or "").strip()
                if created_path:
                    return Path(created_path)

        return None

    def _detect_unresolved_folder_reference(self, message: str, context: dict[str, Any]) -> Optional[dict[str, Any]]:
        msg = str(message or "").strip().lower()
        if not self._contains_folder_reference_phrase(msg):
            return None

        if not any(token in msg for token in ["create", "make", "add", "put", "write", "save"]):
            return None

        if self._resolve_last_real_folder_path(context):
            return None

        entities = {
            "path_reference_unresolved": True,
            "reference_target": "folder_reference",
            "action_requested": True,
            "missing_parameters": ["path"],
        }
        return {
            "tool": None,
            "args": {},
            "intent": "filesystem",
            "confidence": 0.89,
            "mode": "conversation",
            "topic": "filesystem",
            "followup_topic": "filesystem",
            "entities": entities,
        }

    def _detect_unresolved_file_reference(self, message: str, context: dict[str, Any]) -> Optional[dict[str, Any]]:
        msg = str(message or "").strip().lower()
        if not re.search(r"(?:delete|remove|erase)\s+(?:that|it|the\s+(?:file|one))\b", msg):
            return None

        # If we can resolve a prior successful file, this is not unresolved.
        if self._resolve_last_real_file_path(context):
            return None

        entities = {
            "path_reference_unresolved": True,
            "reference_target": "file_reference",
            "action_requested": True,
            "missing_parameters": ["path"],
        }
        return {
            "tool": None,
            "args": {},
            "intent": "filesystem",
            "confidence": 0.9,
            "mode": "conversation",
            "topic": "filesystem",
            "followup_topic": "filesystem",
            "entities": entities,
        }

    def _all_states_text(self) -> str:
        states = [
            "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware",
            "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky",
            "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi",
            "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey", "New Mexico",
            "New York", "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania",
            "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont",
            "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
        ]
        return "\n".join(states)
