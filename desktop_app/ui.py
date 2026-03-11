"""Tkinter UI for local Mashbak control and observability."""

import json
import threading
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, Y, Text, Tk
from tkinter import scrolledtext, ttk

from widgets import action_bar, add_refresh_button, labeled_scroll_text, set_text

# ── colour palette ─────────────────────────────────────────────────────────────
_GREEN = "#1a7f37"
_RED   = "#b42318"


class DesktopControlApp:
    def __init__(
        self,
        root: Tk,
        client,
        runtime_summary: dict,
        local_app_pin: str | None = None,
        openai_api_key: str | None = None,
        openai_model: str = "gpt-4.1-mini",
    ):
        if not local_app_pin:
            raise RuntimeError("LOCAL_APP_PIN is required. Set it in agent/.env or the environment.")
        if not openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required. Set it in agent/.env or the environment.")

        self.root = root
        self.root.title("Mashbak Desktop")
        self.root.geometry("1380x860")
        self.root.minsize(900, 600)

        self.client = client
        self.runtime_summary = runtime_summary
        self.local_app_pin = local_app_pin
        self.openai_api_key = openai_api_key
        self.openai_model = openai_model
        self.activity: list[str] = []
        self.chat_history: list[tuple[str, str]] = []  # (role, text)
        self.quick_buttons: list[ttk.Button] = []
        self.is_unlocked = False

        workspace = Path(runtime_summary["workspace"])
        self.agent_log_file = workspace / "logs" / "agent.log"
        self.bridge_log_file = workspace.parent.parent / "sms-bridge" / "logs" / "bridge.log"

        self._apply_styles()
        self._build_ui()
        self._set_interaction_enabled(False)
        self._show_chat_placeholder()
        self.refresh_status()
        self.refresh_logs()

    # ── theming ────────────────────────────────────────────────────────────────

    def _apply_styles(self) -> None:
        style = ttk.Style(self.root)
        for theme in ("vista", "clam", "default"):
            if theme in style.theme_names():
                style.theme_use(theme)
                break

        style.configure("Header.TFrame", background="#1c2128")
        style.configure("Header.TLabel", background="#1c2128", foreground="#cdd9e5",
                        font=("Segoe UI", 10))
        style.configure("AppTitle.TLabel", background="#1c2128", foreground="#e6edf3",
                        font=("Segoe UI", 14, "bold"))
        style.configure("Section.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("StatusBar.TLabel", font=("Segoe UI", 8), foreground="#656d76")
        style.configure("Send.TButton", font=("Segoe UI", 10, "bold"))

    # ── layout ─────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._build_header()

        body = ttk.Frame(self.root)
        body.pack(fill=BOTH, expand=True, padx=8, pady=(4, 0))

        sidebar = ttk.Frame(body, width=210)
        sidebar.pack(side=LEFT, fill=Y)
        sidebar.pack_propagate(False)
        self._build_sidebar(sidebar)

        ttk.Separator(body, orient="vertical").pack(side=LEFT, fill=Y, padx=(6, 6))

        chat_col = ttk.Frame(body)
        chat_col.pack(side=LEFT, fill=BOTH, expand=True)
        self._build_chat_panel(chat_col)

        ttk.Separator(body, orient="vertical").pack(side=LEFT, fill=Y, padx=(6, 6))

        right_col = ttk.Frame(body, width=430)
        right_col.pack(side=RIGHT, fill=BOTH)
        right_col.pack_propagate(False)
        self._build_right_panel(right_col)

        self._build_statusbar()

    def _build_header(self) -> None:
        header = ttk.Frame(self.root, style="Header.TFrame", padding=(14, 8))
        header.pack(fill=X)

        ttk.Label(header, text="Mashbak", style="AppTitle.TLabel").pack(side=LEFT)
        ttk.Label(header, text="Desktop", style="Header.TLabel").pack(side=LEFT, padx=(6, 0))

        lock_bar = ttk.Frame(header, style="Header.TFrame")
        lock_bar.pack(side=RIGHT)

        self.lock_icon_label = ttk.Label(lock_bar, text="🔒", style="Header.TLabel")
        self.lock_icon_label.pack(side=LEFT, padx=(0, 4))
        self.lock_status = ttk.Label(lock_bar, text="Locked", style="Header.TLabel")
        self.lock_status.pack(side=LEFT, padx=(0, 8))
        self.pin_entry = ttk.Entry(lock_bar, width=9, show="●", font=("Segoe UI", 10))
        self.pin_entry.pack(side=LEFT, padx=(0, 4))
        self.pin_entry.bind("<Return>", lambda _e: self.unlock_app())
        self.unlock_button = ttk.Button(lock_bar, text="Unlock", command=self.unlock_app, width=7)
        self.unlock_button.pack(side=LEFT, padx=(0, 16))

        self.bridge_badge = ttk.Label(header, text="Bridge ●", style="Header.TLabel")
        self.bridge_badge.pack(side=RIGHT, padx=(0, 10))
        self.agent_badge = ttk.Label(header, text="Agent ●", style="Header.TLabel")
        self.agent_badge.pack(side=RIGHT, padx=(0, 10))

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Quick Commands", style="Section.TLabel").pack(
            anchor="w", padx=8, pady=(8, 4)
        )
        for label, message in [
            ("📥  Check Inbox", "check my inbox"),
            ("💻  System Info", "system info"),
            ("📊  CPU Usage", "cpu usage"),
            ("⚙️   List Processes", "show running processes"),
            ("🕐  Current Time", "what time is it"),
        ]:
            btn = ttk.Button(
                parent, text=label,
                command=lambda m=message: self._send_quick_command(m),
            )
            btn.pack(fill=X, padx=8, pady=2)
            self.quick_buttons.append(btn)

        ttk.Separator(parent, orient="horizontal").pack(fill=X, padx=8, pady=10)

        ttk.Label(parent, text="Available Tools", style="Section.TLabel").pack(
            anchor="w", padx=8, pady=(0, 4)
        )
        tools_frame = ttk.Frame(parent)
        tools_frame.pack(fill=BOTH, expand=True, padx=8, pady=(0, 8))
        self.tools_text = Text(
            tools_frame, wrap="word", font=("Segoe UI", 8),
            relief="flat", bd=0, state="disabled",
        )
        tools_scroll = ttk.Scrollbar(tools_frame, orient="vertical", command=self.tools_text.yview)
        self.tools_text.configure(yscrollcommand=tools_scroll.set)
        tools_scroll.pack(side=RIGHT, fill=Y)
        self.tools_text.pack(side=LEFT, fill=BOTH, expand=True)

    def _build_chat_panel(self, parent: ttk.Frame) -> None:
        chat_frame = ttk.LabelFrame(parent, text="Chat")
        chat_frame.pack(fill=BOTH, expand=True, pady=(4, 4))

        self.chat_text = scrolledtext.ScrolledText(
            chat_frame, wrap="word", font=("Segoe UI", 10),
            state="disabled", relief="flat", bd=0,
            spacing1=3, spacing3=3,
        )
        self.chat_text.pack(fill=BOTH, expand=True, padx=6, pady=6)
        self.chat_text.tag_configure("you",   foreground="#0969da", font=("Segoe UI", 10, "bold"))
        self.chat_text.tag_configure("agent", foreground="#1c2128", font=("Segoe UI", 10))
        self.chat_text.tag_configure("error", foreground=_RED,      font=("Segoe UI", 10, "italic"))
        self.chat_text.tag_configure("placeholder", foreground="#8b949e", font=("Segoe UI", 10, "italic"))

        input_frame = ttk.Frame(parent)
        input_frame.pack(fill=X, pady=(0, 6))
        self.message_entry = ttk.Entry(input_frame, font=("Segoe UI", 11))
        self.message_entry.pack(side=LEFT, fill=X, expand=True, ipady=4, padx=(0, 6))
        self.message_entry.bind("<Return>", lambda _e: self.on_send())
        self.send_button = ttk.Button(
            input_frame, text="Send ▶", command=self.on_send,
            style="Send.TButton", width=8,
        )
        self.send_button.pack(side=RIGHT)

    def _build_right_panel(self, parent: ttk.Frame) -> None:
        actions = ttk.Frame(parent)
        actions.pack(fill=X, pady=(4, 4))
        add_refresh_button(actions, self.refresh_status, label="⟳ Status")
        add_refresh_button(actions, self.refresh_logs,  label="⟳ Logs")
        ttk.Button(actions, text="✕ Chat",     command=self.clear_chat).pack(side=LEFT, padx=(6, 0))
        ttk.Button(actions, text="✕ Activity", command=self.clear_activity).pack(side=LEFT, padx=(4, 0))

        nb = ttk.Notebook(parent)
        nb.pack(fill=BOTH, expand=True)

        def _tab(title: str) -> ttk.Frame:
            frame = ttk.Frame(nb, padding=4)
            nb.add(frame, text=title)
            return frame

        detail_tab = _tab("Details")
        self.details_text = labeled_scroll_text(detail_tab, height=0, font=("Consolas", 9))

        activity_tab = _tab("Activity")
        self.activity_list = labeled_scroll_text(activity_tab, height=0, font=("Consolas", 9), wrap="none")

        status_tab = _tab("Status")
        self.status_text = labeled_scroll_text(status_tab, height=0, font=("Consolas", 9))

        config_tab = _tab("Config")
        self.config_text = labeled_scroll_text(config_tab, height=0, font=("Consolas", 9))

        logs_tab = _tab("Logs")
        ttk.Label(logs_tab, text="Agent", style="Section.TLabel").pack(anchor="w")
        self.agent_logs_text = labeled_scroll_text(logs_tab, height=12, font=("Consolas", 8), wrap="none")
        ttk.Label(logs_tab, text="Bridge", style="Section.TLabel").pack(anchor="w", pady=(6, 0))
        self.bridge_logs_text = labeled_scroll_text(logs_tab, height=12, font=("Consolas", 8), wrap="none")

    def _build_statusbar(self) -> None:
        bar = ttk.Frame(self.root, relief="sunken", padding=(8, 2))
        bar.pack(fill=X, side="bottom")
        self.statusbar_label = ttk.Label(bar, text="Mashbak Desktop  •  locked", style="StatusBar.TLabel")
        self.statusbar_label.pack(side=LEFT)
        ttk.Label(bar, text=f"Model: {self.openai_model}", style="StatusBar.TLabel").pack(side=RIGHT)

    # ── lock / unlock ──────────────────────────────────────────────────────────

    def _show_chat_placeholder(self) -> None:
        self.chat_text.configure(state="normal")
        self.chat_text.delete("1.0", END)
        self.chat_text.insert(
            "1.0",
            "Enter your PIN in the header bar to unlock and start chatting.",
            "placeholder",
        )
        self.chat_text.configure(state="disabled")

    def unlock_app(self) -> None:
        candidate = self.pin_entry.get().strip()
        self.pin_entry.delete(0, END)

        if candidate != self.local_app_pin:
            self.is_unlocked = False
            self.lock_icon_label.configure(text="🔒")
            self.lock_status.configure(text="Wrong PIN", foreground=_RED)
            self.statusbar_label.configure(text="Mashbak Desktop  •  locked — wrong PIN")
            self._set_interaction_enabled(False)
            self.root.after(2000, lambda: self.lock_status.configure(
                text="Locked", foreground="#cdd9e5",
            ))
            return

        self.is_unlocked = True
        self.lock_icon_label.configure(text="🔓")
        self.lock_status.configure(text="Unlocked", foreground=_GREEN)
        self.unlock_button.configure(state="disabled")
        self.pin_entry.configure(state="disabled")
        self.statusbar_label.configure(text="Mashbak Desktop  •  unlocked")
        self.chat_text.configure(state="normal")
        self.chat_text.delete("1.0", END)
        self.chat_text.configure(state="disabled")
        self._set_interaction_enabled(True)
        self.message_entry.focus_set()

    def _set_interaction_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.message_entry.configure(state=state)
        self.send_button.configure(state=state)
        for button in self.quick_buttons:
            button.configure(state=state)

    # ── messaging ──────────────────────────────────────────────────────────────

    def _send_quick_command(self, message: str) -> None:
        if not self.is_unlocked:
            return
        self.message_entry.delete(0, END)
        self.message_entry.insert(0, message)
        self.on_send()

    def on_send(self) -> None:
        if not self.is_unlocked:
            return
        message = self.message_entry.get().strip()
        if not message:
            return

        self.send_button.configure(state="disabled")
        self.message_entry.delete(0, END)
        self._append_chat("you", message)
        self._append_chat("pending", "…")
        set_text(self.details_text, "Running…")

        thread = threading.Thread(target=self._run_message, args=(message,), daemon=True)
        thread.start()

    def _append_chat(self, role: str, text: str) -> None:
        self.chat_text.configure(state="normal")
        if self.chat_text.get("1.0", END).strip():
            self.chat_text.insert(END, "\n\n")
        if role == "you":
            self.chat_text.insert(END, "You: ", "you")
            self.chat_text.insert(END, text, "you")
        elif role == "pending":
            self.chat_text.insert(END, "Mashbak: ", "agent")
            self.chat_text.insert(END, text, "agent")
        elif role == "error":
            self.chat_text.insert(END, "Mashbak: ", "agent")
            self.chat_text.insert(END, text, "error")
        else:
            self.chat_text.insert(END, "Mashbak: ", "agent")
            self.chat_text.insert(END, text, "agent")
        self.chat_text.configure(state="disabled")
        self.chat_text.see(END)

    def _replace_last_pending(self, text: str, tag: str = "agent") -> None:
        """Replace the trailing '…' placeholder with the real response."""
        self.chat_text.configure(state="normal")
        content = self.chat_text.get("1.0", END)
        idx = content.rfind("Mashbak: …")
        if idx >= 0:
            line = content[:idx].count("\n") + 1
            col  = idx - content[:idx].rfind("\n") - 1
            self.chat_text.delete(f"{line}.{col}", END)
            self.chat_text.insert(END, "Mashbak: ", "agent")
            self.chat_text.insert(END, text, tag)
        self.chat_text.configure(state="disabled")
        self.chat_text.see(END)

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
            "messages": [
                {"role": "system", "content": "You are Mashbak Desktop assistant. Reply clearly and concisely."},
                {"role": "user",   "content": message},
            ],
            "max_tokens": 400,
        }

        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
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
            return parsed["choices"][0]["message"]["content"].strip()
        except Exception:
            return None

    def _display_result(self, message: str, result: dict) -> None:
        self.send_button.configure(state="normal")

        trace = result.get("trace") or {}
        detail_lines = [
            f"Tool:           {result.get('tool_name')}",
            f"Success:        {result.get('success')}",
            f"Request ID:     {result.get('request_id')}",
            f"Exec time (ms): {trace.get('execution_time_ms')}",
            "",
            f"Intent class:   {trace.get('intent_classification')}",
            f"Interpreted:    {trace.get('interpreted_intent')}",
            f"Selected tool:  {trace.get('selected_tool')}",
            f"Validation:     {trace.get('validation_status')}",
            f"Exec status:    {trace.get('execution_status')}",
            "",
            f"Args: {json.dumps(trace.get('interpreted_args', {}), ensure_ascii=True)}",
        ]
        set_text(self.details_text, "\n".join(detail_lines))

        final_text = (
            result.get("output") or "Command executed successfully."
            if result.get("success")
            else result.get("error") or "Request failed."
        )
        response_tag = "agent" if result.get("success") else "error"
        self._replace_last_pending(final_text, response_tag)

        self.chat_history.append(("you", message))
        self.chat_history.append((response_tag, final_text))
        if len(self.chat_history) > 200:
            self.chat_history = self.chat_history[-200:]

        ts = datetime.now().strftime("%H:%M:%S")
        tool = result.get("tool_name") or "ai_chat"
        self.activity.insert(0, f"{ts}  {tool}  {message[:60]}")
        self.activity = self.activity[:50]
        set_text(self.activity_list, "\n".join(self.activity))

        self.refresh_logs()

    def _display_error(self, error_text: str) -> None:
        self.send_button.configure(state="normal")
        set_text(self.details_text, f"Error:\n{error_text}")
        self._replace_last_pending(error_text, "error")

        self.chat_history.append(("you", "[message failed]"))
        self.chat_history.append(("error", error_text))

        ts = datetime.now().strftime("%H:%M:%S")
        self.activity.insert(0, f"{ts}  [error]  {error_text[:60]}")
        self.activity = self.activity[:50]
        set_text(self.activity_list, "\n".join(self.activity))

    def refresh_status(self) -> None:
        summary = self.runtime_summary

        agent_status  = self._check_agent_health()
        bridge_status = self._check_http_health("http://127.0.0.1:34567/health")

        self.agent_badge.configure(
            text=f"Agent ●",
            foreground=(_GREEN if agent_status["running"] else _RED),
        )
        self.bridge_badge.configure(
            text=f"Bridge ●",
            foreground=(_GREEN if bridge_status["running"] else _RED),
        )

        set_text(self.status_text, "\n".join([
            f"Agent  : {'running' if agent_status['running']  else 'NOT RUNNING'}",
            f"Bridge : {'running' if bridge_status['running'] else 'NOT RUNNING'}",
            "",
            f"Agent  detail : {agent_status['detail']}",
            f"Bridge detail : {bridge_status['detail']}",
        ]))

        tools_response = self.client.list_tools()
        tools_payload = tools_response.get("tools")
        tools: list = []
        if isinstance(tools_payload, dict):
            tools = list(tools_payload.values())
        elif isinstance(tools_payload, list):
            tools = tools_payload

        tool_lines = []
        for item in tools:
            if isinstance(item, dict):
                tool_lines.append(f"▸ {item.get('name') or 'unknown'}")
                desc = (item.get("description") or "").strip()
                if desc:
                    tool_lines.append(f"  {desc}")
            else:
                tool_lines.append(f"▸ {item}")

        self.tools_text.configure(state="normal")
        self.tools_text.delete("1.0", END)
        self.tools_text.insert("1.0", "\n".join(tool_lines) if tool_lines else "unavailable")
        self.tools_text.configure(state="disabled")

        config_lines = [
            f"Workspace : {summary['workspace']}",
            "",
            "Allowed directories:",
        ]
        config_lines.extend([f"  {item}" for item in summary["allowed_directories"]])
        config_lines += [
            "",
            f"Allowed tools : {summary['allowed_tools']}",
            f"Timeout (s)   : {summary['tool_timeout_seconds']}",
        ]
        set_text(self.config_text, "\n".join(config_lines))

    def refresh_logs(self) -> None:
        agent_lines  = self._tail_file(self.agent_log_file,  max_lines=40)
        bridge_lines = self._tail_file(self.bridge_log_file, max_lines=40)
        set_text(self.agent_logs_text,  "\n".join(agent_lines)  if agent_lines  else "No agent logs yet.")
        set_text(self.bridge_logs_text, "\n".join(bridge_lines) if bridge_lines else "No bridge logs yet.")

    # ── helpers ────────────────────────────────────────────────────────────────

    def _check_agent_health(self) -> dict:
        health = self.client.health()
        if health.get("status") == "ok":
            return {"running": True, "detail": json.dumps(health, ensure_ascii=True)[:200]}
        return {"running": False, "detail": health.get("error", "unavailable")}

    def _tail_file(self, path: Path, max_lines: int = 40) -> list[str]:
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            return lines[-max_lines:]
        except Exception as exc:
            return [f"Error reading {path.name}: {exc}"]

    def _check_http_health(self, url: str) -> dict:
        try:
            with urllib.request.urlopen(url, timeout=1.2) as response:
                raw = response.read().decode("utf-8", errors="replace")
                return {"running": response.status == 200, "detail": raw.strip()[:200]}
        except urllib.error.URLError as exc:
            return {"running": False, "detail": str(exc.reason)}
        except Exception as exc:
            return {"running": False, "detail": str(exc)}

    # ── clear actions ──────────────────────────────────────────────────────────

    def clear_chat(self) -> None:
        self.chat_history.clear()
        self.chat_text.configure(state="normal")
        self.chat_text.delete("1.0", END)
        self.chat_text.configure(state="disabled")

    def clear_activity(self) -> None:
        self.activity.clear()
        set_text(self.activity_list, "")
