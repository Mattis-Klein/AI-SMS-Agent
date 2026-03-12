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


def _respond(assistant: AssistantCore, message: str, session_id: str = "desktop:test") -> dict:
    return asyncio.run(
        assistant.respond(
            message,
            AssistantMetadata(sender="review-local", source="desktop", session_id=session_id),
        )
    )


def _contains_completion_words(text: str) -> bool:
    lower = text.lower()
    return any(word in lower for word in ["created", "added", "saved", "deleted", "moved", "done"])


def test_no_tool_selected_action_does_not_claim_creation():
    runtime = FakeRuntime()
    assistant = AssistantCore(runtime)

    # No last folder in session context, so this follow-up cannot map to a real tool.
    response = _respond(assistant, "add a file in that folder with all 50 states")

    assert response["success"] is False
    assert response["tool_name"] is None
    assert response.get("trace", {}).get("selected_tool") is None
    assert response.get("trace", {}).get("execution_status") == "not_run"
    assert _contains_completion_words(response.get("assistant_reply", "")) is False


def test_failed_filesystem_execution_reports_failure_not_success_claim():
    def fake_result(tool_name: str, _args: dict) -> dict:
        return {
            "success": False,
            "tool_name": tool_name,
            "output": None,
            "error": "Path is not in allowed directories",
            "error_type": "denied_action",
            "data": None,
        }

    runtime = FakeRuntime(fake_result)
    assistant = AssistantCore(runtime)

    response = _respond(assistant, "create a folder on my desktop called RestrictedTest")

    assert response["success"] is False
    assert response["tool_name"] == "create_folder"
    assert response.get("trace", {}).get("selected_tool") == "create_folder"
    assert response.get("trace", {}).get("execution_status") in {"failed", "success"}
    assert _contains_completion_words(response.get("assistant_reply", "")) is False


def test_successful_filesystem_execution_allows_grounded_success_claim():
    def fake_result(tool_name: str, _args: dict) -> dict:
        return {
            "success": True,
            "tool_name": tool_name,
            "output": "Folder created: C:/Users/owner/Desktop/DocsX",
            "error": None,
            "data": {
                "created_path": "C:/Users/owner/Desktop/DocsX",
                "fs_action": "create_folder",
                "action_status": "success",
            },
        }

    runtime = FakeRuntime(fake_result)
    assistant = AssistantCore(runtime)

    response = _respond(assistant, "create a folder on my desktop called DocsX")

    assert response["success"] is True
    assert response["tool_name"] == "create_folder"
    assert response.get("trace", {}).get("selected_tool") == "create_folder"
    assert response.get("trace", {}).get("tool_execution_occurred") is True


def test_followup_where_is_it_resolves_from_last_real_action_result():
    def fake_result(tool_name: str, _args: dict) -> dict:
        if tool_name == "create_folder":
            return {
                "success": True,
                "tool_name": tool_name,
                "output": "Folder created: C:/Users/owner/Desktop/TripPack",
                "error": None,
                "data": {
                    "created_path": "C:/Users/owner/Desktop/TripPack",
                    "fs_action": "create_folder",
                    "action_status": "success",
                },
            }
        if tool_name == "create_file":
            return {
                "success": True,
                "tool_name": tool_name,
                "output": "File created: C:/Users/owner/Desktop/TripPack/states.txt",
                "error": None,
                "data": {
                    "created_path": "C:/Users/owner/Desktop/TripPack/states.txt",
                    "fs_action": "create_file",
                    "action_status": "success",
                },
            }
        return {
            "success": False,
            "tool_name": tool_name,
            "output": None,
            "error": "Unexpected tool",
            "error_type": "execution_failure",
            "data": None,
        }

    runtime = FakeRuntime(fake_result)
    assistant = AssistantCore(runtime)

    first = _respond(assistant, "create a folder on my desktop called TripPack", session_id="desktop:follow")
    assert first["success"] is True

    second = _respond(assistant, "where is it?", session_id="desktop:follow")
    assert second["tool_name"] is None
    assert "TripPack" in (second.get("assistant_reply") or "")


def test_successful_filesystem_result_without_created_path_is_rejected():
    def fake_result(tool_name: str, _args: dict) -> dict:
        return {
            "success": True,
            "tool_name": tool_name,
            "output": "Folder created",
            "error": None,
            "data": {
                "fs_action": "create_folder",
                "action_status": "success",
            },
        }

    runtime = FakeRuntime(fake_result)
    assistant = AssistantCore(runtime)
    response = _respond(assistant, "create a folder on my desktop called MissingPath")

    assert response["success"] is False
    assert response.get("error_type") == "execution_failure"
    assert "resolved path" in (response.get("assistant_reply") or "").lower()


def test_contextual_followup_put_file_in_it_maps_to_real_tool():
    interpreter = NaturalLanguageInterpreter()
    ctx = {
        "last_created_path": "C:/Users/owner/Desktop/TripPack",
        "last_result": "success",
        "last_task": "create_folder",
        "recent_turns": [],
    }
    parsed = interpreter.parse_to_dict("put a file in it", context=ctx)
    assert parsed.get("tool") == "create_file"
    parent_path = str(parsed.get("args", {}).get("parent_path", "")).replace("\\", "/")
    assert parent_path == "C:/Users/owner/Desktop/TripPack"


def test_contextual_followup_add_states_maps_to_real_tool_with_content():
    interpreter = NaturalLanguageInterpreter()
    ctx = {
        "last_created_path": "C:/Users/owner/Desktop/TripPack",
        "last_result": "success",
        "last_task": "create_folder",
        "recent_turns": [],
    }
    parsed = interpreter.parse_to_dict("add a file in that folder with all 50 states", context=ctx)
    assert parsed.get("tool") == "create_file"
    assert parsed.get("args", {}).get("name") == "states.txt"
    assert "Wyoming" in str(parsed.get("args", {}).get("content", ""))


def test_desktop_file_creation_phrase_maps_to_create_file():
    interpreter = NaturalLanguageInterpreter()
    parsed = interpreter.parse_to_dict("create a new file on my desktop called Mashbak", context={})
    assert parsed.get("tool") == "create_file"
    path_value = str(parsed.get("args", {}).get("path", "")).replace("\\", "/")
    assert path_value.endswith("/Desktop/Mashbak")


def test_make_file_on_desktop_phrase_maps_to_create_file():
    interpreter = NaturalLanguageInterpreter()
    parsed = interpreter.parse_to_dict("make a file on the desktop called todo", context={})
    assert parsed.get("tool") == "create_file"
    path_value = str(parsed.get("args", {}).get("path", "")).replace("\\", "/")
    assert path_value.endswith("/Desktop/todo")


def test_unresolved_that_folder_reference_does_not_invent_path():
    runtime = FakeRuntime()
    assistant = AssistantCore(runtime)

    response = _respond(assistant, "create a file named states in that folder")

    assert response["success"] is False
    assert response["tool_name"] is None
    reply = str(response.get("assistant_reply") or "").lower()
    assert "couldn't resolve which folder" in reply
