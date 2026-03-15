"""Twilio voice webhook layer for Mashbak backend runtime."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Form, Request, Response
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Gather, VoiceResponse

if __package__:
    from .config_loader import ConfigLoader
else:
    from config_loader import ConfigLoader


def create_voice_router(runtime) -> APIRouter:
    router = APIRouter(tags=["voice"])

    @router.post("/voice", name="voice_webhook")
    async def voice_webhook(
        request: Request,
        call_sid: str = Form(default=""),
        from_number: str = Form(default="", alias="From"),
        to_number: str = Form(default="", alias="To"),
    ):
        request_id = f"voice-{str(uuid.uuid4())[:8]}"

        if not await _is_valid_twilio_request(request):
            runtime.logger.log_error(
                request_id=request_id,
                error_type="voice_invalid_signature",
                error_message="Rejected voice webhook with invalid Twilio signature",
                source="voice",
                call_sid=call_sid or None,
                from_number=from_number or None,
            )
            response = VoiceResponse()
            response.say("Sorry, I cannot verify this call request.", voice="alice", language="en-US")
            return Response(content=str(response), media_type="application/xml", status_code=403)

        runtime.logger.log(
            request_id=request_id,
            event_type="voice_inbound_call",
            source="voice",
            call_sid=call_sid or None,
            from_number=from_number or None,
            to_number=to_number or None,
        )

        twiml = VoiceResponse()
        twiml.say(
            "Hello, this is Mashbak. What would you like to do?",
            voice="alice",
            language="en-US",
        )
        _append_speech_gather(twiml, action_url=str(request.url_for("process_voice_webhook")))
        twiml.say("I did not catch that. Please say your request again.", voice="alice", language="en-US")
        twiml.redirect(str(request.url_for("voice_webhook")), method="POST")
        return Response(content=str(twiml), media_type="application/xml")

    @router.post("/process_voice", name="process_voice_webhook")
    async def process_voice_webhook(
        request: Request,
        call_sid: str = Form(default="", alias="CallSid"),
        from_number: str = Form(default="", alias="From"),
        to_number: str = Form(default="", alias="To"),
        speech_result: str = Form(default="", alias="SpeechResult"),
        confidence: str = Form(default="", alias="Confidence"),
    ):
        request_id = f"voice-{str(uuid.uuid4())[:8]}"

        if not await _is_valid_twilio_request(request):
            runtime.logger.log_error(
                request_id=request_id,
                error_type="voice_invalid_signature",
                error_message="Rejected process_voice webhook with invalid Twilio signature",
                source="voice",
                call_sid=call_sid or None,
                from_number=from_number or None,
            )
            response = VoiceResponse()
            response.say("Sorry, I cannot verify this call request.", voice="alice", language="en-US")
            return Response(content=str(response), media_type="application/xml", status_code=403)

        spoken_text = (speech_result or "").strip()
        confidence_val = _parse_confidence(confidence)

        runtime.logger.log(
            request_id=request_id,
            event_type="voice_speech_received",
            source="voice",
            call_sid=call_sid or None,
            from_number=from_number or None,
            to_number=to_number or None,
            speech_result=spoken_text,
            speech_confidence=confidence_val,
        )

        twiml = VoiceResponse()
        process_url = str(request.url_for("process_voice_webhook"))

        if not spoken_text:
            twiml.say("I did not hear anything. Please say your request again.", voice="alice", language="en-US")
            _append_speech_gather(twiml, action_url=process_url)
            twiml.redirect(process_url, method="POST")
            return Response(content=str(twiml), media_type="application/xml")

        if confidence_val is not None and confidence_val < 0.35:
            twiml.say("I am not fully sure what you said. Please repeat that clearly.", voice="alice", language="en-US")
            _append_speech_gather(twiml, action_url=process_url)
            twiml.redirect(process_url, method="POST")
            return Response(content=str(twiml), media_type="application/xml")

        sender_identity = f"call:{call_sid or from_number or 'unknown'}"
        try:
            result = await runtime.execute_nl(
                message=spoken_text,
                sender=sender_identity,
                request_id=request_id,
                source="voice",
                owner_unlocked=True,
            )
            assistant_text = _to_voice_text(result.get("output") or result.get("assistant_reply") or result.get("error") or "")
            if not assistant_text:
                assistant_text = "I could not produce a response. Please try again."

            runtime.logger.log(
                request_id=request_id,
                event_type="voice_assistant_reply",
                source="voice",
                call_sid=call_sid or None,
                from_number=from_number or None,
                selected_tool=(result.get("trace") or {}).get("selected_tool"),
                execution_status=(result.get("trace") or {}).get("execution_status"),
                success=bool(result.get("success")),
                reply=assistant_text,
            )

            twiml.say(assistant_text, voice="alice", language="en-US")
            _append_speech_gather(twiml, action_url=process_url)
            twiml.say("What would you like to do next?", voice="alice", language="en-US")
            twiml.redirect(process_url, method="POST")
            return Response(content=str(twiml), media_type="application/xml")
        except Exception as exc:
            runtime.logger.log_error(
                request_id=request_id,
                error_type="voice_runtime_error",
                error_message=str(exc),
                source="voice",
                call_sid=call_sid or None,
                from_number=from_number or None,
            )
            twiml.say("Sorry, I hit an error. Please try that again.", voice="alice", language="en-US")
            _append_speech_gather(twiml, action_url=process_url)
            twiml.redirect(process_url, method="POST")
            return Response(content=str(twiml), media_type="application/xml")

    return router


def _append_speech_gather(response: VoiceResponse, action_url: str) -> Gather:
    gather = Gather(
        input="speech",
        action=action_url,
        method="POST",
        language="en-US",
        speech_timeout="auto",
        hints="email, inbox, desktop, file, folder, time, system, status",
    )
    response.append(gather)
    return gather


def _parse_confidence(value: str) -> Optional[float]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_voice_text(value: str, max_chars: int = 420) -> str:
    compact = " ".join(str(value or "").split())
    if len(compact) <= max_chars:
        return compact
    return f"{compact[: max_chars - 3]}..."


async def _is_valid_twilio_request(request: Request) -> bool:
    """Validate webhook signature when TWILIO_AUTH_TOKEN is configured."""
    token = (ConfigLoader.get("TWILIO_AUTH_TOKEN", "") or "").strip()
    if not token:
        return True

    signature = request.headers.get("x-twilio-signature", "")
    if not signature:
        return False

    validator = RequestValidator(token)
    url = str(request.url)
    form = await request.form()
    params = {str(k): str(v) for k, v in form.multi_items()}
    return validator.validate(url, params, signature)
