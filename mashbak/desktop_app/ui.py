"""Tkinter UI for local Mashbak control and observability."""

import json
import threading
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, Y, Text, Tk
from tkinter import ttk

from widgets import add_refresh_button, labeled_scroll_text, make_scrolled_text, set_text

try:
    from agent.redaction import sanitize_for_logging
except Exception:  # pragma: no cover - desktop fallback if import path changes
    def sanitize_for_logging(value, key=None):
        return value

_GREEN = "#1a7f37"
_RED = "#b42318"
_AMBER = "#9a6700"
_SLATE = "#57606a"


class DesktopControlApp:
    def __init__(
        self,
        root: Tk,
        client,
        runtime_summary: dict,
        local_app_pin: str | None = None,
    ):
        if not local_app_pin:
            raise RuntimeError("LOCAL_APP_PIN is required. Set it in mashbak/.env.master or the environment.")

        self.root = root
        self.root.title("Mashbak Desktop")
        self.root.geometry("1380x860")
        self.root.minsize(960, 640)

        self.client = client
        self.runtime_summary = runtime_summary
        self.local_app_pin = local_app_pin
        self.activity: list[str] = []
        self.chat_history: list[tuple[str, str]] = []
        self.quick_buttons: list[ttk.Button] = []
        self.lock_sensitive_buttons: list[ttk.Button] = []
        self.is_unlocked = False
        self.pending_start_index: str | None = None

        workspace = Path(runtime_summary["workspace"])
        platform_root = workspace.parent.parent
        self.agent_log_file = platform_root / "data" / "logs" / "agent.log"
        self.bridge_log_file = platform_root / "data" / "logs" / "bridge.log"

        self._apply_styles()
        self._build_ui()
        self._set_backend_status("starting", "Mashbak is starting the local assistant backend.")
        self._lock_ui("Mashbak is locked. Enter your PIN above to unlock the assistant.")

    # ── theming ────────────────────────────────────────────────────────────────

    def _apply_styles(self) -> None:
        style = ttk.Style(self.root)
        for theme in ("vista", "clam", "default"):
            if theme in style.theme_names():
                style.theme_use(theme)
                break

        style.configure("Header.TFrame", background="#1c2128")
        style.configure("Header.TLabel", background="#1c2128", foreground="#cdd9e5", font=("Segoe UI", 10))
        style.configure("AppTitle.TLabel", background="#1c2128", foreground="#e6edf3", font=("Segoe UI", 16, "bold"))
        style.configure("SubTitle.TLabel", background="#1c2128", foreground="#9fb0c1", font=("Segoe UI", 9))
        style.configure("Section.TLabel", font=("Segoe UI", 10, "bold"), foreground="#1f2328")
        style.configure("ConversationTitle.TLabel", font=("Segoe UI", 12, "bold"), foreground="#1f2328")
        style.configure("ConversationSub.TLabel", font=("Segoe UI", 9), foreground=_SLATE)
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

        title_col = ttk.Frame(header, style="Header.TFrame")
        title_col.pack(side=LEFT)
        ttk.Label(title_col, text="Mashbak", style="AppTitle.TLabel").pack(anchor="w")
        ttk.Label(title_col, text="Personal desktop assistant", style="SubTitle.TLabel").pack(anchor="w")

        self.backend_status_label = ttk.Label(header, text="Starting backend", style="Header.TLabel")
        self.backend_status_label.pack(side=LEFT, padx=(20, 0))

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
        self.unlock_button.pack(side=LEFT, padx=(0, 6))
        self.lock_button = ttk.Button(lock_bar, text="Lock", command=self.lock_app, width=7, state="disabled")
        self.lock_button.pack(side=LEFT, padx=(0, 16))

        self.bridge_badge = ttk.Label(header, text="Bridge: checking", style="Header.TLabel")
        self.bridge_badge.pack(side=RIGHT, padx=(0, 10))
        self.agent_badge = ttk.Label(header, text="Agent: starting", style="Header.TLabel")
        self.agent_badge.pack(side=RIGHT, padx=(0, 10))

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Quick Commands", style="Section.TLabel").pack(
            anchor="w", padx=8, pady=(8, 4)
        )
        for label, message in [
            ("Inbox Summary", "Do I have any new emails?"),
            ("System Info", "system info"),
            ("CPU Usage", "How busy is my computer right now?"),
            ("Running Apps", "show running processes"),
            ("Current Time", "what time is it"),
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

        intro = ttk.Frame(chat_frame)
        intro.pack(fill=X, padx=10, pady=(10, 0))
        ttk.Label(intro, text="Conversation", style="ConversationTitle.TLabel").pack(anchor="w")
        ttk.Label(
            intro,
            text="Mashbak replies here in natural language using the shared backend assistant.",
            style="ConversationSub.TLabel",
        ).pack(anchor="w", pady=(0, 8))

        self.chat_state_label = ttk.Label(
            intro,
            text="Waiting for unlock",
            style="ConversationSub.TLabel",
        )
        self.chat_state_label.pack(anchor="w")

        self.chat_text = make_scrolled_text(
            chat_frame, wrap="word", font=("Segoe UI", 10),
            state="disabled", relief="flat", bd=0,
            spacing1=3, spacing3=3, padx=6, pady=6,
        )
        self.chat_text.tag_configure("user_meta", foreground=_SLATE, font=("Segoe UI", 8, "bold"), justify="right")
        self.chat_text.tag_configure("assistant_meta", foreground=_SLATE, font=("Segoe UI", 8, "bold"), justify="left")
        self.chat_text.tag_configure("user_bubble", foreground="#0a3069", background="#ddf4ff", font=("Segoe UI", 10), lmargin1=190, lmargin2=190, rmargin=12, spacing3=10, justify="right")
        self.chat_text.tag_configure("assistant_bubble", foreground="#1f2328", background="#f6f8fa", font=("Segoe UI", 10), lmargin1=12, lmargin2=12, rmargin=190, spacing3=10)
        self.chat_text.tag_configure("error_bubble", foreground="#8c2f39", background="#fff1f0", font=("Segoe UI", 10), lmargin1=12, lmargin2=12, rmargin=190, spacing3=10)
        self.chat_text.tag_configure("system_bubble", foreground="#57606a", background="#f3f4f6", font=("Segoe UI", 10, "italic"), lmargin1=70, lmargin2=70, rmargin=70, spacing3=12, justify="center")
        self.chat_text.tag_configure("pending_bubble", foreground="#57606a", background="#f6f8fa", font=("Segoe UI", 10, "italic"), lmargin1=12, lmargin2=12, rmargin=190, spacing3=10)

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
        self.refresh_status_button = add_refresh_button(actions, self.refresh_status, label="⟳ Status")
        self.refresh_logs_button = add_refresh_button(actions, self.refresh_logs,  label="⟳ Logs")
        self.clear_chat_button = ttk.Button(actions, text="✕ Chat", command=self.clear_chat)
        self.clear_chat_button.pack(side=LEFT, padx=(6, 0))
        self.clear_activity_button = ttk.Button(actions, text="✕ Activity", command=self.clear_activity)
        self.clear_activity_button.pack(side=LEFT, padx=(4, 0))

        self.lock_sensitive_buttons.extend([
            self.refresh_status_button,
            self.refresh_logs_button,
            self.clear_chat_button,
            self.clear_activity_button,
        ])

        nb = ttk.Notebook(parent)
        nb.pack(fill=BOTH, expand=True)
        self.info_notebook = nb

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
        model_label = self.runtime_summary.get("assistant_model") or "fallback"
        ttk.Label(bar, text=f"Assistant model: {model_label}", style="StatusBar.TLabel").pack(side=RIGHT)

    # ── lock / unlock ──────────────────────────────────────────────────────────

    def _show_chat_placeholder(self) -> None:
        self.chat_text.configure(state="normal")
        self.chat_text.delete("1.0", END)
        self.chat_text.insert("1.0", "Mashbak is locked.\nEnter your PIN to unlock your assistant.", "system_bubble")
        self.chat_text.configure(state="disabled")
        self.pending_start_index = None

    def unlock_app(self) -> None:
        candidate = self.pin_entry.get().strip()
        self.pin_entry.delete(0, END)

        if candidate != self.local_app_pin:
            self.lock_status.configure(text="Wrong PIN", foreground=_RED)
            self.statusbar_label.configure(text="Mashbak Desktop  •  locked — wrong PIN")
            self._lock_ui("Desktop locked. Enter PIN to unlock.")
            self.root.after(2000, lambda: self.lock_status.configure(
                text="Locked", foreground="#cdd9e5",
            ))
            return

        self.is_unlocked = True
        self.lock_icon_label.configure(text="🔓")
        self.lock_status.configure(text="Unlocked", foreground=_GREEN)
        self.unlock_button.configure(state="disabled")
        self.lock_button.configure(state="normal")
        self.pin_entry.configure(state="disabled")
        self.statusbar_label.configure(text="Mashbak Desktop  •  unlocked")
        self.chat_state_label.configure(text="Unlocked and ready")
        self.chat_text.configure(state="normal")
        self.chat_text.delete("1.0", END)
        self.chat_text.configure(state="disabled")
        self._set_interaction_enabled(True)
        self._append_message("assistant", "I'm ready. Ask me about your computer, files, or email.")
        self.refresh_status()
        self.refresh_logs()
        self.message_entry.focus_set()

    def lock_app(self) -> None:
        self._lock_ui("Desktop locked. Enter PIN to unlock.")

    def _lock_ui(self, details_message: str) -> None:
        self.is_unlocked = False
        self.lock_icon_label.configure(text="🔒")
        self.lock_status.configure(text="Locked", foreground="#cdd9e5")
        self.statusbar_label.configure(text="Mashbak Desktop  •  locked")
        self.chat_state_label.configure(text="Locked until you enter your PIN")
        self.unlock_button.configure(state="normal")
        self.lock_button.configure(state="disabled")
        self.pin_entry.configure(state="normal")
        self._set_interaction_enabled(False)

        self._show_chat_placeholder()
        set_text(self.details_text, details_message)
        set_text(self.activity_list, "Locked")
        set_text(self.status_text, "Locked")
        set_text(self.config_text, "Locked")
        set_text(self.agent_logs_text, "Locked")
        set_text(self.bridge_logs_text, "Locked")
        self.tools_text.configure(state="normal")
        self.tools_text.delete("1.0", END)
        self.tools_text.insert("1.0", "Locked")
        self.tools_text.configure(state="disabled")
        self.pin_entry.focus_set()

    def _set_interaction_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.message_entry.configure(state=state)
        self.send_button.configure(state=state)
        for button in self.quick_buttons:
            button.configure(state=state)
        for button in self.lock_sensitive_buttons:
            button.configure(state=state)
        try:
            self.info_notebook.configure(state=state)
        except Exception:
            pass

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
        self._append_message("user", message)
        self._append_message("pending", "Mashbak is thinking…")
        self.chat_state_label.configure(text="Waiting for Mashbak's reply")
        set_text(self.details_text, "Mashbak is processing your message…")

        thread = threading.Thread(target=self._run_message, args=(message,), daemon=True)
        thread.start()

    def _append_message(self, role: str, text: str) -> None:
        self.chat_text.configure(state="normal")
        has_prior = bool(self.chat_text.get("1.0", END).strip())
        timestamp = datetime.now().strftime("%I:%M %p").lstrip("0")
        if role == "user":
            if has_prior:
                self.chat_text.insert(END, "\n\n")
            self.chat_text.insert(END, f"You  •  {timestamp}\n", "user_meta")
            self.chat_text.insert(END, text, "user_bubble")
        elif role == "assistant":
            if has_prior:
                self.chat_text.insert(END, "\n\n")
            self.chat_text.insert(END, f"Mashbak  •  {timestamp}\n", "assistant_meta")
            self.chat_text.insert(END, text, "assistant_bubble")
        elif role == "error":
            if has_prior:
                self.chat_text.insert(END, "\n\n")
            self.chat_text.insert(END, f"Mashbak  •  {timestamp}\n", "assistant_meta")
            self.chat_text.insert(END, text, "error_bubble")
        elif role == "system":
            if has_prior:
                self.chat_text.insert(END, "\n\n")
            self.chat_text.insert(END, text, "system_bubble")
        else:
            # Set a mark with LEFT gravity BEFORE inserting the separator so that
            # _replace_last_pending can delete(mark, END) and remove exactly the
            # separator + meta + pending text in one step – no trailing \n\n orphan.
            self.chat_text.mark_set("pending_msg_start", "end")
            self.chat_text.mark_gravity("pending_msg_start", "left")
            self.pending_start_index = "pending_msg_start"
            if has_prior:
                self.chat_text.insert(END, "\n\n")
            self.chat_text.insert(END, f"Mashbak  •  {timestamp}\n", "assistant_meta")
            self.chat_text.insert(END, text, "pending_bubble")
        self.chat_text.configure(state="disabled")
        self.chat_text.see(END)

    def _replace_last_pending(self, text: str, tag: str = "assistant") -> None:
        self.chat_text.configure(state="normal")
        if self.pending_start_index:
            # delete(mark, END) removes the separator \n\n + the pending meta + the
            # pending text in one shot, leaving only the prior user content.
            self.chat_text.delete(self.pending_start_index, END)
            self.pending_start_index = None
            # Add a single clean separator before the final response.
            if self.chat_text.get("1.0", END).strip():
                self.chat_text.insert(END, "\n\n")
            timestamp = datetime.now().strftime("%I:%M %p").lstrip("0")
            self.chat_text.insert(END, f"Mashbak  •  {timestamp}\n", "assistant_meta")
            bubble_tag = "assistant_bubble" if tag == "assistant" else "error_bubble"
            self.chat_text.insert(END, text, bubble_tag)
        self.chat_text.configure(state="disabled")
        self.chat_text.see(END)

    def _run_message(self, message: str) -> None:
        try:
            result = self.client.execute_nl(
                message=message,
                sender="local-desktop",
                owner_unlocked=self.is_unlocked,
            )
            self.root.after(0, lambda: self._display_result(message, result))
        except Exception as exc:
            self.root.after(0, lambda: self._display_error(str(exc)))

    def _display_result(self, message: str, result: dict) -> None:
        self.send_button.configure(state="normal")
        self.chat_state_label.configure(text="Connected and ready")

        trace = result.get("trace") or {}
        context = trace.get("context") or {}
        raw_tool_output = trace.get("tool_output")
        safe_trace_args = sanitize_for_logging(trace.get("interpreted_args", {}))
        safe_raw_tool_output = sanitize_for_logging(raw_tool_output)
        safe_message = sanitize_for_logging(message)
        detail_lines = [
            f"Assistant mode: {trace.get('assistant_mode')}",
            f"Tool:           {result.get('tool_name')}",
            f"Success:        {result.get('success')}",
            f"Request ID:     {result.get('request_id')}",
            f"Exec time (ms): {trace.get('execution_time_ms')}",
            f"Reply source:   {trace.get('assistant_response_source')}",
            "",
            f"Intent class:   {trace.get('intent_classification')}",
            f"Interpreted:    {trace.get('interpreted_intent')}",
            f"Selected tool:  {trace.get('selected_tool')}",
            f"Validation:     {trace.get('validation_status')}",
            f"Exec status:    {trace.get('execution_status')}",
            f"Topic:          {trace.get('topic') or trace.get('followup_topic')}",
            f"Ctx topic:      {context.get('last_topic')}",
            f"Ctx intent:     {context.get('last_intent')}",
            f"Ctx tool:       {context.get('last_tool')}",
            f"Ctx failure:    {context.get('last_failure_type')}",
            f"Cfg progress:   {context.get('config_progress_state')}",
            f"Cfg missing:    {', '.join(context.get('missing_config_fields') or []) or 'none'}",
            f"Cfg restart:    {', '.join(context.get('pending_restart_components') or []) or 'none'}",
            "",
            f"Args: {json.dumps(safe_trace_args, ensure_ascii=True)}",
        ]
        if safe_raw_tool_output:
            detail_lines += ["", "Raw tool output:", str(safe_raw_tool_output)]
        set_text(self.details_text, "\n".join(detail_lines))

        final_text = (
            result.get("output") or "Mashbak finished that request."
            if result.get("success")
            else result.get("error") or "Request failed."
        )
        response_tag = "assistant" if result.get("success") else "error"
        self._replace_last_pending(final_text, response_tag)

        self.chat_history.append(("user", message))
        self.chat_history.append((response_tag, final_text))
        if len(self.chat_history) > 200:
            self.chat_history = self.chat_history[-200:]

        ts = datetime.now().strftime("%H:%M:%S")
        tool = result.get("tool_name") or trace.get("assistant_mode") or "conversation"
        self.activity.insert(0, f"{ts}  {tool}  {str(safe_message)[:60]}")
        self.activity = self.activity[:50]
        set_text(self.activity_list, "\n".join(self.activity))

        self.refresh_logs()

    def _display_error(self, error_text: str) -> None:
        self.send_button.configure(state="normal")
        self.chat_state_label.configure(text="Connection problem")
        set_text(self.details_text, f"Error:\n{error_text}")
        self._replace_last_pending(error_text, "error")

        self.chat_history.append(("user", "[message failed]"))
        self.chat_history.append(("error", error_text))

        ts = datetime.now().strftime("%H:%M:%S")
        self.activity.insert(0, f"{ts}  [error]  {error_text[:60]}")
        self.activity = self.activity[:50]
        set_text(self.activity_list, "\n".join(self.activity))

    def refresh_status(self) -> None:
        summary = self.runtime_summary

        agent_status  = self._check_agent_health()
        bridge_status = self._check_http_health("http://127.0.0.1:34567/health")

        self._set_service_badge(self.agent_badge, "Agent", agent_status)
        self._set_service_badge(self.bridge_badge, "Bridge", bridge_status)

        if agent_status["running"]:
            self._set_backend_status("connected", "Mashbak is connected to the local backend.")
        else:
            self._set_backend_status("error", f"Mashbak cannot reach the local backend: {agent_status['detail']}")

        if not self.is_unlocked:
            set_text(self.status_text, "Locked")
            self.tools_text.configure(state="normal")
            self.tools_text.delete("1.0", END)
            self.tools_text.insert("1.0", "Locked")
            self.tools_text.configure(state="disabled")
            set_text(self.config_text, "Locked")
            return

        set_text(self.status_text, "\n".join([
            f"Agent  : {'connected' if agent_status['running']  else 'error'}",
            f"Bridge : {'connected' if bridge_status['running'] else 'error'}",
            f"AI     : {'enabled' if summary.get('assistant_ai_enabled') else 'fallback only'}",
            f"Email  : {'configured' if summary.get('email_configured') else 'not configured'}",
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
            f"AI enabled    : {summary.get('assistant_ai_enabled')}",
            f"Model         : {summary.get('assistant_model')}",
            f"Max tokens    : {summary.get('model_response_max_tokens')}",
            f"Ctx turns     : {summary.get('session_context_max_turns')}",
            f"Log level     : {summary.get('log_level')}",
            f"Debug mode    : {summary.get('debug_mode')}",
            f"Email ready   : {summary.get('email_configured')}",
        ]
        set_text(self.config_text, "\n".join(config_lines))

    def refresh_logs(self) -> None:
        if not self.is_unlocked:
            set_text(self.agent_logs_text, "Locked")
            set_text(self.bridge_logs_text, "Locked")
            return

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

    def _set_service_badge(self, label: ttk.Label, name: str, status: dict) -> None:
        if status["running"]:
            label.configure(text=f"{name}: connected", foreground=_GREEN)
        else:
            label.configure(text=f"{name}: error", foreground=_RED)

    def _set_backend_status(self, level: str, text: str) -> None:
        colour = {"starting": _AMBER, "connected": _GREEN, "error": _RED}.get(level, "#cdd9e5")
        self.backend_status_label.configure(text=text, foreground=colour)

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
        self.pending_start_index = None
        if self.is_unlocked:
            self._append_message("assistant", "Chat cleared. I'm ready when you are.")
        else:
            self._show_chat_placeholder()

    def clear_activity(self) -> None:
        self.activity.clear()
        set_text(self.activity_list, "")
