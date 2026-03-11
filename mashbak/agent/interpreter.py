"""Natural language interpreter for SMS messages"""

import re
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class ParsedRequest:
    intent: Optional[str]
    tool: Optional[str]
    args: dict
    confidence: float


class NaturalLanguageInterpreter:
    """Maps natural language SMS to tool calls"""
    
    def __init__(self):
        # Map patterns to (tool_name, args_extractor_fn)
        self.patterns = [
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
        if any(word in msg for word in ["inbox", "outbox", "files", "file", "folder", "directory"]):
            return "filesystem"
        if any(word in msg for word in ["system", "os", "cpu", "disk", "time", "network", "process", "uptime"]):
            return "system"
        return None

    def select_tool(self, message: str, intent: Optional[str]) -> tuple[Optional[str], Optional[re.Match], float]:
        """Stage 2: select tool based on message and intent."""
        message_lower = message.lower().strip()
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
        intent = self.classify_intent(message)
        tool_name, match, confidence = self.select_tool(message, intent)
        args = self.extract_args(tool_name, match)
        return ParsedRequest(intent=intent, tool=tool_name, args=args, confidence=confidence)

    def parse_to_dict(self, message: str) -> dict:
        """Return structured parse in tool/args format."""
        parsed = self.parse(message)
        return {
            "tool": parsed.tool,
            "args": parsed.args,
            "intent": parsed.intent,
            "confidence": parsed.confidence,
        }
    
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
