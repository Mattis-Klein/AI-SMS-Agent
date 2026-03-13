"""PySide6 UI for Mashbak Control Board."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QIcon, QTextCursor, QPixmap, QColor
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QPlainTextEdit,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFrame,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
    QSpinBox,
    QTabWidget,
    QScrollArea,
    QApplication,
)

try:
    from agent.redaction import sanitize_for_logging
except Exception:  # pragma: no cover
    def sanitize_for_logging(value, key=None):
        return value


# Color palette (matching Tkinter theme)
_GREEN = "#1a7f37"
_RED = "#b42318"
_AMBER = "#9a6700"
_SLATE = "#57606a"
_YELLOW = "#b98900"
_UNKNOWN = "#6b7280"
_BG = "#eef2f7"
_CARD = "#ffffff"
_NAV_BG = "#121722"
_SURFACE = "#e7ecf4"
_HEADER_BG = "#101826"


def create_label(text: str, font_size: int = 10, bold: bool = False, color: str = "#111827") -> QLabel:
    """Create a styled label."""
    label = QLabel(text)
    font = QFont("Segoe UI", font_size)
    font.setBold(bold)
    label.setFont(font)
    label.setStyleSheet(f"color: {color};")
    return label


def create_button(text: str, callback=None, style: str = "primary") -> QPushButton:
    """Create a styled button."""
    btn = QPushButton(text)
    btn.setFont(QFont("Segoe UI", 9))
    if callback:
        btn.clicked.connect(callback)
    if style == "primary":
        btn.setStyleSheet(
            f"QPushButton {{ background-color: #0f4fbf; color: white; border: none; padding: 8px 12px; "
            "border-radius: 4px; font-weight: bold; }} "
            "QPushButton:hover { background-color: #0b45aa; }"
        )
    else:  # subtle
        btn.setStyleSheet(
            f"QPushButton {{ background-color: #f3f4f6; color: #111827; border: none; padding: 7px 10px; "
            "border-radius: 4px; }} "
            "QPushButton:hover { background-color: #e5e7eb; }"
        )
    return btn


def create_status_badge(text: str, status: str = "info") -> QLabel:
    """Create a styled status badge."""
    badge = QLabel(text)
    badge.setFont(QFont("Segoe UI", 9, QFont.Bold))
    if status == "ok":
        bg, fg = "#e9f7ef", "#17683a"
    elif status == "warn":
        bg, fg = "#fff5db", "#8a5a00"
    elif status == "error":
        bg, fg = "#ffebe9", "#9f1239"
    else:  # info
        bg, fg = "#1a2638", "#e6edf5"
    badge.setStyleSheet(f"background-color: {bg}; color: {fg}; padding: 6px 10px; border-radius: 4px;")
    return badge


class StatusCard(QFrame):
    """A card showing component status with indicator dot."""
    
    def __init__(self, title: str, subtitle: str):
        super().__init__()
        self.title = title
        self.subtitle_text = subtitle
        self._setup_ui()
        self.setStyleSheet("background-color: white; border-radius: 4px; padding: 12px;")
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Top row: title + indicator
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        self.title_label = create_label(self.title, 10, bold=True)
        top_layout.addWidget(self.title_label)
        
        self.indicator = QLabel("●")
        self.indicator.setStyleSheet(f"color: {_UNKNOWN}; font-size: 14px;")
        top_layout.addStretch()
        top_layout.addWidget(self.indicator)
        layout.addLayout(top_layout)
        
        # Subtitle
        self.subtitle_label = create_label(self.subtitle_text, 9, color=_SLATE)
        layout.addWidget(self.subtitle_label)
        
        # Status
        self.status_label = create_label("Unknown", 10, bold=True)
        layout.addWidget(self.status_label)
        
        # Timestamp
        self.stamp_label = create_label("Updated: --", 8, color="#64748b")
        layout.addWidget(self.stamp_label)
        
    def set_status(self, status: str, detail: str):
        """Update card status and indicator"""
        state = (status or "unknown").lower()
        if state in {"healthy", "connected", "configured", "active", "success"}:
            color = _GREEN
        elif state in {"warning", "warn", "degraded", "not configured"}:
            color = _YELLOW
        elif state in {"error", "failed", "disconnected", "failure", "blocked"}:
            color = _RED
        else:
            color = _UNKNOWN
        
        self.indicator.setStyleSheet(f"color: {color}; font-size: 14px;")
        self.status_label.setText(status.title() if status else "Unknown")
        self.subtitle_label.setText(detail[:80])
        self.stamp_label.setText(f"Updated: {datetime.now().strftime('%H:%M:%S')}")


class ChatBubble(QFrame):
    """A styled chat message bubble."""
    
    def __init__(self, role: str, text: str, timestamp: str = ""):
        super().__init__()
        self.role = role
        self.setText_msg = text
        self._setup_ui(timestamp)
        
    def _setup_ui(self, timestamp: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        
        # Timestamp
        if timestamp:
            ts_label = create_label(f"{self.role}  |  {timestamp}", 8, color=_SLATE)
            layout.addWidget(ts_label)
        
        # Message text
        text_label = QLabel(self.setText_msg)
        text_label.setWordWrap(True)
        text_label.setFont(QFont("Segoe UI", 9))
        
        if self.role == "You":
            self.setStyleSheet("background-color: #dceeff; border-radius: 8px; margin: 4px; margin-left: 100px;")
            text_label.setStyleSheet("color: #0a3069;")
        elif self.role == "Error":
            self.setStyleSheet("background-color: #fff1f0; border-radius: 8px; margin: 4px;")
            text_label.setStyleSheet("color: #8c2f39;")
        else:
            self.setStyleSheet("background-color: #f4f6f8; border-radius: 8px; margin: 4px; margin-right: 100px;")
            text_label.setStyleSheet("color: #111827;")
        
        layout.addWidget(text_label)


class DashboardPage(QWidget):
    """Dashboard page with status cards and tables."""
    
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(create_label("Dashboard", 12, bold=True))
        header_layout.addWidget(create_label("System health and operator activity", 9, color=_SLATE))
        header_layout.addStretch()
        refresh_btn = create_button("Refresh Dashboard", self.app.refresh_status)
        header_layout.addWidget(refresh_btn)
        layout.addLayout(header_layout)
        
        # Status cards
        cards_layout = QHBoxLayout()
        self.cards = {}
        for key, title, subtitle in [
            ("backend", "Backend", "Connection status"),
            ("bridge", "Bridge", "SMS transport status"),
            ("email", "Email", "Configuration health"),
            ("assistant", "Active Assistant", "Current primary assistant"),
        ]:
            card = StatusCard(title, subtitle)
            self.cards[key] = card
            cards_layout.addWidget(card)
        layout.addLayout(cards_layout)
        
        # Tables area
        tables_layout = QHBoxLayout()
        
        # Attention queue
        attention_layout = QVBoxLayout()
        self.attention_label = create_label("No alerts.", 9, color=_SLATE)
        attention_layout.addWidget(self.attention_label)
        
        self.failures_table = QTableWidget()
        self.failures_table.setColumnCount(5)
        self.failures_table.setHorizontalHeaderLabels(["Timestamp", "Assistant", "Action", "Result", "Status"])
        self.failures_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.failures_table.setMaximumWidth(450)
        attention_layout.addWidget(self.failures_table)
        tables_layout.addLayout(attention_layout, 0)
        
        # Recent Activity
        self.actions_table = QTableWidget()
        self.actions_table.setColumnCount(5)
        self.actions_table.setHorizontalHeaderLabels(["Timestamp", "Assistant", "Action", "Result", "Status"])
        self.actions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tables_layout.addWidget(self.actions_table, 1)
        
        layout.addLayout(tables_layout, 1)
        
    def update_cards(self, cards_data: dict):
        """Update status cards."""
        for key, (status, detail) in cards_data.items():
            if key in self.cards:
                self.cards[key].set_status(status, detail)


class ChatConsolePage(QWidget):
    """Chat and console page with conversation and trace."""
    
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(create_label("Chat / Console", 12, bold=True))
        header_layout.addWidget(create_label("Operational conversation and trace", 9, color=_SLATE))
        self.chat_state_label = create_label("Waiting for unlock", 9, color=_SLATE)
        header_layout.addWidget(self.chat_state_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Quick commands
        quick_layout = QHBoxLayout()
        for label, cmd in [
            ("System snapshot", "system info"),
            ("Recent inbox", "list files in inbox"),
            ("Check bridge", "check bridge health"),
        ]:
            btn = create_button(label, lambda m=cmd: self.app._send_quick_command(m), style="subtle")
            quick_layout.addWidget(btn)
        quick_layout.addStretch()
        layout.addLayout(quick_layout)
        
        # Main split area
        splitter = QSplitter(Qt.Horizontal)
        
        # Left: Conversation
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet(f"background-color: white; color: #111827; border: none; padding: 8px;")
        left_layout.addWidget(self.chat_display, 1)
        
        self.processing_label = create_label("", 9, color=_SLATE)
        left_layout.addWidget(self.processing_label)
        
        # Input area
        input_layout = QHBoxLayout()
        self.message_input = QLineEdit()
        self.message_input.setFont(QFont("Segoe UI", 10))
        self.message_input.setStyleSheet("padding: 8px; border: 1px solid #ddd; border-radius: 4px;")
        self.message_input.returnPressed.connect(self.app.on_send)
        input_layout.addWidget(self.message_input)
        
        send_btn = create_button("Send", self.app.on_send)
        input_layout.addWidget(send_btn)
        left_layout.addLayout(input_layout)
        
        # Right: Trace
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        
        trace_header = QHBoxLayout()
        trace_header.addWidget(create_label("Execution Trace", 10, bold=True))
        self.verification_label = create_label("Verification: Local-only", 8, color=_SLATE)
        trace_header.addStretch()
        trace_header.addWidget(self.verification_label)
        right_layout.addLayout(trace_header)
        
        # Trace tabs
        self.trace_tabs = QTabWidget()
        
        self.details_text = QPlainTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setStyleSheet("background-color: white; border: none;")
        self.trace_tabs.addTab(self.details_text, "Details")
        
        self.activity_list = QPlainTextEdit()
        self.activity_list.setReadOnly(True)
        self.activity_list.setStyleSheet("background-color: white; border: none; font-family: monospace;")
        self.trace_tabs.addTab(self.activity_list, "Activity")
        
        logs_widget = QWidget()
        logs_layout = QVBoxLayout(logs_widget)
        logs_layout.addWidget(create_label("Agent Logs", 10, bold=True))
        self.agent_logs = QPlainTextEdit()
        self.agent_logs.setReadOnly(True)
        self.agent_logs.setStyleSheet("background-color: white; border: none; font-family: monospace; font-size: 8pt;")
        logs_layout.addWidget(self.agent_logs)
        logs_layout.addWidget(create_label("Bridge Logs", 10, bold=True))
        self.bridge_logs = QPlainTextEdit()
        self.bridge_logs.setReadOnly(True)
        self.bridge_logs.setStyleSheet("background-color: white; border: none; font-family: monospace; font-size: 8pt;")
        logs_layout.addWidget(self.bridge_logs)
        self.trace_tabs.addTab(logs_widget, "Logs")
        
        right_layout.addWidget(self.trace_tabs)
        
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)
        
        # Action buttons
        action_layout = QHBoxLayout()
        action_layout.addWidget(create_button("Clear Conversation", self.app.clear_chat, style="subtle"))
        action_layout.addWidget(create_button("Clear Activity", self.app.clear_activity, style="subtle"))
        action_layout.addWidget(create_button("Copy Last Response", self.app.copy_last_response, style="subtle"))
        action_layout.addWidget(create_button("Copy Raw Trace", self.app.copy_raw_trace, style="subtle"))
        action_layout.addWidget(create_button("Refresh Logs", self.app.refresh_logs, style="subtle"))
        action_layout.addStretch()
        layout.addLayout(action_layout)
    
    def append_message(self, role: str, text: str):
        """Append message to chat display."""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_display.setTextCursor(cursor)
        
        timestamp = datetime.now().strftime("%I:%M %p").lstrip("0")
        
        if role == "user":
            self.chat_display.insertHtml(f"<b>{role.upper()} | {timestamp}</b><br>")
            self.chat_display.insertPlainText(text + "\n\n")
        elif role == "assistant":
            self.chat_display.insertHtml(f"<b>MASHBAK | {timestamp}</b><br>")
            self.chat_display.insertPlainText(text + "\n\n")
        elif role == "error":
            self.chat_display.insertHtml(f"<span style='color: #8c2f39;'><b>ERROR | {timestamp}</b></span><br>")
            self.chat_display.insertHtml(f"<span style='color: #8c2f39;'>{text}</span><br><br>")
        else:
            self.chat_display.insertHtml(f"<i>{text}</i><br><br>")
        
        self.chat_display.ensureCursorVisible()


class AssistantsPage(QWidget):
    """Assistants configuration page."""
    
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(create_label("Assistants", 12, bold=True))
        header_layout.addStretch()
        header_layout.addWidget(create_button("Refresh", self.app.refresh_assistants, style="subtle"))
        layout.addLayout(header_layout)
        
        self.assistants_text = QPlainTextEdit()
        self.assistants_text.setReadOnly(True)
        self.assistants_text.setStyleSheet("background-color: white; border: none; font-family: monospace;")
        layout.addWidget(self.assistants_text)


class CommunicationsPage(QWidget):
    """Communications, email and routing page."""
    
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(create_label("Communications", 12, bold=True))
        header_layout.addWidget(create_label("Membership routing and messaging", 9, color=_SLATE))
        header_layout.addStretch()
        header_layout.addWidget(create_button("Refresh", self.app.refresh_communications, style="subtle"))
        layout.addLayout(header_layout)
        
        # Tabs for Email and Routing
        tabs = QTabWidget()
        
        # Email tab
        email_widget = QWidget()
        email_layout = QVBoxLayout(email_widget)
        email_layout.addWidget(create_label("Email Configuration", 10, bold=True))
        
        grid = QGridLayout()
        self.email_address = QLineEdit()
        self.email_password = QLineEdit()
        self.email_password.setEchoMode(QLineEdit.Password)
        self.email_imap_host = QLineEdit()
        self.email_imap_port = QLineEdit("993")
        
        grid.addWidget(create_label("Email Address"), 0, 0)
        grid.addWidget(self.email_address, 0, 1)
        grid.addWidget(create_label("Password"), 1, 0)
        grid.addWidget(self.email_password, 1, 1)
        grid.addWidget(create_label("IMAP Server"), 2, 0)
        grid.addWidget(self.email_imap_host, 2, 1)
        grid.addWidget(create_label("IMAP Port"), 3, 0)
        grid.addWidget(self.email_imap_port, 3, 1)
        
        email_layout.addLayout(grid)
        email_layout.addWidget(create_button("Save Email Settings", self.app.save_email_config))
        email_layout.addWidget(create_button("Test Connection", self.app.test_email_connection, style="subtle"))
        self.email_status = create_label("Email status: unknown", 9, color=_SLATE)
        email_layout.addWidget(self.email_status)
        self.email_result = QPlainTextEdit()
        self.email_result.setReadOnly(True)
        email_layout.addWidget(self.email_result)
        
        tabs.addTab(email_widget, "Email")
        
        # Routing tab
        routing_widget = QWidget()
        routing_layout = QVBoxLayout(routing_widget)
        routing_layout.addWidget(create_label("SMS / Routing", 10, bold=True))
        self.routing_counts = create_label("Approved: 0   Pending: 0   Blocked: 0", 9)
        routing_layout.addWidget(self.routing_counts)
        
        # Lists layout
        lists_layout = QHBoxLayout()
        
        self.allowlist_widget = QListWidget()
        routing_layout.addWidget(create_label("Approved Members", 10, bold=True))
        lists_layout.addWidget(self.allowlist_widget)
        
        self.blocked_widget = QListWidget()
        routing_layout.addWidget(create_label("Blocked Numbers", 10, bold=True))
        lists_layout.addWidget(self.blocked_widget)
        
        self.pending_widget = QListWidget()
        routing_layout.addWidget(create_label("Pending Requests", 10, bold=True))
        lists_layout.addWidget(self.pending_widget)
        
        routing_layout.addLayout(lists_layout)
        
        tabs.addTab(routing_widget, "SMS / Routing")
        layout.addWidget(tabs)


class FilesPermissionsPage(QWidget):
    """Files and permissions policy page."""
    
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(create_label("Files & Permissions", 12, bold=True))
        header_layout.addStretch()
        header_layout.addWidget(create_button("Refresh", self.app.refresh_files_policy, style="subtle"))
        layout.addLayout(header_layout)
        
        # Two columns
        content_layout = QHBoxLayout()
        
        self.allowed_list = QListWidget()
        content_layout.addWidget(self.allowed_list, 1)
        
        self.blocked_text = QPlainTextEdit()
        self.blocked_text.setReadOnly(True)
        self.blocked_text.setStyleSheet("background-color: white; border: none; font-family: monospace;")
        content_layout.addWidget(self.blocked_text, 1)
        
        layout.addLayout(content_layout)
        
        # Controls
        controls_layout = QHBoxLayout()
        self.new_dir_input = QLineEdit()
        controls_layout.addWidget(create_label("Directory"), 0)
        controls_layout.addWidget(self.new_dir_input, 1)
        controls_layout.addWidget(create_button("Add", self.app.add_allowed_directory, style="subtle"))
        controls_layout.addWidget(create_button("Remove Selected", self.app.remove_selected_directory, style="subtle"))
        layout.addLayout(controls_layout)


class ProjectsFilesPage(QWidget):
    """Projects and files page."""
    
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(create_label("Projects / Files", 12, bold=True))
        header_layout.addStretch()
        header_layout.addWidget(create_button("Refresh", self.app.refresh_projects, style="subtle"))
        layout.addLayout(header_layout)
        
        self.projects_text = QPlainTextEdit()
        self.projects_text.setReadOnly(True)
        self.projects_text.setStyleSheet("background-color: white; border: none; font-family: monospace;")
        layout.addWidget(self.projects_text)


class ActivityAuditPage(QWidget):
    """Activity and audit log page."""
    
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(create_label("Activity / Audit", 12, bold=True))
        header_layout.addStretch()
        header_layout.addWidget(create_button("Refresh", self.app.refresh_activity_audit, style="subtle"))
        layout.addLayout(header_layout)
        
        self.activity_table = QTableWidget()
        self.activity_table.setColumnCount(6)
        self.activity_table.setHorizontalHeaderLabels(["Timestamp", "Assistant", "Action", "Tool", "State", "Target"])
        self.activity_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.activity_table)
        
        self.activity_detail = QPlainTextEdit()
        self.activity_detail.setReadOnly(True)
        self.activity_detail.setStyleSheet("background-color: white; border: none; font-family: monospace;")
        layout.addWidget(self.activity_detail, 0)


class DesktopControlApp:
    """Main Mashbak Control Board application using PySide6."""
    
    def __init__(self, client, runtime_summary: dict, local_app_pin: str | None = None):
        if not local_app_pin:
            raise RuntimeError("LOCAL_APP_PIN is required. Set it in mashbak/.env.master or the environment.")
        
        self.client = client
        self.runtime_summary = runtime_summary
        self.local_app_pin = local_app_pin
        
        self.is_unlocked = False
        self.current_section = "Dashboard"
        self.compact_tables = False
        
        self.activity: list[str] = []
        self.chat_history: list[tuple[str, str]] = []
        self.lock_sensitive_buttons: list = []
        self.last_response_text = ""
        self.last_trace_payload: dict = {}
        
        workspace = Path(runtime_summary.get("workspace") or "")
        platform_root = workspace.parent.parent if workspace else Path.cwd()
        self.agent_log_file = platform_root / "data" / "logs" / "agent.log"
        self.bridge_log_file = platform_root / "data" / "logs" / "bridge.log"
        
        self.window = QMainWindow()
        self.window.setWindowTitle("Mashbak Control Board")
        self.window.setGeometry(100, 100, 1520, 940)
        self.window.setMinimumSize(1080, 680)
        
        self._build_ui()
        self._set_backend_status("starting", "Mashbak is starting the local assistant backend.")
        self._lock_ui("Control board locked. Enter your PIN above to unlock.")
        
    def _build_ui(self):
        """Build main UI."""
        central = QWidget()
        self.window.setCentralWidget(central)
        
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header
        self._build_header()
        main_layout.addWidget(self.header_widget, 0)
        
        # Body (nav + pages)
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        
        # Sidebar
        self._build_sidebar()
        body_layout.addWidget(self.sidebar_widget, 0)
        
        # Pages
        self.stacked_widget = QStackedWidget()
        self.pages = {}
        
        for page_class, name in [
            (DashboardPage, "Dashboard"),
            (ChatConsolePage, "Chat / Console"),
            (AssistantsPage, "Assistants"),
            (CommunicationsPage, "Communications"),
            (FilesPermissionsPage, "Files & Permissions"),
            (ProjectsFilesPage, "Projects / Files"),
            (ActivityAuditPage, "Activity / Audit"),
        ]:
            page = page_class(self)
            self.pages[name] = page
            self.stacked_widget.addWidget(page)
        
        self.stacked_widget.setCurrentWidget(self.pages["Dashboard"])
        body_layout.addWidget(self.stacked_widget, 1)
        
        body_widget = QWidget()
        body_widget.setLayout(body_layout)
        main_layout.addWidget(body_widget, 1)
        
        # Statusbar
        self.statusbar = self.window.statusBar()
        model_label = self.runtime_summary.get("assistant_model") or "fallback"
        self.statusbar.showMessage(f"Mashbak Control Board  |  locked  |  Model: {model_label}")
    
    def _build_header(self):
        """Build header with title and status badges."""
        self.header_widget = QFrame()
        self.header_widget.setStyleSheet(f"background-color: {_HEADER_BG}; padding: 12px 18px;")
        
        layout = QHBoxLayout(self.header_widget)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(12)
        
        # Left: Title
        title_layout = QVBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)
        title = create_label("Mashbak Control Board", 18, bold=True, color="#f8fafc")
        subtitle = create_label("Private local operations console.", 9, color="#9dadc1")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        layout.addLayout(title_layout)
        
        # Center: State indicator
        self.header_state_label = create_label("System starting", 9, color=_AMBER)
        layout.addWidget(self.header_state_label)
        
        # Right: Badges and lock
        layout.addStretch()
        
        badges_layout = QHBoxLayout()
        badges_layout.setContentsMargins(0, 0, 0, 0)
        badges_layout.setSpacing(8)
        
        self.agent_badge = create_status_badge("Backend: Starting")
        self.bridge_badge = create_status_badge("Bridge: Checking")
        self.email_badge = create_status_badge("Email: Unknown")
        
        badges_layout.addWidget(self.agent_badge)
        badges_layout.addWidget(self.bridge_badge)
        badges_layout.addWidget(self.email_badge)
        badges_layout.addSpacing(12)
        
        # Lock controls
        lock_layout = QHBoxLayout()
        lock_layout.setContentsMargins(0, 0, 0, 0)
        lock_layout.setSpacing(8)
        
        lock_layout.addWidget(create_label("Control Board", 9, color="#d9e1ec"))
        self.lock_status = create_status_badge("Locked", "error")
        lock_layout.addWidget(self.lock_status)
        
        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.Password)
        self.pin_input.setMaximumWidth(110)
        self.pin_input.setFont(QFont("Segoe UI", 10))
        self.pin_input.setStyleSheet("padding: 4px; border: 1px solid #ddd; border-radius: 4px;")
        self.pin_input.returnPressed.connect(self.unlock_app)
        lock_layout.addWidget(self.pin_input)
        
        self.unlock_button = create_button("Unlock", self.unlock_app)
        lock_layout.addWidget(self.unlock_button)
        
        self.lock_button = create_button("Lock", self.lock_app, style="subtle")
        self.lock_button.setEnabled(False)
        lock_layout.addWidget(self.lock_button)
        
        badges_layout.addLayout(lock_layout)
        layout.addLayout(badges_layout)
    
    def _build_sidebar(self):
        """Build navigation sidebar."""
        self.sidebar_widget = QFrame()
        self.sidebar_widget.setStyleSheet(f"background-color: {_NAV_BG}; width: 276px;")
        self.sidebar_widget.setMaximumWidth(276)
        
        layout = QVBoxLayout(self.sidebar_widget)
        layout.setContentsMargins(16, 18, 16, 12)
        layout.setSpacing(4)
        
        # Title
        title = create_label("CONTROL BOARD", 12, bold=True, color="#e5e7eb")
        layout.addWidget(title)
        
        subtitle = create_label("Operator Navigation", 9, color="#94a3b8")
        layout.addWidget(subtitle)
        layout.addSpacing(10)
        
        # Nav buttons
        self.nav_buttons = {}
        for label, section in [
            ("Dashboard", "Dashboard"),
            ("Chat and Console", "Chat / Console"),
            ("Assistants", "Assistants"),
            ("Communications", "Communications"),
            ("Files and Permissions", "Files & Permissions"),
            ("Projects and Files", "Projects / Files"),
            ("Activity and Audit", "Activity / Audit"),
        ]:
            btn = QPushButton(label)
            btn.setFont(QFont("Segoe UI", 10))
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, s=section: self._show_section(s))
            btn.setStyleSheet(
                f"QPushButton {{ background-color: transparent; color: #d9e1ec; border: none; "
                "padding: 10px 14px; text-align: left; }} "
                "QPushButton:hover { background-color: #1a2437; }"
            )
            layout.addWidget(btn)
            self.nav_buttons[section] = btn
            self.lock_sensitive_buttons.append(btn)
        
        layout.addSpacing(10)
        
        # Quick commands
        quick_label = create_label("QUICK COMMANDS", 11, bold=True, color="#e5e7eb")
        layout.addWidget(quick_label)
        
        for label, msg in [
            ("System Info", "system info"),
            ("CPU Usage", "How busy is my computer right now?"),
            ("Recent Emails", "Do I have any new emails?"),
            ("Current Time", "what time is it"),
        ]:
            btn = create_button(label, lambda m=msg: self._send_quick_command(m), style="subtle")
            layout.addWidget(btn)
            self.lock_sensitive_buttons.append(btn)
        
        layout.addStretch()
    
    def _show_section(self, section: str):
        """Switch to a page."""
        self.current_section = section
        if section in self.pages:
            self.stacked_widget.setCurrentWidget(self.pages[section])
        
        # Update nav button styles
        for name, btn in self.nav_buttons.items():
            if name == section:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: #0f4fbf; color: white; border: none; "
                    "padding: 10px 14px; text-align: left; font-weight: bold; }} "
                    "QPushButton:hover { background-color: #0b45aa; }"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: transparent; color: #d9e1ec; border: none; "
                    "padding: 10px 14px; text-align: left; }} "
                    "QPushButton:hover { background-color: #1a2437; }"
                )
    
    def show(self):
        """Show the main window."""
        self.window.show()
        self.refresh_status()
    
    # --- LOCK CONTROL ---
    
    def unlock_app(self):
        """Unlock the application."""
        candidate = self.pin_input.text().strip()
        self.pin_input.clear()
        
        if candidate != self.local_app_pin:
            self.lock_status.setText("Wrong PIN")
            self.statusbar.showMessage("Mashbak Control Board  |  locked (wrong PIN)")
            self._lock_ui("Control board locked. Enter PIN to unlock.")
            QTimer.singleShot(2000, lambda: self.lock_status.setText("Locked"))
            return
        
        self.is_unlocked = True
        self.lock_status.setText("Unlocked")
        self.lock_status.setStyleSheet("background-color: #e9f7ef; color: #17683a; padding: 6px 10px; border-radius: 4px;")
        self.unlock_button.setEnabled(False)
        self.lock_button.setEnabled(True)
        self.pin_input.setEnabled(False)
        self.statusbar.showMessage("Mashbak Control Board  |  unlocked")
        
        # Enable controls
        self._set_interaction_enabled(True)
        
        # Initialize all pages
        self.refresh_status()
        self.refresh_logs()
        self.refresh_assistants()
        self.refresh_communications()
        self.refresh_files_policy()
        self.refresh_activity_audit()
        self.refresh_projects()
        
        # Get chat page and show welcome
        chat_page = self.pages.get("Chat / Console")
        if chat_page:
            chat_page.append_message("assistant", "Control board unlocked. I am ready.")
        
        self.message_input.setFocus()
    
    def lock_app(self):
        """Lock the application."""
        self._lock_ui("Control board locked. Enter PIN to unlock.")
    
    def _lock_ui(self, message: str):
        """Lock the UI and show lock message."""
        self.is_unlocked = False
        self.lock_status.setText("Locked")
        self.lock_status.setStyleSheet("background-color: #ffebe9; color: #9f1239; padding: 6px 10px; border-radius: 4px;")
        self.unlock_button.setEnabled(True)
        self.lock_button.setEnabled(False)
        self.pin_input.setEnabled(True)
        self.statusbar.showMessage("Mashbak Control Board  |  locked")
        
        # Disable controls
        self._set_interaction_enabled(False)
        
        # Show lock message on chat page
        chat_page = self.pages.get("Chat / Console")
        if chat_page:
            chat_page.chat_display.clear()
            chat_page.chat_display.setPlainText("Mashbak is locked.\nEnter your PIN to unlock the control board.")
            chat_page.details_text.setPlainText(message)
        
        self.pin_input.setFocus()
    
    def _set_interaction_enabled(self, enabled: bool):
        """Enable/disable interactive controls."""
        for btn in self.lock_sensitive_buttons:
            btn.setEnabled(enabled)
    
    # --- CHAT/MESSAGE HANDLING ---
    
    def on_send(self):
        """Send a message."""
        if not self.is_unlocked:
            return
        
        chat_page = self.pages.get("Chat / Console")
        if not chat_page:
            return
        
        message = chat_page.message_input.text().strip()
        if not message:
            return
        
        chat_page.message_input.clear()
        chat_page.append_message("You", message)
        chat_page.processing_label.setText("Mashbak is thinking...")
        chat_page.chat_state_label.setText("Waiting for Mashbak reply")
        chat_page.details_text.setPlainText("Mashbak is processing your message...")
        
        thread = threading.Thread(target=self._run_message, args=(message,), daemon=True)
        thread.start()
    
    def _run_message(self, message: str):
        """Run message in background thread."""
        try:
            result = self.client.execute_nl(message=message, sender="local-desktop", owner_unlocked=self.is_unlocked)
            # Schedule UI update on main thread
            self.window.after(0, lambda: self._display_result(message, result))
        except Exception as exc:
            self.window.after(0, lambda: self._display_error(str(exc)))
    
    def _display_result(self, message: str, result: dict):
        """Display result in chat."""
        chat_page = self.pages.get("Chat / Console")
        if not chat_page:
            return
        
        chat_page.processing_label.setText("")
        chat_page.chat_state_label.setText("Connected and ready")
        
        # Extract trace info
        trace = result.get("trace") or {}
        verification_state = str(trace.get("verification_state") or "Local-only")
        context = trace.get("context") or {}
        raw_tool_output = trace.get("tool_output")
        safe_trace_args = sanitize_for_logging(trace.get("interpreted_args", {}))
        safe_raw_tool_output = sanitize_for_logging(raw_tool_output)
        
        # Build details
        detail_lines = [
            f"Assistant mode: {trace.get('assistant_mode')}",
            f"Tool:           {result.get('tool_name')}",
            f"Success:        {result.get('success')}",
            f"Verification:   {verification_state}",
            f"Request ID:     {result.get('request_id')}",
            f"Exec time (ms): {trace.get('execution_time_ms')}",
            "",
            f"Intent:         {trace.get('intent_classification')}",
            f"Validation:     {trace.get('validation_status')}",
            f"Exec status:    {trace.get('execution_status')}",
            "",
            f"Args: {json.dumps(safe_trace_args, ensure_ascii=True)[:200]}",
        ]
        if safe_raw_tool_output:
            detail_lines.append(f"Tool output: {str(safe_raw_tool_output)[:200]}")
        
        chat_page.details_text.setPlainText("\n".join(detail_lines))
        
        # Update verification
        verify_color = _SLATE
        if verification_state.lower() in {"verified", "tool-assisted"}:
            verify_color = _GREEN
        elif verification_state.lower() == "unverified":
            verify_color = _RED
        chat_page.verification_label.setText(f"Verification: {verification_state}")
        chat_page.verification_label.setStyleSheet(f"color: {verify_color};")
        
        # Display message
        final_text = (
            (result.get("output") or "Mashbak finished that request.")
            if result.get("success")
            else (result.get("error") or "Request failed.")
        )
        self.last_response_text = str(final_text)
        self.last_trace_payload = dict(trace)
        
        role = "Error" if not result.get("success") else "Mashbak"
        chat_page.append_message(role, final_text)
        
        # Update history and logs
        self.chat_history.append(("user", message))
        self.chat_history.append((role.lower(), final_text))
        if len(self.chat_history) > 200:
            self.chat_history = self.chat_history[-200:]
        
        # Update activity
        ts = datetime.now().strftime("%H:%M:%S")
        tool = result.get("tool_name") or trace.get("assistant_mode") or "conversation"
        safe_message = sanitize_for_logging(message)
        self.activity.insert(0, f"{ts}  {tool}  {str(safe_message)[:70]}")
        self.activity = self.activity[:80]
        
        chat_page.activity_list.setPlainText("\n".join(self.activity))
        
        # Refresh dashboard
        self.refresh_logs()
        self.refresh_activity_audit()
        self.refresh_dashboard_overview()
    
    def _display_error(self, error_text: str):
        """Display error in chat."""
        chat_page = self.pages.get("Chat / Console")
        if not chat_page:
            return
        
        chat_page.processing_label.setText("")
        chat_page.chat_state_label.setText("Connection problem")
        chat_page.verification_label.setText("Verification: Unverified")
        chat_page.verification_label.setStyleSheet(f"color: {_RED};")
        chat_page.details_text.setPlainText(f"Error:\n{error_text}")
        
        self.last_response_text = error_text
        self.last_trace_payload = {"error": error_text}
        
        chat_page.append_message("Error", error_text)
        
        # Update history
        self.chat_history.append(("user", "[message failed]"))
        self.chat_history.append(("error", error_text))
        
        ts = datetime.now().strftime("%H:%M:%S")
        self.activity.insert(0, f"{ts}  [error]  {error_text[:70]}")
        self.activity = self.activity[:80]
        chat_page.activity_list.setPlainText("\n".join(self.activity))
    
    def _send_quick_command(self, message: str):
        """Send a quick command."""
        if not self.is_unlocked:
            return
        self._show_section("Chat / Console")
        chat_page = self.pages.get("Chat / Console")
        if chat_page:
            chat_page.message_input.setText(message)
            chat_page.message_input.setFocus()
            self.on_send()
    
    # --- DATA REFRESH METHODS (preserved from Tkinter version) ---
    
    def refresh_status(self):
        """Refresh system status badges."""
        agent_status = self._check_agent_health()
        bridge_status = self._check_http_health("http://127.0.0.1:34567/health")
        summary = self.runtime_summary
        
        # Update badges
        if agent_status["running"]:
            self.agent_badge.setText("Backend: Connected")
            self.agent_badge.setStyleSheet("background-color: #e9f7ef; color: #17683a; padding: 6px 10px; border-radius: 4px; font-weight: bold; font-size: 9pt;")
        else:
            self.agent_badge.setText("Backend: Error")
            self.agent_badge.setStyleSheet("background-color: #ffebe9; color: #9f1239; padding: 6px 10px; border-radius: 4px; font-weight: bold; font-size: 9pt;")
        
        if bridge_status["running"]:
            self.bridge_badge.setText("Bridge: Connected")
            self.bridge_badge.setStyleSheet("background-color: #e9f7ef; color: #17683a; padding: 6px 10px; border-radius: 4px; font-weight: bold; font-size: 9pt;")
        else:
            self.bridge_badge.setText("Bridge: Error")
            self.bridge_badge.setStyleSheet("background-color: #ffebe9; color: #9f1239; padding: 6px 10px; border-radius: 4px; font-weight: bold; font-size: 9pt;")
        
        if summary.get("email_configured"):
            self.email_badge.setText("Email: Configured")
            self.email_badge.setStyleSheet("background-color: #e9f7ef; color: #17683a; padding: 6px 10px; border-radius: 4px; font-weight: bold; font-size: 9pt;")
        else:
            self.email_badge.setText("Email: Needs setup")
            self.email_badge.setStyleSheet("background-color: #fff5db; color: #8a5a00; padding: 6px 10px; border-radius: 4px; font-weight: bold; font-size: 9pt;")
        
        # Update header state
        if agent_status["running"]:
            self._set_backend_status("connected", "Mashbak backend connected.")
        else:
            self._set_backend_status("error", f"Mashbak cannot reach backend: {agent_status['detail']}")
        
        # Update dashboard if unlocked
        if self.is_unlocked:
            self.refresh_dashboard_overview()
    
    def refresh_dashboard_overview(self):
        """Refresh dashboard overview data."""
        if not self.is_unlocked:
            return
        
        overview = self.client.get_overview()
        if not isinstance(overview, dict) or overview.get("success") is False:
            return
        
        dashboard = self.pages.get("Dashboard")
        if not dashboard:
            return
        
        # Update status cards
        backend = overview.get("backend") or {}
        bridge = overview.get("bridge") or {}
        email = overview.get("email") or {}
        
        cards_data = {
            "backend": ("connected" if backend.get("connected") else "error", f"Model: {backend.get('model') or 'unknown'}"),
            "bridge": ("connected" if bridge.get("connected") else "error", str(bridge.get("detail") or "Bridge health")),
            "email": ("configured" if email.get("configured") else "warning", "Credentials and inbox ready" if email.get("configured") else "Configuration required"),
            "assistant": ("active", (overview.get("active_assistant") or "mashbak").title()),
        }
        dashboard.update_cards(cards_data)
        
        # Update tables
        dashboard.actions_table.setRowCount(0)
        for idx, row in enumerate(overview.get("recent_actions") or []):
            dashboard.actions_table.insertRow(idx)
            ts = row.get("timestamp") or ""
            assistant = row.get("assistant") or "desktop"
            action = row.get("requested_action") or row.get("selected_tool") or "-"
            result = row.get("result") or "-"
            status = (row.get("state") or "-").title()
            
            dashboard.actions_table.setItem(idx, 0, QTableWidgetItem(ts))
            dashboard.actions_table.setItem(idx, 1, QTableWidgetItem(assistant))
            dashboard.actions_table.setItem(idx, 2, QTableWidgetItem(self._condense_detail(str(action), 58)))
            dashboard.actions_table.setItem(idx, 3, QTableWidgetItem(self._condense_detail(str(result), 38)))
            dashboard.actions_table.setItem(idx, 4, QTableWidgetItem(status))
        
        # Update failures/attention
        failures = overview.get("recent_failures") or []
        dashboard.attention_label.setText(f"Attention items: {len(failures)}" if failures else "No alerts.")
        dashboard.failures_table.setRowCount(0)
        for idx, row in enumerate(failures):
            dashboard.failures_table.insertRow(idx)
            ts = row.get("timestamp") or ""
            assistant = str(row.get("assistant") or "backend")
            action = self._condense_detail(str(row.get("tool") or "-"), 48)
            result = self._condense_detail(str(row.get("error") or "Action failed"), 78)
            state_raw = str(row.get("state") or "failure").lower()
            state = "Warning" if "warn" in state_raw else ("Failure" if "fail" in state_raw or "error" in state_raw else "Needs review")
            
            dashboard.failures_table.setItem(idx, 0, QTableWidgetItem(ts))
            dashboard.failures_table.setItem(idx, 1, QTableWidgetItem(assistant))
            dashboard.failures_table.setItem(idx, 2, QTableWidgetItem(action))
            dashboard.failures_table.setItem(idx, 3, QTableWidgetItem(result))
            dashboard.failures_table.setItem(idx, 4, QTableWidgetItem(state))
    
    def _condense_detail(self, text: str, max_len: int = 84) -> str:
        """Condense detail text with ellipsis."""
        cleaned = " ".join(str(text or "").split())
        if len(cleaned) <= max_len:
            return cleaned or "-"
        return cleaned[: max_len - 3].rstrip() + "..."
    
    def refresh_assistants(self):
        """Refresh assistants information."""
        if not self.is_unlocked:
            return
        
        payload = self.client.get_assistants()
        if not isinstance(payload, dict) or payload.get("success") is False:
            return
        
        page = self.pages.get("Assistants")
        if not page:
            return
        
        mashbak = payload.get("mashbak") or {}
        bucherim = payload.get("bucherim") or {}
        
        lines = [
            "Mashbak",
            f"  AI enabled: {mashbak.get('ai_enabled')}",
            f"  Model: {mashbak.get('model')}",
            f"  Base URL: {mashbak.get('base_url')}",
            "",
            "Bucherim",
            f"  Assistant number: {bucherim.get('assistant_number')}",
            f"  Allowlist count: {bucherim.get('allowlist_count')}",
        ]
        page.assistants_text.setPlainText("\n".join(lines))
    
    def refresh_communications(self):
        """Refresh communications data."""
        if not self.is_unlocked:
            return
        self.refresh_email_config_view()
        self.refresh_routing_view()
    
    def refresh_email_config_view(self):
        """Refresh email configuration view."""
        payload = self.client.get_email_config()
        if not isinstance(payload, dict) or payload.get("success") is False:
            return
        
        page = self.pages.get("Communications")
        if not page:
            return
        
        page.email_address.setText(str(payload.get("email_address") or ""))
        page.email_imap_host.setText(str(payload.get("imap_host") or ""))
        page.email_imap_port.setText(str(payload.get("imap_port") or "993"))
        
        if payload.get("password_set"):
            page.email_status.setText("Email status: configured")
            page.email_status.setStyleSheet(f"color: {_GREEN};")
        else:
            page.email_status.setText("Email status: password missing")
            page.email_status.setStyleSheet(f"color: {_AMBER};")
    
    def refresh_routing_view(self):
        """Refresh routing view."""
        payload = self.client.get_routing()
        if not isinstance(payload, dict) or payload.get("success") is False:
            return
        
        page = self.pages.get("Communications")
        if not page:
            return
        
        allowlist = payload.get("allowlist") or []
        blocked = payload.get("blocked_numbers") or []
        pending = payload.get("pending_join_requests") or []
        
        page.allowlist_widget.clear()
        for item in allowlist:
            page.allowlist_widget.addItem(str(item))
        
        page.blocked_widget.clear()
        for item in blocked:
            page.blocked_widget.addItem(str(item))
        
        page.pending_widget.clear()
        for item in pending:
            phone = item.get("phone_number") if isinstance(item, dict) else str(item)
            ts = item.get("timestamp") if isinstance(item, dict) else ""
            page.pending_widget.addItem(f"{phone}  ({ts})")
        
        page.routing_counts.setText(f"Approved: {len(allowlist)}   Pending: {len(pending)}   Blocked: {len(blocked)}")
    
    def refresh_files_policy(self):
        """Refresh files and permissions policy."""
        if not self.is_unlocked:
            return
        
        payload = self.client.get_files_policy()
        if not isinstance(payload, dict) or payload.get("success") is False:
            return
        
        page = self.pages.get("Files & Permissions")
        if not page:
            return
        
        page.allowed_list.clear()
        for path in payload.get("allowed_directories") or []:
            page.allowed_list.addItem(str(path))
        
        lines = []
        for row in payload.get("blocked_attempts") or []:
            lines.append(f"{row.get('timestamp')} | {row.get('tool')} | {row.get('path') or '-'}")
        page.blocked_text.setPlainText("\n".join(lines) if lines else "No blocked attempts.")
    
    def refresh_projects(self):
        """Refresh projects/files information."""
        if not self.is_unlocked:
            return
        
        payload = self.client.get_activity(limit=120)
        if not isinstance(payload, dict) or payload.get("success") is False:
            return
        
        page = self.pages.get("Projects / Files")
        if not page:
            return
        
        file_like = []
        for item in payload.get("items") or []:
            tool = str(item.get("selected_tool") or "")
            target = str(item.get("target") or "")
            if tool in {"create_file", "create_folder", "delete_file", "list_files"} or target:
                file_like.append(f"{item.get('timestamp')} | {tool} | {item.get('state')} | {target or '-'}")
        
        page.projects_text.setPlainText("\n".join(file_like) if file_like else "No recent file/project actions.")
    
    def refresh_activity_audit(self):
        """Refresh activity and audit log."""
        if not self.is_unlocked:
            return
        
        payload = self.client.get_activity(limit=160)
        if not isinstance(payload, dict) or payload.get("success") is False:
            return
        
        page = self.pages.get("Activity / Audit")
        if not page:
            return
        
        page.activity_table.setRowCount(0)
        for idx, row in enumerate(payload.get("items") or []):
            page.activity_table.insertRow(idx)
            values = [
                row.get("timestamp") or "",
                row.get("assistant") or "",
                row.get("requested_action") or "",
                row.get("selected_tool") or "",
                row.get("state") or "",
                row.get("target") or "",
            ]
            for col, value in enumerate(values):
                page.activity_table.setItem(idx, col, QTableWidgetItem(value))
        
        sample = (payload.get("items") or [])[:12]
        lines = []
        for row in sample:
            lines.append(f"{row.get('timestamp')} | {row.get('selected_tool')} | {row.get('state')}")
        page.activity_detail.setPlainText("\n".join(lines) if lines else "No recent activity.")
    
    def refresh_logs(self):
        """Refresh logs display."""
        if not self.is_unlocked:
            chat_page = self.pages.get("Chat / Console")
            if chat_page:
                chat_page.agent_logs.setPlainText("Locked")
                chat_page.bridge_logs.setPlainText("Locked")
            return
        
        agent_lines = self._tail_file(self.agent_log_file, 40)
        bridge_lines = self._tail_file(self.bridge_log_file, 40)
        
        chat_page = self.pages.get("Chat / Console")
        if chat_page:
            chat_page.agent_logs.setPlainText("\n".join(agent_lines) if agent_lines else "No agent logs yet.")
            chat_page.bridge_logs.setPlainText("\n".join(bridge_lines) if bridge_lines else "No bridge logs yet.")
    
    def _tail_file(self, path: Path, max_lines: int = 40) -> list[str]:
        """Read last N lines from a file."""
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            return lines[-max_lines:]
        except Exception as exc:
            return [f"Error reading {path.name}: {exc}"]
    
    def _set_backend_status(self, level: str, text: str):
        """Set backend status display."""
        color = {"starting": _AMBER, "connected": _GREEN, "error": _RED}.get(level, "#9ca3af")
        state = {"starting": "System starting", "connected": "System ready", "error": "System issue"}.get(level, "System")
        self.header_state_label.setText(state)
        self.header_state_label.setStyleSheet(f"color: {color};")
    
    def _check_agent_health(self) -> dict:
        """Check agent backend health."""
        health = self.client.health()
        if health.get("status") == "ok":
            return {"running": True, "detail": json.dumps(health, ensure_ascii=True)[:220]}
        return {"running": False, "detail": health.get("error", "unavailable")}
    
    def _check_http_health(self, url: str) -> dict:
        """Check HTTP endpoint health."""
        try:
            with urllib.request.urlopen(url, timeout=1.2) as response:
                return {"running": response.status == 200, "detail": "OK"}
        except Exception:
            return {"running": False, "detail": "Unreachable"}
    
    # --- ACTION HANDLERS ---
    
    def save_email_config(self):
        """Save email configuration (stub)."""
        pass
    
    def test_email_connection(self):
        """Test email connection (stub)."""
        pass
    
    def add_allowed_directory(self):
        """Add allowed directory (stub)."""
        pass
    
    def remove_selected_directory(self):
        """Remove selected directory (stub)."""
        pass
    
    def clear_chat(self):
        """Clear chat conversation."""
        chat_page = self.pages.get("Chat / Console")
        if chat_page:
            chat_page.chat_display.clear()
            if self.is_unlocked:
                chat_page.append_message("Mashbak", "Chat cleared. Ready for the next command.")
    
    def clear_activity(self):
        """Clear activity list."""
        self.activity.clear()
        chat_page = self.pages.get("Chat / Console")
        if chat_page:
            chat_page.activity_list.setPlainText("")
    
    def copy_last_response(self):
        """Copy last response to clipboard."""
        if not self.last_response_text:
            return
        app = QApplication.instance()
        if app:
            app.clipboard().setText(self.last_response_text)
    
    def copy_raw_trace(self):
        """Copy raw trace JSON to clipboard."""
        if not self.last_trace_payload:
            return
        app = QApplication.instance()
        if app:
            app.clipboard().setText(json.dumps(self.last_trace_payload, indent=2, ensure_ascii=True))
    
    @property
    def message_input(self):
        """Get message input from chat page."""
        chatpage = self.pages.get("Chat / Console")
        return chatpage.message_input if chatpage else None
