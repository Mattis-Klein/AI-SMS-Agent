"""Shared agent runtime used by FastAPI endpoints and local desktop tooling."""

import os
from pathlib import Path
from typing import Optional

from config import Config
from logger import StructuredLogger
from tools import ToolRegistry
from tools.builtin import ALL_BUILTIN_TOOLS
from dispatcher import Dispatcher, RequestContext
from interpreter import NaturalLanguageInterpreter


def load_env_file(env_path: Path) -> None:
    """Load environment variables from .env file before reading AGENT_* values."""
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


class AgentRuntime:
    """Initializes and exposes shared dispatcher/tool runtime state."""

    def __init__(self, base_dir: Path):
        # Initialization order is intentional:
        # 1) determine project root, 2) load .env, 3) read AGENT_* env vars,
        # 4) initialize workspace paths/configuration.
        self.base_dir = base_dir.resolve()
        load_env_file(self.base_dir / ".env")

        self.workspace = Path(
            os.getenv("AGENT_WORKSPACE", str(self.base_dir / "workspace"))
        ).resolve()
        self.api_key = os.getenv("AGENT_API_KEY", "")

        if not self.api_key:
            raise RuntimeError("AGENT_API_KEY is required. Set it in agent/.env or the environment.")

        for required_dir in (
            self.workspace,
            self.workspace / "inbox",
            self.workspace / "outbox",
            self.workspace / "logs",
        ):
            required_dir.mkdir(parents=True, exist_ok=True)

        self.config = Config(self.base_dir / "config.json")
        self.logger = StructuredLogger(self.workspace / "logs" / "agent.log")

        self.registry = ToolRegistry()
        for tool in ALL_BUILTIN_TOOLS:
            self.registry.register(tool)

        self.interpreter = NaturalLanguageInterpreter()
        self.dispatcher = Dispatcher(self.registry, self.interpreter, self.logger)

    async def execute_nl(self, message: str, sender: str = "unknown", request_id: Optional[str] = None) -> dict:
        """Execute a natural-language request through the shared dispatcher pipeline."""
        context = RequestContext(
            sender=sender,
            raw_message=message,
            workspace=self.workspace,
            allowed_directories=self.config.get_allowed_directories(),
            allowed_tools=self.config.get_allowed_tools(),
        )
        if request_id:
            context.request_id = request_id

        return await self.dispatcher.dispatch(context)

    async def execute_tool(self, tool_name: str, args: Optional[dict] = None, sender: str = "unknown", request_id: Optional[str] = None) -> dict:
        """Execute a specific tool through the same validation/execution path used by the API."""
        args = args or {}

        context = RequestContext(
            sender=sender,
            raw_message=f"execute: {tool_name}",
            workspace=self.workspace,
            allowed_directories=self.config.get_allowed_directories(),
            allowed_tools=self.config.get_allowed_tools(),
        )
        if request_id:
            context.request_id = request_id

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
                "request_id": context.request_id,
                "trace": {
                    "raw_request": context.raw_message,
                    "interpreted_intent": tool_name,
                    "interpreted_args": args,
                    "confidence": 1.0,
                    "selected_tool": tool_name,
                    "validation_status": "failed",
                    "validated_arguments": args,
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
                "request_id": context.request_id,
                "trace": {
                    "raw_request": context.raw_message,
                    "interpreted_intent": tool_name,
                    "interpreted_args": args,
                    "confidence": 1.0,
                    "selected_tool": tool_name,
                    "validation_status": "failed",
                    "validated_arguments": args,
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

        result = await tool.execute(args, exec_context)

        self.logger.log_tool_execution(
            request_id=context.request_id,
            tool_name=tool_name,
            arguments=args,
            success=result.success,
            output=result.output,
            error=result.error,
            sender=context.sender,
        )

        return {
            "success": result.success,
            "tool_name": tool_name,
            "output": result.output,
            "error": result.error,
            "request_id": context.request_id,
            "trace": {
                "raw_request": context.raw_message,
                "interpreted_intent": tool_name,
                "interpreted_args": args,
                "confidence": 1.0,
                "selected_tool": tool_name,
                "validation_status": "passed",
                "validated_arguments": args,
                "execution_status": "success" if result.success else "failed",
            },
        }

    def summary(self) -> dict:
        """Return runtime status/config summary for local tools."""
        return {
            "workspace": str(self.workspace),
            "allowed_directories": [str(p) for p in self.config.get_allowed_directories()],
            "allowed_tools": self.config.get_allowed_tools(),
            "registered_tools": self.registry.list_all(),
            "version": "2.0.0",
        }


def create_runtime(base_dir: Optional[Path] = None) -> AgentRuntime:
    """Factory function for creating shared agent runtime."""
    root = base_dir or Path(__file__).resolve().parent
    return AgentRuntime(root)
