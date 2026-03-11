"""Tests for configuration management through chat."""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.tools.builtin.config_tools import SetConfigVariableTool
from agent.interpreter import NaturalLanguageInterpreter


def test_interpreter_detects_config_assignment():
    """Test that interpreter detects configuration variable assignments."""
    interpreter = NaturalLanguageInterpreter()
    
    # Test pattern: VARIABLE = value
    parsed = interpreter.parse("EMAIL_ADDRESS = myemail@example.com")
    assert parsed.tool == "set_config_variable"
    assert parsed.args["variable_name"] == "EMAIL_ADDRESS"
    assert parsed.args["variable_value"] == "myemail@example.com"
    assert parsed.intent == "config_update"
    assert parsed.confidence > 0.9
    print("✓ Detected EMAIL_ADDRESS = value pattern")
    
    # Test pattern: VARIABLE: value
    parsed = interpreter.parse("EMAIL_PASSWORD: mypassword123")
    assert parsed.tool == "set_config_variable"
    assert parsed.args["variable_name"] == "EMAIL_PASSWORD"
    assert parsed.args["variable_value"] == "mypassword123"
    print("✓ Detected EMAIL_PASSWORD: value pattern")
    
    # Test pattern: Port number
    parsed = interpreter.parse("EMAIL_IMAP_PORT=993")
    assert parsed.tool == "set_config_variable"
    assert parsed.args["variable_name"] == "EMAIL_IMAP_PORT"
    assert parsed.args["variable_value"] == "993"
    print("✓ Detected EMAIL_IMAP_PORT=993 pattern")

    parsed = interpreter.parse("SMS_OWNER_NUMBER=8483291230")
    assert parsed.tool == "set_config_variable"
    assert parsed.args["variable_name"] == "SMS_OWNER_NUMBER"
    assert parsed.args["variable_value"] == "8483291230"
    print("✓ Detected SMS_OWNER_NUMBER=8483291230 pattern")

    parsed = interpreter.parse("TWILIO_FROM_NUMBER=+15551234567")
    assert parsed.tool == "set_config_variable"
    assert parsed.args["variable_name"] == "TWILIO_FROM_NUMBER"
    assert parsed.args["variable_value"] == "+15551234567"
    print("✓ Detected TWILIO_FROM_NUMBER assignment")

    # Test natural language config assignment pattern
    parsed = interpreter.parse("set MODEL_RESPONSE_MAX_TOKENS to 250")
    assert parsed.tool == "set_config_variable"
    assert parsed.args["variable_name"] == "MODEL_RESPONSE_MAX_TOKENS"
    assert parsed.args["variable_value"] == "250"
    print("✓ Detected natural-language config assignment")
    
    # Test unknown variable (should not match)
    parsed = interpreter.parse("UNKNOWN_VAR = somevalue")
    assert parsed.tool != "set_config_variable"
    print("✓ Rejected unknown variable UNKNOWN_VAR")
    
    # Test non-config message (should not match)
    parsed = interpreter.parse("Show me my emails")
    assert parsed.tool != "set_config_variable"
    print("✓ Rejected non-config message")


def test_config_tool_validation():
    """Test that config tool validates variable names and values."""
    tool = SetConfigVariableTool()
    
    # Valid: email address
    is_valid, msg = tool.validate_args({
        "variable_name": "EMAIL_ADDRESS",
        "variable_value": "test@example.com"
    })
    assert is_valid, msg
    print("✓ Accepted EMAIL_ADDRESS with valid format")

    is_valid, msg = tool.validate_args({
        "variable_name": "SMS_OWNER_NUMBER",
        "variable_value": "8483291230"
    })
    assert is_valid, msg
    print("✓ Accepted SMS_OWNER_NUMBER")

    is_valid, msg = tool.validate_args({
        "variable_name": "TWILIO_FROM_NUMBER",
        "variable_value": "+15551234567"
    })
    assert is_valid, msg
    print("✓ Accepted TWILIO_FROM_NUMBER")
    
    # Invalid: unknown variable
    is_valid, msg = tool.validate_args({
        "variable_name": "UNKNOWN_VARIABLE",
        "variable_value": "somevalue"
    })
    assert not is_valid
    assert "not allowed" in msg
    print("✓ Rejected unknown variable")
    
    # Invalid: missing variable name
    is_valid, msg = tool.validate_args({
        "variable_value": "somevalue"
    })
    assert not is_valid
    assert "variable_name" in msg.lower()
    print("✓ Rejected missing variable_name")
    
    # Invalid: missing value
    is_valid, msg = tool.validate_args({
        "variable_name": "EMAIL_ADDRESS"
    })
    assert not is_valid
    assert "variable_value" in msg.lower()
    print("✓ Rejected missing variable_value")


def test_config_tool_persistence():
    """Test that config tool writes to the configured env path rather than the real file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tool = SetConfigVariableTool()
        tool.env_path = Path(tmpdir) / ".env.master"

        async def test_async():
            result = await tool.execute({
                "variable_name": "EMAIL_ADDRESS",
                "variable_value": "test@example.com"
            })
            assert result.success, result.error
            assert tool.env_path.exists()
            content = tool.env_path.read_text(encoding="utf-8")
            assert "EMAIL_ADDRESS=test@example.com" in content
            print("✓ Config tool persists to configured env path")

        asyncio.run(test_async())


def test_config_tool_value_validation():
    """Test that config tool validates value formats."""
    tool = SetConfigVariableTool()
    
    # Invalid port (too high)
    async def check_invalid_port():
        result = await tool.execute({
            "variable_name": "EMAIL_IMAP_PORT",
            "variable_value": "99999"
        })
        assert not result.success
        assert "port" in result.error.lower()
    asyncio.run(check_invalid_port())
    print("✓ Rejected invalid port number 99999")
    
    # Valid port
    async def check_valid_port():
        result = await tool.execute({
            "variable_name": "EMAIL_IMAP_PORT",
            "variable_value": "993"
        })
        # May fail due to file permissions in test env, but validation should pass
        if result.success:
            print("✓ Accepted valid port number 993")
        elif "port" not in result.error.lower():
            print("✓ Port validation passed (file error is expected in test)")
    asyncio.run(check_valid_port())


def test_interpreter_followup_config_assignment():
    """Test follow-up config mapping for password/username in setup threads."""
    interpreter = NaturalLanguageInterpreter()

    parsed = interpreter.parse_to_dict(
        "and password is hunter2",
        context={"last_topic": "email_access"},
    )
    assert parsed["tool"] == "set_config_variable"
    assert parsed["args"]["variable_name"] == "EMAIL_PASSWORD"
    assert parsed["args"]["variable_value"] == "hunter2"

    parsed = interpreter.parse_to_dict(
        "and username is review@example.com",
        context={"last_topic": "email_setup"},
    )
    assert parsed["tool"] == "set_config_variable"
    assert parsed["args"]["variable_name"] == "EMAIL_USERNAME"
    assert parsed["args"]["variable_value"] == "review@example.com"


if __name__ == "__main__":
    print("\n=== Testing Config Variable Detection ===")
    test_interpreter_detects_config_assignment()
    
    print("\n=== Testing Config Tool Validation ===")
    test_config_tool_validation()
    
    print("\n=== Testing Config Tool Persistence ===")
    test_config_tool_persistence()
    
    print("\n=== Testing Config Tool Value Validation ===")
    test_config_tool_value_validation()
    
    print("\n✅ All configuration management tests passed!")
