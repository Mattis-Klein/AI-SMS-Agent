"""Structured logging system"""

import json
import platform
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


class StructuredLogger:
    """Structured JSON logger for agent"""
    
    def __init__(self, log_file: Path, hostname: str = None):
        self.log_file = log_file
        self.hostname = hostname or platform.node()
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, **kwargs) -> None:
        """Log an event as JSON line"""
        event = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "hostname": self.hostname,
            **kwargs,
        }
        
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            print(f"[logger] Error writing log: {e}")
    
    def log_request(self, request_id: str, sender: str, raw_message: str, 
                   interpreted_intent: str = None, selected_tool: str = None,
                   **kwargs) -> None:
        """Log incoming request"""
        self.log(
            request_id=request_id,
            event_type="request",
            sender=sender,
            raw_message=raw_message,
            interpreted_intent=interpreted_intent,
            selected_tool=selected_tool,
            **kwargs,
        )
    
    def log_tool_execution(self, request_id: str, tool_name: str, 
                          arguments: Dict[str, Any], success: bool,
                          output: str = None, error: str = None, **kwargs) -> None:
        """Log tool execution"""
        self.log(
            request_id=request_id,
            event_type="tool_execution",
            tool_name=tool_name,
            arguments=arguments,
            success=success,
            output=output[:200] if output else None,  # Truncate long outputs
            error=error,
            **kwargs,
        )
    
    def log_response(self, request_id: str, status: str, response_message: str,
                    tool_name: str = None, **kwargs) -> None:
        """Log outgoing response"""
        self.log(
            request_id=request_id,
            event_type="response",
            status=status,
            response_message=response_message[:200] if response_message else None,
            tool_name=tool_name,
            **kwargs,
        )
    
    def log_error(self, request_id: str, error_type: str, error_message: str, **kwargs) -> None:
        """Log error"""
        self.log(
            request_id=request_id,
            event_type="error",
            error_type=error_type,
            error_message=error_message,
            **kwargs,
        )
