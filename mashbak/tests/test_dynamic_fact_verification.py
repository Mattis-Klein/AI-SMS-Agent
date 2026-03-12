import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.assistant_core import AssistantCore, AssistantMetadata
from agent.interpreter import NaturalLanguageInterpreter
from agent.session_context import SessionContextManager


class FakeRuntime:
    def __init__(self, tool_result_factory=None):
        self.session_context = SessionContextManager(max_recent_turns=10)
        self.interpreter = NaturalLanguageInterpreter()
        self.openai_api_key = ""
        self.openai_model = "gpt-4.1-mini"
        self.model_response_max_tokens = 250
        self._tool_result_factory = tool_result_factory

    async def execute_tool(self, tool_name: str, args: dict, sender: str, request_id: str | None, source: str):
        if self._tool_result_factory:
            result = self._tool_result_factory(tool_name, args)
        else:
            result = {
                "success": False,
                "tool_name": tool_name,
                "output": None,
                "error": "No fake tool result configured",
                "error_type": "execution_failure",
                "data": None,
            }

        trace = result.get("trace") or {
            "selected_tool": tool_name,
            "validation_status": "passed",
            "execution_status": "success" if result.get("success") else "failed",
        }
        return {
            "success": bool(result.get("success")),
            "tool_name": result.get("tool_name", tool_name),
            "output": result.get("output"),
            "error": result.get("error"),
            "error_type": result.get("error_type"),
            "missing_config_fields": result.get("missing_config_fields"),
            "remediation": result.get("remediation"),
            "request_id": request_id or "fake-req",
            "source": source,
            "data": result.get("data"),
            "trace": trace,
        }


def _respond(assistant: AssistantCore, message: str, session_id: str = "desktop:verify") -> dict:
    return asyncio.run(
        assistant.respond(
            message,
            AssistantMetadata(sender="review-local", source="desktop", session_id=session_id),
        )
    )


def test_unverifiable_dynamic_fact_query_refuses_cleanly():
    runtime = FakeRuntime()
    assistant = AssistantCore(runtime)

    response = _respond(assistant, "Who won the 2024 U.S. presidential election?")

    assert response["success"] is True
    assert response.get("trace", {}).get("verification_state") == "Unverified"
    reply = (response.get("assistant_reply") or "").lower()
    assert "can't verify" in reply or "cannot verify" in reply
    assert "guess" in reply or "stale" in reply


def test_current_time_query_is_tool_assisted_when_tool_succeeds():
    def fake_result(tool_name: str, _args: dict) -> dict:
        if tool_name == "current_time":
            return {
                "success": True,
                "tool_name": tool_name,
                "output": "Mon 03/12/2026 10:10:10.10",
                "error": None,
                "data": {},
            }
        return {
            "success": False,
            "tool_name": tool_name,
            "output": None,
            "error": "unexpected tool",
            "error_type": "execution_failure",
            "data": None,
        }

    runtime = FakeRuntime(fake_result)
    assistant = AssistantCore(runtime)

    response = _respond(assistant, "what time is it?")

    assert response.get("trace", {}).get("verification_state") == "Tool-assisted"
    assert "currently" in (response.get("assistant_reply") or "").lower()


def test_non_dynamic_conversation_is_local_only():
    runtime = FakeRuntime()
    assistant = AssistantCore(runtime)

    response = _respond(assistant, "hello")

    assert response["success"] is True
    assert response.get("trace", {}).get("verification_state") == "Local-only"
