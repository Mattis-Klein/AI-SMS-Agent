import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.voice_handler import create_voice_router
from agent.config_loader import ConfigLoader


class _FakeLogger:
    def __init__(self):
        self.events = []

    def log(self, **kwargs):
        self.events.append(("log", kwargs))

    def log_error(self, **kwargs):
        self.events.append(("error", kwargs))


class _FakeRuntime:
    def __init__(self):
        self.logger = _FakeLogger()
        self.calls = []
        self.raise_error = False

    async def execute_nl(self, *, message, sender, request_id, source, owner_unlocked):
        self.calls.append(
            {
                "message": message,
                "sender": sender,
                "request_id": request_id,
                "source": source,
                "owner_unlocked": owner_unlocked,
            }
        )
        if self.raise_error:
            raise RuntimeError("voice runtime test failure")
        return {
            "success": True,
            "tool_name": "current_time",
            "output": "It is 9:08 PM.",
            "assistant_reply": "It is 9:08 PM.",
            "trace": {
                "selected_tool": "current_time",
                "execution_status": "success",
            },
        }


def _with_no_twilio_token(monkeypatch):
    original = ConfigLoader.get

    def _fake_get(cls, key, default=""):
        if key == "TWILIO_AUTH_TOKEN":
            return ""
        return original(key, default)

    monkeypatch.setattr(ConfigLoader, "get", classmethod(_fake_get))


def _build_client(runtime):
    app = FastAPI()
    app.include_router(create_voice_router(runtime))
    return TestClient(app)


def test_voice_endpoint_answers_and_starts_gather(monkeypatch):
    _with_no_twilio_token(monkeypatch)
    runtime = _FakeRuntime()
    client = _build_client(runtime)

    response = client.post(
        "/voice",
        data={
            "CallSid": "CA123",
            "From": "+15551230000",
            "To": "+15550009999",
        },
    )

    assert response.status_code == 200
    xml = response.text
    assert "Hello, this is Mashbak" in xml
    assert "<Gather" in xml
    assert "/process_voice" in xml


def test_process_voice_blank_input_reprompts(monkeypatch):
    _with_no_twilio_token(monkeypatch)
    runtime = _FakeRuntime()
    client = _build_client(runtime)

    response = client.post(
        "/process_voice",
        data={
            "CallSid": "CAblank",
            "From": "+15551230000",
            "To": "+15550009999",
            "SpeechResult": "",
        },
    )

    assert response.status_code == 200
    xml = response.text
    assert "did not hear anything" in xml.lower()
    assert "<Gather" in xml
    assert not runtime.calls


def test_process_voice_runs_runtime_and_continues_loop(monkeypatch):
    _with_no_twilio_token(monkeypatch)
    runtime = _FakeRuntime()
    client = _build_client(runtime)

    response = client.post(
        "/process_voice",
        data={
            "CallSid": "CAloop",
            "From": "+15551230000",
            "To": "+15550009999",
            "SpeechResult": "what time is it",
            "Confidence": "0.92",
        },
    )

    assert response.status_code == 200
    assert runtime.calls
    assert runtime.calls[0]["message"] == "what time is it"
    assert runtime.calls[0]["source"] == "voice"
    xml = response.text
    assert "It is 9:08 PM" in xml
    assert "What would you like to do next" in xml
    assert "<Gather" in xml


def test_process_voice_runtime_error_recovers(monkeypatch):
    _with_no_twilio_token(monkeypatch)
    runtime = _FakeRuntime()
    runtime.raise_error = True
    client = _build_client(runtime)

    response = client.post(
        "/process_voice",
        data={
            "CallSid": "CAerr",
            "From": "+15551230000",
            "To": "+15550009999",
            "SpeechResult": "create a folder called days on my desktop",
            "Confidence": "0.94",
        },
    )

    assert response.status_code == 200
    xml = response.text
    assert "hit an error" in xml.lower()
    assert "<Gather" in xml
