import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.runtime import create_runtime


def test_openai_runtime_settings_loaded_from_config(monkeypatch):
    monkeypatch.setenv("AGENT_API_KEY", "test-agent-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example-openai.local/v1")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "41")
    monkeypatch.setenv("OPENAI_TEMPERATURE", "0.9")

    runtime = create_runtime(Path(__file__).resolve().parent.parent)
    runtime.reload_dynamic_config()

    assert runtime.openai_base_url == "https://example-openai.local/v1"
    assert runtime.openai_timeout_seconds == 41.0
    assert runtime.openai_temperature == 0.9

    assert runtime.assistant.model_client.base_url == "https://example-openai.local/v1"
    assert runtime.assistant.model_client.timeout_seconds == 41.0
    assert runtime.assistant.model_client.temperature == 0.9
