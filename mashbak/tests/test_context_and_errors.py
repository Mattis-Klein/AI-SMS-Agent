import os

from agent.interpreter import NaturalLanguageInterpreter
from agent.session_context import SessionContextManager
from agent.tools.builtin.email_tools import ListRecentEmailsTool


def test_followup_uses_session_topic_for_ambiguous_config_question():
    interpreter = NaturalLanguageInterpreter()
    manager = SessionContextManager(max_recent_turns=4)

    parsed_first = interpreter.parse_to_dict("Do I have unread emails?")
    manager.update(
        session_id="desktop:local",
        user_message="Do I have unread emails?",
        parsed=parsed_first,
        result={"success": True, "tool_name": parsed_first.get("tool")},
    )

    context = manager.get_snapshot("desktop:local")
    parsed_followup = interpreter.parse_to_dict("How do I configure it?", context=context)

    assert parsed_followup.get("followup_topic") == "email"
    assert parsed_followup.get("topic") == "email"


def test_session_context_isolated_between_sessions():
    manager = SessionContextManager(max_recent_turns=2)

    manager.update(
        session_id="desktop:local",
        user_message="check cpu",
        parsed={"intent": "system", "tool": "cpu_usage", "entities": {}},
        result={"success": True, "tool_name": "cpu_usage"},
    )

    desktop_context = manager.get_snapshot("desktop:local")
    sms_context = manager.get_snapshot("sms:15551234567")

    assert desktop_context.get("last_tool") == "cpu_usage"
    assert sms_context.get("last_tool") is None


def test_email_missing_config_returns_structured_error():
    original = {key: os.environ.get(key) for key in [
        "EMAIL_IMAP_HOST",
        "IMAP_SERVER",
        "EMAIL_USERNAME",
        "EMAIL_ADDRESS",
        "EMAIL_PASSWORD",
    ]}

    for key in original:
        os.environ.pop(key, None)

    try:
        tool = ListRecentEmailsTool()
        result = __import__("asyncio").run(tool.execute({"limit": 3}))
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    assert result.success is False
    assert result.error_type == "missing_configuration"
    assert result.missing_config_fields
    assert "EMAIL_PASSWORD" in result.missing_config_fields
