"""Shared assistant reasoning layer for Mashbak."""

from __future__ import annotations

import asyncio
import json
import re
import urllib.error
import urllib.request
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
    def __init__(self, api_key: str | None, model: str):
        self.api_key = api_key or ""
        self.model = model

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
            "temperature": 0.3,
            "max_tokens": max_tokens,
        }

        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=25) as response:
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
            },
        }

    async def _build_conversation_response(
        self,
        message: str,
        metadata: AssistantMetadata,
        parsed: dict[str, Any],
        context_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
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
                "execution_status": "completed",
                "confidence": parsed.get("confidence", 0.0),
                "assistant_response_source": "openai" if self.model_client.enabled else "fallback",
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
        reply = await self._generate_tool_reply(
            user_message=message,
            metadata=metadata,
            parsed=parsed,
            result=result,
        )

        trace = sanitize_trace(result.get("trace") or {})
        trace["assistant_mode"] = parsed.get("mode") or "tool"
        trace["assistant_response_source"] = "openai" if self.model_client.enabled else "fallback"
        trace["tool_output"] = sanitize_for_logging(raw_output)
        trace["tool_data"] = sanitize_for_logging(result.get("data"))
        if result.get("error"):
            trace["tool_error"] = sanitize_for_logging(result.get("error"))
            trace["error_type"] = result.get("error_type")
            trace["remediation"] = result.get("remediation")
            trace["missing_config_fields"] = result.get("missing_config_fields")

        result["assistant_reply"] = reply
        result["output"] = reply
        if not result.get("success"):
            result["error"] = reply
        result["trace"] = trace
        return result

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
        source_guidance = (
            "Keep the reply brief and compact for SMS." if metadata.source == "sms"
            else "Sound like a calm personal desktop assistant."
        )
        return (
            "You are Mashbak, the single assistant core for the user's desktop and SMS access. "
            "Use natural language, avoid raw debug formatting, and stay faithful to the actual tool results. "
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
            if error and "not configured" in error.lower():
                return self._email_setup_guidance()
            return "I couldn't reach your email right now."
        if error_type == "validation_failure":
            return error or "I need a bit more detail to run that request safely."
        if error_type == "timeout":
            return "That request took too long and timed out. Try again with a narrower scope."
        if error_type == "denied_action":
            return "That action is currently restricted by policy settings."
        return error or "I couldn't complete that request."

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

    def _safe_json(self, value: Any) -> str:
        try:
            return self._trim_text(json.dumps(value, ensure_ascii=True), max_length=1800)
        except TypeError:
            return self._trim_text(str(value), max_length=1800)