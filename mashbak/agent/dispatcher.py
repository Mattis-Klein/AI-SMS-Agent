"""Dispatcher for routing SMS requests to appropriate tools"""

import asyncio
import time
import uuid
from typing import Optional, Dict, Any

try:
    from .tools import ToolRegistry
    from .interpreter import NaturalLanguageInterpreter
    from .logger import StructuredLogger
except ImportError:
    from tools import ToolRegistry
    from interpreter import NaturalLanguageInterpreter
    from logger import StructuredLogger


class RequestContext:
    """Context object for a single request"""
    
    def __init__(
        self,
        sender: str,
        source: str,
        raw_message: str,
        workspace: Any,
        allowed_directories: list,
        allowed_tools: Optional[list] = None,
        tool_timeout_seconds: float = 10.0,
    ):
        self.request_id = str(uuid.uuid4())[:8]
        self.sender = sender
        self.source = source
        self.raw_message = raw_message
        self.workspace = workspace
        self.allowed_directories = allowed_directories
        self.allowed_tools = allowed_tools
        self.tool_timeout_seconds = float(tool_timeout_seconds)
        self.interpreted_tool = None
        self.interpreted_args = None
        self.confidence = 0.0


class Dispatcher:
    """Routes SMS messages to appropriate tools"""
    
    def __init__(self, registry: ToolRegistry, interpreter: NaturalLanguageInterpreter, 
                 logger: StructuredLogger):
        self.registry = registry
        self.interpreter = interpreter
        self.logger = logger
    
    async def dispatch(self, context: RequestContext) -> Dict[str, Any]:
        """
        Main dispatch logic.
        
        Returns:
            {
                "success": bool,
                "tool_name": Optional[str],
                "output": Optional[str],
                "error": Optional[str],
                "request_id": str,
                "trace": dict,
            }
        """
        trace = {
            "raw_request": context.raw_message,
            "intent_classification": None,
            "interpreted_intent": None,
            "interpreted_args": {},
            "confidence": 0.0,
            "selected_tool": None,
            "validation_status": "pending",
            "validated_arguments": None,
            "execution_status": "pending",
        }

        # Log incoming request
        self.logger.log_request(
            request_id=context.request_id,
            sender=context.sender,
            raw_message=context.raw_message,
            source=context.source,
        )
        
        # Try to interpret message
        parsed = self.interpreter.parse_to_dict(context.raw_message)
        tool_name = parsed.get("tool")
        args = parsed.get("args", {})
        confidence = parsed.get("confidence", 0.0)
        
        context.interpreted_tool = tool_name
        context.interpreted_args = args
        context.confidence = confidence
        trace["intent_classification"] = parsed.get("intent")
        trace["interpreted_intent"] = tool_name
        trace["interpreted_args"] = args
        trace["confidence"] = confidence
        
        # Log interpretation
        if tool_name:
            self.logger.log_request(
                request_id=context.request_id,
                sender=context.sender,
                raw_message=context.raw_message,
                interpreted_intent=tool_name,
                confidence=confidence,
                source=context.source,
            )
        
        # Validate tool exists
        if not tool_name or not self.registry.exists(tool_name):
            self.logger.log_error(
                request_id=context.request_id,
                error_type="unknown_tool",
                error_message=f"Could not interpret: {context.raw_message}",
            )
            return {
                "success": False,
                "tool_name": None,
                "output": None,
                "error": "I didn't understand that. Try: list inbox, check cpu, show files in documents, etc.",
                "request_id": context.request_id,
                "trace": trace,
            }
        
        # Check if tool is allowed
        if context.allowed_tools and tool_name not in context.allowed_tools:
            trace["selected_tool"] = tool_name
            trace["validation_status"] = "failed"
            self.logger.log_error(
                request_id=context.request_id,
                error_type="unauthorized_tool",
                error_message=f"Tool not allowed: {tool_name}",
            )
            return {
                "success": False,
                "tool_name": tool_name,
                "output": None,
                "error": f"Tool '{tool_name}' is not allowed",
                "request_id": context.request_id,
                "trace": trace,
            }
        
        # Get tool
        tool = self.registry.get(tool_name)
        
        # Validate arguments
        is_valid, validation_error = tool.validate_args(args)
        if not is_valid:
            trace["selected_tool"] = tool_name
            trace["validation_status"] = "failed"
            trace["validated_arguments"] = args
            self.logger.log_error(
                request_id=context.request_id,
                error_type="invalid_arguments",
                error_message=validation_error,
            )
            return {
                "success": False,
                "tool_name": tool_name,
                "output": None,
                "error": f"Invalid input: {validation_error}",
                "request_id": context.request_id,
                "trace": trace,
            }

        trace["selected_tool"] = tool_name
        trace["validation_status"] = "passed"
        trace["validated_arguments"] = args
        trace["execution_status"] = "running"
        
        # Execute tool
        try:
            exec_context = {
                "workspace": context.workspace,
                "allowed_directories": context.allowed_directories,
                "request_id": context.request_id,
                "sender": context.sender,
                "logger": self.logger,
            }
            
            started = time.perf_counter()
            result = await asyncio.wait_for(
                tool.execute(args, exec_context),
                timeout=context.tool_timeout_seconds,
            )
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            
            # Log execution
            self.logger.log_tool_execution(
                request_id=context.request_id,
                tool_name=tool_name,
                arguments=args,
                success=result.success,
                execution_time_ms=elapsed_ms,
                tool_runtime_ms=elapsed_ms,
                output=result.output,
                error=result.error,
            )
            
            # Log response
            if result.success:
                self.logger.log_response(
                    request_id=context.request_id,
                    status="success",
                    response_message=result.output,
                    tool_name=tool_name,
                )
            else:
                self.logger.log_response(
                    request_id=context.request_id,
                    status="error",
                    response_message=result.error,
                    tool_name=tool_name,
                )
            
            return {
                "success": result.success,
                "tool_name": tool_name,
                "output": result.output,
                "error": result.error,
                "request_id": context.request_id,
                "trace": {
                    **trace,
                    "execution_status": "success" if result.success else "failed",
                    "execution_time_ms": elapsed_ms,
                },
            }

        except asyncio.TimeoutError:
            elapsed_ms = int(context.tool_timeout_seconds * 1000)
            self.logger.log_tool_execution(
                request_id=context.request_id,
                tool_name=tool_name,
                arguments=args,
                success=False,
                execution_time_ms=elapsed_ms,
                tool_runtime_ms=elapsed_ms,
                error=f"Tool timeout after {context.tool_timeout_seconds:.0f}s",
            )
            self.logger.log_error(
                request_id=context.request_id,
                error_type="execution_timeout",
                error_message=f"Tool '{tool_name}' timed out after {context.tool_timeout_seconds:.0f}s",
            )
            return {
                "success": False,
                "tool_name": tool_name,
                "output": None,
                "error": f"Tool timeout after {context.tool_timeout_seconds:.0f}s",
                "request_id": context.request_id,
                "trace": {
                    **trace,
                    "execution_status": "failed",
                    "execution_time_ms": elapsed_ms,
                },
            }
        
        except Exception as e:
            self.logger.log_error(
                request_id=context.request_id,
                error_type="execution_error",
                error_message=str(e),
            )
            return {
                "success": False,
                "tool_name": tool_name,
                "output": None,
                "error": f"Tool execution failed: {str(e)}",
                "request_id": context.request_id,
                "trace": {
                    **trace,
                    "execution_status": "failed",
                },
            }
