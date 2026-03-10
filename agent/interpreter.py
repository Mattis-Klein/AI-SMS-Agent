"""Natural language interpreter for SMS messages"""

import re
from typing import Optional, Tuple


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
    
    def interpret(self, message: str) -> Tuple[Optional[str], dict, float]:
        """
        Interpret natural language message.
        
        Returns:
            (tool_name, args, confidence)
            or (None, {}, 0) if no match
        """
        message_lower = message.lower().strip()
        
        # Try each pattern
        for pattern, tool_name, extractor in self.patterns:
            match = re.search(pattern, message_lower)
            if match:
                try:
                    args = extractor(match)
                    return tool_name, args, 0.9
                except:
                    pass
        
        return None, {}, 0
    
    def _extract_path(self, match) -> dict:
        """Extract path from regex match group"""
        if match.groups() and match.group(1):
            return {"path": match.group(1).strip()}
        return {}
