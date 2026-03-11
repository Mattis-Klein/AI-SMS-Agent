import asyncio

from agent.assistant_core import AssistantCore, AssistantMetadata
from agent.interpreter import NaturalLanguageInterpreter
from agent.session_context import SessionContextManager


class _RuntimeStub:
    def __init__(self):
        self.interpreter = NaturalLanguageInterpreter()
        self.openai_api_key = ""
        self.openai_model = "gpt-4.1-mini"
        self.session_context = SessionContextManager()

    async def execute_tool(self, **_kwargs):
        return {
            "success": True,
            "tool_name": "current_time",
            "output": "10:00 AM",
            "error": None,
            "trace": {},
        }


def test_desktop_locked_blocks_request():
    runtime = _RuntimeStub()
    assistant = AssistantCore(runtime)

    result = asyncio.run(
        assistant.respond(
            "check cpu",
            AssistantMetadata(
                sender="local-desktop",
                source="desktop",
                session_id="desktop:local-desktop",
                owner_unlocked=False,
            ),
        )
    )

    assert result["success"] is False
    assert result["trace"]["execution_status"] == "blocked"


def test_desktop_unlocked_allows_request():
    runtime = _RuntimeStub()
    assistant = AssistantCore(runtime)

    result = asyncio.run(
        assistant.respond(
            "check cpu",
            AssistantMetadata(
                sender="local-desktop",
                source="desktop",
                session_id="desktop:local-desktop",
                owner_unlocked=True,
            ),
        )
    )

    assert result["success"] is True
    assert result["tool_name"] == "current_time"
    assert result["trace"]["assistant_mode"] == "tool"
