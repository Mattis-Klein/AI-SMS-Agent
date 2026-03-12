import asyncio
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from assistants.bucherim.bucherim_service import BucherimService, BucherimSmsRequest
from assistants.bucherim.storage import BucherimStorage


def make_service(tmp_path: Path, allowlist: list[str] | None = None) -> BucherimService:
    service = BucherimService(
        base_dir=tmp_path,
        openai_api_key="",
        openai_model="gpt-4.1-mini",
        session_turns=4,
    )
    storage = BucherimStorage(base_dir=tmp_path)
    for number in allowlist or []:
        storage.add_approved_number(number)
    return service


def run_request(service: BucherimService, sender: str, body: str, media: list[dict] | None = None) -> dict:
    req = BucherimSmsRequest(
        sender=sender,
        recipient="+18772683048",
        body=body,
        request_id="test-request",
        message_sid="SM123",
        account_sid="AC123",
        media=media or [],
    )
    return asyncio.run(service.process_sms(req))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def test_allowlisted_number_join_command_becomes_active():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        service = make_service(root, allowlist=["+1 (212) 555-0101"])

        result = run_request(service, "+1 212-555-0101", "hello")
        assert result["status"] == "approved"
        assert result["response_mode"] == "approved_ai"
        assert result["reply"]


def test_non_allowlisted_join_command_rejected_with_instructions():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        service = make_service(root, allowlist=[])

        result = run_request(service, "+1 646-555-0202", "@bucherim")
        assert result["status"] == "unknown"
        assert result["response_mode"] == "not_approved"
        assert result["reply"] == "You are not currently approved for Bucherim. Text join@bucherim to request access."


def test_non_allowlisted_join_request_logged_and_acknowledged():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        service = make_service(root, allowlist=[])

        result = run_request(service, "+1 718-555-0303", "join@bucherim")
        assert result["status"] == "pending"
        assert "received" in result["reply"].lower()

        pending_payload = load_json(root / "assistants" / "bucherim" / "config" / "pending_requests.json")
        assert pending_payload["requests"]
        assert pending_payload["requests"][-1]["phone_number"] == "+17185550303"


def test_active_member_normal_message_is_processed_and_appended():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        service = make_service(root, allowlist=["+12125550404"])

        message_result = run_request(service, "+1 212-555-0404", "hello bucherim")
        assert message_result["status"] == "approved"
        assert message_result["response_mode"] == "approved_ai"

        user_dir = root / "assistants" / "bucherim" / "logs" / "users" / "+12125550404"
        rows = load_jsonl(user_dir / "messages.jsonl")
        assert len(rows) >= 2
        assert rows[-2]["direction"] == "inbound"
        assert rows[-1]["direction"] == "outbound"


def test_non_member_normal_message_is_blocked():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        service = make_service(root, allowlist=[])

        result = run_request(service, "+1 332-555-0505", "what is quantum mechanics")
        assert result["status"] == "unknown"
        assert result["response_mode"] == "access_restricted"
        assert result["reply"] == "Access restricted. Text join@bucherim to request access."


def test_blocked_number_gets_blocked_response():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        service = make_service(root, allowlist=[])
        storage = BucherimStorage(base_dir=root)
        storage.add_blocked_number("+1 917-555-4444")

        result = run_request(service, "+1 917-555-4444", "hello")
        assert result["status"] == "blocked"
        assert result["response_mode"] == "blocked"
        assert "blocked" in result["reply"].lower()


def test_phone_normalization_to_e164_and_user_key():
    assert BucherimService.normalize_phone_e164("+1 (848) 329-1230") == "+18483291230"
    assert BucherimService.normalize_phone_e164("18483291230") == "+18483291230"
    assert BucherimService.normalize_phone_e164("8483291230") == "+18483291230"
    assert BucherimService.phone_to_user_key("+18483291230") == "+18483291230"


def test_user_files_created_and_conversation_appends():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        service = make_service(root, allowlist=["+17185550606"])

        run_request(service, "+1 718-555-0606", "first message")
        run_request(service, "+1 718-555-0606", "second message")

        user_dir = root / "assistants" / "bucherim" / "logs" / "users" / "+17185550606"
        assert (user_dir / "profile.json").exists()
        assert (user_dir / "messages.jsonl").exists()

        rows = load_jsonl(user_dir / "messages.jsonl")
        assert len(rows) >= 4


def test_media_references_are_logged_when_present():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        service = make_service(root, allowlist=["+16465550707"])

        result = run_request(
            service,
            "+1 646-555-0707",
            "what do you see in this image?",
            media=[{"url": "https://example.com/image.jpg", "content_type": "image/jpeg"}],
        )

        assert result["response_mode"] == "approved_ai"
        user_dir = root / "assistants" / "bucherim" / "logs" / "users" / "+16465550707"
        rows = load_jsonl(user_dir / "messages.jsonl")
        assert rows[-2]["direction"] == "inbound"
        assert rows[-2]["media"][0]["url"] == "https://example.com/image.jpg"
