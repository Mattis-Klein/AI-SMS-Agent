import json
import tempfile
from pathlib import Path

from agent.interpreter import NaturalLanguageInterpreter
from agent.logger import StructuredLogger
from agent.redaction import redact_config_assignments, sanitize_for_logging
from agent.session_context import SessionContextManager
from agent.tools.builtin.config_tools import SetConfigVariableTool


def test_redact_config_assignment_text():
    source = "EMAIL_PASSWORD=hunter2 and TWILIO_AUTH_TOKEN: abc123"
    redacted = redact_config_assignments(source)
    assert "hunter2" not in redacted
    assert "abc123" not in redacted
    assert "EMAIL_PASSWORD=[REDACTED]" in redacted
    assert "TWILIO_AUTH_TOKEN:[REDACTED]" in redacted


def test_logger_redacts_sensitive_payloads():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "agent.log"
        logger = StructuredLogger(log_file)
        logger.log_request(request_id="abc", sender="desktop", raw_message="EMAIL_PASSWORD=hunter2")
        logger.log_tool_execution(
            request_id="abc",
            tool_name="set_config_variable",
            arguments={"variable_name": "EMAIL_PASSWORD", "variable_value": "hunter2"},
            success=True,
            output="saved",
        )

        lines = [line for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        merged = "\n".join(lines)
        assert "hunter2" not in merged
        assert "[REDACTED]" in merged


def test_followup_context_and_progress_tracking():
    interpreter = NaturalLanguageInterpreter()
    manager = SessionContextManager(max_recent_turns=4)

    parsed_first = interpreter.parse_to_dict("check my inbox")
    manager.update(
        session_id="desktop:local",
        user_message="check my inbox",
        parsed=parsed_first,
        result={
            "success": False,
            "tool_name": "summarize_inbox",
            "error_type": "missing_configuration",
            "missing_config_fields": ["EMAIL_IMAP_HOST|IMAP_SERVER", "EMAIL_PASSWORD"],
        },
    )

    ctx = manager.get_snapshot("desktop:local")
    parsed_followup = interpreter.parse_to_dict("do you need my password?", context=ctx)
    assert parsed_followup.get("followup_topic") == "email_setup"
    assert parsed_followup.get("topic") == "email_setup"

    parsed_update = interpreter.parse_to_dict("EMAIL_PASSWORD=app-pass", context=ctx)
    assert parsed_update.get("tool") == "set_config_variable"

    manager.update(
        session_id="desktop:local",
        user_message="EMAIL_PASSWORD=app-pass",
        parsed=parsed_update,
        result={
            "success": True,
            "tool_name": "set_config_variable",
            "data": {"restart_required": []},
        },
    )

    ctx_after = manager.get_snapshot("desktop:local")
    assert "EMAIL_PASSWORD" not in ctx_after.get("missing_config_fields", [])
    assert ctx_after.get("config_progress_state") == "in_progress"


def test_set_config_variable_restart_signal_and_safe_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env.master"
        env_file.write_text("PUBLIC_BASE_URL=https://old.example\n", encoding="utf-8")

        tool = SetConfigVariableTool()
        tool.env_path = env_file

        result = __import__("asyncio").run(
            tool.execute({
                "variable_name": "PUBLIC_BASE_URL",
                "variable_value": "https://new value#frag.example",
            })
        )

        assert result.success is True
        assert result.data and result.data.get("restart_required") == ["sms_bridge"]

        content = env_file.read_text(encoding="utf-8")
        assert 'PUBLIC_BASE_URL="https://new value#frag.example"' in content


def test_sanitize_for_logging_redacts_variable_value_key():
    payload = {"variable_name": "EMAIL_PASSWORD", "variable_value": "secret"}
    safe = sanitize_for_logging(payload)
    assert safe["variable_value"] == "[REDACTED]"
    assert "secret" not in json.dumps(safe)
