import asyncio
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from assistants.bucherim.service import BucherimService, BucherimSmsRequest


def make_service(tmp_path: Path, allowlist: list[str] | None = None) -> BucherimService:
    service = BucherimService(
        base_dir=tmp_path,
        openai_api_key="",
        openai_model="gpt-4.1-mini",
        session_turns=4,
    )
    config = {
        "assistant_number": "+18772683048",
        "allowlist": allowlist or [],
        "blocked_numbers": [],
        "responses": {
            "welcome": "Welcome to Bucherim. You are now connected and can start asking questions.",
            "not_approved": "You are not currently approved for Bucherim. Text join@bucherim to request access.",
            "join_ack": "Your request to join Bucherim has been received and will be reviewed.",
            "already_active": "You are already connected to Bucherim. Ask me anything.",
            "not_member": "You are not currently a Bucherim member. Text @bucherim if approved, or join@bucherim to request access.",
            "blocked": "Your access to Bucherim is currently blocked. Text join@bucherim to request a review.",
            "media_unavailable": "I received your media, but image analysis is not enabled yet. Please describe what you need in text.",
            "image_generation_unavailable": "I can discuss images, but outbound image generation is not enabled yet.",
        },
    }
    config_path = tmp_path / "assistants" / "bucherim" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
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

        result = run_request(service, "+1 212-555-0101", "@bucherim")
        assert result["status"] == "active"
        assert "connected" in result["reply"].lower()

        user_dir = root / "data" / "users" / "bucherim" / "p12125550101"
        membership = load_json(user_dir / "membership.json")
        assert membership["status"] == "active"
        assert membership["source"] == "allowlist"


def test_non_allowlisted_join_command_rejected_with_instructions():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        service = make_service(root, allowlist=[])

        result = run_request(service, "+1 646-555-0202", "@bucherim")
        assert result["status"] == "rejected"
        assert "join@bucherim" in result["reply"].lower()


def test_non_allowlisted_join_request_logged_and_acknowledged():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        service = make_service(root, allowlist=[])

        result = run_request(service, "+1 718-555-0303", "join@bucherim")
        assert result["status"] == "pending_request"
        assert "received" in result["reply"].lower()

        user_dir = root / "data" / "users" / "bucherim" / "p17185550303"
        membership = load_json(user_dir / "membership.json")
        assert membership["status"] == "pending_request"

        request_rows = load_jsonl(user_dir / "requests.jsonl")
        assert request_rows
        assert request_rows[-1]["review_state"] == "pending"

        pending_rows = load_jsonl(root / "data" / "users" / "bucherim" / "pending_requests.jsonl")
        assert pending_rows
        assert pending_rows[-1]["phone_number"] == "+17185550303"


def test_active_member_normal_message_is_processed_and_appended():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        service = make_service(root, allowlist=["+12125550404"])

        join_result = run_request(service, "+1 212-555-0404", "@bucherim")
        assert join_result["status"] == "active"

        message_result = run_request(service, "+1 212-555-0404", "hello bucherim")
        assert message_result["status"] == "active"
        assert message_result["response_mode"] == "text"

        user_dir = root / "data" / "users" / "bucherim" / "p12125550404"
        rows = load_jsonl(user_dir / "conversation.jsonl")
        assert len(rows) >= 4
        assert rows[-2]["direction"] == "inbound"
        assert rows[-1]["direction"] == "outbound"


def test_non_member_normal_message_is_blocked():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        service = make_service(root, allowlist=[])

        result = run_request(service, "+1 332-555-0505", "what is quantum mechanics")
        assert result["status"] in {"unknown", "rejected", "pending_request", "allowlisted", "blocked"}
        assert result["response_mode"] == "not_authorized"
        assert "join@bucherim" in result["reply"].lower()


def test_context_preserved_with_membership_and_response_metadata():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        service = make_service(root, allowlist=["+12125550808"])

        run_request(service, "+1 212-555-0808", "@bucherim")
        run_request(service, "+1 212-555-0808", "hello")
        run_request(service, "+1 212-555-0808", "and what about tomorrow?")

        snapshot = service.session_context.get_snapshot("bucherim:12125550808")
        assert snapshot["last_intent"] == "conversation"
        assert snapshot["last_topic"] is not None
        assert snapshot["last_entities"]["membership_status"] == "active"
        assert snapshot["last_entities"]["last_response_type"] == "text"
        assert snapshot["last_entities"]["last_media_presence"] is False
        assert len(snapshot["recent_turns"]) >= 2


def test_phone_normalization_to_e164_and_user_key():
    assert BucherimService.normalize_phone_e164("+1 (848) 329-1230") == "+18483291230"
    assert BucherimService.normalize_phone_e164("18483291230") == "+18483291230"
    assert BucherimService.normalize_phone_e164("8483291230") == "+18483291230"
    assert BucherimService.phone_to_user_key("+18483291230") == "p18483291230"


def test_user_files_created_and_conversation_appends():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        service = make_service(root, allowlist=["+17185550606"])

        run_request(service, "+1 718-555-0606", "@bucherim")
        run_request(service, "+1 718-555-0606", "first message")
        run_request(service, "+1 718-555-0606", "second message")

        user_dir = root / "data" / "users" / "bucherim" / "p17185550606"
        assert (user_dir / "profile.json").exists()
        assert (user_dir / "membership.json").exists()
        assert (user_dir / "conversation.jsonl").exists()
        assert (root / "data" / "media" / "bucherim" / "p17185550606").exists()

        rows = load_jsonl(user_dir / "conversation.jsonl")
        assert len(rows) >= 6


def test_media_references_are_logged_when_present():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        service = make_service(root, allowlist=["+16465550707"])

        run_request(service, "+1 646-555-0707", "@bucherim")
        result = run_request(
            service,
            "+1 646-555-0707",
            "what do you see in this image?",
            media=[{"url": "https://example.com/image.jpg", "content_type": "image/jpeg"}],
        )

        assert result["response_mode"] == "image_analysis_unavailable"
        user_dir = root / "data" / "users" / "bucherim" / "p16465550707"
        media_rows = load_jsonl(root / "data" / "media" / "bucherim" / "p16465550707" / "index.jsonl")
        assert media_rows
        assert media_rows[-1]["media_url"] == "https://example.com/image.jpg"
        assert media_rows[-1]["download_status"] == "referenced_only"
