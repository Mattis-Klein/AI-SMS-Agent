"""Shared assistant reasoning layer for Mashbak."""

from __future__ import annotations

import asyncio
import json
import re
import urllib.error
import urllib.request
from urllib.parse import urljoin
import uuid
from dataclasses import dataclass
from typing import Any, Optional

if __package__:
    from .redaction import sanitize_for_logging, sanitize_trace
else:
    from redaction import sanitize_for_logging, sanitize_trace


@dataclass
class AssistantMetadata:
    sender: str
    source: str
    session_id: str
    owner_unlocked: Optional[bool] = None
    request_id: Optional[str] = None


class BackendOpenAIClient:
    def __init__(
        self,
        api_key: str | None,
        model: str,
        *,
        base_url: str | None = None,
        timeout_seconds: float = 25.0,
        temperature: float = 0.3,
    ):
        self.api_key = api_key or ""
        self.model = model
        self.base_url = self._normalize_base_url(base_url)
        self.timeout_seconds = max(1.0, float(timeout_seconds or 25.0))
        self.temperature = self._normalize_temperature(temperature)

    @staticmethod
    def _normalize_base_url(value: str | None) -> str:
        raw = (value or "").strip()
        if not raw:
            return "https://api.openai.com/v1"
        return raw.rstrip("/")

    @staticmethod
    def _normalize_temperature(value: float | int | str | None) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.3
        return min(2.0, max(0.0, numeric))

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def complete(self, *, system_prompt: str, user_prompt: str, max_tokens: int = 250) -> str | None:
        if not self.enabled:
            return None
        return await asyncio.to_thread(
            self._complete_sync,
            system_prompt,
            user_prompt,
            max_tokens,
        )

    def _complete_sync(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str | None:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": max_tokens,
        }

        endpoint = urljoin(f"{self.base_url}/", "chat/completions")

        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                parsed = json.loads(response.read().decode("utf-8", errors="replace"))
            return parsed["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return None


class AssistantCore:
    def __init__(self, runtime):
        self.runtime = runtime
        self.interpreter = runtime.interpreter
        self.model_client = BackendOpenAIClient(runtime.openai_api_key, runtime.openai_model)

    async def respond(self, message: str, metadata: AssistantMetadata) -> dict[str, Any]:
        request_id = metadata.request_id or str(uuid.uuid4())[:8]
        metadata.request_id = request_id

        if metadata.source == "desktop" and metadata.owner_unlocked is False:
            return self._build_locked_response(message, metadata)

        context_snapshot = self.runtime.session_context.get_snapshot(metadata.session_id)
        parsed = self.interpreter.parse_to_dict(message, context=context_snapshot)
        mode = parsed.get("mode") or "conversation"

        is_action_request = bool((parsed.get("entities") or {}).get("action_requested"))

        if parsed.get("tool"):
            result = await self.runtime.execute_tool(
                tool_name=parsed["tool"],
                args=parsed.get("args") or {},
                sender=metadata.sender,
                request_id=request_id,
                source=metadata.source,
            )
            finalized = await self._finalize_tool_response(message, metadata, parsed, result)
            latest_context = self.runtime.session_context.update(
                session_id=metadata.session_id,
                user_message=message,
                parsed=parsed,
                result=finalized,
            )
            # Record the assistant reply back into the turn so follow-up turns
            # can reference it in recent_turns.
            assistant_reply_text = finalized.get("assistant_reply") or finalized.get("output") or ""
            self.runtime.session_context.record_assistant_reply(
                session_id=metadata.session_id,
                assistant_reply=assistant_reply_text,
            )
            finalized_trace = finalized.get("trace") or {}
            finalized_trace["context"] = latest_context
            finalized["trace"] = finalized_trace
            return finalized

        if is_action_request:
            response = self._build_unexecuted_action_response(message, metadata, parsed)
            latest_context = self.runtime.session_context.update(
                session_id=metadata.session_id,
                user_message=message,
                parsed=parsed,
                result=response,
            )
            self.runtime.session_context.record_assistant_reply(
                session_id=metadata.session_id,
                assistant_reply=response.get("assistant_reply") or response.get("output") or "",
            )
            response_trace = response.get("trace") or {}
            response_trace["context"] = latest_context
            response["trace"] = response_trace
            return response

        response = await self._build_conversation_response(message, metadata, parsed, context_snapshot)
        latest_context = self.runtime.session_context.update(
            session_id=metadata.session_id,
            user_message=message,
            parsed=parsed,
            result=response,
        )
        assistant_reply_text = response.get("assistant_reply") or response.get("output") or ""
        self.runtime.session_context.record_assistant_reply(
            session_id=metadata.session_id,
            assistant_reply=assistant_reply_text,
        )
        response_trace = response.get("trace") or {}
        response_trace["context"] = latest_context
        response["trace"] = response_trace
        return response

    _DYNAMIC_FACT_TERMS = (
        "election", "officeholder", "president", "vice president", "senator", "governor", "mayor",
        "congress", "parliament", "prime minister", "won", "winner", "results", "poll", "latest",
        "breaking", "today", "this week", "this month", "this year", "current", "as of", "now",
        "schedule", "calendar", "deadline", "law", "bill", "statute", "court", "ruling",
        "price", "cost", "stock", "market", "inflation", "gdp", "population", "statistics", "stats",
    )

    _LOCAL_CONTEXT_TERMS = (
        "mashbak", "this app", "this system", "my computer", "desktop", "inbox", "outbox",
        "file", "folder", "path", "cpu", "disk", "network", "uptime", "process", "email",
    )

    def _is_time_sensitive_fact_query(self, message: str, parsed: dict[str, Any]) -> bool:
        lower = str(message or "").strip().lower()
        if not lower:
            return False

        # Local operations and runtime diagnostics are not external dynamic-fact queries.
        if any(token in lower for token in self._LOCAL_CONTEXT_TERMS):
            return False

        if parsed.get("tool"):
            return False

        factual_cues = (
            "who", "what", "when", "which", "did", "won", "winner", "result", "latest",
            "current", "as of", "now", "price", "cost", "how much", "schedule", "law", "stat",
        )
        if not any(token in lower for token in factual_cues) and "?" not in lower:
            return False

        return any(token in lower for token in self._DYNAMIC_FACT_TERMS)

    def _is_time_or_date_query(self, message: str) -> bool:
        lower = str(message or "").strip().lower()
        if not lower:
            return False
        date_time_tokens = (
            "what time", "current time", "time is it", "date today", "today's date",
            "what date", "what day is", "today",
        )
        return any(token in lower for token in date_time_tokens)

    async def _dynamic_fact_reply(self, message: str, metadata: AssistantMetadata) -> tuple[str, str, str, str]:
        """Return reply + verification metadata for dynamic factual questions.
        
        Strategy:
        1. For time/date queries: use local current_time tool
        2. For other fact queries: perform web search first, then generate grounded response
        3. If search fails or returns nothing: refuse to answer rather than guess
        """
        if self._is_time_or_date_query(message):
            result = await self.runtime.execute_tool(
                tool_name="current_time",
                args={},
                sender=metadata.sender,
                request_id=metadata.request_id,
                source=metadata.source,
            )
            if result.get("success"):
                reply = self._fallback_tool_reply("current_time", result.get("output"), result.get("data"))
                return (
                    reply,
                    "Tool-assisted",
                    "Verified through current_time tool execution.",
                    "tool",
                )
            return (
                "I can't verify the current date/time right now because the local time tool is unavailable.",
                "Unverified",
                "Dynamic fact check attempted but current_time tool failed.",
                "policy",
            )

        # For non-time-based fact queries: attempt web search
        search_query = self._formulate_search_query(message)
        search_result = await self.runtime.execute_tool(
            tool_name="web_search",
            args={"query": search_query},
            sender=metadata.sender,
            request_id=metadata.request_id,
            source=metadata.source,
        )

        if search_result.get("success"):
            # Web search succeeded - generate response grounded in the results
            search_output = search_result.get("output", "")
            search_data = search_result.get("data", {})
            
            # Build a context for the LLM that includes search results
            grounded_reply = await self._generate_search_grounded_response(
                user_message=message,
                metadata=metadata,
                search_output=search_output,
                search_data=search_data,
            )
            
            if grounded_reply:
                return (
                    grounded_reply,
                    "Web-verified",
                    f"Grounded in web search results for: {search_query}",
                    "web_search",
                )

        # Search failed or returned no usable results - refuse to answer
        return (
            "I tried searching for current information on that, but I couldn't retrieve reliable results and cannot verify it safely. "
            "Rather than guess, I'd rather you check a trusted source directly for the most up-to-date information.",
            "Unverified",
            "Dynamic fact query attempted web search but no reliable results were available.",
            "policy",
        )

    def _build_unexecuted_action_response(
        self,
        message: str,
        metadata: AssistantMetadata,
        parsed: dict[str, Any],
    ) -> dict[str, Any]:
        entities = parsed.get("entities") or {}
        if entities.get("path_reference_unresolved"):
            if entities.get("reference_target") == "file_reference":
                reply = (
                    "I couldn't resolve which file you mean because there isn't a verified created file in this session yet. "
                    "Share the file path explicitly, or create a file first and then refer to it."
                )
            else:
                reply = (
                    "I couldn't resolve which folder you mean. "
                    "Please provide the full folder path, or create/select the folder first."
                )
        else:
            reply = (
                "I have not executed a filesystem tool yet, so no filesystem change was applied. "
                "Share an allowed target path and I can run it."
            )
        return {
            "success": False,
            "tool_name": None,
            "output": reply,
            "assistant_reply": reply,
            "error": reply,
            "error_type": "action_not_executed",
            "request_id": metadata.request_id,
            "source": metadata.source,
            "data": None,
            "trace": {
                "raw_request": sanitize_for_logging(message),
                "source": metadata.source,
                "assistant_mode": parsed.get("mode") or "conversation",
                "intent_classification": parsed.get("intent"),
                "interpreted_intent": None,
                "interpreted_args": sanitize_for_logging(parsed.get("args") or {}),
                "selected_tool": None,
                "validation_status": "skipped",
                "execution_status": "not_run",
                "execution_result": "not_executed",
                "tool_execution_occurred": False,
                "confidence": parsed.get("confidence", 0.0),
                "assistant_response_source": "policy",
                "verification_state": "Local-only",
                "verification_reason": "No external factual claim; action was not executed.",
                "followup_topic": parsed.get("followup_topic"),
                "topic": parsed.get("topic"),
            },
        }

    def _build_locked_response(self, message: str, metadata: AssistantMetadata) -> dict[str, Any]:
        reply = "Mashbak is locked right now. Unlock the desktop app first, then send your message again."
        return {
            "success": False,
            "tool_name": None,
            "output": reply,
            "assistant_reply": reply,
            "error": reply,
            "request_id": metadata.request_id,
            "source": metadata.source,
            "data": None,
            "trace": {
                "raw_request": sanitize_for_logging(message),
                "source": metadata.source,
                "assistant_mode": "locked",
                "intent_classification": "locked",
                "interpreted_intent": None,
                "interpreted_args": {},
                "selected_tool": None,
                "validation_status": "skipped",
                "execution_status": "blocked",
                "confidence": 1.0,
                "assistant_response_source": "policy",
                "verification_state": "Local-only",
                "verification_reason": "Policy lock response; no factual claim made.",
            },
        }

    async def _build_conversation_response(
        self,
        message: str,
        metadata: AssistantMetadata,
        parsed: dict[str, Any],
        context_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        verification_state = "Local-only"
        verification_reason = "No time-sensitive factual verification required for this reply."
        response_source = "openai" if self.model_client.enabled else "fallback"

        if self._is_time_sensitive_fact_query(message, parsed):
            reply, verification_state, verification_reason, response_source = await self._dynamic_fact_reply(message, metadata)
        else:
            reply = await self._generate_conversation_reply(message, metadata, parsed, context_snapshot)

        return {
            "success": True,
            "tool_name": None,
            "output": reply,
            "assistant_reply": reply,
            "error": None,
            "request_id": metadata.request_id,
            "source": metadata.source,
            "data": None,
            "trace": {
                "raw_request": sanitize_for_logging(message),
                "source": metadata.source,
                "assistant_mode": parsed.get("mode") or "conversation",
                "intent_classification": parsed.get("intent"),
                "interpreted_intent": None,
                "interpreted_args": sanitize_for_logging(parsed.get("args") or {}),
                "selected_tool": None,
                "validation_status": "skipped",
                "execution_status": "not_run",
                "execution_result": "not_executed",
                "tool_execution_occurred": False,
                "confidence": parsed.get("confidence", 0.0),
                "assistant_response_source": response_source,
                "verification_state": verification_state,
                "verification_reason": verification_reason,
                "followup_topic": parsed.get("followup_topic"),
                "topic": parsed.get("topic"),
            },
        }

    async def _finalize_tool_response(
        self,
        message: str,
        metadata: AssistantMetadata,
        parsed: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        raw_output = result.get("output")

        # Mandatory grounding: successful filesystem mutation tools must report
        # a resolved created_path or the result is treated as failure.
        if result.get("success") and result.get("tool_name") in {"create_folder", "create_file"}:
            data = result.get("data") if isinstance(result.get("data"), dict) else {}
            if not str(data.get("created_path") or "").strip():
                result["success"] = False
                result["error_type"] = "execution_failure"
                result["error"] = "Filesystem action did not return a resolved path."
                result["output"] = "I could not verify where that filesystem action was applied."

        # Mandatory grounding: successful delete_file must report deleted_path.
        if result.get("success") and result.get("tool_name") == "delete_file":
            data = result.get("data") if isinstance(result.get("data"), dict) else {}
            if not str(data.get("deleted_path") or "").strip():
                result["success"] = False
                result["error_type"] = "execution_failure"
                result["error"] = "I could not verify that the file was deleted."
                result["output"] = "I could not verify that the file was deleted."
        reply = await self._generate_tool_reply(
            user_message=message,
            metadata=metadata,
            parsed=parsed,
            result=result,
        )

        trace = sanitize_trace(result.get("trace") or {})
        trace["assistant_mode"] = parsed.get("mode") or "tool"
        if not result.get("success"):
            response_source = "fallback"
        elif result.get("tool_name") in {"set_config_variable", "create_file", "create_folder", "delete_file"}:
            response_source = "policy"
        else:
            response_source = "openai" if self.model_client.enabled else "fallback"
        trace["assistant_response_source"] = response_source
        trace["tool_output"] = sanitize_for_logging(raw_output)
        trace["tool_data"] = sanitize_for_logging(result.get("data"))
        trace["execution_result"] = "success" if result.get("success") else "failed"
        trace["tool_execution_occurred"] = True
        trace["verification_state"] = "Tool-assisted"
        trace["verification_reason"] = (
            f"Grounded by tool execution: {result.get('tool_name')}."
            if result.get("success")
            else f"Tool execution failed for {result.get('tool_name')}"
        )
        if result.get("error"):
            trace["tool_error"] = sanitize_for_logging(result.get("error"))
            trace["error_type"] = result.get("error_type")
            trace["remediation"] = result.get("remediation")
            trace["missing_config_fields"] = result.get("missing_config_fields")

        # Guard against completion-claim language when execution failed.
        is_action_intent = parsed.get("intent") == "filesystem"
        if is_action_intent and (not result.get("success")) and self._contains_completion_claim(reply):
            tool_nm = result.get("tool_name") or ""
            if "delete" in tool_nm:
                reply = "I did not delete that file. No filesystem change was applied."
            else:
                reply = "I did not complete that filesystem action. No filesystem change was applied."

        result["assistant_reply"] = reply
        result["output"] = reply
        if not result.get("success"):
            result["error"] = reply
        result["trace"] = trace
        return result

    def _contains_completion_claim(self, text: str | None) -> bool:
        if not text:
            return False
        lower = text.lower()
        return any(token in lower for token in ["created", "added", "saved", "deleted", "removed", "moved", "done"])

    async def _generate_conversation_reply(
        self,
        message: str,
        metadata: AssistantMetadata,
        parsed: dict[str, Any],
        context_snapshot: dict[str, Any],
    ) -> str:
        intent = parsed.get("intent") or ""
        entities = parsed.get("entities") or {}
        followup_topic = parsed.get("followup_topic")

        # --- Context-reference intents (resolved by interpreter from recent turns) ---
        if intent in {"reference_query", "status_query", "config_followup"}:
            return self._reply_for_reference_intent(intent, entities, context_snapshot)

        if followup_topic == "email_setup" and any(token in message.lower() for token in ["configure", "set up", "setup"]):
            return self._email_setup_guidance()

        if followup_topic in {"email_setup", "email_access", "config_update"}:
            missing_fields = context_snapshot.get("missing_config_fields") or []
            if any(token in message.lower() for token in ["password", "need", "still need", "what else", "and now", "so?", "did that fix", "what now"]):
                if missing_fields:
                    return f"You're still missing: {', '.join(missing_fields)}."
                pending_restart = context_snapshot.get("pending_restart_components") or []
                if pending_restart:
                    return f"Configuration is complete, but pending restart for: {', '.join(pending_restart)}."
                return "That configuration thread looks complete right now."

        system_prompt = self._build_system_prompt(metadata)
        if self.model_client.enabled:
            recent_turns_text = self._format_recent_turns_for_prompt(context_snapshot)
            prompt = (
                f"Request type: {parsed.get('mode') or 'conversation'}\n"
                f"User message: {sanitize_for_logging(message)}\n"
                f"Context topic: {parsed.get('topic') or 'none'}\n"
            )
            if recent_turns_text:
                prompt += f"Recent conversation:\n{recent_turns_text}\n"
            prompt += "Reply naturally. Do not mention internal tools unless the user asked for technical detail."
            ai_reply = await self.model_client.complete(
                system_prompt=system_prompt,
                user_prompt=prompt,
                max_tokens=min(self.runtime.model_response_max_tokens, 220 if metadata.source == "sms" else self.runtime.model_response_max_tokens),
            )
            if ai_reply:
                return ai_reply

        return self._fallback_conversation_reply(message)

    def _reply_for_reference_intent(
        self,
        intent: str,
        entities: dict[str, Any],
        context_snapshot: dict[str, Any],
    ) -> str:
        """Build a factual reply for a context-reference query using resolved entities."""
        reference_target = entities.get("reference_target", "")
        resolved_path = entities.get("resolved_path")
        last_task = entities.get("last_task") or context_snapshot.get("last_task")
        last_result = entities.get("last_result") or context_snapshot.get("last_result")
        missing_params = entities.get("missing_parameters") or context_snapshot.get("missing_parameters") or []
        missing_config = entities.get("missing_config_fields") or context_snapshot.get("missing_config_fields") or []

        if reference_target == "location":
            # Safety rule: only confirm if backed by a real successful result.
            if last_result == "success" and resolved_path:
                return f"It was saved at: {resolved_path}"
            if last_result == "success" and last_task:
                return f"The {last_task} completed successfully, but the exact path was not recorded."
            if last_result == "failure":
                return "The last action didn't complete successfully, so nothing was created or saved."
            return "I don't have a record of a file or folder being created in this session yet."

        if reference_target == "file_subject":
            if resolved_path:
                return f"The file/folder we were working on is: {resolved_path}"
            last_args = context_snapshot.get("last_args") or {}
            path_hint = last_args.get("path") or last_args.get("file_path")
            if path_hint:
                return f"We were working with: {path_hint}"
            if last_task:
                return f"I last ran {last_task}, but no specific file path was captured."
            return "I don't have a specific file or folder referenced in the current session."

        if reference_target == "missing_requirements":
            parts: list[str] = []
            if missing_params:
                parts.append(f"parameters: {', '.join(missing_params)}")
            if missing_config:
                parts.append(f"configuration: {', '.join(missing_config)}")
            if parts:
                return f"Still needed — {'; '.join(parts)}."
            pending_task = context_snapshot.get("pending_task")
            if pending_task:
                return f"I have a pending {pending_task} task, but everything looks collected. Just confirm and I'll run it."
            return "Nothing appears to be missing right now. What would you like to do?"

        if reference_target == "password_prompt":
            missing_config = context_snapshot.get("missing_config_fields") or []
            needs_password = any("PASSWORD" in f.upper() for f in missing_config)
            if needs_password:
                return (
                    "Yes, I still need your password. Send it as:\n"
                    "EMAIL_PASSWORD = yourpassword"
                )
            if missing_config:
                return f"Password looks covered, but I still need: {', '.join(missing_config)}."
            return "No, I have everything I need right now. What would you like to do?"

        return "I'm not sure what you're referring to. Can you give me a bit more detail?"

    def _format_recent_turns_for_prompt(self, context_snapshot: dict[str, Any]) -> str:
        """Format the last few turns (without sensitive values) for inclusion in AI prompts."""
        turns = context_snapshot.get("recent_turns") or []
        if not turns:
            return ""
        lines: list[str] = []
        for turn in turns[-5:]:  # cap at 5 for prompt size
            user_msg = turn.get("message") or ""
            assistant_msg = turn.get("assistant_reply") or ""
            if user_msg:
                lines.append(f"User: {sanitize_for_logging(user_msg)}")
            if assistant_msg:
                lines.append(f"Assistant: {sanitize_for_logging(assistant_msg)}")
        return "\n".join(lines)

    async def _generate_tool_reply(
        self,
        *,
        user_message: str,
        metadata: AssistantMetadata,
        parsed: dict[str, Any],
        result: dict[str, Any],
    ) -> str:
        if result.get("tool_name") == "set_config_variable":
            return result.get("output") or "Configuration updated."

        if not result.get("success"):
            return self._fallback_error_reply(
                error=result.get("error"),
                tool_name=result.get("tool_name"),
                error_type=result.get("error_type"),
                missing_config_fields=result.get("missing_config_fields"),
                remediation=result.get("remediation"),
            )

        # Keep filesystem mutation confirmations deterministic and fully grounded
        # to tool data to avoid model-added path hallucinations.
        if result.get("tool_name") in {"create_file", "create_folder", "delete_file"}:
            return self._fallback_tool_reply(result.get("tool_name"), result.get("output"), result.get("data"))

        # Safety rule: only describe a completed action when execution
        # actually succeeded.  We already confirmed success=True above, so
        # the AI prompt below is only reached for real successes.
        if self.model_client.enabled:
            context_snapshot = self.runtime.session_context.get_snapshot(metadata.session_id)
            recent_turns_text = self._format_recent_turns_for_prompt(context_snapshot)
            system_prompt = self._build_system_prompt(metadata)
            prompt = (
                "You are summarizing the result of a backend tool for the user.\n"
                f"User request: {user_message}\n"
                f"Tool: {result.get('tool_name')}\n"
                f"Intent: {parsed.get('intent')}\n"
                f"Structured data: {self._safe_json(result.get('data'))}\n"
                f"Raw tool output: {self._trim_text(result.get('output') or '')}\n"
            )
            if recent_turns_text:
                prompt += f"Recent conversation:\n{recent_turns_text}\n"
            prompt += (
                "Write a natural reply. Keep it concise, helpful, and grounded strictly in the tool result above. "
                "Do not claim anything was created, saved, or completed unless the tool data confirms it."
            )
            ai_reply = await self.model_client.complete(
                system_prompt=system_prompt,
                user_prompt=prompt,
                max_tokens=min(self.runtime.model_response_max_tokens, 180 if metadata.source == "sms" else self.runtime.model_response_max_tokens),
            )
            if ai_reply:
                return ai_reply

        return self._fallback_tool_reply(result.get("tool_name"), result.get("output"), result.get("data"))

    def _build_system_prompt(self, metadata: AssistantMetadata) -> str:
        if metadata.source == "sms":
            source_guidance = "Keep the reply brief and compact for SMS."
        elif metadata.source == "voice":
            source_guidance = (
                "You are speaking over a phone call. Keep replies short and natural, "
                "avoid formatting-heavy output, and prioritize spoken clarity."
            )
        else:
            source_guidance = "Sound like a calm personal desktop assistant."
        return (
            "You are Mashbak, the single assistant core for the user's desktop and SMS access. "
            "Use natural language, avoid raw debug formatting, and stay faithful to the actual tool results. "
            "Never present unverified dynamic facts (current events, elections, officeholders, laws, prices, statistics, schedules) as certain. "
            "If a dynamic fact is not verified by a tool or retrieval path in this runtime, clearly say you cannot verify and do not guess. "
            f"{source_guidance}"
        )

    def _fallback_conversation_reply(self, message: str) -> str:
        msg = message.strip().lower()
        if any(token in msg for token in ["hello", "hi", "hey"]):
            return "Hi. I'm ready to help with your computer, files, and email."
        if "thank" in msg:
            return "You're welcome."

        explanations = {
            "cpu usage": "CPU usage is the share of your processor's capacity that's being used right now. Higher numbers mean your computer is working harder.",
            "disk space": "Disk space is the amount of storage available on your drive for files, apps, and system data.",
            "uptime": "Uptime is how long your computer has been running since its last restart.",
            "network": "Network status describes whether your computer is connected and what network details are currently available.",
            "email": "I can check your inbox, summarize recent mail, search email content, and read a thread if email access is configured in the backend.",
        }
        for topic, reply in explanations.items():
            if topic in msg:
                return reply

        return "I can help with questions, check your computer's status, work with files, and handle email once it's configured."

    def _fallback_error_reply(
        self,
        error: str | None,
        tool_name: str | None,
        error_type: str | None = None,
        missing_config_fields: list[str] | None = None,
        remediation: str | None = None,
    ) -> str:
        email_tools = {"list_recent_emails", "summarize_inbox", "search_emails", "read_email_thread"}
        if error_type == "missing_configuration":
            field_text = ", ".join(missing_config_fields or [])
            if field_text:
                return (
                    f"Configuration incomplete. Missing: {field_text}.\n\n"
                    f"You can provide these values directly in chat by sending messages like:\n"
                    f"EMAIL_ADDRESS = myemail@example.com\n"
                    f"EMAIL_PASSWORD = mypassword\n\n"
                    f"Or edit mashbak/.env.master manually."
                )
            return "Configuration incomplete. Provide values via chat or edit mashbak/.env.master."
        if remediation:
            return remediation
        if tool_name in email_tools or (tool_name and "email" in tool_name):
            error_lower = (error or "").lower()
            if error_type == "missing_configuration" or "not configured" in error_lower:
                return self._email_setup_guidance()
            if error_type == "authentication_failure" or any(
                t in error_lower for t in ["authenticationfailed", "invalid credentials", "authentication failed", "login failed"]
            ):
                return (
                    "Email authentication failed. Check your password — for Gmail, you need to create an "
                    "App Password (myaccount.google.com > Security > App Passwords)."
                )
            if error_type == "connection_failure" or any(
                t in error_lower for t in ["connection refused", "name or service not known", "timed out", "network is unreachable", "nodename nor servname"]
            ):
                return (
                    "I could not reach your email server. Check that EMAIL_IMAP_HOST is correct "
                    "and that your network allows outbound IMAP connections."
                )
            if error and error.strip():
                return f"I couldn't access your email right now: {error.strip()}"
            return "I couldn't reach your email right now."
        if error_type == "denied_action":
            if tool_name in {"create_file", "create_folder", "delete_file", "list_files"}:
                allowed_summary = self._allowed_path_summary()
                return (
                    "That path is outside the allowed areas. "
                    f"Allowed locations are: {allowed_summary}."
                )
            return "That action is restricted by policy settings."
        if error_type == "validation_failure":
            return error or "I need a bit more detail to run that request safely."
        if error_type == "timeout":
            return "That request took too long and timed out. Try again with a narrower scope."
        return error or "I couldn't complete that request."

    def _allowed_path_summary(self) -> str:
        try:
            allowed = [str(p) for p in self.runtime.config.get_allowed_directories()]
        except Exception:
            allowed = []
        if not allowed:
            return "the configured safe directories"
        if len(allowed) <= 4:
            return ", ".join(allowed)
        return ", ".join(allowed[:4]) + ", and other configured directories"

    def _email_setup_guidance(self) -> str:
        return (
            "Email access needs configuration. You can provide values directly in chat:\n"
            "• EMAIL_IMAP_HOST = imap.gmail.com\n"
            "• EMAIL_IMAP_PORT = 993\n"
            "• EMAIL_USERNAME = your-email@gmail.com\n"
            "• EMAIL_PASSWORD = your-app-password\n\n"
            "Or add them to mashbak/.env.master manually. "
            "Use IMAP_SERVER and EMAIL_ADDRESS as alternatives to HOST and USERNAME."
        )

    def _fallback_tool_reply(self, tool_name: str | None, output: str | None, data: Any) -> str:
        if tool_name == "create_file":
            path_str = (data or {}).get("created_path") if isinstance(data, dict) else None
            if path_str:
                return f"Done — I created {self._humanize_path(path_str)}."
            return "The file was created."

        if tool_name == "create_folder":
            path_str = (data or {}).get("created_path") if isinstance(data, dict) else None
            if path_str:
                return f"Done — I created the folder {self._humanize_path(path_str)}."
            return "The folder was created."

        if tool_name == "delete_file":
            path_str = (data or {}).get("deleted_path") if isinstance(data, dict) else None
            if path_str:
                return f"Done — I deleted {self._humanize_path(path_str)}."
            return "The file was deleted."

        if tool_name == "cpu_usage":
            cpu_value = self._extract_percentage(output)
            if cpu_value is not None:
                if cpu_value < 35:
                    load = "pretty light"
                elif cpu_value < 70:
                    load = "moderate"
                else:
                    load = "fairly heavy"
                return f"Your CPU is currently running at about {cpu_value:.0f}%, which is {load} usage."

        if tool_name == "current_time":
            if output:
                return f"It's currently {output.strip()}."

        if tool_name in {"dir_inbox", "dir_outbox", "list_files"}:
            items = self._extract_list_items(output)
            if items:
                preview = ", ".join(items[:5])
                if len(items) == 1:
                    return f"I found 1 item: {preview}."
                return f"I found {len(items)} items. The first few are {preview}."

        if tool_name == "system_info" and output:
            info = self._parse_key_value_lines(output)
            os_name = info.get("OS Name") or "your current operating system"
            os_version = info.get("OS Version")
            memory = info.get("Total Physical Memory")
            parts = [f"You're running {os_name}"]
            if os_version:
                parts.append(f"version {os_version}")
            if memory:
                parts.append(f"with {memory} of memory")
            return ", ".join(parts) + "."

        if tool_name and tool_name.startswith("email_") or tool_name in {"list_recent_emails", "summarize_inbox", "search_emails", "read_email_thread"}:
            return self._fallback_email_reply(tool_name, data, output)

        if output:
            trimmed = self._trim_text(output, max_length=260)
            return f"I checked that for you. {trimmed}"
        return "Done."

    def _humanize_path(self, path_str: str) -> str:
        """Convert a raw filesystem path to a short natural description."""
        from pathlib import Path as _Path
        try:
            p = _Path(path_str)
            home = _Path.home()
            desktop = home / "Desktop"
            documents = home / "Documents"
            downloads = home / "Downloads"
            pictures = home / "Pictures"
            for folder, label in (
                (desktop, "your Desktop"),
                (documents, "your Documents"),
                (downloads, "your Downloads"),
                (pictures, "your Pictures"),
            ):
                try:
                    rel = p.relative_to(folder)
                    rel_str = str(rel)
                    return f"'{rel_str}' on {label}" if rel_str != "." else f"a file on {label}"
                except ValueError:
                    pass
            return f"'{p.name}'"
        except Exception:
            return f"'{path_str}'"

    def _fallback_email_reply(self, tool_name: str | None, data: Any, output: str | None) -> str:
        if isinstance(data, dict) and data.get("messages"):
            messages = data["messages"][:3]
            count = data.get("count", len(data["messages"]))
            snippets = []
            for item in messages:
                sender = item.get("from") or "someone"
                subject = item.get("subject") or "(no subject)"
                snippets.append(f"{sender} about {subject}")
            joined = "; ".join(snippets)
            if tool_name == "summarize_inbox":
                unread = data.get("unread_count", count)
                return f"You have {unread} recent unread emails. The main ones are {joined}."
            if tool_name == "search_emails":
                return f"I found {count} matching emails. The closest matches are {joined}."
            if tool_name == "read_email_thread":
                subject = data.get("thread_subject") or "that thread"
                return f"I found {count} messages in {subject}. The latest updates are {joined}."
            return f"You have {count} recent emails. The main ones are {joined}."

        if output:
            return self._trim_text(output, max_length=260)
        return "I couldn't read your email right now."

    def _extract_percentage(self, output: str | None) -> float | None:
        if not output:
            return None
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)%", output)
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    def _extract_list_items(self, output: str | None) -> list[str]:
        if not output:
            return []
        return [line.strip(" -\t") for line in output.splitlines() if line.strip()][:12]

    def _parse_key_value_lines(self, output: str) -> dict[str, str]:
        parsed: dict[str, str] = {}
        for line in output.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            parsed[key.strip()] = value.strip()
        return parsed

    def _trim_text(self, value: str, max_length: int = 1200) -> str:
        compact = " ".join(value.split())
        if len(compact) <= max_length:
            return compact
        return f"{compact[: max_length - 3]}..."

    def _formulate_search_query(self, message: str) -> str:
        """Extract key terms from user message to form a focused search query.
        
        Removes common filler words and keeps substantive terms for searching.
        """
        stop_words = {
            "what", "who", "where", "when", "how", "why", "is", "are", "do", "does",
            "the", "a", "an", "and", "or", "but", "can", "will", "should", "could",
            "have", "has", "had", "be", "been", "was", "were", "i", "you", "he", "she",
            "it", "we", "they", "this", "that", "these", "those", "my", "your", "his", "her",
        }
        
        # Remove punctuation and split into words
        words = []
        current_word = ""
        for char in message.lower():
            if char.isalnum():
                current_word += char
            else:
                if current_word and current_word not in stop_words and len(current_word) > 1:
                    words.append(current_word)
                current_word = ""
        if current_word and current_word not in stop_words and len(current_word) > 1:
            words.append(current_word)
        
        # Build query from kept words (up to 10 words for reasonable search)
        query = " ".join(words[:10]).strip()
        
        # If query is too short, just use original message reduced
        if len(query) < 3:
            query = message[:100].strip()
        
        return query

    async def _generate_search_grounded_response(
        self,
        user_message: str,
        metadata: AssistantMetadata,
        search_output: str,
        search_data: dict[str, Any],
    ) -> str | None:
        """Generate a response grounded in web search results.
        
        Uses the LLM to synthesize search results into a natural, factual answer.
        Falls back to returning search results directly if LLM fails.
        """
        if not self.model_client.enabled:
            # Fallback: return search results in structured format
            results = search_data.get("results", [])
            if results:
                lines = [f"I found {len(results)} sources on that:"]
                for i, result in enumerate(results[:3], 1):
                    title = result.get("title", "Source")
                    snippet = result.get("snippet", "")
                    url = result.get("url", "")
                    lines.append(f"{i}. {title}")
                    if snippet:
                        lines.append(f"   {snippet[:150]}...")
                    if url:
                        lines.append(f"   {url}")
                return "\n".join(lines)
            return None
        
        # Use LLM to synthesize search results
        system_prompt = self._build_system_prompt(metadata)
        
        results = search_data.get("results", [])
        results_text = "\n".join([
            f"- {r.get('title', 'Source')}: {r.get('snippet', '')[:150]}"
            for r in results[:5]
        ])
        
        prompt = (
            f"The user asked: {user_message}\n\n"
            f"Here are current web search results:\n{results_text}\n\n"
            "Use these results to provide a direct, accurate answer. "
            "If results don't directly answer the question, say so. "
            "Always cite or reference the sources you're using. "
            "Keep the answer concise and factual."
        )
        
        ai_reply = await self.model_client.complete(
            system_prompt=system_prompt,
            user_prompt=prompt,
            max_tokens=min(self.runtime.model_response_max_tokens, 250 if metadata.source == "sms" else self.runtime.model_response_max_tokens),
        )
        
        if ai_reply:
            # Add indication that this was search-verified
            if metadata.source != "sms":  # Desktop can show more context
                return ai_reply
            return ai_reply

        # Fallback if LLM fails
        return None

    def _safe_json(self, value: Any) -> str:
        try:
            return self._trim_text(json.dumps(value, ensure_ascii=True), max_length=1800)
        except TypeError:
            return self._trim_text(str(value), max_length=1800)
    def _safe_json(self, value: Any) -> str:
        try:
            return self._trim_text(json.dumps(value, ensure_ascii=True), max_length=1800)
        except TypeError:
            return self._trim_text(str(value), max_length=1800)