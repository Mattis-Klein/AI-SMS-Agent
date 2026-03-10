"""Tkinter UI for local Mashbak control and observability."""

import json
import threading
import urllib.error
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, Y, Text, Tk
from tkinter import ttk

from widgets import action_bar, add_refresh_button, labeled_text_area, set_text


class DesktopControlApp:
    def __init__(self, root: Tk, client, runtime_summary: dict, local_app_pin: str, openai_api_key: str, openai_model: str):
        self.root = root
        self.root.title("Mashbak Desktop")
        self.root.geometry("1320x820")

        self.client = client
        self.runtime_summary = runtime_summary
        self.local_app_pin = local_app_pin
        self.openai_api_key = openai_api_key
        self.openai_model = openai_model
        self.activity = []
        self.chat_history: list[str] = []
        self.quick_buttons: list[ttk.Button] = []
        self.is_unlocked = False

        workspace = Path(runtime_summary["workspace"])
        self.agent_log_file = workspace / "logs" / "agent.log"
        self.bridge_log_file = workspace.parent.parent / "sms-bridge" / "logs" / "bridge.log"

        self._build_ui()
        self._set_interaction_enabled(False)
        set_text(self.details_text, "Desktop is locked. Enter PIN to unlock.")
        self.refresh_status()
        self.refresh_logs()

    def _build_ui(self) -> None:
        header = ttk.Frame(self.root, padding=(12, 10))
        header.pack(fill=X)
        ttk.Label(header, text="Mashbak Desktop", font=("Segoe UI", 14, "bold")).pack(side=LEFT)

        lock_bar = ttk.Frame(header)
        lock_bar.pack(side=RIGHT, padx=(16, 0))
        self.lock_status = ttk.Label(lock_bar, text="Locked")
        self.lock_status.pack(side=LEFT, padx=(0, 6))
        self.pin_entry = ttk.Entry(lock_bar, width=10, show="*")
        self.pin_entry.pack(side=LEFT, padx=(0, 6))
        self.pin_entry.bind("<Return>", lambda _event: self.unlock_app())
        self.unlock_button = ttk.Button(lock_bar, text="Unlock", command=self.unlock_app)
        self.unlock_button.pack(side=LEFT)

        self.agent_badge = ttk.Label(header, text="Agent: checking...")
        self.agent_badge.pack(side=RIGHT, padx=(8, 0))
        self.bridge_badge = ttk.Label(header, text="Bridge: checking...")
        self.bridge_badge.pack(side=RIGHT)

        body = ttk.Frame(self.root)
        body.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        sidebar = ttk.Frame(body, width=230)
        sidebar.pack(side=LEFT, fill=Y)
        sidebar.pack_propagate(False)
        self._build_sidebar(sidebar)

        main_chat = ttk.Frame(body)
        main_chat.pack(side=LEFT, fill=BOTH, expand=True, padx=(10, 10))
        self._build_chat_panel(main_chat)

        right_panel = ttk.Frame(body, width=400)
        right_panel.pack(side=RIGHT, fill=BOTH)
        right_panel.pack_propagate(False)
        self._build_activity_status_panel(right_panel)

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Quick Commands", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 8))
        for label, message in [
            ("Check Inbox", "check my inbox"),
            ("System Info", "system info"),
            ("CPU Usage", "cpu usage"),
            ("List Processes", "show running processes"),
            ("Current Time", "what time is it"),
        ]:
            button = ttk.Button(parent, text=label, command=lambda m=message: self._send_quick_command(m))
            button.pack(fill=X, pady=2)
            self.quick_buttons.append(button)

        ttk.Separator(parent, orient="horizontal").pack(fill=X, pady=10)
        ttk.Label(parent, text="Tools", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 6))
        self.tools_text = Text(parent, height=18, wrap="word")
        self.tools_text.pack(fill=BOTH, expand=True)

    def _build_chat_panel(self, parent: ttk.Frame) -> None:
        self.chat_text = labeled_text_area(parent, "Chat", height=25, wrap="word")

        input_frame = ttk.Frame(parent)
        input_frame.pack(fill=X, padx=10, pady=10)

        ttk.Label(input_frame, text="Type a message").pack(anchor="w")
        self.message_entry = ttk.Entry(input_frame)
        self.message_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
        self.message_entry.bind("<Return>", lambda _event: self.on_send())

        self.send_button = ttk.Button(input_frame, text="Send", command=self.on_send)
        self.send_button.pack(side=RIGHT)

    def _build_activity_status_panel(self, parent: ttk.Frame) -> None:
        actions = action_bar(parent)
        add_refresh_button(actions, self.refresh_status, label="Refresh Status")
        add_refresh_button(actions, self.refresh_logs, label="Refresh Logs")
        ttk.Button(actions, text="Clear Chat", command=self.clear_chat).pack(side=LEFT, padx=(6, 0))
        ttk.Button(actions, text="Clear Activity", command=self.clear_activity).pack(side=LEFT, padx=(6, 0))

        self.details_text = labeled_text_area(parent, "Execution Details", height=12, wrap="word")
        self.activity_list = labeled_text_area(parent, "Recent Activity", height=8, wrap="none")
        self.status_text = labeled_text_area(parent, "Service Status", height=8, wrap="word")
        self.config_text = labeled_text_area(parent, "Runtime Config", height=8, wrap="word")
        self.agent_logs_text = labeled_text_area(parent, "Recent Agent Logs", height=7, wrap="none")
        self.bridge_logs_text = labeled_text_area(parent, "Recent Bridge Logs", height=7, wrap="none")

    def _send_quick_command(self, message: str) -> None:
        if not self.is_unlocked:
            set_text(self.details_text, "Desktop is locked. Enter PIN to unlock.")
            return
        self.message_entry.delete(0, END)
        self.message_entry.insert(0, message)
        self.on_send()

    def unlock_app(self) -> None:
        candidate = self.pin_entry.get().strip()
        self.pin_entry.delete(0, END)

        if candidate != self.local_app_pin:
            self.is_unlocked = False
            self.lock_status.configure(text="Locked - wrong PIN", foreground="#b42318")
            set_text(self.details_text, "Wrong PIN. Desktop remains locked.")
            self._set_interaction_enabled(False)
            return

        self.is_unlocked = True
        self.lock_status.configure(text="Unlocked", foreground="#0a7d2a")
        set_text(self.details_text, "Unlocked. Chat is enabled.")
        self._set_interaction_enabled(True)

    def _set_interaction_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.message_entry.configure(state=state)
        self.send_button.configure(state=state)
        for button in self.quick_buttons:
            button.configure(state=state)

    def on_send(self) -> None:
        if not self.is_unlocked:
            set_text(self.details_text, "Desktop is locked. Enter PIN to unlock.")
            return

        message = self.message_entry.get().strip()
        if not message:
            return

        self.send_button.configure(state="disabled")
        set_text(self.details_text, "Running...\n")

        thread = threading.Thread(target=self._run_message, args=(message,), daemon=True)
        thread.start()

    def _run_message(self, message: str) -> None:
        try:
            result = self.client.execute_nl(message=message, sender="local-desktop")
            if not result.get("success"):
                ai_text = self._run_openai_chat(message)
                if ai_text:
                    ai_result = {
                        "success": True,
                        "tool_name": "ai_chat",
                        "output": ai_text,
                        "request_id": result.get("request_id"),
                        "trace": {
                            "raw_request": message,
                            "intent_classification": "chat",
                            "interpreted_intent": "ai_chat",
                            "selected_tool": "ai_chat",
                            "interpreted_args": {},
                            "validation_status": "passed",
                            "validated_arguments": {},
                            "execution_status": "success",
                            "execution_time_ms": None,
                        },
                    }
                    self.root.after(0, lambda: self._display_result(message, ai_result))
                    return
            self.root.after(0, lambda: self._display_result(message, result))
        except Exception as exc:
            self.root.after(0, lambda: self._display_error(str(exc)))

    def _run_openai_chat(self, message: str) -> str | None:
        if not self.openai_api_key:
            return None

        payload = {
            "model": self.openai_model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {"type": "input_text", "text": "You are Mashbak Desktop assistant. Reply clearly and concisely."}
                    ],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": message}],
                },
            ],
            "max_output_tokens": 400,
        }

        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_api_key}",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                parsed = json.loads(response.read().decode("utf-8", errors="replace"))
        except Exception:
            return None

        output_text = parsed.get("output_text")
        if output_text:
            return output_text.strip()

        for item in parsed.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    text = content.get("text")
                    if text:
                        return str(text).strip()

        return None

    def _display_result(self, message: str, result: dict) -> None:
        self.send_button.configure(state="normal")
        self.message_entry.delete(0, END)

        trace = result.get("trace", {})
        detail_lines = [
            f"Raw Request: {trace.get('raw_request', message)}",
            f"Intent Class: {trace.get('intent_classification')}",
            f"Interpreted Intent: {trace.get('interpreted_intent')}",
            f"Selected Tool: {trace.get('selected_tool')}",
            f"Interpreted Args: {json.dumps(trace.get('interpreted_args', {}), ensure_ascii=True)}",
            f"Validation Status: {trace.get('validation_status')}",
            f"Validated Args: {json.dumps(trace.get('validated_arguments'), ensure_ascii=True)}",
            f"Execution Status: {trace.get('execution_status')}",
            f"Execution Time (ms): {trace.get('execution_time_ms')}",
            f"Request ID: {result.get('request_id')}",
        ]
        set_text(self.details_text, "\n".join(detail_lines))

        if result.get("success"):
            final_text = result.get("output") or "Command executed successfully."
        else:
            final_text = result.get("error") or "Request failed."

        chat_block = [f"You: {message}", f"Agent: {final_text}"]
        self.chat_history.extend(chat_block)
        self.chat_history = self.chat_history[-120:]
        set_text(self.chat_text, "\n\n".join(self.chat_history))

        activity_line = (
            f"{datetime.now().strftime('%H:%M:%S')} | {result.get('request_id')} | tool={result.get('tool_name')} | "
            f"success={result.get('success')} | msg={message}"
        )
        self.activity.insert(0, activity_line)
        self.activity = self.activity[:30]
        set_text(self.activity_list, "\n".join(self.activity))

        self.refresh_logs()

    def _display_error(self, error_text: str) -> None:
        self.send_button.configure(state="normal")
        set_text(self.details_text, "Execution Error")
        self.chat_history.extend(["You: [message failed]", f"Agent: {error_text}"])
        self.chat_history = self.chat_history[-120:]
        set_text(self.chat_text, "\n\n".join(self.chat_history))

        self.activity.insert(0, f"{datetime.now().strftime('%H:%M:%S')} | request failed | {error_text}")
        self.activity = self.activity[:30]
        set_text(self.activity_list, "\n".join(self.activity))

    def refresh_status(self) -> None:
        summary = self.runtime_summary

        agent_status = self._check_agent_health()
        bridge_status = self._check_http_health("http://127.0.0.1:34567/health")

        self.agent_badge.configure(text=f"Agent: {'running' if agent_status['running'] else 'down'}")
        self.bridge_badge.configure(text=f"Bridge: {'running' if bridge_status['running'] else 'down'}")
        self.agent_badge.configure(foreground=("#0a7d2a" if agent_status["running"] else "#b42318"))
        self.bridge_badge.configure(foreground=("#0a7d2a" if bridge_status["running"] else "#b42318"))

        status_lines = [
            f"FastAPI Agent Service: {'running' if agent_status['running'] else 'not detected'}",
            f"SMS Bridge Service: {'running' if bridge_status['running'] else 'not detected'}",
            f"Agent Health Detail: {agent_status['detail']}",
            f"Bridge Health Detail: {bridge_status['detail']}",
        ]
        set_text(self.status_text, "\n".join(status_lines))

        tools_response = self.client.list_tools()
        tools_payload = tools_response.get("tools")
        tools = []
        if isinstance(tools_payload, dict):
            tools = list(tools_payload.values())
        elif isinstance(tools_payload, list):
            tools = tools_payload

        tool_lines = []
        for item in tools:
            if isinstance(item, dict):
                tool_name = item.get("name") or "unknown"
                description = item.get("description") or ""
                tool_lines.append(f"- {tool_name}: {description}")
            else:
                tool_lines.append(f"- {item}")

        if not tool_lines:
            tool_lines = ["- unavailable"]

        set_text(self.tools_text, "\n".join(tool_lines))

        config_lines = [
            f"Workspace: {summary['workspace']}",
            "Allowed Directories:",
        ]
        config_lines.extend([f"  - {item}" for item in summary["allowed_directories"]])
        config_lines.append(f"Allowed Tools: {summary['allowed_tools']}")
        config_lines.append(f"Tool Timeout (s): {summary['tool_timeout_seconds']}")
        set_text(self.config_text, "\n".join(config_lines))

    def refresh_logs(self) -> None:
        agent_lines = self._tail_file(self.agent_log_file, max_lines=30)
        bridge_lines = self._tail_file(self.bridge_log_file, max_lines=30)

        set_text(self.agent_logs_text, "\n".join(agent_lines) if agent_lines else "No agent logs yet.")
        set_text(self.bridge_logs_text, "\n".join(bridge_lines) if bridge_lines else "No bridge logs yet.")

    def _check_agent_health(self) -> dict:
        health = self.client.health()
        if health.get("status") == "ok":
            return {"running": True, "detail": json.dumps(health, ensure_ascii=True)[:180]}
        return {"running": False, "detail": health.get("error", "unavailable")}

    def _tail_file(self, path: Path, max_lines: int = 30) -> list[str]:
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            return lines[-max_lines:]
        except Exception as exc:
            return [f"Failed to read {path}: {exc}"]

    def _check_http_health(self, url: str) -> dict:
        try:
            with urllib.request.urlopen(url, timeout=1.2) as response:
                raw = response.read().decode("utf-8", errors="replace")
                detail = raw.strip().replace("\n", " ")
                return {"running": response.status == 200, "detail": detail[:180]}
        except urllib.error.URLError as exc:
            return {"running": False, "detail": str(exc.reason)}
        except Exception as exc:
            return {"running": False, "detail": str(exc)}

    def clear_chat(self) -> None:
        self.chat_history.clear()
        set_text(self.chat_text, "")

    def clear_activity(self) -> None:
        self.activity.clear()
        set_text(self.activity_list, "")
