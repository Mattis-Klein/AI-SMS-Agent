"""Tkinter UI for Mashbak Control Board."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, Y, BooleanVar, Canvas, Listbox, StringVar, Text, Tk
from tkinter import ttk

from widgets import add_refresh_button, labeled_scroll_text, make_scrolled_text, set_text

try:
    from agent.redaction import sanitize_for_logging
except Exception:  # pragma: no cover
    def sanitize_for_logging(value, key=None):
        return value


_GREEN = "#1a7f37"
_RED = "#b42318"
_AMBER = "#9a6700"
_SLATE = "#57606a"
_YELLOW = "#b98900"
_UNKNOWN = "#6b7280"
_BG = "#f3f4f7"
_CARD = "#ffffff"
_NAV_BG = "#121722"
_SURFACE = "#eaedf3"


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
        self.root.title("Mashbak Control Board")
        self.root.geometry("1520x940")
        self.root.minsize(1080, 680)

        self.client = client
        self.runtime_summary = runtime_summary
        self.local_app_pin = local_app_pin

        self.is_unlocked = False
        self.pending_start_index: str | None = None
        self.current_section = StringVar(value="Dashboard")
        self.compact_tables = BooleanVar(value=False)

        self.activity: list[str] = []
        self.chat_history: list[tuple[str, str]] = []
        self.quick_buttons: list[ttk.Button] = []
        self.lock_sensitive_buttons: list[ttk.Widget] = []
        self.last_response_text = ""
        self.last_trace_payload: dict = {}

        workspace = Path(runtime_summary.get("workspace") or "")
        platform_root = workspace.parent.parent if workspace else Path.cwd()
        self.agent_log_file = platform_root / "data" / "logs" / "agent.log"
        self.bridge_log_file = platform_root / "data" / "logs" / "bridge.log"

        self.section_frames: dict[str, ttk.Frame] = {}
        self.section_buttons: dict[str, ttk.Button] = {}
        self.status_cards: dict[str, dict] = {}

        self._apply_styles()
        self._build_ui()
        self._set_backend_status("starting", "Mashbak is starting the local assistant backend.")
        self._lock_ui("Control board locked. Enter your PIN above to unlock.")

    # ------------------------------------------------------------------
    # Theme and shell
    # ------------------------------------------------------------------

    def _apply_styles(self) -> None:
        self.root.configure(background=_BG)
        style = ttk.Style(self.root)
        for theme in ("vista", "clam", "default"):
            if theme in style.theme_names():
                style.theme_use(theme)
                break

        style.configure("App.TFrame", background=_BG)
        style.configure("Surface.TFrame", background=_SURFACE)
        style.configure("SectionSurface.TFrame", background=_SURFACE)
        style.configure("Card.TFrame", background=_CARD)
        style.configure("CardSoft.TFrame", background="#f8fafc")
        style.configure("Card.TLabelframe", background=_CARD, borderwidth=1, relief="groove")
        style.configure("Card.TLabelframe.Label", background=_CARD, foreground="#111827", font=("Segoe UI", 10, "bold"))

        style.configure("Header.TFrame", background="#0f1623")
        style.configure("Header.TLabel", background="#0f1623", foreground="#d1d8e2", font=("Segoe UI", 10))
        style.configure("HeaderBadge.TLabel", background="#1d2636", foreground="#dde4ee", font=("Segoe UI", 9, "bold"), padding=(10, 4))
        style.configure("AppTitle.TLabel", background="#0f1623", foreground="#f8fafc", font=("Segoe UI Semibold", 18, "bold"))
        style.configure("SubTitle.TLabel", background="#0f1623", foreground="#9dadc1", font=("Segoe UI", 9))
        style.configure("Section.TLabel", background=_SURFACE, font=("Segoe UI", 12, "bold"), foreground="#111827")
        style.configure("Muted.TLabel", background=_SURFACE, foreground=_SLATE, font=("Segoe UI", 9))
        style.configure("CardTitle.TLabel", background=_CARD, foreground="#111827", font=("Segoe UI Semibold", 10, "bold"))
        style.configure("CardBody.TLabel", background=_CARD, foreground="#334155", font=("Segoe UI", 9))
        style.configure("CardMeta.TLabel", background=_CARD, foreground="#64748b", font=("Segoe UI", 8))
        style.configure("StatusBar.TLabel", font=("Segoe UI", 8), foreground="#6b7280")
        style.configure("StatusDot.TLabel", font=("Segoe UI", 8, "bold"))

        style.configure("NavPane.TFrame", background=_NAV_BG)
        style.configure("NavTitle.TLabel", background=_NAV_BG, foreground="#e5e7eb", font=("Segoe UI Semibold", 11, "bold"))
        style.configure("NavSub.TLabel", background=_NAV_BG, foreground="#94a3b8", font=("Segoe UI", 9))
        style.configure("Nav.TButton", font=("Segoe UI", 10), padding=(12, 10), anchor="w", relief="flat")
        style.map(
            "Nav.TButton",
            background=[("active", "#1a2334"), ("pressed", "#23304a")],
            foreground=[("active", "#e2e8f0"), ("pressed", "#f1f5f9")],
        )
        style.configure("NavActive.TButton", font=("Segoe UI", 10, "bold"), padding=(12, 10), anchor="w", relief="flat")
        style.map(
            "NavActive.TButton",
            background=[("!disabled", "#2157bf"), ("active", "#1d4ea9")],
            foreground=[("!disabled", "#f8fbff")],
        )

        style.configure("Primary.TButton", font=("Segoe UI", 9, "bold"), padding=(10, 6))
        style.configure("Subtle.TButton", font=("Segoe UI", 9), padding=(8, 6))

        style.configure("Ops.Treeview", rowheight=24, font=("Segoe UI", 9), background="#ffffff", fieldbackground="#ffffff")
        style.configure("Ops.Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.configure("OpsDense.Treeview", rowheight=20, font=("Segoe UI", 8), background="#ffffff", fieldbackground="#ffffff")
        style.configure("OpsDense.Treeview.Heading", font=("Segoe UI", 8, "bold"))

    def _build_ui(self) -> None:
        self._build_header()

        shell = ttk.Frame(self.root, style="App.TFrame")
        shell.pack(fill=BOTH, expand=True, padx=10, pady=(8, 0))

        nav = ttk.Frame(shell, style="NavPane.TFrame", width=250)
        nav.pack(side=LEFT, fill=Y)
        nav.pack_propagate(False)
        self._build_sidebar(nav)

        ttk.Separator(shell, orient="vertical").pack(side=LEFT, fill=Y, padx=10)

        self.content_root = ttk.Frame(shell, style="Surface.TFrame")
        self.content_root.pack(side=LEFT, fill=BOTH, expand=True)

        self._build_sections(self.content_root)
        self._show_section("Dashboard")

        self._build_statusbar()

    def _build_header(self) -> None:
        header = ttk.Frame(self.root, style="Header.TFrame", padding=(14, 10))
        header.pack(fill=X)

        title_col = ttk.Frame(header, style="Header.TFrame")
        title_col.pack(side=LEFT)
        ttk.Label(title_col, text="Mashbak Control Board", style="AppTitle.TLabel").pack(anchor="w")
        ttk.Label(title_col, text="Private local operations console", style="SubTitle.TLabel").pack(anchor="w")

        self.backend_status_label = ttk.Label(header, text="Starting backend", style="Header.TLabel")
        self.backend_status_label.pack(side=LEFT, padx=(22, 0))

        badges = ttk.Frame(header, style="Header.TFrame")
        badges.pack(side=RIGHT, padx=(0, 14))
        self.agent_badge = ttk.Label(badges, text="Backend: Starting", style="HeaderBadge.TLabel")
        self.agent_badge.pack(side=LEFT, padx=(0, 8))
        self.bridge_badge = ttk.Label(badges, text="Bridge: Checking", style="HeaderBadge.TLabel")
        self.bridge_badge.pack(side=LEFT, padx=(0, 8))
        self.email_badge = ttk.Label(badges, text="Email: Unknown", style="HeaderBadge.TLabel")
        self.email_badge.pack(side=LEFT, padx=(0, 8))

        lock_bar = ttk.Frame(badges, style="Header.TFrame")
        lock_bar.pack(side=RIGHT)

        self.lock_icon_label = ttk.Label(lock_bar, text="Lock", style="Header.TLabel")
        self.lock_icon_label.pack(side=LEFT, padx=(0, 4))
        self.lock_status = ttk.Label(lock_bar, text="Locked", style="Header.TLabel")
        self.lock_status.pack(side=LEFT, padx=(0, 8))
        self.pin_entry = ttk.Entry(lock_bar, width=9, show="*", font=("Segoe UI", 10))
        self.pin_entry.pack(side=LEFT, padx=(0, 4))
        self.pin_entry.bind("<Return>", lambda _e: self.unlock_app())
        self.unlock_button = ttk.Button(lock_bar, text="Unlock", command=self.unlock_app, width=7)
        self.unlock_button.pack(side=LEFT, padx=(0, 6))
        self.lock_button = ttk.Button(lock_bar, text="Lock", command=self.lock_app, width=7, state="disabled")
        self.lock_button.pack(side=LEFT, padx=(0, 16))

        

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="CONTROL BOARD", style="NavTitle.TLabel").pack(anchor="w", padx=12, pady=(14, 2))
        ttk.Label(parent, text="Operator Navigation", style="NavSub.TLabel").pack(anchor="w", padx=12, pady=(0, 10))

        sections = [
            ("Dashboard", "Dashboard"),
            ("Chat and Console", "Chat / Console"),
            ("Assistants", "Assistants"),
            ("Communications", "Communications"),
            ("Files and Permissions", "Files & Permissions"),
            ("Projects and Files", "Projects / Files"),
            ("Activity and Audit", "Activity / Audit"),
        ]

        for label, section in sections:
            btn = ttk.Button(
                parent,
                text=label,
                style="Nav.TButton",
                command=lambda s=section: self._show_section(s),
            )
            btn.pack(fill=X, padx=10, pady=3)
            self.section_buttons[section] = btn
            self.lock_sensitive_buttons.append(btn)

        ttk.Separator(parent, orient="horizontal").pack(fill=X, padx=10, pady=12)

        quick_panel = ttk.LabelFrame(parent, text="Quick Commands", style="Card.TLabelframe")
        quick_panel.pack(fill=X, padx=10, pady=(0, 10))
        for label, message in [
            ("System Info", "system info"),
            ("CPU Usage", "How busy is my computer right now?"),
            ("Recent Emails", "Do I have any new emails?"),
            ("Current Time", "what time is it"),
        ]:
            btn = ttk.Button(quick_panel, text=label, command=lambda m=message: self._send_quick_command(m), width=24, style="Subtle.TButton")
            btn.pack(fill=X, padx=8, pady=3)
            self.quick_buttons.append(btn)

    def _build_sections(self, parent: ttk.Frame) -> None:
        self.section_frames["Dashboard"] = self._build_dashboard_section(parent)
        self.section_frames["Chat / Console"] = self._build_chat_section(parent)
        self.section_frames["Assistants"] = self._build_assistants_section(parent)
        self.section_frames["Communications"] = self._build_communications_section(parent)
        self.section_frames["Files & Permissions"] = self._build_files_section(parent)
        self.section_frames["Projects / Files"] = self._build_projects_section(parent)
        self.section_frames["Activity / Audit"] = self._build_activity_section(parent)

    def _new_section_frame(self, parent: ttk.Frame) -> ttk.Frame:
        frame = ttk.Frame(parent, style="SectionSurface.TFrame", padding=(12, 10))
        frame.pack(fill=BOTH, expand=True)
        return frame

    def _show_section(self, section: str) -> None:
        self.current_section.set(section)
        for name, frame in self.section_frames.items():
            if name == section:
                frame.pack(fill=BOTH, expand=True)
            else:
                frame.pack_forget()

        for name, button in self.section_buttons.items():
            button.configure(style="NavActive.TButton" if name == section else "Nav.TButton")

    def _build_statusbar(self) -> None:
        bar = ttk.Frame(self.root, relief="sunken", padding=(8, 2))
        bar.pack(fill=X, side="bottom")
        self.statusbar_label = ttk.Label(bar, text="Mashbak Control Board  |  locked", style="StatusBar.TLabel")
        self.statusbar_label.pack(side=LEFT)
        model_label = self.runtime_summary.get("assistant_model") or "fallback"
        ttk.Label(bar, text=f"Assistant model: {model_label}", style="StatusBar.TLabel").pack(side=RIGHT)

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _build_dashboard_section(self, parent: ttk.Frame) -> ttk.Frame:
        frame = self._new_section_frame(parent)

        head = ttk.Frame(frame, style="SectionSurface.TFrame")
        head.pack(fill=X, pady=(2, 10))
        ttk.Label(head, text="Dashboard", style="Section.TLabel").pack(side=LEFT)
        ttk.Label(head, text="System health, attention queue, and operator activity", style="Muted.TLabel").pack(side=LEFT, padx=(10, 0))
        ttk.Checkbutton(
            head,
            text="Compact tables",
            variable=self.compact_tables,
            command=lambda: self._set_table_density(self.compact_tables.get()),
        ).pack(side=RIGHT, padx=(0, 8))
        self.dashboard_refresh_btn = add_refresh_button(head, self.refresh_status, label="Refresh Dashboard")
        self.lock_sensitive_buttons.append(self.dashboard_refresh_btn)

        cards = ttk.Frame(frame, style="SectionSurface.TFrame")
        cards.pack(fill=X, pady=(0, 12))

        self._create_status_card(cards, key="backend", title="Backend", subtitle="Connection status", icon="[BE]", padx=(0, 6))
        self._create_status_card(cards, key="bridge", title="Bridge", subtitle="SMS transport status", icon="[BR]", padx=6)
        self._create_status_card(cards, key="email", title="Email", subtitle="Configuration health", icon="[EM]", padx=6)
        self._create_status_card(cards, key="assistant", title="Active Assistant", subtitle="Current primary assistant", icon="[AS]", padx=(6, 0))

        lower = ttk.Frame(frame, style="SectionSurface.TFrame")
        lower.pack(fill=BOTH, expand=True, pady=(10, 0))

        attention = ttk.LabelFrame(lower, text="Attention Queue", style="Card.TLabelframe")
        attention.pack(side=LEFT, fill=BOTH, expand=False, padx=(0, 6))
        self.attention_summary = ttk.Label(attention, text="No alerts.", style="CardBody.TLabel")
        self.attention_summary.pack(anchor="w", padx=8, pady=(8, 2))

        recent_actions = ttk.LabelFrame(lower, text="Recent Activity", style="Card.TLabelframe")
        recent_actions.pack(side=LEFT, fill=BOTH, expand=True, padx=6)
        self.dashboard_actions_tree = ttk.Treeview(
            recent_actions,
            columns=("timestamp", "assistant", "action", "result", "status"),
            show="headings",
            style="Ops.Treeview",
            height=11,
        )
        for col, width in [
            ("timestamp", 130),
            ("assistant", 100),
            ("action", 170),
            ("result", 110),
            ("status", 90),
        ]:
            self.dashboard_actions_tree.heading(col, text=col.title())
            self.dashboard_actions_tree.column(col, width=width, anchor="w")
        self.dashboard_actions_tree.tag_configure("odd", background="#f8fafc")
        self.dashboard_actions_tree.tag_configure("even", background="#ffffff")
        self.dashboard_actions_tree.pack(fill=BOTH, expand=True, padx=8, pady=8)

        recent_failures = ttk.LabelFrame(attention, text="Pending or Failed", style="Card.TLabelframe")
        recent_failures.pack(fill=BOTH, expand=True, padx=8, pady=(2, 8))
        self.dashboard_failures_tree = ttk.Treeview(
            recent_failures,
            columns=("timestamp", "assistant", "action", "result", "status"),
            show="headings",
            style="Ops.Treeview",
            height=11,
        )
        for col, width in [
            ("timestamp", 130),
            ("assistant", 100),
            ("action", 160),
            ("result", 120),
            ("status", 90),
        ]:
            self.dashboard_failures_tree.heading(col, text=col.title())
            self.dashboard_failures_tree.column(col, width=width, anchor="w")
        self.dashboard_failures_tree.tag_configure("odd", background="#fff7ed")
        self.dashboard_failures_tree.tag_configure("even", background="#ffffff")
        self.dashboard_failures_tree.pack(fill=BOTH, expand=True, padx=8, pady=8)

        quick_actions = ttk.LabelFrame(lower, text="Operator Actions", style="Card.TLabelframe")
        quick_actions.pack(side=LEFT, fill=BOTH, expand=False, padx=(6, 0))
        qa = ttk.Frame(quick_actions)
        qa.pack(fill=BOTH, expand=True, padx=10, pady=10)
        for label, msg in [
            ("Check System", "system info"),
            ("Check Emails", "list recent emails"),
            ("Show Processes", "show running processes"),
        ]:
            btn = ttk.Button(qa, text=label, command=lambda m=msg: self._send_quick_command(m), width=22, style="Subtle.TButton")
            btn.pack(fill=X, pady=4)
            self.quick_buttons.append(btn)

        return frame

    def _create_status_card(self, parent: ttk.Frame, *, key: str, title: str, subtitle: str, icon: str, padx=(0, 0)) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=(10, 10))
        card.pack(side=LEFT, fill=BOTH, expand=True, padx=padx)
        self._bind_card_hover(card)

        top = ttk.Frame(card, style="Card.TFrame")
        top.pack(fill=X)
        ttk.Label(top, text=f"{icon}  {title}", style="CardTitle.TLabel").pack(side=LEFT)

        indicator = Canvas(top, width=10, height=10, highlightthickness=0, bd=0, bg=_CARD)
        indicator.pack(side=RIGHT)
        dot_id = indicator.create_oval(1, 1, 9, 9, fill=_UNKNOWN, outline=_UNKNOWN)

        subtitle_label = ttk.Label(card, text=subtitle, style="CardBody.TLabel")
        subtitle_label.pack(anchor="w", pady=(6, 0))
        status_label = ttk.Label(card, text="Unknown", style="CardBody.TLabel")
        status_label.pack(anchor="w", pady=(4, 0))
        stamp_label = ttk.Label(card, text="Updated: --", style="CardMeta.TLabel")
        stamp_label.pack(anchor="w", pady=(4, 0))

        self.status_cards[key] = {
            "card": card,
            "indicator": indicator,
            "dot": dot_id,
            "status": status_label,
            "subtitle": subtitle_label,
            "stamp": stamp_label,
        }

    def _bind_card_hover(self, widget: ttk.Frame) -> None:
        def _on_enter(_event):
            widget.configure(padding=(11, 11))

        def _on_leave(_event):
            widget.configure(padding=(10, 10))

        widget.bind("<Enter>", _on_enter)
        widget.bind("<Leave>", _on_leave)

    def _set_table_density(self, compact: bool) -> None:
        style_name = "OpsDense.Treeview" if compact else "Ops.Treeview"
        for tree_name in ("dashboard_actions_tree", "dashboard_failures_tree", "activity_tree"):
            tree = getattr(self, tree_name, None)
            if tree is not None:
                tree.configure(style=style_name)

    def _set_status_card(self, key: str, status: str, detail: str) -> None:
        card = self.status_cards.get(key)
        if not card:
            return
        state = (status or "unknown").lower()
        if state in {"healthy", "connected", "configured", "active", "success"}:
            color = _GREEN
        elif state in {"warning", "warn", "degraded", "not configured"}:
            color = _YELLOW
        elif state in {"error", "failed", "disconnected", "failure", "blocked"}:
            color = _RED
        else:
            color = _UNKNOWN
        canvas: Canvas = card["indicator"]
        canvas.itemconfigure(card["dot"], fill=color, outline=color)
        card["status"].configure(text=detail)
        card["stamp"].configure(text=f"Updated: {datetime.now().strftime('%H:%M:%S')}")

    def _build_chat_section(self, parent: ttk.Frame) -> ttk.Frame:
        frame = self._new_section_frame(parent)

        top = ttk.Frame(frame)
        top.pack(fill=X, pady=(2, 6))
        ttk.Label(top, text="Chat / Console", style="Section.TLabel").pack(side=LEFT)
        ttk.Label(top, text="Operational conversation and execution trace", style="Muted.TLabel").pack(side=LEFT, padx=(10, 0))
        self.chat_state_label = ttk.Label(top, text="Waiting for unlock", foreground=_SLATE)
        self.chat_state_label.pack(side=LEFT, padx=(10, 0))
        self.verification_state_label = ttk.Label(top, text="Verification: Local-only", foreground=_SLATE)
        self.verification_state_label.pack(side=RIGHT)

        helper_strip = ttk.Frame(frame, style="SectionSurface.TFrame")
        helper_strip.pack(fill=X, pady=(0, 8))
        for label, cmd in [
            ("System snapshot", "system info"),
            ("Recent inbox", "list files in inbox"),
            ("Check bridge", "check bridge health"),
        ]:
            btn = ttk.Button(helper_strip, text=label, style="Subtle.TButton", command=lambda m=cmd: self._send_quick_command(m))
            btn.pack(side=LEFT, padx=(0, 6))
            self.quick_buttons.append(btn)

        body = ttk.Frame(frame)
        body.pack(fill=BOTH, expand=True)

        left = ttk.LabelFrame(body, text="Conversation", style="Card.TLabelframe")
        left.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 6))

        self.chat_text = make_scrolled_text(
            left,
            wrap="word",
            font=("Segoe UI", 10),
            state="disabled",
            relief="flat",
            bd=0,
            spacing1=3,
            spacing3=3,
            padx=6,
            pady=6,
        )
        self.chat_text.tag_configure("user_meta", foreground=_SLATE, font=("Segoe UI", 8, "bold"), justify="right")
        self.chat_text.tag_configure("assistant_meta", foreground=_SLATE, font=("Segoe UI", 8, "bold"), justify="left")
        self.chat_text.tag_configure("user_bubble", foreground="#0a3069", background="#dceeff", font=("Segoe UI", 10), lmargin1=210, lmargin2=210, rmargin=14, spacing3=10, justify="right")
        self.chat_text.tag_configure("assistant_bubble", foreground="#111827", background="#f4f6f8", font=("Segoe UI", 10), lmargin1=14, lmargin2=14, rmargin=210, spacing3=10)
        self.chat_text.tag_configure("error_bubble", foreground="#8c2f39", background="#fff1f0", font=("Segoe UI", 10), lmargin1=12, lmargin2=12, rmargin=190, spacing3=10)
        self.chat_text.tag_configure("system_bubble", foreground="#57606a", background="#f3f4f6", font=("Segoe UI", 10, "italic"), lmargin1=70, lmargin2=70, rmargin=70, spacing3=12, justify="center")
        self.chat_text.tag_configure("pending_bubble", foreground="#57606a", background="#f6f8fa", font=("Segoe UI", 10, "italic"), lmargin1=12, lmargin2=12, rmargin=190, spacing3=10)

        input_frame = ttk.LabelFrame(left, text="Operator Input", style="Card.TLabelframe")
        input_frame.pack(fill=X, padx=8, pady=8)
        self.message_entry = ttk.Entry(input_frame, font=("Segoe UI", 11))
        self.message_entry.pack(side=LEFT, fill=X, expand=True, ipady=4, padx=(8, 6), pady=8)
        self.message_entry.bind("<Return>", lambda _e: self.on_send())
        self.send_button = ttk.Button(input_frame, text="Send", command=self.on_send, width=10, style="Primary.TButton")
        self.send_button.pack(side=RIGHT, padx=(0, 8), pady=8)

        right = ttk.LabelFrame(body, text="Trace / Debug", style="Card.TLabelframe")
        right.pack(side=LEFT, fill=BOTH, expand=True, padx=(6, 0))

        self.trace_notebook = ttk.Notebook(right)
        self.trace_notebook.pack(fill=BOTH, expand=True)

        details_tab = ttk.Frame(self.trace_notebook)
        activity_tab = ttk.Frame(self.trace_notebook)
        logs_tab = ttk.Frame(self.trace_notebook)
        self.trace_notebook.add(details_tab, text="Details")
        self.trace_notebook.add(activity_tab, text="Activity")
        self.trace_notebook.add(logs_tab, text="Logs")

        self.details_text = labeled_scroll_text(details_tab, height=0, font=("Consolas", 9))
        self.activity_list = labeled_scroll_text(activity_tab, height=0, font=("Consolas", 9), wrap="none")

        ttk.Label(logs_tab, text="Agent", style="Section.TLabel").pack(anchor="w")
        self.agent_logs_text = labeled_scroll_text(logs_tab, height=10, font=("Consolas", 8), wrap="none")
        ttk.Label(logs_tab, text="Bridge", style="Section.TLabel").pack(anchor="w", pady=(6, 0))
        self.bridge_logs_text = labeled_scroll_text(logs_tab, height=10, font=("Consolas", 8), wrap="none")

        chat_actions = ttk.Frame(frame, style="SectionSurface.TFrame")
        chat_actions.pack(fill=X, pady=(6, 0))
        self.clear_chat_button = ttk.Button(chat_actions, text="Clear Conversation", command=self.clear_chat, style="Subtle.TButton")
        self.clear_chat_button.pack(side=LEFT)
        self.clear_activity_button = ttk.Button(chat_actions, text="Clear Activity", command=self.clear_activity, style="Subtle.TButton")
        self.clear_activity_button.pack(side=LEFT, padx=(6, 0))
        self.copy_response_button = ttk.Button(chat_actions, text="Copy Last Response", command=self.copy_last_response, style="Subtle.TButton")
        self.copy_response_button.pack(side=LEFT, padx=(6, 0))
        self.copy_trace_button = ttk.Button(chat_actions, text="Copy Raw Trace", command=self.copy_raw_trace, style="Subtle.TButton")
        self.copy_trace_button.pack(side=LEFT, padx=(6, 0))
        self.refresh_logs_button = add_refresh_button(chat_actions, self.refresh_logs, label="Refresh Logs")

        self.lock_sensitive_buttons.extend([
            self.message_entry,
            self.send_button,
            self.clear_chat_button,
            self.clear_activity_button,
            self.copy_response_button,
            self.copy_trace_button,
            self.refresh_logs_button,
        ])

        return frame

    def _build_assistants_section(self, parent: ttk.Frame) -> ttk.Frame:
        frame = self._new_section_frame(parent)

        head = ttk.Frame(frame)
        head.pack(fill=X, pady=(2, 8))
        ttk.Label(head, text="Assistants", style="Section.TLabel").pack(side=LEFT)
        self.refresh_assistants_button = add_refresh_button(head, self.refresh_assistants, label="Refresh")
        self.lock_sensitive_buttons.append(self.refresh_assistants_button)

        self.assistants_text = labeled_scroll_text(frame, height=0, font=("Consolas", 9), wrap="none")
        return frame

    def _build_communications_section(self, parent: ttk.Frame) -> ttk.Frame:
        frame = self._new_section_frame(parent)

        head = ttk.Frame(frame)
        head.pack(fill=X, pady=(2, 8))
        ttk.Label(head, text="Communications", style="Section.TLabel").pack(side=LEFT)
        ttk.Label(head, text="Membership routing and messaging operations", style="Muted.TLabel").pack(side=LEFT, padx=(10, 0))
        self.refresh_comms_button = add_refresh_button(head, self.refresh_communications, label="Refresh")
        self.lock_sensitive_buttons.append(self.refresh_comms_button)

        nb = ttk.Notebook(frame)
        nb.pack(fill=BOTH, expand=True)

        email_tab = ttk.Frame(nb, padding=8)
        routing_tab = ttk.Frame(nb, padding=8)
        nb.add(email_tab, text="Email")
        nb.add(routing_tab, text="SMS / Routing")

        self._build_email_panel(email_tab)
        self._build_routing_panel(routing_tab)

        return frame

    def _build_email_panel(self, parent: ttk.Frame) -> None:
        form = ttk.LabelFrame(parent, text="Email Configuration", style="Card.TLabelframe")
        form.pack(fill=X)

        grid = ttk.Frame(form)
        grid.pack(fill=X, padx=8, pady=8)

        self.email_provider = StringVar(value="imap")
        self.email_address = StringVar(value="")
        self.email_password = StringVar(value="")
        self.email_imap_host = StringVar(value="")
        self.email_imap_port = StringVar(value="993")
        self.email_mailbox = StringVar(value="INBOX")
        self.email_use_ssl = BooleanVar(value=True)

        rows = [
            ("Provider", ttk.Entry(grid, textvariable=self.email_provider, width=36)),
            ("Email Address", ttk.Entry(grid, textvariable=self.email_address, width=36)),
            ("Password / App Password", ttk.Entry(grid, textvariable=self.email_password, width=36, show="*")),
            ("IMAP Server", ttk.Entry(grid, textvariable=self.email_imap_host, width=36)),
            ("IMAP Port", ttk.Entry(grid, textvariable=self.email_imap_port, width=36)),
            ("Mailbox", ttk.Entry(grid, textvariable=self.email_mailbox, width=36)),
        ]

        for idx, (label, widget) in enumerate(rows):
            ttk.Label(grid, text=label).grid(row=idx, column=0, sticky="w", padx=(0, 8), pady=4)
            widget.grid(row=idx, column=1, sticky="w", pady=4)

        ttk.Checkbutton(grid, text="Use SSL/TLS", variable=self.email_use_ssl).grid(row=6, column=1, sticky="w", pady=4)

        actions = ttk.Frame(form)
        actions.pack(fill=X, padx=8, pady=(0, 8))
        self.email_save_button = ttk.Button(actions, text="Save Email Settings", command=self.save_email_config)
        self.email_save_button.pack(side=LEFT)
        self.email_test_button = ttk.Button(actions, text="Test Connection", command=self.test_email_connection)
        self.email_test_button.pack(side=LEFT, padx=(6, 0))

        self.email_status = ttk.Label(parent, text="Email status: unknown", foreground=_SLATE)
        self.email_status.pack(anchor="w", pady=(8, 6))

        self.email_result_text = labeled_scroll_text(parent, height=10, font=("Consolas", 9), wrap="word")

        self.lock_sensitive_buttons.extend([self.email_save_button, self.email_test_button])

    def _build_routing_panel(self, parent: ttk.Frame) -> None:
        stats = ttk.LabelFrame(parent, text="Routing Summary", style="Card.TLabelframe")
        stats.pack(fill=X)
        self.routing_counts = ttk.Label(stats, text="Approved: 0   Pending: 0   Blocked: 0", style="CardBody.TLabel")
        self.routing_counts.pack(anchor="w", padx=8, pady=8)

        top = ttk.Frame(parent)
        top.pack(fill=X)

        left = ttk.LabelFrame(top, text="Approved Members", style="Card.TLabelframe")
        left.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 6))
        self.routing_allowlist = Listbox(left, height=10)
        self.routing_allowlist.pack(fill=BOTH, expand=True, padx=8, pady=8)
        self.routing_allowlist.bind("<<ListboxSelect>>", lambda _e: self._update_routing_selection_detail("approved"))

        mid = ttk.LabelFrame(top, text="Blocked Numbers", style="Card.TLabelframe")
        mid.pack(side=LEFT, fill=BOTH, expand=True, padx=6)
        self.routing_blocked = Listbox(mid, height=10)
        self.routing_blocked.pack(fill=BOTH, expand=True, padx=8, pady=8)
        self.routing_blocked.bind("<<ListboxSelect>>", lambda _e: self._update_routing_selection_detail("blocked"))

        right = ttk.LabelFrame(top, text="Pending Join Requests", style="Card.TLabelframe")
        right.pack(side=LEFT, fill=BOTH, expand=True, padx=(6, 0))
        self.routing_pending = Listbox(right, height=10)
        self.routing_pending.pack(fill=BOTH, expand=True, padx=8, pady=8)
        self.routing_pending.bind("<<ListboxSelect>>", lambda _e: self._update_routing_selection_detail("pending"))

        detail = ttk.LabelFrame(parent, text="Selected Member", style="Card.TLabelframe")
        detail.pack(fill=X, pady=(10, 0))
        self.routing_detail = ttk.Label(detail, text="Select a member from Approved, Pending, or Blocked.", style="CardBody.TLabel")
        self.routing_detail.pack(anchor="w", padx=8, pady=8)

        controls = ttk.LabelFrame(parent, text="Member Controls", style="Card.TLabelframe")
        controls.pack(fill=X, pady=(10, 0))

        row = ttk.Frame(controls)
        row.pack(fill=X, padx=8, pady=8)
        self.routing_phone_var = StringVar(value="")
        ttk.Label(row, text="Phone").pack(side=LEFT)
        ttk.Entry(row, textvariable=self.routing_phone_var, width=28).pack(side=LEFT, padx=(6, 8))

        self.routing_activate_var = BooleanVar(value=False)
        ttk.Checkbutton(row, text="Activate now", variable=self.routing_activate_var).pack(side=LEFT)

        self.routing_approve_button = ttk.Button(row, text="Approve", command=self.approve_member)
        self.routing_approve_button.pack(side=LEFT, padx=(10, 0))
        self.routing_deactivate_button = ttk.Button(row, text="Deactivate", command=self.deactivate_member)
        self.routing_deactivate_button.pack(side=LEFT, padx=(6, 0))

        self.routing_status = ttk.Label(parent, text="Routing status: unknown", foreground=_SLATE)
        self.routing_status.pack(anchor="w", pady=(8, 6))

        self.lock_sensitive_buttons.extend([self.routing_approve_button, self.routing_deactivate_button])

    def _build_files_section(self, parent: ttk.Frame) -> ttk.Frame:
        frame = self._new_section_frame(parent)

        head = ttk.Frame(frame)
        head.pack(fill=X, pady=(2, 8))
        ttk.Label(head, text="Files & Permissions", style="Section.TLabel").pack(side=LEFT)
        self.refresh_policy_button = add_refresh_button(head, self.refresh_files_policy, label="Refresh")
        self.lock_sensitive_buttons.append(self.refresh_policy_button)

        upper = ttk.Frame(frame)
        upper.pack(fill=BOTH, expand=True)

        allowed_box = ttk.LabelFrame(upper, text="Allowed Directories", style="Card.TLabelframe")
        allowed_box.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 6))
        self.allowed_dirs_list = Listbox(allowed_box, height=16)
        self.allowed_dirs_list.pack(fill=BOTH, expand=True, padx=8, pady=8)

        blocked_box = ttk.LabelFrame(upper, text="Recent Blocked Filesystem Attempts", style="Card.TLabelframe")
        blocked_box.pack(side=LEFT, fill=BOTH, expand=True, padx=(6, 0))
        self.blocked_attempts_text = labeled_scroll_text(blocked_box, height=16, font=("Consolas", 9), wrap="none")

        actions = ttk.LabelFrame(frame, text="Policy Controls", style="Card.TLabelframe")
        actions.pack(fill=X, pady=(10, 0))

        row1 = ttk.Frame(actions)
        row1.pack(fill=X, padx=8, pady=(8, 4))
        self.new_allowed_dir_var = StringVar(value="")
        ttk.Label(row1, text="Directory").pack(side=LEFT)
        ttk.Entry(row1, textvariable=self.new_allowed_dir_var, width=65).pack(side=LEFT, padx=(8, 8), fill=X, expand=True)
        self.add_allowed_button = ttk.Button(row1, text="Add", command=self.add_allowed_directory)
        self.add_allowed_button.pack(side=LEFT)
        self.remove_allowed_button = ttk.Button(row1, text="Remove Selected", command=self.remove_selected_directory)
        self.remove_allowed_button.pack(side=LEFT, padx=(6, 0))

        row2 = ttk.Frame(actions)
        row2.pack(fill=X, padx=8, pady=(0, 8))
        self.save_policy_button = ttk.Button(row2, text="Save Allowed Directories", command=self.save_allowed_directories)
        self.save_policy_button.pack(side=LEFT)

        self.test_path_var = StringVar(value="")
        ttk.Entry(row2, textvariable=self.test_path_var, width=58).pack(side=LEFT, padx=(10, 6), fill=X, expand=True)
        self.test_path_button = ttk.Button(row2, text="Test Path", command=self.test_path_policy)
        self.test_path_button.pack(side=LEFT)

        self.policy_status_label = ttk.Label(frame, text="Policy status: unknown", foreground=_SLATE)
        self.policy_status_label.pack(anchor="w", pady=(8, 0))

        self.lock_sensitive_buttons.extend([
            self.add_allowed_button,
            self.remove_allowed_button,
            self.save_policy_button,
            self.test_path_button,
        ])

        return frame

    def _build_projects_section(self, parent: ttk.Frame) -> ttk.Frame:
        frame = self._new_section_frame(parent)

        head = ttk.Frame(frame)
        head.pack(fill=X, pady=(2, 8))
        ttk.Label(head, text="Projects / Files", style="Section.TLabel").pack(side=LEFT)
        self.refresh_projects_button = add_refresh_button(head, self.refresh_projects, label="Refresh")
        self.lock_sensitive_buttons.append(self.refresh_projects_button)

        self.projects_text = labeled_scroll_text(frame, height=0, font=("Consolas", 9), wrap="none")
        return frame

    def _build_activity_section(self, parent: ttk.Frame) -> ttk.Frame:
        frame = self._new_section_frame(parent)

        head = ttk.Frame(frame)
        head.pack(fill=X, pady=(2, 8))
        ttk.Label(head, text="Activity / Audit", style="Section.TLabel").pack(side=LEFT)
        ttk.Checkbutton(
            head,
            text="Compact tables",
            variable=self.compact_tables,
            command=lambda: self._set_table_density(self.compact_tables.get()),
        ).pack(side=RIGHT, padx=(0, 8))
        self.refresh_activity_button = add_refresh_button(head, self.refresh_activity_audit, label="Refresh")
        self.lock_sensitive_buttons.append(self.refresh_activity_button)

        columns = ("timestamp", "assistant", "action", "tool", "state", "target")
        self.activity_tree = ttk.Treeview(frame, columns=columns, show="headings", height=18, style="Ops.Treeview")
        for col, width in [
            ("timestamp", 140),
            ("assistant", 120),
            ("action", 170),
            ("tool", 130),
            ("state", 100),
            ("target", 360),
        ]:
            self.activity_tree.heading(col, text=col.title())
            self.activity_tree.column(col, width=width, anchor="w")
        self.activity_tree.tag_configure("odd", background="#f8fafc")
        self.activity_tree.tag_configure("even", background="#ffffff")
        self.activity_tree.pack(fill=BOTH, expand=True)

        self.activity_detail = labeled_scroll_text(frame, height=7, font=("Consolas", 9), wrap="word")
        return frame

    # ------------------------------------------------------------------
    # Lock handling
    # ------------------------------------------------------------------

    def _show_chat_placeholder(self) -> None:
        self.chat_text.configure(state="normal")
        self.chat_text.delete("1.0", END)
        self.chat_text.insert("1.0", "Mashbak is locked.\nEnter your PIN to unlock the control board.", "system_bubble")
        self.chat_text.configure(state="disabled")
        self.pending_start_index = None

    def unlock_app(self) -> None:
        candidate = self.pin_entry.get().strip()
        self.pin_entry.delete(0, END)

        if candidate != self.local_app_pin:
            self.lock_status.configure(text="Wrong PIN", foreground=_RED)
            self.statusbar_label.configure(text="Mashbak Control Board  |  locked (wrong PIN)")
            self._lock_ui("Control board locked. Enter PIN to unlock.")
            self.root.after(2000, lambda: self.lock_status.configure(text="Locked", foreground="#d1d5db"))
            return

        self.is_unlocked = True
        self.lock_icon_label.configure(text="Unlock")
        self.lock_status.configure(text="Unlocked", foreground=_GREEN)
        self.unlock_button.configure(state="disabled")
        self.lock_button.configure(state="normal")
        self.pin_entry.configure(state="disabled")
        self.statusbar_label.configure(text="Mashbak Control Board  |  unlocked")
        self.chat_state_label.configure(text="Connected and ready")
        self.chat_text.configure(state="normal")
        self.chat_text.delete("1.0", END)
        self.chat_text.configure(state="disabled")
        self._set_interaction_enabled(True)
        self._append_message("assistant", "Control board unlocked. I am ready.")
        self.refresh_status()
        self.refresh_logs()
        self.refresh_assistants()
        self.refresh_communications()
        self.refresh_files_policy()
        self.refresh_activity_audit()
        self.refresh_projects()
        self.message_entry.focus_set()

    def lock_app(self) -> None:
        self._lock_ui("Control board locked. Enter PIN to unlock.")

    def _lock_ui(self, details_message: str) -> None:
        self.is_unlocked = False
        self.lock_icon_label.configure(text="LOCK")
        self.lock_status.configure(text="Locked", foreground="#d1d5db")
        self.statusbar_label.configure(text="Mashbak Control Board  |  locked")
        self.unlock_button.configure(state="normal")
        self.lock_button.configure(state="disabled")
        self.pin_entry.configure(state="normal")
        self._set_interaction_enabled(False)

        self._show_chat_placeholder()
        set_text(self.details_text, details_message)
        set_text(self.activity_list, "Locked")
        set_text(self.agent_logs_text, "Locked")
        set_text(self.bridge_logs_text, "Locked")
        self.pin_entry.focus_set()

    def _set_interaction_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in self.quick_buttons:
            try:
                button.configure(state=state)
            except Exception:
                pass
        for widget in self.lock_sensitive_buttons:
            try:
                widget.configure(state=state)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    def _send_quick_command(self, message: str) -> None:
        if not self.is_unlocked:
            return
        self._show_section("Chat / Console")
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
        self._append_message("pending", "Mashbak is thinking...")
        self.chat_state_label.configure(text="Waiting for Mashbak reply")
        set_text(self.details_text, "Mashbak is processing your message...")

        thread = threading.Thread(target=self._run_message, args=(message,), daemon=True)
        thread.start()

    def _append_message(self, role: str, text: str) -> None:
        self.chat_text.configure(state="normal")
        has_prior = bool(self.chat_text.get("1.0", END).strip())
        timestamp = datetime.now().strftime("%I:%M %p").lstrip("0")

        if role == "user":
            if has_prior:
                self.chat_text.insert(END, "\n\n")
            self.chat_text.insert(END, f"You  |  {timestamp}\n", "user_meta")
            self.chat_text.insert(END, text, "user_bubble")
        elif role == "assistant":
            if has_prior:
                self.chat_text.insert(END, "\n\n")
            self.chat_text.insert(END, f"Mashbak  |  {timestamp}\n", "assistant_meta")
            self.chat_text.insert(END, text, "assistant_bubble")
        elif role == "error":
            if has_prior:
                self.chat_text.insert(END, "\n\n")
            self.chat_text.insert(END, f"Mashbak  |  {timestamp}\n", "assistant_meta")
            self.chat_text.insert(END, text, "error_bubble")
        elif role == "system":
            if has_prior:
                self.chat_text.insert(END, "\n\n")
            self.chat_text.insert(END, text, "system_bubble")
        else:
            self.chat_text.mark_set("pending_msg_start", "end")
            self.chat_text.mark_gravity("pending_msg_start", "left")
            self.pending_start_index = "pending_msg_start"
            if has_prior:
                self.chat_text.insert(END, "\n\n")
            self.chat_text.insert(END, f"Mashbak  |  {timestamp}\n", "assistant_meta")
            self.chat_text.insert(END, text, "pending_bubble")

        self.chat_text.configure(state="disabled")
        self.chat_text.see(END)

    def _replace_last_pending(self, text: str, tag: str = "assistant") -> None:
        self.chat_text.configure(state="normal")
        if self.pending_start_index:
            self.chat_text.delete(self.pending_start_index, END)
            self.pending_start_index = None
            if self.chat_text.get("1.0", END).strip():
                self.chat_text.insert(END, "\n\n")
            timestamp = datetime.now().strftime("%I:%M %p").lstrip("0")
            self.chat_text.insert(END, f"Mashbak  |  {timestamp}\n", "assistant_meta")
            bubble_tag = "assistant_bubble" if tag == "assistant" else "error_bubble"
            self.chat_text.insert(END, text, bubble_tag)
        self.chat_text.configure(state="disabled")
        self.chat_text.see(END)

    def _run_message(self, message: str) -> None:
        try:
            result = self.client.execute_nl(message=message, sender="local-desktop", owner_unlocked=self.is_unlocked)
            self.root.after(0, lambda: self._display_result(message, result))
        except Exception as exc:
            self.root.after(0, lambda: self._display_error(str(exc)))

    def _display_result(self, message: str, result: dict) -> None:
        self.send_button.configure(state="normal")
        self.chat_state_label.configure(text="Connected and ready")

        trace = result.get("trace") or {}
        verification_state = str(trace.get("verification_state") or "Local-only")
        verification_reason = str(trace.get("verification_reason") or "No verification metadata provided.")
        context = trace.get("context") or {}
        raw_tool_output = trace.get("tool_output")
        safe_trace_args = sanitize_for_logging(trace.get("interpreted_args", {}))
        safe_raw_tool_output = sanitize_for_logging(raw_tool_output)
        safe_message = sanitize_for_logging(message)

        detail_lines = [
            f"Assistant mode: {trace.get('assistant_mode')}",
            f"Tool:           {result.get('tool_name')}",
            f"Success:        {result.get('success')}",
            f"Verification:   {verification_state}",
            f"Verify reason:  {verification_reason}",
            f"Request ID:     {result.get('request_id')}",
            f"Exec time (ms): {trace.get('execution_time_ms')}",
            f"Reply source:   {trace.get('assistant_response_source')}",
            "",
            f"Intent class:   {trace.get('intent_classification')}",
            f"Selected tool:  {trace.get('selected_tool')}",
            f"Validation:     {trace.get('validation_status')}",
            f"Exec status:    {trace.get('execution_status')}",
            f"Topic:          {trace.get('topic') or trace.get('followup_topic')}",
            f"Ctx topic:      {context.get('last_topic')}",
            f"Ctx intent:     {context.get('last_intent')}",
            f"Ctx tool:       {context.get('last_tool')}",
            f"Ctx failure:    {context.get('last_failure_type')}",
            "",
            f"Args: {json.dumps(safe_trace_args, ensure_ascii=True)}",
        ]
        if safe_raw_tool_output:
            detail_lines += ["", "Raw tool output:", str(safe_raw_tool_output)]
        set_text(self.details_text, "\n".join(detail_lines))

        final_text = (
            (result.get("output") or "Mashbak finished that request.")
            if result.get("success")
            else (result.get("error") or "Request failed.")
        )
        self.last_response_text = str(final_text)
        self.last_trace_payload = dict(trace)

        verify_color = _SLATE
        if verification_state.lower() in {"verified", "tool-assisted"}:
            verify_color = _GREEN
        elif verification_state.lower() == "unverified":
            verify_color = _RED
        self.verification_state_label.configure(text=f"Verification: {verification_state}", foreground=verify_color)

        response_tag = "assistant" if result.get("success") else "error"
        self._replace_last_pending(final_text, response_tag)

        self.chat_history.append(("user", message))
        self.chat_history.append((response_tag, final_text))
        if len(self.chat_history) > 200:
            self.chat_history = self.chat_history[-200:]

        ts = datetime.now().strftime("%H:%M:%S")
        tool = result.get("tool_name") or trace.get("assistant_mode") or "conversation"
        self.activity.insert(0, f"{ts}  {tool}  {str(safe_message)[:70]}")
        self.activity = self.activity[:80]
        set_text(self.activity_list, "\n".join(self.activity))

        self.refresh_logs()
        self.refresh_activity_audit()
        self.refresh_dashboard_overview()

    def _display_error(self, error_text: str) -> None:
        self.send_button.configure(state="normal")
        self.chat_state_label.configure(text="Connection problem")
        self.verification_state_label.configure(text="Verification: Unverified", foreground=_RED)
        set_text(self.details_text, f"Error:\n{error_text}")
        self.last_response_text = str(error_text)
        self.last_trace_payload = {"error": str(error_text)}
        self._replace_last_pending(error_text, "error")

        self.chat_history.append(("user", "[message failed]"))
        self.chat_history.append(("error", error_text))

        ts = datetime.now().strftime("%H:%M:%S")
        self.activity.insert(0, f"{ts}  [error]  {error_text[:70]}")
        self.activity = self.activity[:80]
        set_text(self.activity_list, "\n".join(self.activity))

    # ------------------------------------------------------------------
    # Section refresh actions
    # ------------------------------------------------------------------

    def refresh_status(self) -> None:
        summary = self.runtime_summary

        agent_status = self._check_agent_health()
        bridge_status = self._check_http_health("http://127.0.0.1:34567/health")

        self._set_service_badge(self.agent_badge, "Backend", agent_status)
        self._set_service_badge(self.bridge_badge, "Bridge", bridge_status)
        self.email_badge.configure(
            text=("Email: Configured" if summary.get("email_configured") else "Email: Needs setup"),
            foreground=(_GREEN if summary.get("email_configured") else _YELLOW),
        )

        self._set_status_card(
            "backend",
            "connected" if agent_status["running"] else "error",
            ("Connected" if agent_status["running"] else "Disconnected") + f" | {agent_status['detail'][:80]}",
        )
        self._set_status_card(
            "bridge",
            "connected" if bridge_status["running"] else "error",
            ("Connected" if bridge_status["running"] else "Disconnected") + f" | {bridge_status['detail'][:80]}",
        )
        self._set_status_card(
            "email",
            "configured" if summary.get("email_configured") else "warning",
            "Configured" if summary.get("email_configured") else "Not configured",
        )

        if agent_status["running"]:
            self._set_backend_status("connected", "Mashbak backend connected.")
        else:
            self._set_backend_status("error", f"Mashbak cannot reach backend: {agent_status['detail']}")

        if not self.is_unlocked:
            return

        self.refresh_dashboard_overview()

    def refresh_dashboard_overview(self) -> None:
        if not self.is_unlocked:
            return
        overview = self.client.get_overview()
        if not isinstance(overview, dict) or overview.get("success") is False:
            return

        backend = overview.get("backend") or {}
        bridge = overview.get("bridge") or {}
        email = overview.get("email") or {}

        self._set_status_card(
            "assistant",
            "active",
            (overview.get("active_assistant") or "mashbak").title(),
        )
        self._set_status_card(
            "backend",
            "connected" if backend.get("connected") else "error",
            ("Connected" if backend.get("connected") else "Disconnected") + f" | model {backend.get('model')}",
        )
        self._set_status_card(
            "bridge",
            "connected" if bridge.get("connected") else "error",
            "Connected" if bridge.get("connected") else "Disconnected",
        )
        self._set_status_card(
            "email",
            "configured" if email.get("configured") else "warning",
            "Configured" if email.get("configured") else "Not configured",
        )

        for item in self.dashboard_actions_tree.get_children():
            self.dashboard_actions_tree.delete(item)
        for idx, row in enumerate(overview.get("recent_actions") or []):
            assistant = row.get("assistant") or "desktop"
            action = row.get("requested_action") or row.get("selected_tool") or "-"
            result = row.get("result") or "-"
            status = row.get("state") or "-"
            values = (row.get("timestamp") or "", assistant, action, result, status)
            tag = "even" if idx % 2 == 0 else "odd"
            self.dashboard_actions_tree.insert("", END, values=values, tags=(tag,))

        for item in self.dashboard_failures_tree.get_children():
            self.dashboard_failures_tree.delete(item)
        failures = overview.get("recent_failures") or []
        self.attention_summary.configure(text=(f"Attention items: {len(failures)}" if failures else "No items require attention."))
        for idx, row in enumerate(failures):
            ts = row.get("timestamp") or ""
            assistant = "backend"
            action = row.get("tool") or "-"
            result = row.get("error") or "failure"
            values = (ts, assistant, action, result[:80], "failure")
            tag = "even" if idx % 2 == 0 else "odd"
            self.dashboard_failures_tree.insert("", END, values=values, tags=(tag,))

    def refresh_assistants(self) -> None:
        if not self.is_unlocked:
            return
        payload = self.client.get_assistants()
        if not isinstance(payload, dict) or payload.get("success") is False:
            set_text(self.assistants_text, str(payload))
            return

        mashbak = payload.get("mashbak") or {}
        bucherim = payload.get("bucherim") or {}

        lines = [
            "Mashbak",
            f"  AI enabled: {mashbak.get('ai_enabled')}",
            f"  Model: {mashbak.get('model')}",
            f"  Base URL: {mashbak.get('base_url')}",
            f"  Temperature: {mashbak.get('temperature')}",
            f"  Max tokens: {mashbak.get('max_tokens')}",
            "",
            "Bucherim",
            f"  Assistant number: {bucherim.get('assistant_number')}",
            f"  Allowlist count: {bucherim.get('allowlist_count')}",
            f"  Blocked count: {bucherim.get('blocked_numbers_count')}",
            "",
            "Bucherim Responses",
        ]
        responses = bucherim.get("responses") or {}
        for key, value in responses.items():
            lines.append(f"  {key}: {value}")
        set_text(self.assistants_text, "\n".join(lines))

    def refresh_communications(self) -> None:
        if not self.is_unlocked:
            return
        self.refresh_email_config_view()
        self.refresh_routing_view()

    def refresh_email_config_view(self) -> None:
        payload = self.client.get_email_config()
        if not isinstance(payload, dict) or payload.get("success") is False:
            set_text(self.email_result_text, str(payload))
            return

        self.email_provider.set(str(payload.get("provider") or "imap"))
        self.email_address.set(str(payload.get("email_address") or ""))
        self.email_imap_host.set(str(payload.get("imap_host") or ""))
        self.email_imap_port.set(str(payload.get("imap_port") or "993"))
        self.email_mailbox.set(str(payload.get("mailbox") or "INBOX"))
        self.email_use_ssl.set(bool(payload.get("use_ssl")))

        self.email_status.configure(
            text=("Email status: configured" if payload.get("password_set") else "Email status: password missing"),
            foreground=(_GREEN if payload.get("password_set") else _AMBER),
        )

    def refresh_routing_view(self) -> None:
        payload = self.client.get_routing()
        if not isinstance(payload, dict) or payload.get("success") is False:
            self.routing_status.configure(text=f"Routing status: {payload}", foreground=_RED)
            return

        self.routing_allowlist.delete(0, END)
        self.routing_blocked.delete(0, END)
        self.routing_pending.delete(0, END)

        allowlist = payload.get("allowlist") or []
        blocked = payload.get("blocked_numbers") or []
        pending = payload.get("pending_join_requests") or []

        for item in allowlist:
            self.routing_allowlist.insert(END, str(item))
        for item in blocked:
            self.routing_blocked.insert(END, str(item))
        for item in pending:
            phone = item.get("phone_number") if isinstance(item, dict) else str(item)
            ts = item.get("timestamp") if isinstance(item, dict) else ""
            self.routing_pending.insert(END, f"{phone}  ({ts})")

        self.routing_counts.configure(text=f"Approved: {len(allowlist)}   Pending: {len(pending)}   Blocked: {len(blocked)}")

        self.routing_status.configure(
            text=f"Routing status: assistant number {payload.get('assistant_number')}",
            foreground=_SLATE,
        )

    def _update_routing_selection_detail(self, source: str) -> None:
        if source == "approved":
            idxs = self.routing_allowlist.curselection()
            if idxs:
                phone = self.routing_allowlist.get(idxs[0])
                self.routing_phone_var.set(phone)
                self.routing_detail.configure(text=f"Approved member selected: {phone}")
                return
        if source == "blocked":
            idxs = self.routing_blocked.curselection()
            if idxs:
                phone = self.routing_blocked.get(idxs[0])
                self.routing_phone_var.set(phone)
                self.routing_detail.configure(text=f"Blocked member selected: {phone}")
                return
        if source == "pending":
            idxs = self.routing_pending.curselection()
            if idxs:
                row = self.routing_pending.get(idxs[0])
                phone = row.split("  (")[0].strip()
                self.routing_phone_var.set(phone)
                self.routing_detail.configure(text=f"Pending request selected: {row}")
                return

    def refresh_files_policy(self) -> None:
        if not self.is_unlocked:
            return
        payload = self.client.get_files_policy()
        if not isinstance(payload, dict) or payload.get("success") is False:
            self.policy_status_label.configure(text=f"Policy status: {payload}", foreground=_RED)
            return

        self.allowed_dirs_list.delete(0, END)
        for path in payload.get("allowed_directories") or []:
            self.allowed_dirs_list.insert(END, str(path))

        lines = []
        for row in payload.get("blocked_attempts") or []:
            lines.append(
                f"{row.get('timestamp')} | {row.get('tool')} | {row.get('path') or '-'} | {row.get('error') or '-'}"
            )
        set_text(self.blocked_attempts_text, "\n".join(lines) if lines else "No blocked attempts.")
        self.policy_status_label.configure(text="Policy status: loaded", foreground=_GREEN)

    def refresh_projects(self) -> None:
        if not self.is_unlocked:
            return
        payload = self.client.get_activity(limit=120)
        if not isinstance(payload, dict) or payload.get("success") is False:
            set_text(self.projects_text, str(payload))
            return

        file_like = []
        for item in payload.get("items") or []:
            tool = str(item.get("selected_tool") or "")
            target = str(item.get("target") or "")
            if tool in {"create_file", "create_folder", "delete_file", "list_files"} or target:
                file_like.append(
                    f"{item.get('timestamp')} | {tool} | {item.get('state')} | {target or '-'}"
                )
        if not file_like:
            file_like = ["No recent file/project actions."]
        set_text(self.projects_text, "\n".join(file_like))

    def refresh_activity_audit(self) -> None:
        if not self.is_unlocked:
            return
        payload = self.client.get_activity(limit=160)
        if not isinstance(payload, dict) or payload.get("success") is False:
            set_text(self.activity_detail, str(payload))
            return

        for item in self.activity_tree.get_children():
            self.activity_tree.delete(item)

        for idx, row in enumerate(payload.get("items") or []):
            values = (
                row.get("timestamp") or "",
                row.get("assistant") or "",
                row.get("requested_action") or "",
                row.get("selected_tool") or "",
                row.get("state") or "",
                row.get("target") or "",
            )
            tag = "even" if idx % 2 == 0 else "odd"
            self.activity_tree.insert("", END, values=values, tags=(tag,))

        sample = (payload.get("items") or [])[:12]
        lines = []
        for row in sample:
            lines.append(
                f"{row.get('timestamp')} | {row.get('selected_tool')} | {row.get('state')}\n"
                f"  Details: {row.get('details') or '-'}"
            )
        set_text(self.activity_detail, "\n\n".join(lines) if lines else "No recent activity.")

    def refresh_logs(self) -> None:
        if not self.is_unlocked:
            set_text(self.agent_logs_text, "Locked")
            set_text(self.bridge_logs_text, "Locked")
            return

        agent_lines = self._tail_file(self.agent_log_file, max_lines=40)
        bridge_lines = self._tail_file(self.bridge_log_file, max_lines=40)
        set_text(self.agent_logs_text, "\n".join(agent_lines) if agent_lines else "No agent logs yet.")
        set_text(self.bridge_logs_text, "\n".join(bridge_lines) if bridge_lines else "No bridge logs yet.")

    # ------------------------------------------------------------------
    # Actions (forms/buttons)
    # ------------------------------------------------------------------

    def save_email_config(self) -> None:
        if not self.is_unlocked:
            return
        try:
            port = int(self.email_imap_port.get().strip() or "993")
        except ValueError:
            self.email_status.configure(text="Email status: invalid IMAP port", foreground=_RED)
            return

        result = self.client.save_email_config(
            provider=self.email_provider.get().strip(),
            email_address=self.email_address.get().strip(),
            password=self.email_password.get(),
            imap_host=self.email_imap_host.get().strip(),
            imap_port=port,
            use_ssl=bool(self.email_use_ssl.get()),
            mailbox=self.email_mailbox.get().strip() or "INBOX",
        )

        ok = bool(result.get("success"))
        self.email_status.configure(
            text=("Email status: saved" if ok else f"Email status: save failed ({result})"),
            foreground=(_GREEN if ok else _RED),
        )
        set_text(self.email_result_text, json.dumps(result, indent=2, ensure_ascii=True))
        self.refresh_status()

    def test_email_connection(self) -> None:
        if not self.is_unlocked:
            return
        result = self.client.test_email_connection()
        ok = bool(result.get("success"))
        message = result.get("message") or result.get("error") or "No response"
        self.email_status.configure(
            text=("Email status: test successful" if ok else "Email status: test failed"),
            foreground=(_GREEN if ok else _RED),
        )
        set_text(self.email_result_text, message)

    def approve_member(self) -> None:
        if not self.is_unlocked:
            return
        phone = self.routing_phone_var.get().strip()
        if not phone:
            self.routing_status.configure(text="Routing status: enter a phone number", foreground=_RED)
            return
        result = self.client.approve_routing_member(phone_number=phone, activate_now=bool(self.routing_activate_var.get()))
        ok = bool(result.get("success"))
        self.routing_status.configure(
            text=(f"Approved {result.get('phone_number')} ({result.get('status')})" if ok else f"Approval failed: {result}"),
            foreground=(_GREEN if ok else _RED),
        )
        if ok:
            self.refresh_routing_view()

    def deactivate_member(self) -> None:
        if not self.is_unlocked:
            return
        phone = self.routing_phone_var.get().strip()
        if not phone:
            self.routing_status.configure(text="Routing status: enter a phone number", foreground=_RED)
            return
        result = self.client.deactivate_routing_member(phone_number=phone)
        ok = bool(result.get("success"))
        self.routing_status.configure(
            text=(f"Deactivated {result.get('phone_number')}" if ok else f"Deactivate failed: {result}"),
            foreground=(_GREEN if ok else _RED),
        )
        if ok:
            self.refresh_routing_view()

    def add_allowed_directory(self) -> None:
        path = self.new_allowed_dir_var.get().strip()
        if not path:
            self.policy_status_label.configure(text="Policy status: enter a directory path", foreground=_RED)
            return
        self.allowed_dirs_list.insert(END, path)
        self.new_allowed_dir_var.set("")
        self.policy_status_label.configure(text="Policy status: directory staged", foreground=_AMBER)

    def remove_selected_directory(self) -> None:
        selected = self.allowed_dirs_list.curselection()
        if not selected:
            return
        for idx in reversed(selected):
            self.allowed_dirs_list.delete(idx)
        self.policy_status_label.configure(text="Policy status: directory removed (not saved yet)", foreground=_AMBER)

    def save_allowed_directories(self) -> None:
        values = [self.allowed_dirs_list.get(i) for i in range(self.allowed_dirs_list.size())]
        result = self.client.save_files_policy(values)
        ok = bool(result.get("success"))
        self.policy_status_label.configure(
            text=("Policy status: saved" if ok else f"Policy status: save failed ({result})"),
            foreground=(_GREEN if ok else _RED),
        )
        if ok:
            self.refresh_files_policy()

    def test_path_policy(self) -> None:
        path = self.test_path_var.get().strip()
        if not path:
            self.policy_status_label.configure(text="Policy status: enter a path to test", foreground=_RED)
            return
        result = self.client.test_policy_path(path)
        allowed = bool(result.get("allowed"))
        self.policy_status_label.configure(
            text=f"Policy test: {'ALLOWED' if allowed else 'BLOCKED'} | {result.get('reason')}",
            foreground=(_GREEN if allowed else _RED),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_agent_health(self) -> dict:
        health = self.client.health()
        if health.get("status") == "ok":
            return {"running": True, "detail": json.dumps(health, ensure_ascii=True)[:220]}
        return {"running": False, "detail": health.get("error", "unavailable")}

    def _set_service_badge(self, label: ttk.Label, name: str, status: dict) -> None:
        if status["running"]:
            label.configure(text=f"{name}: Connected", foreground=_GREEN)
        else:
            label.configure(text=f"{name}: Error", foreground=_RED)

    def _set_backend_status(self, level: str, text: str) -> None:
        color = {"starting": _AMBER, "connected": _GREEN, "error": _RED}.get(level, "#d1d5db")
        self.backend_status_label.configure(text=text, foreground=color)

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
                return {"running": response.status == 200, "detail": raw.strip()[:220]}
        except urllib.error.URLError as exc:
            return {"running": False, "detail": str(exc.reason)}
        except Exception as exc:
            return {"running": False, "detail": str(exc)}

    # ------------------------------------------------------------------
    # Clear actions
    # ------------------------------------------------------------------

    def clear_chat(self) -> None:
        self.chat_history.clear()
        self.chat_text.configure(state="normal")
        self.chat_text.delete("1.0", END)
        self.chat_text.configure(state="disabled")
        self.pending_start_index = None
        if self.is_unlocked:
            self._append_message("assistant", "Chat cleared. Ready for the next command.")
        else:
            self._show_chat_placeholder()

    def clear_activity(self) -> None:
        self.activity.clear()
        set_text(self.activity_list, "")

    def copy_last_response(self) -> None:
        if not self.last_response_text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.last_response_text)
        self.chat_state_label.configure(text="Last response copied")

    def copy_raw_trace(self) -> None:
        if not self.last_trace_payload:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(json.dumps(self.last_trace_payload, indent=2, ensure_ascii=True))
        self.chat_state_label.configure(text="Raw trace copied")
