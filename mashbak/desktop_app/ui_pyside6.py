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
    QComboBox,
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
        layout.setSpacing(10)
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(create_label("Assistants", 12, bold=True))
        header_layout.addStretch()
        header_layout.addWidget(create_button("Refresh", self.app.refresh_assistants, style="subtle"))
        layout.addLayout(header_layout)
        
        split = QHBoxLayout()

        left = QVBoxLayout()
        left.addWidget(create_label("Mashbak Runtime", 10, bold=True))
        self.mashbak_table = QTableWidget()
        self.mashbak_table.setColumnCount(2)
        self.mashbak_table.setHorizontalHeaderLabels(["Setting", "Value"])
        self.mashbak_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.mashbak_table.verticalHeader().setVisible(False)
        left.addWidget(self.mashbak_table)

        left.addWidget(create_label("Bucherim Summary", 10, bold=True))
        self.bucherim_counts_table = QTableWidget()
        self.bucherim_counts_table.setColumnCount(2)
        self.bucherim_counts_table.setHorizontalHeaderLabels(["Field", "Value"])
        self.bucherim_counts_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.bucherim_counts_table.verticalHeader().setVisible(False)
        left.addWidget(self.bucherim_counts_table)

        right = QVBoxLayout()
        right.addWidget(create_label("Bucherim Response Templates", 10, bold=True))
        self.responses_table = QTableWidget()
        self.responses_table.setColumnCount(2)
        self.responses_table.setHorizontalHeaderLabels(["Template", "Text"])
        self.responses_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.responses_table.verticalHeader().setVisible(False)
        right.addWidget(self.responses_table)

        split.addLayout(left, 1)
        split.addLayout(right, 1)
        layout.addLayout(split, 1)


class CommunicationsPage(QWidget):
    """Communications, email and routing page."""
    
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        self.current_email_account_id: str | None = None
        
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
        email_layout.addWidget(create_label("Email Accounts", 10, bold=True))

        email_top = QHBoxLayout()
        self.email_accounts_widget = QListWidget()
        self.email_accounts_widget.currentItemChanged.connect(self.app.on_email_account_selected)
        email_top.addWidget(self.email_accounts_widget, 1)
        
        grid = QGridLayout()
        self.email_label = QLineEdit()
        self.email_address = QLineEdit()
        self.email_password = QLineEdit()
        self.email_password.setEchoMode(QLineEdit.Password)
        self.email_imap_host = QLineEdit()
        self.email_imap_port = QLineEdit("993")
        self.email_mailbox = QLineEdit("INBOX")
        self.email_make_default = QCheckBox("Set as default account")
        
        grid.addWidget(create_label("Label"), 0, 0)
        grid.addWidget(self.email_label, 0, 1)
        grid.addWidget(create_label("Email Address"), 1, 0)
        grid.addWidget(self.email_address, 1, 1)
        grid.addWidget(create_label("Password"), 2, 0)
        grid.addWidget(self.email_password, 2, 1)
        grid.addWidget(create_label("IMAP Server"), 3, 0)
        grid.addWidget(self.email_imap_host, 3, 1)
        grid.addWidget(create_label("IMAP Port"), 4, 0)
        grid.addWidget(self.email_imap_port, 4, 1)
        grid.addWidget(create_label("Mailbox"), 5, 0)
        grid.addWidget(self.email_mailbox, 5, 1)
        grid.addWidget(self.email_make_default, 6, 1)
        
        email_top.addLayout(grid, 2)
        email_layout.addLayout(email_top)

        email_actions = QHBoxLayout()
        email_actions.addWidget(create_button("New Account", self.app.new_email_account, style="subtle"))
        email_actions.addWidget(create_button("Save Account", self.app.save_email_config))
        email_actions.addWidget(create_button("Test Connection", self.app.test_email_connection, style="subtle"))
        email_actions.addWidget(create_button("Set Default", self.app.set_default_email_account, style="subtle"))
        email_actions.addWidget(create_button("Delete", self.app.delete_email_account, style="subtle"))
        email_actions.addStretch()
        email_layout.addLayout(email_actions)
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
        
        self.approved_widget = QListWidget()
        routing_layout.addWidget(create_label("Approved Members", 10, bold=True))
        lists_layout.addWidget(self.approved_widget)
        
        self.blocked_widget = QListWidget()
        routing_layout.addWidget(create_label("Blocked Numbers", 10, bold=True))
        lists_layout.addWidget(self.blocked_widget)
        
        self.pending_widget = QListWidget()
        routing_layout.addWidget(create_label("Pending Requests", 10, bold=True))
        lists_layout.addWidget(self.pending_widget)
        
        routing_layout.addLayout(lists_layout)

        routing_actions = QHBoxLayout()
        self.routing_phone_input = QLineEdit()
        self.routing_phone_input.setPlaceholderText("Phone number")
        routing_actions.addWidget(self.routing_phone_input, 1)
        routing_actions.addWidget(create_button("Approve", self.app.approve_routing_member, style="subtle"))
        routing_actions.addWidget(create_button("Block", self.app.block_routing_member, style="subtle"))
        routing_layout.addLayout(routing_actions)

        detail_layout = QHBoxLayout()
        detail_left = QVBoxLayout()
        detail_left.addWidget(create_label("Selected Member", 10, bold=True))
        self.routing_member_table = QTableWidget()
        self.routing_member_table.setColumnCount(2)
        self.routing_member_table.setHorizontalHeaderLabels(["Field", "Value"])
        self.routing_member_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.routing_member_table.verticalHeader().setVisible(False)
        detail_left.addWidget(self.routing_member_table)

        detail_right = QVBoxLayout()
        detail_right.addWidget(create_label("Recent Message History", 10, bold=True))
        self.routing_history_table = QTableWidget()
        self.routing_history_table.setColumnCount(4)
        self.routing_history_table.setHorizontalHeaderLabels(["Time", "Direction", "State", "Preview"])
        self.routing_history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.routing_history_table.verticalHeader().setVisible(False)
        detail_right.addWidget(self.routing_history_table)

        detail_layout.addLayout(detail_left, 1)
        detail_layout.addLayout(detail_right, 2)
        routing_layout.addLayout(detail_layout)

        self.routing_result = QPlainTextEdit()
        self.routing_result.setReadOnly(True)
        routing_layout.addWidget(self.routing_result)

        self.approved_widget.itemSelectionChanged.connect(self.app.on_routing_selection_changed)
        self.blocked_widget.itemSelectionChanged.connect(self.app.on_routing_selection_changed)
        self.pending_widget.itemSelectionChanged.connect(self.app.on_routing_selection_changed)
        
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
        
        allowed_column = QVBoxLayout()
        allowed_column.addWidget(create_label("Allowed Directories", 10, bold=True))
        self.allowed_list = QListWidget()
        allowed_column.addWidget(self.allowed_list)
        content_layout.addLayout(allowed_column, 1)

        blocked_column = QVBoxLayout()
        blocked_column.addWidget(create_label("Blocked Attempts", 10, bold=True))
        self.blocked_table = QTableWidget()
        self.blocked_table.setColumnCount(3)
        self.blocked_table.setHorizontalHeaderLabels(["Timestamp", "Tool", "Path"])
        self.blocked_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.blocked_table.verticalHeader().setVisible(False)
        blocked_column.addWidget(self.blocked_table)
        content_layout.addLayout(blocked_column, 2)
        
        layout.addLayout(content_layout)
        
        # Controls
        controls_layout = QHBoxLayout()
        self.new_dir_input = QLineEdit()
        controls_layout.addWidget(create_label("Directory"), 0)
        controls_layout.addWidget(self.new_dir_input, 1)
        controls_layout.addWidget(create_button("Add", self.app.add_allowed_directory, style="subtle"))
        controls_layout.addWidget(create_button("Remove Selected", self.app.remove_selected_directory, style="subtle"))
        layout.addLayout(controls_layout)

        test_layout = QHBoxLayout()
        self.path_test_input = QLineEdit()
        self.path_test_input.setPlaceholderText("Path to validate against file policy")
        test_layout.addWidget(self.path_test_input, 1)
        test_layout.addWidget(create_button("Test Path", self.app.test_policy_path, style="subtle"))
        layout.addLayout(test_layout)
        self.path_test_result = create_label("", 9, color=_SLATE)
        layout.addWidget(self.path_test_result)


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
        
        filter_layout = QHBoxLayout()
        self.projects_query = QLineEdit()
        self.projects_query.setPlaceholderText("Filter by file name, path, or action")
        filter_layout.addWidget(self.projects_query, 1)
        filter_layout.addWidget(create_button("Apply Filter", self.app.refresh_projects, style="subtle"))
        layout.addLayout(filter_layout)

        self.projects_table = QTableWidget()
        self.projects_table.setColumnCount(6)
        self.projects_table.setHorizontalHeaderLabels(["Timestamp", "Action", "Tool", "State", "Target", "Source"])
        self.projects_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.projects_table.verticalHeader().setVisible(False)
        self.projects_table.itemSelectionChanged.connect(self.app.on_project_row_selected)
        layout.addWidget(self.projects_table)

        self.projects_detail = QPlainTextEdit()
        self.projects_detail.setReadOnly(True)
        self.projects_detail.setStyleSheet("background-color: white; border: none; font-family: Consolas;")
        layout.addWidget(self.projects_detail, 0)


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

        filter_layout = QHBoxLayout()
        self.activity_source = QComboBox()
        self.activity_source.addItems(["all", "desktop", "voice", "backend"])
        self.activity_state = QComboBox()
        self.activity_state.addItems(["all", "received", "success", "failure", "blocked", "completed"])
        self.activity_tool = QLineEdit()
        self.activity_tool.setPlaceholderText("Tool filter")
        self.activity_query = QLineEdit()
        self.activity_query.setPlaceholderText("Search text")
        filter_layout.addWidget(create_label("Source"))
        filter_layout.addWidget(self.activity_source)
        filter_layout.addWidget(create_label("State"))
        filter_layout.addWidget(self.activity_state)
        filter_layout.addWidget(self.activity_tool, 1)
        filter_layout.addWidget(self.activity_query, 2)
        filter_layout.addWidget(create_button("Apply", self.app.refresh_activity_audit, style="subtle"))
        layout.addLayout(filter_layout)
        
        self.activity_table = QTableWidget()
        self.activity_table.setColumnCount(8)
        self.activity_table.setHorizontalHeaderLabels(["Timestamp", "Event", "Assistant", "Action", "Tool", "State", "Target", "Source"])
        self.activity_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.activity_table.itemSelectionChanged.connect(self.app.on_activity_row_selected)
        layout.addWidget(self.activity_table)
        
        self.activity_detail = QPlainTextEdit()
        self.activity_detail.setReadOnly(True)
        self.activity_detail.setStyleSheet("background-color: white; border: none; font-family: monospace;")
        layout.addWidget(self.activity_detail, 0)


class PersonalContextPage(QWidget):
    """Personal context editor page."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)

        header_layout = QHBoxLayout()
        header_layout.addWidget(create_label("Personal Context", 12, bold=True))
        header_layout.addStretch()
        header_layout.addWidget(create_button("Refresh", self.app.refresh_personal_context, style="subtle"))
        header_layout.addWidget(create_button("Save", self.app.save_personal_context))
        layout.addLayout(header_layout)

        self.profile_text = QPlainTextEdit()
        self.profile_text.setPlaceholderText("Profile JSON: name, preferred_tone, response_style, notes")
        self.people_text = QPlainTextEdit()
        self.people_text.setPlaceholderText("People JSON array")
        self.routines_text = QPlainTextEdit()
        self.routines_text.setPlaceholderText("Routines JSON array")
        self.projects_text = QPlainTextEdit()
        self.projects_text.setPlaceholderText("Projects JSON array")
        self.preferences_text = QPlainTextEdit()
        self.preferences_text.setPlaceholderText("Preferences JSON")

        layout.addWidget(create_label("Profile", 10, bold=True))
        layout.addWidget(self.profile_text)
        layout.addWidget(create_label("People", 10, bold=True))
        layout.addWidget(self.people_text)
        layout.addWidget(create_label("Routines", 10, bold=True))
        layout.addWidget(self.routines_text)
        layout.addWidget(create_label("Projects", 10, bold=True))
        layout.addWidget(self.projects_text)
        layout.addWidget(create_label("Preferences", 10, bold=True))
        layout.addWidget(self.preferences_text)
        self.status_label = create_label("", 9, color=_SLATE)
        layout.addWidget(self.status_label)


class ToolsPermissionsPage(QWidget):
    """Tool permissions and approvals/tasks panel."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)

        header = QHBoxLayout()
        header.addWidget(create_label("Tools & Permissions", 12, bold=True))
        header.addStretch()
        header.addWidget(create_button("Refresh", self.app.refresh_tools_permissions, style="subtle"))
        layout.addLayout(header)

        self.tools_table = QTableWidget()
        self.tools_table.setColumnCount(6)
        self.tools_table.setHorizontalHeaderLabels(["Tool", "Enabled", "Sources", "Approval", "Unlock", "Scope"])
        self.tools_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tools_table.itemSelectionChanged.connect(self.app.on_tool_permission_selected)
        layout.addWidget(self.tools_table)

        controls = QHBoxLayout()
        self.tool_enabled = QCheckBox("Enabled")
        self.tool_requires_approval = QCheckBox("Requires approval")
        self.tool_requires_unlock = QCheckBox("Requires unlocked desktop")
        self.tool_sources = QLineEdit()
        self.tool_sources.setPlaceholderText("desktop,sms,voice")
        controls.addWidget(self.tool_enabled)
        controls.addWidget(self.tool_requires_approval)
        controls.addWidget(self.tool_requires_unlock)
        controls.addWidget(self.tool_sources, 1)
        controls.addWidget(create_button("Apply", self.app.save_selected_tool_permission, style="subtle"))
        layout.addLayout(controls)

        split = QHBoxLayout()
        self.approvals_table = QTableWidget()
        self.approvals_table.setColumnCount(5)
        self.approvals_table.setHorizontalHeaderLabels(["ID", "Tool", "Source", "Sender", "Status"])
        self.approvals_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.approvals_table.itemSelectionChanged.connect(self.app.on_approval_selected)
        split.addWidget(self.approvals_table, 2)

        right = QVBoxLayout()
        right.addWidget(create_button("Approve & Run", self.app.approve_selected_action))
        right.addWidget(create_button("Reject", self.app.reject_selected_action, style="subtle"))
        self.tasks_table = QTableWidget()
        self.tasks_table.setColumnCount(4)
        self.tasks_table.setHorizontalHeaderLabels(["Task ID", "Title", "Status", "Updated"])
        self.tasks_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right.addWidget(self.tasks_table, 1)
        split.addLayout(right, 3)

        layout.addLayout(split, 1)
        self.result_text = QPlainTextEdit()
        self.result_text.setReadOnly(True)
        layout.addWidget(self.result_text)


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
        self.activity_rows: list[dict[str, Any]] = []
        self.project_rows: list[dict[str, Any]] = []
        self.tool_permission_rows: list[tuple[str, dict[str, Any]]] = []
        self.approval_rows: list[dict[str, Any]] = []
        self.selected_tool_name: str | None = None
        self.selected_approval_id: str | None = None
        
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

        self.root_stack = QStackedWidget()
        main_layout.addWidget(self.root_stack, 1)

        # Lock screen
        self.lock_screen = QWidget()
        lock_layout = QVBoxLayout(self.lock_screen)
        lock_layout.setContentsMargins(30, 30, 30, 30)
        lock_layout.addStretch()
        card = QFrame()
        card.setMaximumWidth(560)
        card.setStyleSheet("background-color: white; border-radius: 10px; padding: 16px;")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(10)
        title = create_label("Mashbak", 22, bold=True)
        msg = create_label("System is locked. Enter your PIN to unlock.", 10, color=_SLATE)
        self.lock_pin_input = QLineEdit()
        self.lock_pin_input.setEchoMode(QLineEdit.Password)
        self.lock_pin_input.setPlaceholderText("PIN")
        self.lock_pin_input.returnPressed.connect(self.unlock_app)
        unlock_btn = create_button("Unlock", self.unlock_app)
        card_layout.addWidget(title)
        card_layout.addWidget(msg)
        card_layout.addWidget(self.lock_pin_input)
        card_layout.addWidget(unlock_btn)
        lock_layout.addWidget(card, alignment=Qt.AlignHCenter)
        lock_layout.addStretch()

        # Control board shell
        self.app_shell = QWidget()
        app_layout = QVBoxLayout(self.app_shell)
        app_layout.setContentsMargins(0, 0, 0, 0)
        app_layout.setSpacing(0)

        self._build_header()
        app_layout.addWidget(self.header_widget, 0)

        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self._build_sidebar()
        body_layout.addWidget(self.sidebar_widget, 0)

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
            (PersonalContextPage, "Personal Context"),
            (ToolsPermissionsPage, "Tools & Permissions"),
        ]:
            page = page_class(self)
            self.pages[name] = page
            self.stacked_widget.addWidget(page)

        self.stacked_widget.setCurrentWidget(self.pages["Dashboard"])
        body_layout.addWidget(self.stacked_widget, 1)

        body_widget = QWidget()
        body_widget.setLayout(body_layout)
        app_layout.addWidget(body_widget, 1)

        self.root_stack.addWidget(self.lock_screen)
        self.root_stack.addWidget(self.app_shell)
        self.root_stack.setCurrentWidget(self.lock_screen)
        
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
            ("Personal Context", "Personal Context"),
            ("Tools and Permissions", "Tools & Permissions"),
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
        candidate = self.pin_input.text().strip() or self.lock_pin_input.text().strip()
        self.pin_input.clear()
        self.lock_pin_input.clear()
        
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
        self.root_stack.setCurrentWidget(self.app_shell)
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
        self.refresh_personal_context()
        self.refresh_tools_permissions()
        
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
        self.root_stack.setCurrentWidget(self.lock_screen)
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

        self.lock_pin_input.setFocus()
    
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
            QTimer.singleShot(0, lambda: self._display_result(message, result))
        except Exception as exc:
            QTimer.singleShot(0, lambda: self._display_error(str(exc)))
    
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
        ]
        
        # Add verification reason for better transparency
        verification_reason = trace.get("verification_reason")
        if verification_reason:
            detail_lines.append(f"Verification reason: {str(verification_reason)[:150]}")
            detail_lines.append("")
        
        # If web search was performed, show search results
        if verification_state.lower() == "web-verified" and trace.get("tool_data"):
            try:
                tool_data = trace.get("tool_data")
                if isinstance(tool_data, dict) and "results" in tool_data:
                    results = tool_data.get("results", [])
                    if results:
                        detail_lines.append("WEB SEARCH RESULTS:")
                        for i, res in enumerate(results[:3], 1):
                            title = res.get("title", "Result")[:80]
                            detail_lines.append(f"  {i}. {title}")
                            if res.get("url"):
                                detail_lines.append(f"     {res['url']}")
                        detail_lines.append("")
            except Exception:
                pass
        
        detail_lines.append(f"Args: {json.dumps(safe_trace_args, ensure_ascii=True)[:200]}")
        
        if safe_raw_tool_output:
            detail_lines.append(f"Tool output: {str(safe_raw_tool_output)[:200]}")
        
        chat_page.details_text.setPlainText("\n".join(detail_lines))
        
        # Update verification
        verify_color = _SLATE
        if verification_state.lower() in {"verified", "tool-assisted", "web-verified"}:
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

        mashbak_rows = [
            ("AI enabled", str(bool(mashbak.get("ai_enabled")))),
            ("Model", str(mashbak.get("model") or "-")),
            ("Base URL", str(mashbak.get("base_url") or "-")),
            ("Temperature", str(mashbak.get("temperature") or "-")),
            ("Max tokens", str(mashbak.get("max_tokens") or "-")),
        ]
        page.mashbak_table.setRowCount(0)
        for idx, (key, value) in enumerate(mashbak_rows):
            page.mashbak_table.insertRow(idx)
            page.mashbak_table.setItem(idx, 0, QTableWidgetItem(key))
            page.mashbak_table.setItem(idx, 1, QTableWidgetItem(value))

        counts = bucherim.get("counts") or {}
        bucherim_rows = [
            ("Assistant number", str(bucherim.get("assistant_number") or "-")),
            ("Approved", str(counts.get("approved", 0))),
            ("Pending", str(counts.get("pending", 0))),
            ("Blocked", str(counts.get("blocked", 0))),
        ]
        page.bucherim_counts_table.setRowCount(0)
        for idx, (key, value) in enumerate(bucherim_rows):
            page.bucherim_counts_table.insertRow(idx)
            page.bucherim_counts_table.setItem(idx, 0, QTableWidgetItem(key))
            page.bucherim_counts_table.setItem(idx, 1, QTableWidgetItem(value))

        responses = bucherim.get("responses") or {}
        page.responses_table.setRowCount(0)
        for idx, (key, value) in enumerate(sorted(responses.items())):
            page.responses_table.insertRow(idx)
            page.responses_table.setItem(idx, 0, QTableWidgetItem(str(key)))
            page.responses_table.setItem(idx, 1, QTableWidgetItem(self._condense_detail(str(value), 220)))
    
    def refresh_communications(self):
        """Refresh communications data."""
        if not self.is_unlocked:
            return
        self.refresh_email_config_view()
        self.refresh_routing_view()
    
    def refresh_email_config_view(self):
        """Refresh email accounts view."""
        payload = self.client.get_email_accounts()
        if not isinstance(payload, dict) or payload.get("success") is False:
            return
        
        page = self.pages.get("Communications")
        if not page:
            return

        accounts = payload.get("accounts") or []
        default_id = payload.get("default_account_id")
        page.email_accounts_widget.clear()
        for account in accounts:
            label = str(account.get("label") or account.get("email_address") or "Email account")
            suffix = " [default]" if account.get("account_id") == default_id else ""
            item = QListWidgetItem(label + suffix)
            item.setData(Qt.UserRole, account)
            page.email_accounts_widget.addItem(item)

        if accounts:
            page.email_accounts_widget.setCurrentRow(0)
            page.email_result.setPlainText(json.dumps(payload, indent=2, ensure_ascii=True))
            page.email_status.setText(f"Email status: {len(accounts)} account(s) configured")
            page.email_status.setStyleSheet(f"color: {_GREEN};")
        else:
            self.new_email_account()
            page.email_result.setPlainText("No email accounts configured.")
            page.email_status.setText("Email status: not configured")
            page.email_status.setStyleSheet(f"color: {_AMBER};")
    
    def refresh_routing_view(self):
        """Refresh routing view."""
        payload = self.client.get_routing()
        if not isinstance(payload, dict) or payload.get("success") is False:
            return
        
        page = self.pages.get("Communications")
        if not page:
            return
        
        approved = payload.get("approved_numbers") or []
        blocked = payload.get("blocked_numbers") or []
        pending = payload.get("pending_requests") or []
        
        page.approved_widget.clear()
        for item in approved:
            page.approved_widget.addItem(str(item))
        
        page.blocked_widget.clear()
        for item in blocked:
            page.blocked_widget.addItem(str(item))
        
        page.pending_widget.clear()
        for item in pending:
            phone = item.get("phone_number") if isinstance(item, dict) else str(item)
            ts = item.get("timestamp") if isinstance(item, dict) else ""
            page.pending_widget.addItem(f"{phone}  ({ts})")
        
        counts = payload.get("counts") or {}
        page.routing_counts.setText(
            f"Approved: {counts.get('approved', len(approved))}   Pending: {counts.get('pending', len(pending))}   Blocked: {counts.get('blocked', len(blocked))}"
        )
        page.routing_result.setPlainText(json.dumps(payload, indent=2, ensure_ascii=True))
        self.refresh_selected_routing_member()

    def on_routing_selection_changed(self):
        """Load selected routing member detail into the side panel."""
        self.refresh_selected_routing_member()

    def refresh_selected_routing_member(self):
        """Refresh selected routing member details and history."""
        page = self.pages.get("Communications")
        if not page:
            return
        phone = self._selected_routing_phone()
        if not phone:
            page.routing_member_table.setRowCount(0)
            page.routing_history_table.setRowCount(0)
            return
        payload = self.client.get_routing_member(phone)
        if payload.get("success") is False:
            page.routing_result.setPlainText(json.dumps(payload, indent=2, ensure_ascii=True))
            return

        profile = payload.get("profile") or {}
        rows = [
            ("Phone", str(payload.get("phone_number") or phone)),
            ("State", str(payload.get("state") or "unknown")),
            ("Pending request", str(bool(payload.get("has_pending_request")))),
            ("Last seen", str(profile.get("last_seen") or "-")),
            ("Display name", str(profile.get("display_name") or "-")),
        ]
        page.routing_member_table.setRowCount(0)
        for idx, (key, value) in enumerate(rows):
            page.routing_member_table.insertRow(idx)
            page.routing_member_table.setItem(idx, 0, QTableWidgetItem(key))
            page.routing_member_table.setItem(idx, 1, QTableWidgetItem(value))

        history = payload.get("history") or []
        page.routing_history_table.setRowCount(0)
        for idx, row in enumerate(history[:40]):
            page.routing_history_table.insertRow(idx)
            page.routing_history_table.setItem(idx, 0, QTableWidgetItem(str(row.get("timestamp") or "")))
            page.routing_history_table.setItem(idx, 1, QTableWidgetItem(str(row.get("direction") or "")))
            page.routing_history_table.setItem(idx, 2, QTableWidgetItem(str(row.get("state") or "")))
            preview = str(row.get("body") or row.get("content") or "")
            page.routing_history_table.setItem(idx, 3, QTableWidgetItem(self._condense_detail(preview, 120)))
    
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
        
        page.blocked_table.setRowCount(0)
        for idx, row in enumerate(payload.get("blocked_attempts") or []):
            page.blocked_table.insertRow(idx)
            page.blocked_table.setItem(idx, 0, QTableWidgetItem(str(row.get("timestamp") or "")))
            page.blocked_table.setItem(idx, 1, QTableWidgetItem(str(row.get("tool") or "")))
            page.blocked_table.setItem(idx, 2, QTableWidgetItem(str(row.get("path") or "-")))
    
    def refresh_projects(self):
        """Refresh projects/files information."""
        if not self.is_unlocked:
            return
        
        page = self.pages.get("Projects / Files")
        if not page:
            return

        payload = self.client.get_activity(
            limit=150,
            event_types="tool_execution",
            query=page.projects_query.text().strip(),
        )
        if not isinstance(payload, dict) or payload.get("success") is False:
            return

        relevant_tools = {
            "create_file",
            "create_folder",
            "delete_file",
            "list_files",
            "write_file",
            "read_file",
            "update_file",
        }
        self.project_rows = []
        for item in payload.get("items") or []:
            tool = str(item.get("selected_tool") or "")
            target = str(item.get("target") or "")
            if tool in relevant_tools or target:
                self.project_rows.append(item)

        page.projects_table.setRowCount(0)
        for idx, row in enumerate(self.project_rows):
            page.projects_table.insertRow(idx)
            values = [
                str(row.get("timestamp") or ""),
                self._condense_detail(str(row.get("requested_action") or ""), 72),
                str(row.get("selected_tool") or ""),
                str(row.get("state") or ""),
                self._condense_detail(str(row.get("target") or "-"), 86),
                str(row.get("source") or ""),
            ]
            for col, value in enumerate(values):
                page.projects_table.setItem(idx, col, QTableWidgetItem(value))

        if not self.project_rows:
            page.projects_detail.setPlainText("No recent file/project actions.")
        else:
            page.projects_table.selectRow(0)

    def on_project_row_selected(self):
        """Show selected project/file event details."""
        page = self.pages.get("Projects / Files")
        if not page:
            return
        row = page.projects_table.currentRow()
        if row < 0 or row >= len(self.project_rows):
            return
        selected = self.project_rows[row]
        page.projects_detail.setPlainText(json.dumps(selected, indent=2, ensure_ascii=True))
    
    def refresh_activity_audit(self):
        """Refresh activity and audit log."""
        if not self.is_unlocked:
            return

        page = self.pages.get("Activity / Audit")
        if not page:
            return
        
        source_value = page.activity_source.currentText().strip().lower()
        state_value = page.activity_state.currentText().strip().lower()
        payload = self.client.get_activity(
            limit=180,
            sources="" if source_value == "all" else source_value,
            state="" if state_value == "all" else state_value,
            tool_name=page.activity_tool.text().strip(),
            query=page.activity_query.text().strip(),
        )
        if not isinstance(payload, dict) or payload.get("success") is False:
            return

        page.activity_table.setRowCount(0)
        self.activity_rows = list(payload.get("items") or [])
        for idx, row in enumerate(self.activity_rows):
            page.activity_table.insertRow(idx)
            values = [
                row.get("timestamp") or "",
                row.get("event_type") or "",
                row.get("assistant") or "",
                row.get("requested_action") or "",
                row.get("selected_tool") or "",
                row.get("state") or "",
                row.get("target") or "",
                row.get("source") or "",
            ]
            for col, value in enumerate(values):
                page.activity_table.setItem(idx, col, QTableWidgetItem(value))

        if not self.activity_rows:
            page.activity_detail.setPlainText("No recent activity.")
        else:
            page.activity_table.selectRow(0)

    def on_activity_row_selected(self):
        """Show selected activity event details."""
        page = self.pages.get("Activity / Audit")
        if not page:
            return
        row = page.activity_table.currentRow()
        if row < 0 or row >= len(self.activity_rows):
            return
        selected = self.activity_rows[row]
        page.activity_detail.setPlainText(json.dumps(selected, indent=2, ensure_ascii=True))

    def refresh_personal_context(self):
        """Load personal context data from backend."""
        if not self.is_unlocked:
            return
        page = self.pages.get("Personal Context")
        if not page:
            return
        payload = self.client.get_personal_context()
        if not isinstance(payload, dict):
            return
        page.profile_text.setPlainText(json.dumps(payload.get("profile") or {}, indent=2, ensure_ascii=True))
        page.people_text.setPlainText(json.dumps(payload.get("people") or [], indent=2, ensure_ascii=True))
        page.routines_text.setPlainText(json.dumps(payload.get("routines") or [], indent=2, ensure_ascii=True))
        page.projects_text.setPlainText(json.dumps(payload.get("projects") or [], indent=2, ensure_ascii=True))
        page.preferences_text.setPlainText(json.dumps(payload.get("preferences") or {}, indent=2, ensure_ascii=True))
        page.status_label.setText("Loaded personal context.")
        page.status_label.setStyleSheet(f"color: {_GREEN};")

    def save_personal_context(self):
        """Save personal context from editor widgets."""
        page = self.pages.get("Personal Context")
        if not page:
            return
        try:
            payload = {
                "profile": json.loads(page.profile_text.toPlainText() or "{}"),
                "people": json.loads(page.people_text.toPlainText() or "[]"),
                "routines": json.loads(page.routines_text.toPlainText() or "[]"),
                "projects": json.loads(page.projects_text.toPlainText() or "[]"),
                "preferences": json.loads(page.preferences_text.toPlainText() or "{}"),
            }
        except json.JSONDecodeError as exc:
            page.status_label.setText(f"Invalid JSON: {exc}")
            page.status_label.setStyleSheet(f"color: {_RED};")
            return
        result = self.client.save_personal_context(payload)
        page.status_label.setText("Personal context saved." if isinstance(result, dict) else "Save failed")
        page.status_label.setStyleSheet(f"color: {_GREEN if isinstance(result, dict) else _RED};")

    def refresh_tools_permissions(self):
        """Refresh tools permissions, pending approvals, and recent tasks."""
        if not self.is_unlocked:
            return
        page = self.pages.get("Tools & Permissions")
        if not page:
            return

        payload = self.client.get_tools_permissions()
        tools = (payload or {}).get("tools") or {}
        self.tool_permission_rows = list(sorted(tools.items(), key=lambda item: item[0]))
        page.tools_table.setRowCount(0)
        for idx, (name, cfg) in enumerate(self.tool_permission_rows):
            page.tools_table.insertRow(idx)
            values = [
                name,
                str(bool(cfg.get("enabled", True))),
                ",".join(cfg.get("allowed_sources") or []),
                str(bool(cfg.get("requires_approval", False))),
                str(bool(cfg.get("requires_unlocked_desktop", False))),
                str(cfg.get("scope") or "default"),
            ]
            for col, value in enumerate(values):
                page.tools_table.setItem(idx, col, QTableWidgetItem(value))

        approvals = self.client.get_approvals(limit=80, status="pending")
        self.approval_rows = list((approvals or {}).get("approvals") or [])
        page.approvals_table.setRowCount(0)
        for idx, row in enumerate(self.approval_rows):
            page.approvals_table.insertRow(idx)
            values = [
                str(row.get("approval_id") or ""),
                str(row.get("tool_name") or ""),
                str(row.get("source") or ""),
                str(row.get("sender") or ""),
                str(row.get("status") or ""),
            ]
            for col, value in enumerate(values):
                page.approvals_table.setItem(idx, col, QTableWidgetItem(value))

        tasks = self.client.get_tasks(limit=80)
        task_rows = list((tasks or {}).get("tasks") or [])
        page.tasks_table.setRowCount(0)
        for idx, row in enumerate(task_rows):
            page.tasks_table.insertRow(idx)
            values = [
                str(row.get("task_id") or ""),
                self._condense_detail(str(row.get("title") or ""), 70),
                str(row.get("status") or ""),
                str(row.get("updated_at") or ""),
            ]
            for col, value in enumerate(values):
                page.tasks_table.setItem(idx, col, QTableWidgetItem(value))

    def on_tool_permission_selected(self):
        page = self.pages.get("Tools & Permissions")
        if not page:
            return
        idx = page.tools_table.currentRow()
        if idx < 0 or idx >= len(self.tool_permission_rows):
            return
        name, cfg = self.tool_permission_rows[idx]
        self.selected_tool_name = name
        page.tool_enabled.setChecked(bool(cfg.get("enabled", True)))
        page.tool_requires_approval.setChecked(bool(cfg.get("requires_approval", False)))
        page.tool_requires_unlock.setChecked(bool(cfg.get("requires_unlocked_desktop", False)))
        page.tool_sources.setText(",".join(cfg.get("allowed_sources") or []))
        page.result_text.setPlainText(json.dumps({"tool": name, "settings": cfg}, indent=2, ensure_ascii=True))

    def save_selected_tool_permission(self):
        page = self.pages.get("Tools & Permissions")
        if not page or not self.selected_tool_name:
            return
        sources = [value.strip() for value in page.tool_sources.text().split(",") if value.strip()]
        result = self.client.update_tool_permission(
            self.selected_tool_name,
            {
                "enabled": bool(page.tool_enabled.isChecked()),
                "requires_approval": bool(page.tool_requires_approval.isChecked()),
                "requires_unlocked_desktop": bool(page.tool_requires_unlock.isChecked()),
                "allowed_sources": sources,
            },
        )
        page.result_text.setPlainText(json.dumps(result, indent=2, ensure_ascii=True))
        self.refresh_tools_permissions()

    def on_approval_selected(self):
        page = self.pages.get("Tools & Permissions")
        if not page:
            return
        idx = page.approvals_table.currentRow()
        if idx < 0 or idx >= len(self.approval_rows):
            return
        row = self.approval_rows[idx]
        self.selected_approval_id = str(row.get("approval_id") or "")
        page.result_text.setPlainText(json.dumps(row, indent=2, ensure_ascii=True))

    def approve_selected_action(self):
        page = self.pages.get("Tools & Permissions")
        if not page or not self.selected_approval_id:
            return
        result = self.client.approve_and_run(self.selected_approval_id)
        page.result_text.setPlainText(json.dumps(result, indent=2, ensure_ascii=True))
        self.refresh_tools_permissions()
        self.refresh_activity_audit()

    def reject_selected_action(self):
        page = self.pages.get("Tools & Permissions")
        if not page or not self.selected_approval_id:
            return
        result = self.client.reject_approval(self.selected_approval_id)
        page.result_text.setPlainText(json.dumps(result, indent=2, ensure_ascii=True))
        self.refresh_tools_permissions()
    
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
        """Save the current email account."""
        page = self.pages.get("Communications")
        if not page:
            return
        try:
            port = int((page.email_imap_port.text() or "993").strip())
        except ValueError:
            page.email_result.setPlainText("IMAP port must be a number.")
            return
        payload = self.client.save_email_config(
            account_id=page.current_email_account_id,
            label=page.email_label.text().strip(),
            provider="imap",
            email_address=page.email_address.text().strip(),
            password=page.email_password.text(),
            imap_host=page.email_imap_host.text().strip(),
            imap_port=port,
            use_ssl=True,
            mailbox=page.email_mailbox.text().strip() or "INBOX",
            make_default=page.email_make_default.isChecked(),
        )
        page.email_result.setPlainText(json.dumps(payload, indent=2, ensure_ascii=True))
        if payload.get("success") is False:
            page.email_status.setText("Email status: save failed")
            page.email_status.setStyleSheet(f"color: {_RED};")
            return
        self.refresh_email_config_view()
    
    def test_email_connection(self):
        """Test the selected email account."""
        page = self.pages.get("Communications")
        if not page:
            return
        payload = self.client.test_email_connection(page.current_email_account_id)
        page.email_result.setPlainText(json.dumps(payload, indent=2, ensure_ascii=True))
        if payload.get("success"):
            page.email_status.setText("Email status: connection successful")
            page.email_status.setStyleSheet(f"color: {_GREEN};")
        else:
            page.email_status.setText("Email status: connection failed")
            page.email_status.setStyleSheet(f"color: {_RED};")

    def new_email_account(self):
        """Reset the email form for a new account."""
        page = self.pages.get("Communications")
        if not page:
            return
        page.current_email_account_id = None
        page.email_label.clear()
        page.email_address.clear()
        page.email_password.clear()
        page.email_imap_host.clear()
        page.email_imap_port.setText("993")
        page.email_mailbox.setText("INBOX")
        page.email_make_default.setChecked(False)

    def on_email_account_selected(self, current, previous=None):
        """Load the selected email account into the form."""
        del previous
        page = self.pages.get("Communications")
        if not page or current is None:
            return
        account = current.data(Qt.UserRole) or {}
        page.current_email_account_id = account.get("account_id")
        page.email_label.setText(str(account.get("label") or ""))
        page.email_address.setText(str(account.get("email_address") or ""))
        page.email_password.clear()
        page.email_imap_host.setText(str(account.get("imap_host") or ""))
        page.email_imap_port.setText(str(account.get("imap_port") or "993"))
        page.email_mailbox.setText(str(account.get("mailbox") or "INBOX"))
        page.email_make_default.setChecked(bool(account.get("is_default")))

    def set_default_email_account(self):
        """Set the selected email account as default."""
        page = self.pages.get("Communications")
        if not page or not page.current_email_account_id:
            return
        payload = self.client.set_default_email_account(page.current_email_account_id)
        page.email_result.setPlainText(json.dumps(payload, indent=2, ensure_ascii=True))
        self.refresh_email_config_view()

    def delete_email_account(self):
        """Delete the selected email account."""
        page = self.pages.get("Communications")
        if not page or not page.current_email_account_id:
            return
        payload = self.client.delete_email_account(page.current_email_account_id)
        page.email_result.setPlainText(json.dumps(payload, indent=2, ensure_ascii=True))
        self.refresh_email_config_view()
    
    def add_allowed_directory(self):
        """Add an allowed directory and persist the policy."""
        page = self.pages.get("Files & Permissions")
        if not page:
            return
        value = page.new_dir_input.text().strip()
        if not value:
            return
        existing = [page.allowed_list.item(index).text() for index in range(page.allowed_list.count())]
        if value not in existing:
            existing.append(value)
        payload = self.client.save_files_policy(existing)
        page.path_test_result.setText(json.dumps(payload, ensure_ascii=True)[:220])
        if payload.get("success") is not False:
            page.new_dir_input.clear()
            self.refresh_files_policy()
    
    def remove_selected_directory(self):
        """Remove the selected allowed directory and persist the policy."""
        page = self.pages.get("Files & Permissions")
        if not page:
            return
        current = page.allowed_list.currentItem()
        if current is None:
            return
        remove_value = current.text()
        remaining = [
            page.allowed_list.item(index).text()
            for index in range(page.allowed_list.count())
            if page.allowed_list.item(index).text() != remove_value
        ]
        payload = self.client.save_files_policy(remaining)
        page.path_test_result.setText(json.dumps(payload, ensure_ascii=True)[:220])
        if payload.get("success") is not False:
            self.refresh_files_policy()

    def test_policy_path(self):
        """Test path against current file policy."""
        page = self.pages.get("Files & Permissions")
        if not page:
            return
        value = page.path_test_input.text().strip()
        if not value:
            return
        payload = self.client.test_policy_path(value)
        allowed = bool(payload.get("allowed"))
        reason = str(payload.get("reason") or "")
        page.path_test_result.setText(("Allowed: " if allowed else "Blocked: ") + reason)
        page.path_test_result.setStyleSheet(f"color: {_GREEN if allowed else _RED};")

    def _selected_routing_phone(self) -> str:
        """Resolve the phone number selected or typed in the routing panel."""
        page = self.pages.get("Communications")
        if not page:
            return ""
        direct = page.routing_phone_input.text().strip()
        if direct:
            return direct
        for widget in (page.pending_widget, page.approved_widget, page.blocked_widget):
            item = widget.currentItem()
            if item is not None:
                return item.text().split()[0]
        return ""

    def approve_routing_member(self):
        """Approve the selected or typed phone number."""
        page = self.pages.get("Communications")
        if not page:
            return
        phone = self._selected_routing_phone()
        if not phone:
            page.routing_result.setPlainText("Select or enter a phone number to approve.")
            return
        payload = self.client.approve_routing_member(phone)
        page.routing_result.setPlainText(json.dumps(payload, indent=2, ensure_ascii=True))
        self.refresh_routing_view()
        self.refresh_selected_routing_member()

    def block_routing_member(self):
        """Block the selected or typed phone number."""
        page = self.pages.get("Communications")
        if not page:
            return
        phone = self._selected_routing_phone()
        if not phone:
            page.routing_result.setPlainText("Select or enter a phone number to block.")
            return
        payload = self.client.block_routing_member(phone)
        page.routing_result.setPlainText(json.dumps(payload, indent=2, ensure_ascii=True))
        self.refresh_routing_view()
        self.refresh_selected_routing_member()
    
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
