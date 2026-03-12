"""Shared agent runtime used by FastAPI endpoints and local desktop tooling."""

import asyncio
import time
from pathlib import Path
from typing import Optional

if __package__:
    from .config import Config
    from .config_loader import ConfigLoader
    from .assistant_core import AssistantCore, AssistantMetadata
    from assistants.bucherim.service import BucherimService, BucherimSmsRequest
    from .logger import StructuredLogger
    from .tools import ToolRegistry
    from .tools.builtin import ALL_BUILTIN_TOOLS
    from .dispatcher import Dispatcher, RequestContext
    from .interpreter import NaturalLanguageInterpreter
    from .session_context import SessionContextManager
    from .redaction import sanitize_for_logging, sanitize_trace
else:
    from config import Config
    from config_loader import ConfigLoader
    from assistant_core import AssistantCore, AssistantMetadata
    from assistants.bucherim.service import BucherimService, BucherimSmsRequest
    from logger import StructuredLogger
    from tools import ToolRegistry
    from tools.builtin import ALL_BUILTIN_TOOLS
    from dispatcher import Dispatcher, RequestContext
    from interpreter import NaturalLanguageInterpreter
    from session_context import SessionContextManager
    from redaction import sanitize_for_logging, sanitize_trace


class AgentRuntime:
    """Initializes and exposes shared dispatcher/tool runtime state."""

    def __init__(self, base_dir: Path):
        # Initialization order is intentional:
        # 1) Load master config from .env.master, 2) set base dir,
        # 3) read AGENT_* values through ConfigLoader, 4) initialize workspace.
        self.base_dir = base_dir.resolve()

        # Always refresh config from master file on runtime init.
        ConfigLoader.load(reload=True)

        workspace_override = (ConfigLoader.get("AGENT_WORKSPACE", "") or "").strip()
        if workspace_override:
            self.workspace = Path(workspace_override).resolve()
        else:
            self.workspace = (self.base_dir / "data" / "workspace").resolve()
        self.logs_dir = (self.base_dir / "data" / "logs").resolve()
        self.api_key = (ConfigLoader.get("AGENT_API_KEY", "") or "").strip()
        self.openai_api_key = (ConfigLoader.get("OPENAI_API_KEY", "") or "").strip()
        self.openai_model = (ConfigLoader.get("OPENAI_MODEL", "gpt-4.1-mini") or "gpt-4.1-mini").strip()
        self.model_response_max_tokens = max(64, ConfigLoader.get_int("MODEL_RESPONSE_MAX_TOKENS", 250))
        self.session_context_turns = max(1, ConfigLoader.get_int("SESSION_CONTEXT_MAX_TURNS", 4))
        timeout_override = ConfigLoader.get("TOOL_EXECUTION_TIMEOUT", "").strip()

        if not self.api_key:
            raise RuntimeError("AGENT_API_KEY is required. Set it in mashbak/.env.master or environment.")

        for required_dir in (
            self.workspace,
            self.workspace / "inbox",
            self.workspace / "outbox",
            self.workspace / "logs",
            self.logs_dir,
        ):
            required_dir.mkdir(parents=True, exist_ok=True)

        self.config = Config(self.base_dir / "agent" / "config.json")
        self.logger = StructuredLogger(self.logs_dir / "agent.log")

        self.registry = ToolRegistry()
        for tool in ALL_BUILTIN_TOOLS:
            self.registry.register(tool)

        self.interpreter = NaturalLanguageInterpreter()
        self.dispatcher = Dispatcher(self.registry, self.interpreter, self.logger)
        self.session_context = SessionContextManager(max_recent_turns=self.session_context_turns)
        self.default_tool_timeout_seconds = self.config.get_tool_timeout_seconds()
        if timeout_override:
            try:
                self.default_tool_timeout_seconds = max(1.0, float(timeout_override))
            except ValueError:
                pass
        self.assistant = AssistantCore(self)
        self.bucherim = BucherimService(
            base_dir=self.base_dir,
            openai_api_key=self.openai_api_key,
            openai_model=self.openai_model,
            session_turns=self.session_context_turns,
        )

    def reload_dynamic_config(self) -> dict:
        """Reload dynamic config values used at runtime without restarting the process."""
        ConfigLoader.load(reload=True)
        self.openai_api_key = (ConfigLoader.get("OPENAI_API_KEY", "") or "").strip()
        self.openai_model = (ConfigLoader.get("OPENAI_MODEL", "gpt-4.1-mini") or "gpt-4.1-mini").strip()
        self.model_response_max_tokens = max(64, ConfigLoader.get_int("MODEL_RESPONSE_MAX_TOKENS", 250))
        self.session_context_turns = max(1, ConfigLoader.get_int("SESSION_CONTEXT_MAX_TURNS", self.session_context.max_recent_turns))
        self.session_context.max_recent_turns = self.session_context_turns

        timeout_override = (ConfigLoader.get("TOOL_EXECUTION_TIMEOUT", "") or "").strip()
        self.default_tool_timeout_seconds = self.config.get_tool_timeout_seconds()
        if timeout_override:
            try:
                self.default_tool_timeout_seconds = max(1.0, float(timeout_override))
            except ValueError:
                pass

        self.assistant.model_client.api_key = self.openai_api_key
        self.assistant.model_client.model = self.openai_model
        self.bucherim.update_model_config(
            api_key=self.openai_api_key,
            model=self.openai_model,
            session_turns=self.session_context_turns,
        )

        return {
            "assistant_ai_enabled": bool(self.openai_api_key),
            "assistant_model": self.openai_model,
            "session_context_max_turns": self.session_context_turns,
            "tool_timeout_seconds": self.default_tool_timeout_seconds,
            "model_response_max_tokens": self.model_response_max_tokens,
        }

    async def execute_bucherim_sms(
        self,
        *,
        sender: str,
        recipient: str,
        body: str,
        request_id: str,
        message_sid: str | None = None,
        account_sid: str | None = None,
        media: list[dict] | None = None,
    ) -> dict:
        """Process Bucherim SMS flow using dedicated backend membership + assistant logic."""
        self.reload_dynamic_config()
        return await self.bucherim.process_sms(
            BucherimSmsRequest(
                sender=sender,
                recipient=recipient,
                body=body,
                request_id=request_id,
                message_sid=message_sid,
                account_sid=account_sid,
                media=media or [],
            )
        )

    def _resolve_source(self, sender: str, source: Optional[str]) -> str:
        if source:
            return source.strip().lower()
        if str(sender).lower().startswith("sms"):
            return "sms"
        return "desktop"

    def _format_output_for_source(self, value: Optional[str], source: str, max_sms_chars: int = 320) -> Optional[str]:
        if value is None:
            return None
        if source != "sms":
            return value

        compact = " ".join(str(value).split())
        if len(compact) <= max_sms_chars:
            return compact
        return f"{compact[: max_sms_chars - 3]}..."

    def _normalize_sender_key(self, sender: str) -> str:
        sender_text = str(sender or "unknown").strip().lower()
        digits = "".join(ch for ch in sender_text if ch.isdigit())
        if digits:
            return digits[-10:]
        return sender_text or "unknown"

    def build_session_id(self, source: str, sender: str) -> str:
        sender_key = self._normalize_sender_key(sender)
        return f"{source}:{sender_key}"

    async def execute_nl(
        self,
        message: str,
        sender: str = "unknown",
        request_id: Optional[str] = None,
        source: Optional[str] = None,
        owner_unlocked: Optional[bool] = None,
    ) -> dict:
        """Execute a natural-language request through Mashbak's shared assistant core."""
        request_source = self._resolve_source(sender, source)
        self.reload_dynamic_config()
        result = await self.assistant.respond(
            message,
            AssistantMetadata(
                sender=sender,
                source=request_source,
                session_id=self.build_session_id(request_source, sender),
                owner_unlocked=owner_unlocked,
                request_id=request_id,
            ),
        )
        result["output"] = self._format_output_for_source(result.get("output"), request_source)
        result["error"] = self._format_output_for_source(result.get("error"), request_source)
        result["source"] = request_source
        trace = result.get("trace") or {}
        trace = sanitize_trace(trace)
        trace["source"] = request_source
        result["trace"] = trace
        return result

    async def execute_tool(
        self,
        tool_name: str,
        args: Optional[dict] = None,
        sender: str = "unknown",
        request_id: Optional[str] = None,
        source: Optional[str] = None,
    ) -> dict:
        """Execute a specific tool through the same validation/execution path used by the API."""
        args = args or {}
        request_source = self._resolve_source(sender, source)
        self.reload_dynamic_config()
        safe_args = sanitize_for_logging(args)
        safe_raw_request = sanitize_for_logging(f"execute: {tool_name}")

        context = RequestContext(
            sender=sender,
            source=request_source,
            raw_message=f"execute: {tool_name}",
            workspace=self.workspace,
            allowed_directories=self.config.get_allowed_directories(),
            allowed_tools=self.config.get_allowed_tools(),
            tool_timeout_seconds=self.config.get_tool_timeout_seconds(),
            session_id=self.build_session_id(request_source, sender),
            session_context=self.session_context.get_snapshot(self.build_session_id(request_source, sender)),
        )
        if request_id:
            context.request_id = request_id

        context.tool_timeout_seconds = self.default_tool_timeout_seconds

        if not self.registry.exists(tool_name):
            self.logger.log_error(
                request_id=context.request_id,
                error_type="unknown_tool",
                error_message=f"Tool not found: {tool_name}",
            )
            return {
                "success": False,
                "tool_name": None,
                "output": None,
                "error": f"Tool '{tool_name}' not found. Available tools: {', '.join(self.registry.list_all())}",
                "error_type": "unavailable_tool",
                "request_id": context.request_id,
                "trace": {
                    "raw_request": safe_raw_request,
                    "session_id": context.session_id,
                    "session_context": sanitize_for_logging(context.session_context),
                    "source": request_source,
                    "interpreted_intent": tool_name,
                    "interpreted_args": safe_args,
                    "confidence": 1.0,
                    "selected_tool": tool_name,
                    "validation_status": "failed",
                    "validated_arguments": safe_args,
                    "execution_status": "failed",
                },
            }

        if context.allowed_tools and tool_name not in context.allowed_tools:
            self.logger.log_error(
                request_id=context.request_id,
                error_type="unauthorized_tool",
                error_message=f"Tool not allowed: {tool_name}",
                sender=context.sender,
            )
            return {
                "success": False,
                "tool_name": tool_name,
                "output": None,
                "error": f"Tool '{tool_name}' is not allowed",
                "error_type": "denied_action",
                "request_id": context.request_id,
                "trace": {
                    "raw_request": safe_raw_request,
                    "session_id": context.session_id,
                    "session_context": sanitize_for_logging(context.session_context),
                    "source": request_source,
                    "interpreted_intent": tool_name,
                    "interpreted_args": safe_args,
                    "confidence": 1.0,
                    "selected_tool": tool_name,
                    "validation_status": "failed",
                    "validated_arguments": safe_args,
                    "execution_status": "failed",
                },
            }

        tool = self.registry.get(tool_name)

        is_valid, validation_error = tool.validate_args(args)
        if not is_valid:
            self.logger.log_error(
                request_id=context.request_id,
                error_type="invalid_arguments",
                error_message=validation_error,
            )
            return {
                "success": False,
                "tool_name": tool_name,
                "output": None,
                "error": validation_error,
                "error_type": "validation_failure",
                "request_id": context.request_id,
                "trace": {
                    "raw_request": safe_raw_request,
                    "session_id": context.session_id,
                    "session_context": sanitize_for_logging(context.session_context),
                    "source": request_source,
                    "interpreted_intent": tool_name,
                    "interpreted_args": safe_args,
                    "confidence": 1.0,
                    "selected_tool": tool_name,
                    "validation_status": "failed",
                    "validated_arguments": safe_args,
                    "execution_status": "failed",
                },
            }

        exec_context = {
            "workspace": self.workspace,
            "allowed_directories": self.config.get_allowed_directories(),
            "request_id": context.request_id,
            "sender": context.sender,
            "logger": self.logger,
        }

        started = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                tool.execute(args, exec_context),
                timeout=context.tool_timeout_seconds,
            )
        except asyncio.TimeoutError:
            elapsed_ms = int(context.tool_timeout_seconds * 1000)
            self.logger.log_tool_execution(
                request_id=context.request_id,
                tool_name=tool_name,
                arguments=safe_args,
                success=False,
                execution_time_ms=elapsed_ms,
                tool_runtime_ms=elapsed_ms,
                error=f"Tool timeout after {context.tool_timeout_seconds:.0f}s",
                sender=context.sender,
            )
            return {
                "success": False,
                "tool_name": tool_name,
                "output": None,
                "error": f"Tool timeout after {context.tool_timeout_seconds:.0f}s",
                "error_type": "timeout",
                "request_id": context.request_id,
                "trace": {
                    "raw_request": safe_raw_request,
                    "session_id": context.session_id,
                    "session_context": sanitize_for_logging(context.session_context),
                    "source": request_source,
                    "interpreted_intent": tool_name,
                    "interpreted_args": safe_args,
                    "confidence": 1.0,
                    "selected_tool": tool_name,
                    "validation_status": "passed",
                    "validated_arguments": safe_args,
                    "execution_status": "failed",
                    "execution_time_ms": elapsed_ms,
                },
            }

        elapsed_ms = int((time.perf_counter() - started) * 1000)

        self.logger.log_tool_execution(
            request_id=context.request_id,
            tool_name=tool_name,
            arguments=safe_args,
            success=result.success,
            execution_time_ms=elapsed_ms,
            tool_runtime_ms=elapsed_ms,
            output=result.output,
            error=result.error,
            sender=context.sender,
        )

        return {
            "success": result.success,
            "tool_name": tool_name,
            "output": self._format_output_for_source(result.output, request_source),
            "error": self._format_output_for_source(result.error, request_source),
            "error_type": result.error_type,
            "missing_config_fields": result.missing_config_fields,
            "remediation": result.remediation,
            "request_id": context.request_id,
            "source": request_source,
            "data": result.data,
            "trace": {
                "raw_request": safe_raw_request,
                "session_id": context.session_id,
                "session_context": sanitize_for_logging(context.session_context),
                "source": request_source,
                "interpreted_intent": tool_name,
                "interpreted_args": safe_args,
                "confidence": 1.0,
                "selected_tool": tool_name,
                "validation_status": "passed",
                "validated_arguments": safe_args,
                "execution_status": "success" if result.success else "failed",
                "execution_time_ms": elapsed_ms,
            },
        }

    def summary(self) -> dict:
        """Return runtime status/config summary for local tools."""
        return {
            "workspace": str(self.workspace),
            "allowed_directories": [str(p) for p in self.config.get_allowed_directories()],
            "allowed_tools": self.config.get_allowed_tools(),
            "tool_timeout_seconds": self.default_tool_timeout_seconds,
            "registered_tools": self.registry.list_all(),
            "assistant_ai_enabled": bool(self.openai_api_key),
            "assistant_model": self.openai_model,
            "model_response_max_tokens": self.model_response_max_tokens,
            "session_context_max_turns": self.session_context_turns,
            "log_level": (ConfigLoader.get("LOG_LEVEL", "INFO") or "INFO").upper(),
            "debug_mode": ConfigLoader.get_bool("DEBUG_MODE", False),
            "email_configured": bool(
                (ConfigLoader.get("EMAIL_IMAP_HOST") or ConfigLoader.get("IMAP_SERVER"))
                and (ConfigLoader.get("EMAIL_USERNAME") or ConfigLoader.get("EMAIL_ADDRESS"))
                and ConfigLoader.get("EMAIL_PASSWORD")
            ),
            "version": "2.0.0",
        }


def create_runtime(base_dir: Optional[Path] = None) -> AgentRuntime:
    """Factory function for creating shared agent runtime."""
    root = base_dir or Path(__file__).resolve().parent.parent
    return AgentRuntime(root)
