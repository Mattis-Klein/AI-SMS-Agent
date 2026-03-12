import tempfile
from pathlib import Path

from agent.config_loader import ConfigLoader
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

    assert parsed_followup.get("followup_topic") == "email_access"
    assert parsed_followup.get("topic") == "email_access"


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
    original_method = ConfigLoader._get_master_env_path
    original_cache = ConfigLoader._config_cache
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            test_master_path = Path(tmpdir) / ".env.master"
            test_master_path.write_text("OPENAI_MODEL=gpt-4.1-mini\n", encoding="utf-8")

            ConfigLoader._get_master_env_path = classmethod(lambda cls: test_master_path)
            ConfigLoader._config_cache = None

            tool = ListRecentEmailsTool()
            result = __import__("asyncio").run(tool.execute({"limit": 3}))
    finally:
        ConfigLoader._get_master_env_path = original_method
        ConfigLoader._config_cache = original_cache

    assert result.success is False
    assert result.error_type == "missing_configuration"
    assert result.missing_config_fields
    assert "EMAIL_PASSWORD" in result.missing_config_fields


def test_session_context_denied_action_not_marked_missing_path():
    manager = SessionContextManager(max_recent_turns=4)

    manager.update(
        session_id="desktop:denied",
        user_message="create file in blocked path",
        parsed={"intent": "filesystem", "tool": "create_file", "args": {"path": "C:/Windows/system32/test.txt"}, "entities": {"action_requested": True}},
        result={"success": False, "tool_name": "create_file", "error_type": "denied_action", "error": "Path is not in allowed directories"},
    )

    snapshot = manager.get_snapshot("desktop:denied")
    assert snapshot.get("last_failure_type") == "denied_action"
    assert snapshot.get("missing_parameters") == []


def test_session_context_existing_file_not_marked_missing_path():
    manager = SessionContextManager(max_recent_turns=4)

    manager.update(
        session_id="desktop:exists",
        user_message="create file",
        parsed={"intent": "filesystem", "tool": "create_file", "args": {"path": "inbox/existing.txt"}, "entities": {"action_requested": True}},
        result={"success": False, "tool_name": "create_file", "error_type": "validation_failure", "error": "File already exists: inbox/existing.txt"},
    )

    snapshot = manager.get_snapshot("desktop:exists")
    assert snapshot.get("last_failure_type") == "validation_failure"
    assert snapshot.get("missing_parameters") == []


def test_session_context_truly_missing_path_marks_missing_parameter():
    manager = SessionContextManager(max_recent_turns=4)

    manager.update(
        session_id="desktop:missing-path",
        user_message="create a file",
        parsed={"intent": "filesystem", "tool": "create_file", "args": {}, "entities": {"action_requested": True}},
        result={"success": False, "tool_name": "create_file", "error_type": "validation_failure", "error": "Invalid input: Provide either 'path' or both 'parent_path' and 'name'"},
    )

    snapshot = manager.get_snapshot("desktop:missing-path")
    assert snapshot.get("missing_parameters") == ["path"]
