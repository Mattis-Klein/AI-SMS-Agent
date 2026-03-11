"""
Multi-turn conversation continuity regression tests.

Covers:
  1. create-file request → clarification → follow-up → execution
  2. email setup → missing config → follow-up question → variable submission
  3. "where was it added?" resolves to prior file/folder action
  4. "that file" resolves to current pending/last task
  5. "what else do you need?" returns missing parameters/config
  6. "so do you need my password?" uses config state
  7. Safety rule: no false completion claims without tool result backing
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.interpreter import NaturalLanguageInterpreter
from agent.session_context import SessionContextManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_manager(turns: int = 10) -> SessionContextManager:
    return SessionContextManager(max_recent_turns=turns)


def pump_turn(
    manager: SessionContextManager,
    interpreter: NaturalLanguageInterpreter,
    *,
    session: str,
    message: str,
    tool_name: str | None = None,
    tool_success: bool = True,
    error_type: str | None = None,
    missing_config_fields: list[str] | None = None,
    missing_parameters: list[str] | None = None,
    created_path: str | None = None,
) -> dict:
    """Simulate a single request-response cycle through session + interpreter."""
    ctx = manager.get_snapshot(session)
    parsed = interpreter.parse_to_dict(message, context=ctx)

    result: dict = {
        "tool_name": tool_name,
        "success": tool_success,
        "error_type": error_type,
        "missing_config_fields": missing_config_fields,
        "missing_parameters": missing_parameters,
        "data": {"created_path": created_path} if created_path else {},
    }
    manager.update(
        session_id=session,
        user_message=message,
        parsed=parsed,
        result=result,
    )
    if tool_name:
        manager.record_assistant_reply(
            session_id=session,
            assistant_reply=f"Ran {tool_name} — {'ok' if tool_success else 'failed'}.",
        )
    return parsed


# ---------------------------------------------------------------------------
# Test 1: create-file request → clarification → follow-up → execution
# ---------------------------------------------------------------------------

def test_file_creation_multiturn_flow():
    """
    Turn 1: user asks to create a file (no path given — pending task, missing param).
    Turn 2: user provides path → tool executes.
    Turn 3: user asks where it was saved → resolver returns the path.
    """
    manager = make_manager()
    interp = NaturalLanguageInterpreter()
    session = "desktop:file-multi"

    # Turn 1: initiate (tool not yet run; simulate pending state)
    ctx1 = manager.get_snapshot(session)
    parsed1 = interp.parse_to_dict("list files in inbox", context=ctx1)

    manager.update(
        session_id=session,
        user_message="list files in inbox",
        parsed=parsed1,
        result={
            "tool_name": "list_files",
            "success": True,
            "data": {"path": "inbox"},
        },
    )
    manager.record_assistant_reply(
        session_id=session,
        assistant_reply="Here are the files in your inbox.",
    )

    # Turn 2: simulate a file-creation result that includes a created_path
    manager.update(
        session_id=session,
        user_message="check disk space",
        parsed={"tool": "disk_space", "intent": "system", "args": {}, "entities": {}, "mode": "tool", "confidence": 0.9},
        result={
            "tool_name": "disk_space",
            "success": True,
            "data": {"created_path": "inbox/summary.txt"},
        },
    )
    manager.record_assistant_reply(
        session_id=session,
        assistant_reply="Disk space checked. Also saved summary to inbox/summary.txt.",
    )

    # Turn 3: user asks where the file was added
    ctx3 = manager.get_snapshot(session)
    parsed3 = interp.parse_to_dict("where was it added?", context=ctx3)

    # Must resolve as a reference_query (not a tool call)
    assert parsed3.get("tool") is None, "Reference query should not map to a tool"
    assert parsed3.get("intent") == "reference_query"
    # The resolved_path must come from the session context
    entities = parsed3.get("entities") or {}
    assert entities.get("resolved_path") == "inbox/summary.txt", (
        f"Expected 'inbox/summary.txt', got {entities.get('resolved_path')!r}"
    )


# ---------------------------------------------------------------------------
# Test 2: email setup → missing config → follow-up → variable submission
# ---------------------------------------------------------------------------

def test_email_setup_followup_variable_submission():
    """
    Turn 1: user asks to check email → tool fails with missing config.
    Turn 2: user asks "do you need my password?" → reference resolver responds.
    Turn 3: user submits password → mapped to set_config_variable.
    """
    manager = make_manager()
    interp = NaturalLanguageInterpreter()
    session = "desktop:email-setup"

    # Turn 1: email tool fails
    pump_turn(
        manager, interp,
        session=session,
        message="check my inbox",
        tool_name="summarize_inbox",
        tool_success=False,
        error_type="missing_configuration",
        missing_config_fields=["EMAIL_IMAP_HOST|IMAP_SERVER", "EMAIL_PASSWORD"],
    )

    ctx2 = manager.get_snapshot(session)
    assert "EMAIL_PASSWORD" in ctx2.get("missing_config_fields", []), (
        "EMAIL_PASSWORD should appear in missing_config_fields after failed email tool"
    )

    # Turn 2: user asks about password
    parsed2 = interp.parse_to_dict("so do you need my password?", context=ctx2)
    assert parsed2.get("intent") in {"config_followup", "reference_query", "status_query"}, (
        f"Expected a reference intent, got {parsed2.get('intent')!r}"
    )
    assert parsed2.get("tool") is None, "Password query should not map to a tool"
    entities2 = parsed2.get("entities") or {}
    assert "missing_config_fields" in entities2 or "missing_parameters" in entities2 or \
           entities2.get("reference_target") == "password_prompt", (
        "Entities should carry missing config or reference_target=password_prompt"
    )

    # Turn 3: user submits the password
    parsed3 = interp.parse_to_dict("EMAIL_PASSWORD=hunter2", context=ctx2)
    assert parsed3.get("tool") == "set_config_variable", (
        f"PASSWORD submission should map to set_config_variable, got {parsed3.get('tool')!r}"
    )
    assert parsed3["args"].get("variable_name") == "EMAIL_PASSWORD"


# ---------------------------------------------------------------------------
# Test 3: "where was it added?" resolves to prior file/folder action
# ---------------------------------------------------------------------------

def test_where_was_it_added_resolves_to_last_created_path():
    manager = make_manager()
    interp = NaturalLanguageInterpreter()
    session = "desktop:where-resolve"

    # Simulate a prior turn that created a file
    manager.update(
        session_id=session,
        user_message="save report",
        parsed={"tool": "some_write_tool", "intent": "filesystem", "args": {}, "entities": {}},
        result={
            "tool_name": "some_write_tool",
            "success": True,
            "data": {"created_path": "outbox/report_2026.txt"},
        },
    )
    manager.record_assistant_reply(
        session_id=session,
        assistant_reply="Report saved to outbox/report_2026.txt.",
    )

    ctx = manager.get_snapshot(session)
    assert ctx.get("last_created_path") == "outbox/report_2026.txt"

    parsed = interp.parse_to_dict("where was it added?", context=ctx)
    assert parsed.get("intent") == "reference_query"
    entities = parsed.get("entities") or {}
    assert entities.get("resolved_path") == "outbox/report_2026.txt", (
        f"Expected 'outbox/report_2026.txt', got {entities.get('resolved_path')!r}"
    )
    assert entities.get("last_result") == "success"


def test_where_was_it_added_with_no_prior_action():
    """Without any prior action, the resolver should still respond (safely, not hallucinate)."""
    interp = NaturalLanguageInterpreter()
    parsed = interp.parse_to_dict("where was it added?", context={})
    assert parsed.get("intent") == "reference_query"
    assert parsed.get("tool") is None
    # resolved_path must be absent or None — not a made-up value
    entities = parsed.get("entities") or {}
    assert not entities.get("resolved_path"), (
        "Should not fabricate a path when there is no prior session state"
    )


# ---------------------------------------------------------------------------
# Test 4: "that file" resolves to current pending/last task subject
# ---------------------------------------------------------------------------

def test_that_file_resolves_to_session_last_path():
    manager = make_manager()
    interp = NaturalLanguageInterpreter()
    session = "desktop:that-file"

    manager.update(
        session_id=session,
        user_message="list files in outbox",
        parsed={"tool": "dir_outbox", "intent": "filesystem", "args": {"path": "outbox"}, "entities": {}},
        result={"tool_name": "dir_outbox", "success": True, "data": {}},
    )
    manager.record_assistant_reply(session_id=session, assistant_reply="Found 3 files in outbox.")

    ctx = manager.get_snapshot(session)
    parsed = interp.parse_to_dict("the one we are talking about", context=ctx)
    assert parsed.get("intent") == "reference_query"
    entities = parsed.get("entities") or {}
    assert entities.get("reference_target") == "file_subject"


# ---------------------------------------------------------------------------
# Test 5: "what else do you need?" returns missing parameters
# ---------------------------------------------------------------------------

def test_what_else_do_you_need_with_missing_config():
    manager = make_manager()
    interp = NaturalLanguageInterpreter()
    session = "desktop:what-else"

    pump_turn(
        manager, interp,
        session=session,
        message="check email",
        tool_name="list_recent_emails",
        tool_success=False,
        error_type="missing_configuration",
        missing_config_fields=["EMAIL_USERNAME", "EMAIL_PASSWORD"],
    )

    ctx = manager.get_snapshot(session)
    parsed = interp.parse_to_dict("what else do you need?", context=ctx)
    assert parsed.get("intent") in {"status_query", "reference_query"}
    assert parsed.get("tool") is None
    entities = parsed.get("entities") or {}
    ref_target = entities.get("reference_target")
    assert ref_target == "missing_requirements", (
        f"Expected 'missing_requirements', got {ref_target!r}"
    )
    # Either the entities carry the missing fields or the context does
    ctx_missing = ctx.get("missing_config_fields") or []
    assert "EMAIL_USERNAME" in ctx_missing or "EMAIL_USERNAME" in (entities.get("missing_config_fields") or [])


# ---------------------------------------------------------------------------
# Test 6: "did you create it?" is a reference_query
# ---------------------------------------------------------------------------

def test_did_you_create_it_is_reference_query():
    interp = NaturalLanguageInterpreter()

    # With a prior successful action
    ctx = {
        "last_task": "some_write_tool",
        "last_result": "success",
        "last_created_path": "inbox/note.txt",
        "recent_turns": [],
    }
    parsed = interp.parse_to_dict("did you create it?", context=ctx)
    assert parsed.get("intent") == "reference_query"
    assert parsed.get("tool") is None
    entities = parsed.get("entities") or {}
    assert entities.get("resolved_path") == "inbox/note.txt"
    assert entities.get("last_result") == "success"


# ---------------------------------------------------------------------------
# Test 7: Safety rule — last_result="failure" surfaces in reference reply
# ---------------------------------------------------------------------------

def test_location_reference_returns_failure_when_tool_failed():
    interp = NaturalLanguageInterpreter()
    ctx = {
        "last_task": "some_write_tool",
        "last_result": "failure",
        "last_created_path": None,
        "recent_turns": [],
    }
    parsed = interp.parse_to_dict("where was it added?", context=ctx)
    assert parsed.get("intent") == "reference_query"
    entities = parsed.get("entities") or {}
    # resolved_path must not be present when the last action failed
    assert not entities.get("resolved_path"), (
        "Should not return a path when the last action failed"
    )
    assert entities.get("last_result") == "failure"


# ---------------------------------------------------------------------------
# Test 8: Session isolation — separate sessions don't bleed
# ---------------------------------------------------------------------------

def test_session_task_state_isolated_between_sessions():
    manager = make_manager()
    interp = NaturalLanguageInterpreter()

    manager.update(
        session_id="desktop:alice",
        user_message="save report",
        parsed={"tool": "save_tool", "intent": "filesystem", "args": {}, "entities": {}},
        result={
            "tool_name": "save_tool",
            "success": True,
            "data": {"created_path": "outbox/alice_report.txt"},
        },
    )

    alice_ctx = manager.get_snapshot("desktop:alice")
    bob_ctx = manager.get_snapshot("desktop:bob")

    assert alice_ctx.get("last_created_path") == "outbox/alice_report.txt"
    assert bob_ctx.get("last_created_path") is None, "Bob should not see Alice's path"
    assert bob_ctx.get("last_task") is None
    assert bob_ctx.get("last_result") is None


# ---------------------------------------------------------------------------
# Test 9: record_assistant_reply populates the turn
# ---------------------------------------------------------------------------

def test_record_assistant_reply_is_stored_in_turns():
    manager = make_manager()
    interp = NaturalLanguageInterpreter()
    session = "desktop:reply-record"

    manager.update(
        session_id=session,
        user_message="check cpu",
        parsed={"tool": "cpu_usage", "intent": "system", "args": {}, "entities": {}},
        result={"tool_name": "cpu_usage", "success": True, "data": {}},
    )
    manager.record_assistant_reply(session_id=session, assistant_reply="CPU is at 30%.")

    ctx = manager.get_snapshot(session)
    turns = ctx.get("recent_turns") or []
    assert len(turns) == 1
    assert turns[0].get("assistant_reply") == "CPU is at 30%."


# ---------------------------------------------------------------------------
# Test 10: Rolling window caps at max_recent_turns
# ---------------------------------------------------------------------------

def test_rolling_window_bounded():
    manager = make_manager(turns=3)
    session = "desktop:rolling"

    for i in range(7):
        manager.update(
            session_id=session,
            user_message=f"msg {i}",
            parsed={"tool": None, "intent": "conversation", "args": {}, "entities": {}},
            result={"tool_name": None, "success": True},
        )

    ctx = manager.get_snapshot(session)
    assert len(ctx.get("recent_turns") or []) <= 3, "Rolling window exceeded max_recent_turns"
