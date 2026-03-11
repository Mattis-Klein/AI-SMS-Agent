"""Configuration management tools for setting environment variables through chat."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from ...config_loader import ConfigLoader
from ..base import Tool, ToolResult


class SetConfigVariableTool(Tool):
    """
    Set environment variables safely through chat.
    
    Validates variable names and values, then updates mashbak/.env.master with proper persistence.
    Sensitive variables (passwords, keys) are not echoed in output.
    """

    # Allowed configuration variables (whitelist)
    ALLOWED_VARIABLES = {
        # OpenAI / AI Configuration
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        
        # Email Configuration - Canonical names
        "EMAIL_PROVIDER",
        "EMAIL_IMAP_HOST",
        "EMAIL_IMAP_PORT",
        "EMAIL_USERNAME",
        "EMAIL_PASSWORD",
        "EMAIL_MAILBOX",
        "EMAIL_USE_SSL",
        
        # Email Configuration - Alias names
        "IMAP_SERVER",
        "IMAP_PORT",
        "EMAIL_ADDRESS",
        
        # SMS Access Control
        "SMS_OWNER_NUMBER",
        "SMS_ACCESS_REQUEST_NUMBERS",
        "SMS_ACCESS_REQUEST_RESPONSE",
        "SMS_ACCESS_REQUEST_KEYWORD",
        "HERSHY_NUMBER",
        "HERSHY_RESPONSE",
        "REJECTED_NUMBERS",
        "REJECTED_RESPONSE",
        "SMS_DENIAL_RESPONSE",
        "SMS_PHONE_NORMALIZATION_DIGITS",

        # SMS/Bridge Configuration
        "AGENT_API_KEY",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_FROM_NUMBER",
        "BRIDGE_PORT",
        "PUBLIC_BASE_URL",
        "AGENT_URL",
        
        # Desktop/Local Configuration
        "LOCAL_APP_PIN",
        "AGENT_WORKSPACE",

        # Logging/runtime behavior
        "LOG_LEVEL",
        "DEBUG_MODE",
        "SESSION_CONTEXT_MAX_TURNS",
        "TOOL_EXECUTION_TIMEOUT",
        "MODEL_RESPONSE_MAX_TOKENS",
    }

    # Sensitive variables that should not be echoed in logs/responses
    SENSITIVE_VARIABLES = {
        "OPENAI_API_KEY",
        "EMAIL_PASSWORD",
        "EMAIL_PASS",
        "AGENT_API_KEY",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "LOCAL_APP_PIN",
    }

    BRIDGE_RESTART_VARIABLES = {
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_FROM_NUMBER",
        "BRIDGE_PORT",
        "PUBLIC_BASE_URL",
        "AGENT_URL",
        "SMS_OWNER_NUMBER",
        "SMS_ACCESS_REQUEST_NUMBERS",
        "SMS_ACCESS_REQUEST_RESPONSE",
        "SMS_ACCESS_REQUEST_KEYWORD",
        "HERSHY_NUMBER",
        "HERSHY_RESPONSE",
        "REJECTED_NUMBERS",
        "REJECTED_RESPONSE",
        "SMS_DENIAL_RESPONSE",
        "SMS_PHONE_NORMALIZATION_DIGITS",
    }

    AGENT_RESTART_VARIABLES = {
        "AGENT_API_KEY",
    }

    # Validators: variable_name -> (validation_fn, description)
    VALIDATORS = {
        "EMAIL_IMAP_HOST": (
            lambda v: bool(v.strip()),
            "Host cannot be empty"
        ),
        "IMAP_SERVER": (
            lambda v: bool(v.strip()),
            "Host cannot be empty"
        ),
        "EMAIL_IMAP_PORT": (
            lambda v: _validate_port(v),
            "Port must be a number between 1 and 65535"
        ),
        "IMAP_PORT": (
            lambda v: _validate_port(v),
            "Port must be a number between 1 and 65535"
        ),
        "EMAIL_USERNAME": (
            lambda v: bool(v.strip()),
            "Username cannot be empty"
        ),
        "EMAIL_ADDRESS": (
            lambda v: bool(v.strip()),
            "Email address cannot be empty"
        ),
        "EMAIL_PASSWORD": (
            lambda v: bool(v.strip()),
            "Password cannot be empty"
        ),
        "EMAIL_MAILBOX": (
            lambda v: bool(v.strip()),
            "Mailbox name cannot be empty"
        ),
        "EMAIL_USE_SSL": (
            lambda v: v.lower() in {"true", "false", "1", "0", "yes", "no"},
            "Must be true/false"
        ),
        "LOCAL_APP_PIN": (
            lambda v: _validate_pin(v),
            "PIN must be 4-8 digits"
        ),
        "OPENAI_MODEL": (
            lambda v: bool(v.strip()),
            "Model name cannot be empty"
        ),
        "SMS_PHONE_NORMALIZATION_DIGITS": (
            lambda v: str(v).strip().isdigit() and 4 <= int(str(v).strip()) <= 15,
            "Must be an integer between 4 and 15"
        ),
        "SESSION_CONTEXT_MAX_TURNS": (
            lambda v: str(v).strip().isdigit() and int(str(v).strip()) >= 1,
            "Must be an integer >= 1"
        ),
        "TOOL_EXECUTION_TIMEOUT": (
            lambda v: _validate_positive_number(v),
            "Must be a positive number"
        ),
        "MODEL_RESPONSE_MAX_TOKENS": (
            lambda v: str(v).strip().isdigit() and int(str(v).strip()) >= 64,
            "Must be an integer >= 64"
        ),
        "BRIDGE_PORT": (
            lambda v: _validate_port(v),
            "Port must be a number between 1 and 65535"
        ),
        "LOG_LEVEL": (
            lambda v: str(v).strip().upper() in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"},
            "Must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL"
        ),
        "DEBUG_MODE": (
            lambda v: str(v).strip().lower() in {"true", "false", "1", "0", "yes", "no"},
            "Must be true/false"
        ),
    }

    def __init__(self):
        super().__init__(
            name="set_config_variable",
            description="Set environment configuration variables through chat. "
                       "Supports EMAIL_*, SMS_*, Twilio, URLs, ports, and other config settings. "
                       "Values are validated and safely persisted to mashbak/.env.master.",
            requires_args=True
        )
        self.env_path = self._get_env_path()

    def _get_env_path(self) -> Path:
        """Get path to master .env.master file in project root."""
        script_dir = Path(__file__).parent.parent.parent.parent  # agent/ -> mashbak/
        env_file = script_dir / ".env.master"
        return env_file

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        """Validate required arguments."""
        if "variable_name" not in args:
            return False, "Missing 'variable_name' argument"
        if "variable_value" not in args:
            return False, "Missing 'variable_value' argument"
        
        var_name = str(args["variable_name"]).strip()
        if not var_name:
            return False, "Variable name cannot be empty"
        
        if var_name not in self.ALLOWED_VARIABLES:
            allowed_list = ", ".join(sorted(self.ALLOWED_VARIABLES))
            return False, f"Variable '{var_name}' is not allowed. Allowed variables: {allowed_list}"
        
        return True, ""

    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        """
        Set a configuration variable and persist it to .env.master.
        
        Args:
            args: Must contain 'variable_name' and 'variable_value'
            context: Optional additional context
            
        Returns:
            ToolResult with success/failure and appropriate message
        """
        var_name = str(args["variable_name"]).strip()
        var_value = str(args["variable_value"]).strip()
        
        # Validate arguments
        valid, error_msg = self.validate_args(args)
        if not valid:
            return ToolResult(
                success=False,
                output="",
                error=error_msg,
                error_type="validation_failure",
                tool_name=self.name,
                arguments=args,
            )
        
        # Validate value format if validator exists
        if var_name in self.VALIDATORS:
            validator, description = self.VALIDATORS[var_name]
            if not validator(var_value):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Invalid value for {var_name}: {description}",
                    error_type="validation_failure",
                    tool_name=self.name,
                    arguments=args,
                )
        
        # Check if value is empty
        if not var_value:
            return ToolResult(
                success=False,
                output="",
                error=f"Value for {var_name} cannot be empty",
                error_type="validation_failure",
                tool_name=self.name,
                arguments=args,
            )
        
        # Try to update .env.master file
        try:
            self._update_env_file(var_name, var_value)
            ConfigLoader.load(reload=True)

            restart_required: list[str] = []
            if var_name in self.BRIDGE_RESTART_VARIABLES:
                restart_required.append("sms_bridge")
            if var_name in self.AGENT_RESTART_VARIABLES:
                restart_required.append("agent_auth")
            pending_restart = bool(restart_required)
            
            # Build output message (don't echo sensitive values)
            if var_name in self.SENSITIVE_VARIABLES:
                output = f"Configuration updated: {var_name} has been set."
            else:
                output = f"Configuration updated: {var_name} = {var_value}"

            if pending_restart:
                output += f"\n\nPending restart required for: {', '.join(restart_required)}."
            else:
                output += "\n\nApplied to the backend runtime now."
            
            return ToolResult(
                success=True,
                output=output,
                tool_name=self.name,
                arguments={"variable_name": var_name},  # Don't include value in result
                data={
                    "variable_name": var_name,
                    "applied_live": not pending_restart,
                    "restart_required": restart_required,
                },
            )
        
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to update configuration: {str(e)}",
                error_type="execution_failure",
                tool_name=self.name,
                arguments=args,
            )

    def _update_env_file(self, var_name: str, var_value: str) -> None:
        """
        Update or append variable to .env file.
        
        Preserves existing comments and unrelated variables.
        """
        env_path = self.env_path
        
        # Create .env if it doesn't exist
        if not env_path.exists():
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.write_text(f"{var_name}={_format_env_value(var_value)}\n", encoding="utf-8")
            return
        
        # Read existing content
        try:
            content = env_path.read_text(encoding="utf-8")
        except Exception as e:
            raise ValueError(f"Could not read .env file: {e}")
        
        lines = content.split("\n")
        updated = False
        new_lines = []
        
        # Look for existing variable and update it
        for line in lines:
            # Check if this line defines our variable
            match = re.match(rf"^\s*(?:export\s+)?{re.escape(var_name)}\s*=", line)
            if match:
                new_lines.append(f"{var_name}={_format_env_value(var_value)}")
                updated = True
            else:
                new_lines.append(line)
        
        # If not found, append to end
        if not updated:
            # Remove trailing empty lines
            while new_lines and not new_lines[-1].strip():
                new_lines.pop()
            # Add blank line if content exists
            if new_lines:
                new_lines.append("")
            new_lines.append(f"{var_name}={_format_env_value(var_value)}")
        
        # Write back
        new_content = "\n".join(new_lines)
        if not new_content.endswith("\n"):
            new_content += "\n"
        
        try:
            env_path.write_text(new_content, encoding="utf-8")
        except Exception as e:
            raise ValueError(f"Could not write .env file: {e}")


def _validate_port(value: str) -> bool:
    """Validate port number."""
    try:
        port = int(value.strip())
        return 1 <= port <= 65535
    except (ValueError, AttributeError):
        return False


def _validate_pin(value: str) -> bool:
    """Validate PIN (4-8 digits)."""
    return bool(re.match(r"^\d{4,8}$", value.strip()))


def _validate_positive_number(value: str) -> bool:
    try:
        return float(str(value).strip()) > 0
    except (TypeError, ValueError):
        return False


def _format_env_value(value: str) -> str:
    """Quote dotenv values only when needed to preserve characters safely."""
    text = str(value)
    if text == "":
        return '""'

    needs_quotes = (
        text != text.strip()
        or "#" in text
        or "\n" in text
        or "\r" in text
        or any(ch.isspace() for ch in text)
        or text.startswith(('"', "'"))
    )
    if not needs_quotes:
        return text

    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
