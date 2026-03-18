"""PySide6 UI for Mashbak Control Board."""

from __future__ import annotations

import json
import html
import threading
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer, QPoint, QObject, Signal
from PySide6.QtGui import QFont, QTextCursor, QColor, QAction
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
    QTabWidget,
    QApplication,
    QAbstractItemView,
    QMenu,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
)

try:
    from agent.redaction import sanitize_for_logging
except Exception:  # pragma: no cover
    def sanitize_for_logging(value, key=None):
        return value


# Color palette
_GREEN = "#1a7f37"
_RED = "#b42318"
_AMBER = "#9a6700"
_SLATE = "#57606a"
_YELLOW = "#b98900"
_UNKNOWN = "#6b7280"
_BG = "#eef2f7"
_CARD = "#ffffff"
_NAV_BG = "#5175C2"
_SURFACE = "#e7ecf4"
_HEADER_BG = "#374B6D"


def create_label(text: str, font_size: int = 10, bold: bool = False, color: str = "#34415E") -> QLabel:
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
        bg, fg = "#fff5db", "#b47808"
    elif status == "error":
        bg, fg = "#ffebe9", "#ce1a4d"
    else:  # info
        bg, fg = "#304769", "#e6edf5"
    badge.setStyleSheet(f"background-color: {bg}; color: {fg}; padding: 6px 10px; border-radius: 4px;")
    return badge


class StatusCard(QFrame):
    """A card showing component status with indicator dot."""
    
    _ICONS = {
        "Backend": "🖥",
        "Bridge": "📡",
        "Email": "📬",
        "Active Assistant": "🧠",
    }
    
    def __init__(self, title: str, subtitle: str):
        super().__init__()
        self.title = title
        self.subtitle_text = subtitle
        self._setup_ui()
        self.setStyleSheet(
            "StatusCard { background-color: white; border-radius: 8px; "
            "border: 1px solid #dde3ef; }"
        )
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)
        
        # Top row: icon + title + indicator
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        icon_text = self._ICONS.get(self.title, "●")
        icon_label = create_label(icon_text, 16)
        icon_label.setFixedWidth(26)
        top_layout.addWidget(icon_label)
        
        self.title_label = create_label(self.title, 10, bold=True)
        top_layout.addWidget(self.title_label)
        top_layout.addStretch()
        
        self.indicator = QLabel("●")
        self.indicator.setStyleSheet(f"color: {_UNKNOWN}; font-size: 14px;")
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
        self.refresh_btn = create_button("Refresh Dashboard", self.app.refresh_dashboard_clicked)
        header_layout.addWidget(self.refresh_btn)
        self.last_refreshed_label = create_label("Last refreshed: never", 8, color=_SLATE)
        header_layout.addWidget(self.last_refreshed_label)
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
        
        # Tables area - use splitter so both can be resized
        tables_splitter = QSplitter(Qt.Horizontal)
        tables_splitter.setChildrenCollapsible(False)
        
        # Attention queue
        attention_widget = QWidget()
        attention_layout = QVBoxLayout(attention_widget)
        attention_layout.setContentsMargins(0, 0, 0, 0)
        attention_layout.addWidget(create_label("Attention", 10, bold=True))
        self.attention_label = create_label("No alerts.", 9, color=_SLATE)
        attention_layout.addWidget(self.attention_label)
        
        self.failures_table = QTableWidget()
        self.failures_table.setColumnCount(5)
        self.failures_table.setHorizontalHeaderLabels(["Timestamp", "Assistant", "Action", "Result", "Status"])
        self.failures_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.failures_table.horizontalHeader().setStretchLastSection(True)
        self.failures_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.failures_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        attention_layout.addWidget(self.failures_table)
        tables_splitter.addWidget(attention_widget)
        
        # Recent Activity
        activity_widget = QWidget()
        activity_layout = QVBoxLayout(activity_widget)
        activity_layout.setContentsMargins(0, 0, 0, 0)
        activity_layout.addWidget(create_label("Recent Activity", 10, bold=True))
        self.actions_table = QTableWidget()
        self.actions_table.setColumnCount(5)
        self.actions_table.setHorizontalHeaderLabels(["Timestamp", "Assistant", "Action", "Result", "Status"])
        self.actions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.actions_table.horizontalHeader().setStretchLastSection(True)
        self.actions_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.actions_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        activity_layout.addWidget(self.actions_table)
        tables_splitter.addWidget(activity_widget)
        
        tables_splitter.setStretchFactor(0, 1)
        tables_splitter.setStretchFactor(1, 2)
        layout.addWidget(tables_splitter, 1)

    def set_refreshing(self, refreshing: bool):
        if refreshing:
            self.refresh_btn.setText("Refreshing...")
            self.refresh_btn.setEnabled(False)
            return
        self.refresh_btn.setText("Refresh Dashboard")
        self.refresh_btn.setEnabled(True)

    def mark_refreshed(self):
        self.last_refreshed_label.setText(f"Last refreshed: {datetime.now().strftime('%H:%M:%S')}")
        
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
        self.chat_display.setStyleSheet(
            "background-color: #f8fafc; color: #111827; border: 1px solid #d9e2ec; border-radius: 6px; padding: 10px;"
        )
        self.chat_display.setPlaceholderText("No activity yet")
        left_layout.addWidget(self.chat_display, 1)
        
        self.processing_label = create_label("", 9, color=_SLATE)
        left_layout.addWidget(self.processing_label)
        
        # Input area
        input_layout = QHBoxLayout()
        self.message_input = QLineEdit()
        self.message_input.setFont(QFont("Segoe UI", 10))
        self.message_input.setStyleSheet("padding: 8px; border: 1px solid #ddd; border-radius: 4px;")
        self.message_input.setPlaceholderText("Type a command for Mashbak (e.g., summarize new emails)")
        self.message_input.returnPressed.connect(self.app.on_send)
        input_layout.addWidget(self.message_input)
        
        send_btn = create_button("Send", self.app.on_send)
        input_layout.addWidget(send_btn)
        left_layout.addLayout(input_layout)

        self.quick_suggestion_frame = QFrame()
        self.quick_suggestion_frame.setStyleSheet(
            "background-color: #fffbeb; border: 1px solid #fcd34d; border-radius: 8px;"
        )
        suggest_layout = QHBoxLayout(self.quick_suggestion_frame)
        suggest_layout.setContentsMargins(10, 8, 10, 8)
        self.quick_suggestion_label = create_label("", 9, color="#92400e")
        suggest_layout.addWidget(self.quick_suggestion_label, 1)
        self.quick_suggestion_yes = create_button("Yes", self.app.on_accept_quick_suggestion, style="subtle")
        self.quick_suggestion_no = create_button("No", self.app.on_dismiss_quick_suggestion, style="subtle")
        suggest_layout.addWidget(self.quick_suggestion_yes)
        suggest_layout.addWidget(self.quick_suggestion_no)
        self.quick_suggestion_frame.setVisible(False)
        left_layout.addWidget(self.quick_suggestion_frame)
        
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
        self.details_text.setStyleSheet("background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 6px;")
        self.details_text.setPlaceholderText("Waiting for commands")
        self.trace_tabs.addTab(self.details_text, "Details")
        
        self.activity_list = QPlainTextEdit()
        self.activity_list.setReadOnly(True)
        self.activity_list.setStyleSheet("background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 6px; font-family: monospace;")
        self.activity_list.setPlainText("No activity yet")
        self.trace_tabs.addTab(self.activity_list, "Activity")
        
        logs_widget = QWidget()
        logs_layout = QVBoxLayout(logs_widget)
        logs_layout.addWidget(create_label("Agent Logs", 10, bold=True))
        self.agent_logs = QPlainTextEdit()
        self.agent_logs.setReadOnly(True)
        self.agent_logs.setStyleSheet("background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 6px; font-family: monospace; font-size: 8pt;")
        logs_layout.addWidget(self.agent_logs)
        logs_layout.addWidget(create_label("Bridge Logs", 10, bold=True))
        self.bridge_logs = QPlainTextEdit()
        self.bridge_logs.setReadOnly(True)
        self.bridge_logs.setStyleSheet("background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 6px; font-family: monospace; font-size: 8pt;")
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
        action_layout.setSpacing(8)
        action_layout.addWidget(create_label("Conversation", 9, bold=True, color=_SLATE))
        action_layout.addWidget(create_button("Clear", self.app.clear_chat, style="subtle"))
        action_layout.addWidget(create_button("Copy Last", self.app.copy_last_response, style="subtle"))
        action_layout.addSpacing(12)
        action_layout.addWidget(create_label("Trace", 9, bold=True, color=_SLATE))
        action_layout.addWidget(create_button("Clear Activity", self.app.clear_activity, style="subtle"))
        action_layout.addWidget(create_button("Copy Raw", self.app.copy_raw_trace, style="subtle"))
        action_layout.addWidget(create_button("Refresh Logs", self.app.refresh_logs, style="subtle"))
        action_layout.addStretch()
        layout.addLayout(action_layout)

    def show_quick_suggestion(self, command_text: str):
        safe_text = str(command_text or "").strip()
        self.quick_suggestion_label.setText(f'Create Quick Command for "{safe_text}"?')
        self.quick_suggestion_frame.setVisible(True)

    def hide_quick_suggestion(self):
        self.quick_suggestion_frame.setVisible(False)
    
    def append_message(self, role: str, text: str):
        """Append message to chat display."""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_display.setTextCursor(cursor)
        
        timestamp = datetime.now().strftime("%I:%M %p").lstrip("0")
        body = html.escape(str(text or "")).replace("\n", "<br>")

        normalized_role = str(role or "system").strip().lower()
        if normalized_role in {"you", "user"}:
            header_text = f"You | {timestamp}"
            card_style = "background:#eaf2ff;border:1px solid #cfe0ff;"
            role_color = "#0a3069"
            justify = "flex-end"
            text_align = "right"
        elif normalized_role in {"mashbak", "assistant"}:
            header_text = f"Mashbak | {timestamp}"
            card_style = "background:#ffffff;border:1px solid #d9e2ec;"
            role_color = "#0f4fbf"
            justify = "flex-start"
            text_align = "left"
        elif normalized_role == "error":
            header_text = f"System Error | {timestamp}"
            card_style = "background:#fff1f0;border:1px solid #ffd6d2;"
            role_color = "#8c2f39"
            justify = "flex-start"
            text_align = "left"
        else:
            header_text = f"System | {timestamp}"
            card_style = "background:#f8fafc;border:1px dashed #cbd5e1;"
            role_color = "#64748b"
            justify = "flex-start"
            text_align = "left"

        # Keep each message as an explicit two-line block with a guaranteed spacer after it.
        # This prevents sender headers from merging into the next message body/header.
        block_html = (
            f"<div style='display:flex; justify-content:{justify}; width:100%; margin:6px 0 0 0;'>"
            f"<div style='max-width:76%; {card_style} border-radius:8px; padding:8px;'>"
            f"<div style='font-weight:600; color:{role_color}; margin:0 0 6px 0; text-align:{text_align};'>{header_text}</div>"
            f"<div style='color:#111827; line-height:1.45; text-align:{text_align};'>{body}</div>"
            "</div>"
            "</div>"
            "<div style='height:10px; line-height:10px;'>&nbsp;</div>"
        )
        self.chat_display.insertHtml(block_html)
        
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
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        left_widget = QWidget()
        left = QVBoxLayout(left_widget)
        left.setContentsMargins(0, 0, 0, 0)
        left.addWidget(create_label("Mashbak Runtime", 10, bold=True))
        self.mashbak_table = QTableWidget()
        self.mashbak_table.setColumnCount(2)
        self.mashbak_table.setHorizontalHeaderLabels(["Setting", "Value"])
        self.mashbak_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.mashbak_table.horizontalHeader().setStretchLastSection(True)
        self.mashbak_table.verticalHeader().setVisible(False)
        self.mashbak_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        left.addWidget(self.mashbak_table)
        left.addWidget(create_label("Runtime settings and model controls", 8, color=_SLATE))
        left.addSpacing(10)

        left.addWidget(create_label("Bucherim Summary", 10, bold=True))
        self.bucherim_counts_table = QTableWidget()
        self.bucherim_counts_table.setColumnCount(2)
        self.bucherim_counts_table.setHorizontalHeaderLabels(["Field", "Value"])
        self.bucherim_counts_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.bucherim_counts_table.horizontalHeader().setStretchLastSection(True)
        self.bucherim_counts_table.verticalHeader().setVisible(False)
        self.bucherim_counts_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        left.addWidget(self.bucherim_counts_table)
        self.bucherim_empty_label = create_label("", 9, color=_SLATE)
        left.addWidget(self.bucherim_empty_label)

        right_widget = QWidget()
        right = QVBoxLayout(right_widget)
        right.setContentsMargins(0, 0, 0, 0)
        right.addWidget(create_label("Response Templates", 10, bold=True))
        self.responses_table = QTableWidget()
        self.responses_table.setColumnCount(2)
        self.responses_table.setHorizontalHeaderLabels(["Template", "Text"])
        self.responses_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.responses_table.horizontalHeader().setStretchLastSection(True)
        self.responses_table.verticalHeader().setVisible(False)
        self.responses_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.responses_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.responses_table.customContextMenuRequested.connect(self.app.on_template_context_menu)
        self.responses_table.itemSelectionChanged.connect(self.app.on_template_row_selected)
        right.addWidget(self.responses_table)
        right.addWidget(create_label("Selected template", 9, bold=True, color=_SLATE))
        self.responses_detail = QPlainTextEdit()
        self.responses_detail.setReadOnly(True)
        self.responses_detail.setStyleSheet("background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 6px;")
        self.responses_detail.setPlaceholderText("No template selected")
        right.addWidget(self.responses_detail)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)


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

        email_splitter = QSplitter(Qt.Horizontal)
        email_splitter.setChildrenCollapsible(False)
        
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.addWidget(create_label("Configured Accounts", 9, bold=True, color=_SLATE))
        self.email_accounts_widget = QListWidget()
        self.email_accounts_widget.setStyleSheet(
            "QListWidget::item:selected { background: #eaf2ff; color: #0a3069; border: 1px solid #bfd6ff; }"
        )
        self.email_accounts_widget.currentItemChanged.connect(self.app.on_email_account_selected)
        list_layout.addWidget(self.email_accounts_widget)
        self.email_accounts_empty = create_label("", 9, color=_SLATE)
        list_layout.addWidget(self.email_accounts_empty)
        email_splitter.addWidget(list_widget)
        
        form_widget = QWidget()
        grid = QGridLayout(form_widget)
        grid.setContentsMargins(8, 0, 0, 0)
        self.email_label = QLineEdit()
        self.email_address = QLineEdit()
        
        # Password field with show/hide
        self.email_password = QLineEdit()
        self.email_password.setEchoMode(QLineEdit.Password)
        pw_row = QHBoxLayout()
        pw_row.setContentsMargins(0, 0, 0, 0)
        pw_row.setSpacing(4)
        pw_row.addWidget(self.email_password)
        self._pw_show_btn = QPushButton("Show")
        self._pw_show_btn.setFixedWidth(48)
        self._pw_show_btn.setCheckable(True)
        self._pw_show_btn.setFont(QFont("Segoe UI", 8))
        self._pw_show_btn.setStyleSheet(
            "QPushButton { background: #f3f4f6; border: 1px solid #d1d5db; border-radius: 3px; padding: 3px; }"
            "QPushButton:checked { background: #dbeafe; color: #1d4ed8; }"
        )
        self._pw_show_btn.toggled.connect(
            lambda checked: (
                self.email_password.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password),
                self._pw_show_btn.setText("Hide" if checked else "Show"),
            )
        )
        pw_row.addWidget(self._pw_show_btn)
        pw_widget = QWidget()
        pw_widget.setLayout(pw_row)
        
        self.email_imap_host = QLineEdit()
        self.email_imap_port = QLineEdit("993")
        self.email_mailbox = QLineEdit("INBOX")
        self.email_make_default = QCheckBox("Set as primary account")
        
        self.email_categories = QLineEdit()
        self.email_categories.setPlaceholderText("e.g. Primary, Promotions, Social, Updates")
        self.email_default_category = QComboBox()
        self.email_default_category.addItems(["Primary", "All", "Promotions", "Social", "Updates", "Forums"])
        
        grid.addWidget(create_label("Label"), 0, 0)
        grid.addWidget(self.email_label, 0, 1)
        grid.addWidget(create_label("Email Address"), 1, 0)
        grid.addWidget(self.email_address, 1, 1)
        grid.addWidget(create_label("Password"), 2, 0)
        grid.addWidget(pw_widget, 2, 1)
        grid.addWidget(create_label("IMAP Server"), 3, 0)
        grid.addWidget(self.email_imap_host, 3, 1)
        grid.addWidget(create_label("IMAP Port"), 4, 0)
        grid.addWidget(self.email_imap_port, 4, 1)
        grid.addWidget(create_label("Mailbox"), 5, 0)
        grid.addWidget(self.email_mailbox, 5, 1)
        grid.addWidget(create_label("Categories"), 6, 0)
        grid.addWidget(self.email_categories, 6, 1)
        grid.addWidget(create_label("Default Category"), 7, 0)
        grid.addWidget(self.email_default_category, 7, 1)
        grid.addWidget(self.email_make_default, 8, 1)
        email_splitter.addWidget(form_widget)
        email_splitter.setStretchFactor(0, 1)
        email_splitter.setStretchFactor(1, 2)
        
        email_layout.addWidget(email_splitter)

        email_actions = QHBoxLayout()
        email_actions.addWidget(create_button("New Account", self.app.new_email_account, style="subtle"))
        self.save_account_btn = create_button("Save Account", self.app.save_email_config)
        self.save_account_btn.setEnabled(False)
        email_actions.addWidget(self.save_account_btn)
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

        self.email_label.textChanged.connect(self.app.on_email_form_dirty)
        self.email_address.textChanged.connect(self.app.on_email_form_dirty)
        self.email_password.textChanged.connect(self.app.on_email_form_dirty)
        self.email_imap_host.textChanged.connect(self.app.on_email_form_dirty)
        self.email_imap_port.textChanged.connect(self.app.on_email_form_dirty)
        self.email_mailbox.textChanged.connect(self.app.on_email_form_dirty)
        self.email_categories.textChanged.connect(self.app.on_email_form_dirty)
        self.email_default_category.currentTextChanged.connect(self.app.on_email_form_dirty)
        self.email_make_default.toggled.connect(self.app.on_email_form_dirty)
        
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
        self.routing_member_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.routing_member_table.horizontalHeader().setStretchLastSection(True)
        self.routing_member_table.verticalHeader().setVisible(False)
        self.routing_member_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        detail_left.addWidget(self.routing_member_table)

        detail_right = QVBoxLayout()
        detail_right.addWidget(create_label("Recent Message History", 10, bold=True))
        self.routing_history_table = QTableWidget()
        self.routing_history_table.setColumnCount(4)
        self.routing_history_table.setHorizontalHeaderLabels(["Time", "Direction", "State", "Preview"])
        self.routing_history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.routing_history_table.horizontalHeader().setStretchLastSection(True)
        self.routing_history_table.verticalHeader().setVisible(False)
        self.routing_history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
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
        
        # Two columns in a splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        
        # Left: Allowed Directories
        allowed_widget = QWidget()
        allowed_layout = QVBoxLayout(allowed_widget)
        allowed_layout.setContentsMargins(0, 0, 0, 0)
        
        allowed_hdr = QHBoxLayout()
        allowed_hdr.addWidget(create_label("Allowed Directories", 10, bold=True))
        allowed_hdr.addStretch()
        add_dir_btn = create_button("+ Add Directory", self.app.add_allowed_directory, style="subtle")
        allowed_hdr.addWidget(add_dir_btn)
        allowed_layout.addLayout(allowed_hdr)
        
        self.allowed_list = QListWidget()
        self.allowed_list.setStyleSheet(
            "QListWidget { border: 1px solid #dde3ef; border-radius: 6px; background: white; }"
            "QListWidget::item { padding: 6px 10px; border-bottom: 1px solid #f0f2f5; font-family: Consolas; font-size: 9pt; }"
            "QListWidget::item:selected { background: #eaf2ff; color: #0a3069; }"
        )
        self.allowed_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.allowed_list.customContextMenuRequested.connect(self.app.on_allowed_dir_context_menu)
        allowed_layout.addWidget(self.allowed_list)
        allowed_layout.addWidget(create_label("Right-click a directory for options.", 8, color=_SLATE))
        splitter.addWidget(allowed_widget)
        
        # Right: Blocked Attempts
        blocked_widget = QWidget()
        blocked_layout = QVBoxLayout(blocked_widget)
        blocked_layout.setContentsMargins(0, 0, 0, 0)
        blocked_layout.addWidget(create_label("Blocked Attempts", 10, bold=True))
        self.blocked_table = QTableWidget()
        self.blocked_table.setColumnCount(3)
        self.blocked_table.setHorizontalHeaderLabels(["Timestamp", "Tool", "Path"])
        self.blocked_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.blocked_table.horizontalHeader().setStretchLastSection(True)
        self.blocked_table.verticalHeader().setVisible(False)
        self.blocked_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.blocked_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        blocked_layout.addWidget(self.blocked_table)
        self.blocked_empty_label = create_label("No blocked attempts recorded.", 9, color=_SLATE)
        self.blocked_empty_label.setAlignment(Qt.AlignCenter)
        blocked_layout.addWidget(self.blocked_empty_label)
        splitter.addWidget(blocked_widget)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)
        
        # Path validation area
        layout.addWidget(create_label("Path Validation", 10, bold=True))
        test_layout = QHBoxLayout()
        self.path_test_input = QLineEdit()
        self.path_test_input.setPlaceholderText("Enter a path to validate against file policy")
        test_layout.addWidget(self.path_test_input, 1)
        test_layout.addWidget(create_button("Test Path", lambda: self.app.open_validate_path_dialog(self.path_test_input.text().strip()), style="subtle"))
        layout.addLayout(test_layout)
        self.path_test_result = create_label("", 9, color=_SLATE)
        layout.addWidget(self.path_test_result)
        
        # Hidden input (kept for compatibility with add_allowed_directory logic)
        self.new_dir_input = QLineEdit()
        self.new_dir_input.setVisible(False)


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
        self.projects_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.projects_table.horizontalHeader().setStretchLastSection(True)
        self.projects_table.verticalHeader().setVisible(False)
        self.projects_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.projects_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
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
        
        # Main area: table + detail in vertical splitter
        v_splitter = QSplitter(Qt.Vertical)
        v_splitter.setChildrenCollapsible(False)
        
        self.activity_table = QTableWidget()
        self.activity_table.setColumnCount(8)
        self.activity_table.setHorizontalHeaderLabels(["Timestamp", "Event", "Assistant", "Action", "Tool", "State", "Target", "Source"])
        self.activity_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.activity_table.horizontalHeader().setStretchLastSection(True)
        self.activity_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.activity_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.activity_table.itemSelectionChanged.connect(self.app.on_activity_row_selected)
        v_splitter.addWidget(self.activity_table)

        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(0, 8, 0, 0)
        detail_layout.setSpacing(4)
        
        detail_header = QHBoxLayout()
        detail_header.addWidget(create_label("Selected Event Details", 10, bold=True))
        detail_header.addStretch()
        detail_header.addWidget(create_button("Copy Details", self.app.copy_activity_details, style="subtle"))
        detail_layout.addLayout(detail_header)

        self.activity_detail_tabs = QTabWidget()
        self.activity_meta = QPlainTextEdit()
        self.activity_meta.setReadOnly(True)
        self.activity_meta.setStyleSheet("background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 6px;")
        self.activity_summary = QPlainTextEdit()
        self.activity_summary.setReadOnly(True)
        self.activity_summary.setStyleSheet("background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 6px;")
        self.activity_raw = QPlainTextEdit()
        self.activity_raw.setReadOnly(True)
        self.activity_raw.setStyleSheet("background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 6px; font-family: Consolas;")
        self.activity_detail_tabs.addTab(self.activity_meta, "Metadata")
        self.activity_detail_tabs.addTab(self.activity_summary, "Result Summary")
        self.activity_detail_tabs.addTab(self.activity_raw, "Raw Output")
        detail_layout.addWidget(self.activity_detail_tabs)
        v_splitter.addWidget(detail_widget)
        
        v_splitter.setStretchFactor(0, 3)
        v_splitter.setStretchFactor(1, 2)
        layout.addWidget(v_splitter, 1)


class PersonalContextPage(QWidget):
    """Personal context editor page."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header_layout.addWidget(create_label("Personal Context", 12, bold=True))
        header_layout.addStretch()
        header_layout.addWidget(create_button("Refresh", self.app.refresh_personal_context, style="subtle"))
        self.save_button = create_button("Save", self.app.save_personal_context)
        self.save_button.setEnabled(False)
        header_layout.addWidget(self.save_button)
        layout.addLayout(header_layout)

        self.profile_name = QLineEdit()
        self.profile_name.setPlaceholderText("Name")
        self.profile_tone = QLineEdit()
        self.profile_tone.setPlaceholderText("Preferred tone (e.g., calm, direct)")
        self.profile_style = QLineEdit()
        self.profile_style.setPlaceholderText("Response style (e.g., concise, detailed)")
        self.profile_notes = QPlainTextEdit()
        self.profile_notes.setPlaceholderText("Additional profile notes")

        self.people_text = QPlainTextEdit()
        self.people_text.setPlaceholderText("People list (JSON array)")
        self.routines_text = QPlainTextEdit()
        self.routines_text.setPlaceholderText("Routines list (JSON array)")
        self.projects_text = QPlainTextEdit()
        self.projects_text.setPlaceholderText("Projects list (JSON array)")

        self.pref_response_length = QComboBox()
        self.pref_response_length.addItems(["short", "balanced", "detailed"])
        self.pref_notification_style = QComboBox()
        self.pref_notification_style.addItems(["minimal", "normal", "verbose"])
        self.pref_automation = QComboBox()
        self.pref_automation.addItems(["safe", "balanced", "aggressive"])
        self.pref_notes = QPlainTextEdit()
        self.pref_notes.setPlaceholderText("Preference notes")

        layout.addWidget(create_label("Profile", 10, bold=True))
        profile_grid = QGridLayout()
        profile_grid.addWidget(create_label("Name"), 0, 0)
        profile_grid.addWidget(self.profile_name, 0, 1)
        profile_grid.addWidget(create_label("Tone"), 1, 0)
        profile_grid.addWidget(self.profile_tone, 1, 1)
        profile_grid.addWidget(create_label("Response Style"), 2, 0)
        profile_grid.addWidget(self.profile_style, 2, 1)
        layout.addLayout(profile_grid)
        layout.addWidget(self.profile_notes)
        layout.addWidget(create_label("People", 10, bold=True))
        layout.addWidget(create_label("JSON array of important contacts and context clues.", 8, color=_SLATE))
        layout.addWidget(self.people_text)
        layout.addWidget(create_label("Example: [{\"name\": \"Sam\", \"relationship\": \"Manager\", \"notes\": \"Prefers concise updates\"}]", 8, color=_SLATE))
        layout.addWidget(create_label("Routines", 10, bold=True))
        layout.addWidget(create_label("JSON array of recurring habits or schedules.", 8, color=_SLATE))
        layout.addWidget(self.routines_text)
        layout.addWidget(create_label("Example: [{\"name\": \"Morning review\", \"time\": \"08:30\", \"days\": [\"Mon\", \"Tue\"]}]", 8, color=_SLATE))
        layout.addWidget(create_label("Projects", 10, bold=True))
        layout.addWidget(create_label("JSON array of active projects and constraints.", 8, color=_SLATE))
        layout.addWidget(self.projects_text)
        layout.addWidget(create_label("Example: [{\"name\": \"Website revamp\", \"status\": \"active\", \"owner\": \"Ops\"}]", 8, color=_SLATE))
        layout.addWidget(create_label("Preferences", 10, bold=True))
        pref_grid = QGridLayout()
        pref_grid.addWidget(create_label("Response Length"), 0, 0)
        pref_grid.addWidget(self.pref_response_length, 0, 1)
        pref_grid.addWidget(create_label("Notification Style"), 1, 0)
        pref_grid.addWidget(self.pref_notification_style, 1, 1)
        pref_grid.addWidget(create_label("Automation"), 2, 0)
        pref_grid.addWidget(self.pref_automation, 2, 1)
        layout.addLayout(pref_grid)
        layout.addWidget(self.pref_notes)
        self.status_label = create_label("", 9, color=_SLATE)
        self.last_saved_label = create_label("Last saved: never", 8, color=_SLATE)
        layout.addWidget(self.status_label)
        layout.addWidget(self.last_saved_label)

        self.profile_name.textChanged.connect(self.app.on_personal_context_dirty)
        self.profile_tone.textChanged.connect(self.app.on_personal_context_dirty)
        self.profile_style.textChanged.connect(self.app.on_personal_context_dirty)
        self.profile_notes.textChanged.connect(self.app.on_personal_context_dirty)
        self.people_text.textChanged.connect(self.app.on_personal_context_dirty)
        self.routines_text.textChanged.connect(self.app.on_personal_context_dirty)
        self.projects_text.textChanged.connect(self.app.on_personal_context_dirty)
        self.pref_notes.textChanged.connect(self.app.on_personal_context_dirty)
        self.pref_response_length.currentTextChanged.connect(self.app.on_personal_context_dirty)
        self.pref_notification_style.currentTextChanged.connect(self.app.on_personal_context_dirty)
        self.pref_automation.currentTextChanged.connect(self.app.on_personal_context_dirty)


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
        self.tools_table.setColumnCount(7)
        self.tools_table.setHorizontalHeaderLabels(["Tool", "Description", "Enabled", "Sources", "Approval Required", "Requires Unlocked", "Scope"])
        self.tools_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tools_table.horizontalHeader().setStretchLastSection(True)
        self.tools_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tools_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
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
        self.apply_button = create_button("Apply", self.app.save_selected_tool_permission, style="subtle")
        self.apply_button.setEnabled(False)
        controls.addWidget(self.apply_button)
        layout.addLayout(controls)

        self.tool_enabled.toggled.connect(self.app.on_tool_permission_form_dirty)
        self.tool_requires_approval.toggled.connect(self.app.on_tool_permission_form_dirty)
        self.tool_requires_unlock.toggled.connect(self.app.on_tool_permission_form_dirty)
        self.tool_sources.textChanged.connect(self.app.on_tool_permission_form_dirty)

        approvals_splitter = QSplitter(Qt.Horizontal)
        approvals_splitter.setChildrenCollapsible(False)
        
        self.approvals_table = QTableWidget()
        self.approvals_table.setColumnCount(5)
        self.approvals_table.setHorizontalHeaderLabels(["ID", "Tool", "Source", "Sender", "Status"])
        self.approvals_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.approvals_table.horizontalHeader().setStretchLastSection(True)
        self.approvals_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.approvals_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.approvals_table.itemSelectionChanged.connect(self.app.on_approval_selected)
        approvals_splitter.addWidget(self.approvals_table)

        right_widget = QWidget()
        right = QVBoxLayout(right_widget)
        right.setContentsMargins(6, 0, 0, 0)
        right.addWidget(create_button("✔ Approve", self.app.approve_selected_action))
        right.addWidget(create_button("▶ Run", self.app.run_selected_action, style="subtle"))
        right.addWidget(create_button("✖ Reject", self.app.reject_selected_action, style="subtle"))
        right.addSpacing(8)
        right.addWidget(create_label("Recent Tasks", 10, bold=True))
        self.tasks_table = QTableWidget()
        self.tasks_table.setColumnCount(4)
        self.tasks_table.setHorizontalHeaderLabels(["Task ID", "Title", "Status", "Updated"])
        self.tasks_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tasks_table.horizontalHeader().setStretchLastSection(True)
        self.tasks_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tasks_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        right.addWidget(self.tasks_table, 1)
        self.tasks_empty = create_label("No tasks pending.", 9, color=_SLATE)
        self.tasks_empty.setAlignment(Qt.AlignCenter)
        right.addWidget(self.tasks_empty)
        approvals_splitter.addWidget(right_widget)
        
        approvals_splitter.setStretchFactor(0, 2)
        approvals_splitter.setStretchFactor(1, 3)
        layout.addWidget(approvals_splitter, 1)
        self.result_text = QPlainTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("No tools selected yet.")
        layout.addWidget(self.result_text)


class UiThreadDispatcher(QObject):
    """Routes background worker results back onto the UI thread."""

    result_ready = Signal(object, object)
    error_ready = Signal(object)


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
        self._pre_lock_section: str | None = None
        
        self.activity: list[str] = []
        self.chat_history: list[tuple[str, str]] = []
        self.lock_sensitive_buttons: list = []
        self.last_response_text = ""
        self.last_trace_payload: dict = {}
        self.activity_rows: list[dict[str, Any]] = []
        self.project_rows: list[dict[str, Any]] = []
        self.tool_permission_rows: list[tuple[str, dict[str, Any]]] = []
        self.approval_rows: list[dict[str, Any]] = []
        self.response_templates: list[tuple[str, str]] = []
        self.last_activity_detail_text = ""
        self.selected_tool_name: str | None = None
        self.selected_approval_id: str | None = None
        self._command_frequency: dict[str, int] = {}
        self._suggested_commands: set[str] = set()
        self._pending_quick_command: str | None = None
        self._loading_personal_context = False
        self._loading_email_form = False
        self._loading_tool_form = False

        self._ui_dispatcher = UiThreadDispatcher()
        self._ui_dispatcher.result_ready.connect(self._display_result)
        self._ui_dispatcher.error_ready.connect(self._display_error)
        
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
        self.lock_screen.setStyleSheet(f"background-color: {_BG};")
        lock_layout = QVBoxLayout(self.lock_screen)
        lock_layout.setContentsMargins(0, 0, 0, 0)
        lock_layout.addStretch()
        card = QFrame()
        card.setMaximumWidth(440)
        card.setMinimumWidth(340)
        card.setStyleSheet(
            "background-color: white; border-radius: 16px; "
            "border: 1px solid #dde3ef;"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 32, 36, 32)
        card_layout.setSpacing(14)
        lock_icon = create_label("🔒", 32)
        lock_icon.setAlignment(Qt.AlignHCenter)
        title = create_label("Mashbak Control Board Locked", 16, bold=True)
        title.setAlignment(Qt.AlignHCenter)
        msg = create_label("Enter PIN to unlock", 10, color=_SLATE)
        msg.setAlignment(Qt.AlignHCenter)
        self.lock_backend_status = create_label("Backend: checking...", 9, color=_SLATE)
        self.lock_backend_status.setAlignment(Qt.AlignHCenter)
        self.lock_pin_input = QLineEdit()
        self.lock_pin_input.setEchoMode(QLineEdit.Password)
        self.lock_pin_input.setPlaceholderText("Enter PIN")
        self.lock_pin_input.setFont(QFont("Segoe UI", 13))
        self.lock_pin_input.setStyleSheet(
            "padding: 10px 14px; border: 1px solid #d1d5db; border-radius: 8px;"
            "background-color: #f9fafb;"
        )
        self.lock_pin_input.setAlignment(Qt.AlignHCenter)
        self.lock_pin_input.returnPressed.connect(self.unlock_app)
        unlock_btn = create_button("Unlock", self.unlock_app)
        unlock_btn.setFixedHeight(40)
        self.lock_status_hint = create_label("", 9, color=_RED)
        self.lock_status_hint.setAlignment(Qt.AlignHCenter)
        card_layout.addWidget(lock_icon)
        card_layout.addWidget(title)
        card_layout.addWidget(msg)
        card_layout.addWidget(self.lock_backend_status)
        card_layout.addSpacing(6)
        card_layout.addWidget(self.lock_pin_input)
        card_layout.addWidget(unlock_btn)
        card_layout.addWidget(self.lock_status_hint)
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
        subtitle = create_label("Private local operations console.", 9, color="#9bdbe4")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        layout.addLayout(title_layout)
        
        # Center: State indicator
        self.header_state_label = create_label("System starting", 9, color=_AMBER)
        layout.addWidget(self.header_state_label)
        
        # Right: Badges and lock button
        layout.addStretch()
        
        badges_layout = QHBoxLayout()
        badges_layout.setContentsMargins(0, 0, 0, 0)
        badges_layout.setSpacing(10)
        
        self.agent_badge = create_status_badge("Backend: Starting")
        self.bridge_badge = create_status_badge("Bridge: Checking")
        self.email_badge = create_status_badge("Email: Unknown")
        
        badges_layout.addWidget(self.agent_badge)
        badges_layout.addWidget(self.bridge_badge)
        badges_layout.addWidget(self.email_badge)
        badges_layout.addSpacing(14)
        
        self.lock_button = QPushButton("🔒  Lock")
        self.lock_button.setFont(QFont("Segoe UI", 9))
        self.lock_button.setEnabled(False)
        self.lock_button.clicked.connect(self.lock_app)
        self.lock_button.setStyleSheet(
            "QPushButton { background-color: #4b5563; color: white; border: none; "
            "padding: 7px 14px; border-radius: 5px; font-weight: bold; } "
            "QPushButton:hover { background-color: #374151; } "
            "QPushButton:disabled { background-color: #6b7280; color: #9ca3af; }"
        )
        badges_layout.addWidget(self.lock_button)
        layout.addLayout(badges_layout)
        layout.setStretch(0, 2)
        layout.setStretch(1, 1)
    
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
            ("🏠  Dashboard", "Dashboard"),
            ("💬  Chat and Console", "Chat / Console"),
            ("🧩  Assistants", "Assistants"),
            ("📨  Communications", "Communications"),
            ("📁  Files and Permissions", "Files & Permissions"),
            ("🗂  Projects and Files", "Projects / Files"),
            ("📊  Activity and Audit", "Activity / Audit"),
            ("👤  Personal Context", "Personal Context"),
            ("🛡  Tools and Permissions", "Tools & Permissions"),
        ]:
            btn = QPushButton(label)
            btn.setFont(QFont("Segoe UI", 10))
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, s=section: self._show_section(s))
            btn.setStyleSheet(
                f"QPushButton {{ background-color: transparent; color: #d9e1ec; border: none; "
                "padding: 10px 14px; text-align: left; }} "
                "QPushButton:hover { background-color: #6280b9; }"
            )
            layout.addWidget(btn)
            self.nav_buttons[section] = btn
            self.lock_sensitive_buttons.append(btn)
        
        layout.addSpacing(10)
        
        # Quick commands
        quick_label = create_label("QUICK COMMANDS", 11, bold=True, color="#e5e7eb")  
        layout.addWidget(quick_label)
        
        self.quick_commands: list[tuple[str, str]] = [
            ("System Info", "system info"),
            ("CPU Usage", "How busy is my computer right now?"),
            ("Recent Emails", "Do I have any new emails?"),
            ("Current Time", "what time is it"),
        ]
        self.quick_commands_list = QListWidget()
        self.quick_commands_list.setStyleSheet(
            "QListWidget { background: #4567ad; border: 1px solid #6f8ec6; border-radius: 8px; padding: 4px; }"
            "QListWidget::item { color: #eff6ff; padding: 8px 12px; border-radius: 5px; margin: 2px 0; }"
            "QListWidget::item:hover { background: #5f80be; }"
            "QListWidget::item:selected { background: #0f4fbf; color: white; }"
        )
        self.quick_commands_list.setFont(QFont("Segoe UI", 10))
        self.quick_commands_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.quick_commands_list.customContextMenuRequested.connect(self._on_quick_cmd_context_menu)
        self.quick_commands_list.itemClicked.connect(self._on_quick_cmd_clicked)
        self.quick_commands_list.itemDoubleClicked.connect(self._on_quick_cmd_double_clicked)
        self._rebuild_quick_commands_list()
        layout.addWidget(self.quick_commands_list)
        self.lock_sensitive_buttons.extend([])  # list widget items enabled/disabled via list widget
        
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
                    "QPushButton:hover { background-color: #6280b9; }"
                )
    
    def _rebuild_quick_commands_list(self):
        """Rebuild the quick commands list widget from self.quick_commands."""
        self.quick_commands_list.clear()
        for label, _msg in self.quick_commands:
            self.quick_commands_list.addItem(label)
    
    def _run_quick_command_item(self, item):
        if not self.is_unlocked or not item:
            return
        idx = self.quick_commands_list.row(item)
        if 0 <= idx < len(self.quick_commands):
            _label, msg = self.quick_commands[idx]
            self._send_quick_command(msg)

    def _on_quick_cmd_clicked(self, item):
        """Run a quick command on single-click."""
        self._run_quick_command_item(item)

    def _on_quick_cmd_double_clicked(self, item):
        """Run a quick command on double-click."""
        self._run_quick_command_item(item)
    
    def _on_quick_cmd_context_menu(self, pos: QPoint):
        """Show context menu for quick commands."""
        item = self.quick_commands_list.itemAt(pos)
        idx = self.quick_commands_list.row(item) if item else -1
        
        menu = QMenu(self.quick_commands_list)
        menu.setStyleSheet(
            "QMenu { background: white; border: 1px solid #dde3ef; }"
            "QMenu::item { padding: 6px 20px; } "
            "QMenu::item:selected { background: #eaf2ff; color: #0a3069; }"
        )
        
        if item and 0 <= idx < len(self.quick_commands):
            run_action = QAction("▶  Run", menu)
            run_action.triggered.connect(lambda: self._send_quick_command(self.quick_commands[idx][1]))
            menu.addAction(run_action)
            menu.addSeparator()
            
            rename_action = QAction("✏  Rename", menu)
            rename_action.triggered.connect(lambda: self._rename_quick_command(idx))
            menu.addAction(rename_action)
            
            edit_action = QAction("🔧  Edit Command", menu)
            edit_action.triggered.connect(lambda: self._edit_quick_command(idx))
            menu.addAction(edit_action)
            
            delete_action = QAction("✖  Delete", menu)
            delete_action.triggered.connect(lambda: self._delete_quick_command(idx))
            menu.addAction(delete_action)
            menu.addSeparator()
        
        new_action = QAction("＋  New Quick Command", menu)
        new_action.triggered.connect(self._new_quick_command)
        menu.addAction(new_action)
        
        menu.exec(self.quick_commands_list.mapToGlobal(pos))
    
    def _rename_quick_command(self, idx: int):
        label, msg = self.quick_commands[idx]
        result = self._open_quick_command_dialog(
            title="Rename Quick Command",
            initial_label=label,
            initial_message=msg,
            lock_message=True,
        )
        if result is None:
            return
        self.quick_commands[idx] = (result[0], msg)
        self._rebuild_quick_commands_list()
    
    def _edit_quick_command(self, idx: int):
        label, msg = self.quick_commands[idx]
        result = self._open_quick_command_dialog(
            title="Edit Quick Command",
            initial_label=label,
            initial_message=msg,
            lock_label=True,
        )
        if result is None:
            return
        self.quick_commands[idx] = result
    
    def _delete_quick_command(self, idx: int):
        label = self.quick_commands[idx][0]
        confirm = QMessageBox.question(
            self.window, "Delete Quick Command",
            f"Delete \"{label}\"?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.quick_commands.pop(idx)
            self._rebuild_quick_commands_list()
    
    def _new_quick_command(self):
        result = self._open_quick_command_dialog(
            title="New Quick Command",
            initial_label="",
            initial_message="",
        )
        if result is None:
            return
        self.quick_commands.append(result)
        self._rebuild_quick_commands_list()

    def _open_quick_command_dialog(
        self,
        *,
        title: str,
        initial_label: str,
        initial_message: str,
        lock_label: bool = False,
        lock_message: bool = False,
    ) -> tuple[str, str] | None:
        dialog = QDialog(self.window)
        dialog.setWindowTitle(title)
        dialog.setModal(True)
        dialog.setMinimumWidth(520)
        layout = QVBoxLayout(dialog)
        form = QGridLayout()
        form.addWidget(create_label("Label", 9, bold=True), 0, 0)
        label_input = QLineEdit(initial_label)
        label_input.setReadOnly(lock_label)
        form.addWidget(label_input, 0, 1)
        form.addWidget(create_label("Command", 9, bold=True), 1, 0)
        message_input = QLineEdit(initial_message)
        message_input.setReadOnly(lock_message)
        form.addWidget(message_input, 1, 1)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        save_btn = buttons.button(QDialogButtonBox.Save)
        save_btn.setEnabled(False)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        initial_l = initial_label.strip()
        initial_m = initial_message.strip()

        def _refresh_save_state():
            current_l = label_input.text().strip()
            current_m = message_input.text().strip()
            changed = (current_l != initial_l) or (current_m != initial_m)
            valid = bool(current_l and current_m)
            save_btn.setEnabled(changed and valid)

        label_input.textChanged.connect(_refresh_save_state)
        message_input.textChanged.connect(_refresh_save_state)
        _refresh_save_state()

        if dialog.exec() != QDialog.Accepted:
            return None
        return (label_input.text().strip(), message_input.text().strip())

    def on_accept_quick_suggestion(self):
        if not self._pending_quick_command:
            return
        command = self._pending_quick_command.strip()
        label = command[:28].title() or "Quick Command"
        if not any(cmd.strip().lower() == command.lower() for _, cmd in self.quick_commands):
            self.quick_commands.append((label, command))
            self._rebuild_quick_commands_list()
        page = self.pages.get("Chat / Console")
        if page:
            page.hide_quick_suggestion()
            page.append_message("system", f'Quick command created for "{command}".')
        self._pending_quick_command = None

    def on_dismiss_quick_suggestion(self):
        page = self.pages.get("Chat / Console")
        if page:
            page.hide_quick_suggestion()
        self._pending_quick_command = None

    def on_personal_context_dirty(self):
        page = self.pages.get("Personal Context")
        if not page or self._loading_personal_context:
            return
        page.save_button.setEnabled(True)

    def on_email_form_dirty(self):
        page = self.pages.get("Communications")
        if not page or self._loading_email_form:
            return
        page.save_account_btn.setEnabled(True)

    def on_tool_permission_form_dirty(self):
        page = self.pages.get("Tools & Permissions")
        if not page or self._loading_tool_form or not self.selected_tool_name:
            return
        page.apply_button.setEnabled(True)
    
    def suggest_quick_command(self, command_text: str):
        """Show suggestion to create a quick command for a repeated command."""
        chat_page = self.pages.get("Chat / Console")
        if not chat_page:
            return
        self._pending_quick_command = str(command_text or "").strip()
        chat_page.show_quick_suggestion(self._pending_quick_command)

    def on_allowed_dir_context_menu(self, pos: QPoint):
        """Context menu for allowed directories list."""
        page = self.pages.get("Files & Permissions")
        if not page:
            return
        item = page.allowed_list.itemAt(pos)
        menu = QMenu(page.allowed_list)
        menu.setStyleSheet(
            "QMenu { background: white; border: 1px solid #dde3ef; }"
            "QMenu::item { padding: 6px 20px; }"
            "QMenu::item:selected { background: #eaf2ff; color: #0a3069; }"
        )
        if item:
            remove_action = QAction("✖  Remove Directory", menu)
            remove_action.triggered.connect(self.remove_selected_directory)
            menu.addAction(remove_action)
            
            validate_action = QAction("🔍  Validate Path", menu)
            validate_action.triggered.connect(lambda: self._validate_dir_from_list(item.text()))
            menu.addAction(validate_action)
            
            copy_action = QAction("📋  Copy Path", menu)
            copy_action.triggered.connect(lambda: QApplication.instance().clipboard().setText(item.text()))
            menu.addAction(copy_action)
            menu.addSeparator()
        
        add_action = QAction("＋  Add Directory", menu)
        add_action.triggered.connect(self.add_allowed_directory)
        menu.addAction(add_action)
        
        menu.exec(page.allowed_list.mapToGlobal(pos))
    
    def _validate_dir_from_list(self, path: str):
        """Validate a path from the allowed list."""
        self.open_validate_path_dialog(path)

    def open_validate_path_dialog(self, initial_path: str = ""):
        page = self.pages.get("Files & Permissions")
        if not page:
            return
        dialog = QDialog(self.window)
        dialog.setWindowTitle("Validate Path")
        dialog.setModal(True)
        dialog.setMinimumWidth(560)
        outer = QVBoxLayout(dialog)
        outer.addWidget(create_label("Enter path to test", 10, bold=True))
        input_line = QLineEdit(str(initial_path or ""))
        outer.addWidget(input_line)
        result_label = create_label("", 9, color=_SLATE)

        def _run_test():
            value = input_line.text().strip()
            if not value:
                result_label.setText("Enter a path first.")
                result_label.setStyleSheet(f"color: {_RED};")
                return
            payload = self.client.test_policy_path(value)
            allowed = bool(payload.get("allowed"))
            normalized = str(payload.get("normalized_path") or "-")
            reason = str(payload.get("reason") or "")
            result_label.setText(("Allowed" if allowed else "Blocked") + f" | {normalized} | {reason}")
            result_label.setStyleSheet(f"color: {_GREEN if allowed else _RED};")
            page.path_test_result.setText(result_label.text())
            page.path_test_result.setStyleSheet(result_label.styleSheet())

        buttons = QHBoxLayout()
        test_btn = create_button("Test", _run_test, style="subtle")
        close_btn = create_button("Close", dialog.accept, style="subtle")
        buttons.addWidget(test_btn)
        buttons.addWidget(close_btn)
        buttons.addStretch()
        outer.addLayout(buttons)
        outer.addWidget(result_label)
        dialog.exec()
    
    def show(self):
        """Show the main window."""
        self.window.show()
        self.refresh_status()
    
    # --- LOCK CONTROL ---
    
    def unlock_app(self):
        """Unlock the application."""
        candidate = self.lock_pin_input.text().strip()
        self.lock_pin_input.clear()
        
        if candidate != self.local_app_pin:
            self.lock_status_hint.setText("Incorrect PIN. Try again.")
            self._animate_lock_failure()
            QTimer.singleShot(2000, lambda: self.lock_status_hint.setText(""))
            return
        
        self.is_unlocked = True
        self.lock_button.setEnabled(True)
        self.lock_button.setText("🔓  Lock")
        self.lock_status_hint.setText("")
        self.root_stack.setCurrentWidget(self.app_shell)
        self.statusbar.showMessage("Mashbak Control Board  |  unlocked")
        
        # Restore previous page if any
        if self._pre_lock_section and self._pre_lock_section in self.pages:
            self._show_section(self._pre_lock_section)
        else:
            self._show_section("Dashboard")
        self._pre_lock_section = None
        
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

        # Focus chat input for immediate operator commands
        chat_page = self.pages.get("Chat / Console")
        if chat_page:
            chat_page.message_input.setFocus()
    
    def lock_app(self):
        """Lock the application."""
        self._pre_lock_section = self.current_section
        self._lock_ui("Control board locked. Enter PIN to unlock.")
    
    def _lock_ui(self, message: str):
        """Lock the UI and show lock screen."""
        self.is_unlocked = False
        self.root_stack.setCurrentWidget(self.lock_screen)
        self.lock_button.setEnabled(False)
        self.lock_button.setText("🔐  Lock")
        self.statusbar.showMessage("Mashbak Control Board  |  locked")
        
        # Disable controls
        self._set_interaction_enabled(False)

        self.lock_pin_input.setFocus()
    
    def _set_interaction_enabled(self, enabled: bool):
        """Enable/disable interactive controls."""
        for btn in self.lock_sensitive_buttons:
            btn.setEnabled(enabled)

    def _animate_lock_failure(self):
        """Flash lock PIN border briefly to signal a failed unlock attempt."""
        self.lock_pin_input.setStyleSheet("border: 2px solid #b42318; border-radius: 4px; padding: 6px;")
        QTimer.singleShot(260, lambda: self.lock_pin_input.setStyleSheet(""))
    
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
        
        # Track command frequency and suggest quick commands for repeated ones
        canonical = message.strip().lower()
        self._command_frequency[canonical] = self._command_frequency.get(canonical, 0) + 1
        if self._command_frequency[canonical] == 3 and canonical not in self._suggested_commands:
            self._suggested_commands.add(canonical)
            QTimer.singleShot(200, lambda: self.suggest_quick_command(message))
        
        thread = threading.Thread(target=self._run_message, args=(message,), daemon=True)
        thread.start()
    
    def _run_message(self, message: str):
        """Run message in background thread."""
        try:
            result = self.client.execute_nl(message=message, sender="local-desktop", owner_unlocked=self.is_unlocked)
            self._ui_dispatcher.result_ready.emit(message, result)
        except Exception as exc:
            self._ui_dispatcher.error_ready.emit(str(exc))
    
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

        detail_lines.append("")
        detail_lines.append("Structured Result")
        detail_lines.append(self._format_action_result_summary(result))
        
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
            chat_page.append_message("system", f'Running quick command: "{message}"')
            chat_page.chat_state_label.setText("Executing quick command")
            chat_page.details_text.setPlainText("Quick command dispatched. Waiting for Mashbak reply...")
            chat_page.trace_tabs.setCurrentIndex(0)
            chat_page.message_input.setText(message)
            chat_page.message_input.setFocus()
            self.on_send()

    # --- DATA REFRESH METHODS ---

    def refresh_dashboard_clicked(self):
        """Trigger dashboard refresh with visible in-progress feedback."""
        dashboard = self.pages.get("Dashboard")
        if not dashboard:
            return
        dashboard.set_refreshing(True)
        self.statusbar.showMessage("Mashbak Control Board  |  refreshing dashboard")

        def _run_refresh():
            self.refresh_status()
            dashboard.set_refreshing(False)
            dashboard.mark_refreshed()
            if self.is_unlocked:
                self.statusbar.showMessage("Mashbak Control Board  |  unlocked")

        QTimer.singleShot(350, _run_refresh)
    
    def refresh_status(self):
        """Refresh system status badges."""
        agent_status = self._check_agent_health()
        bridge_status = self._check_http_health("http://127.0.0.1:34567/health")
        summary = self.runtime_summary
        self.lock_backend_status.setText("Backend: connected" if agent_status["running"] else "Backend: unavailable")
        self.lock_backend_status.setStyleSheet(f"color: {_GREEN if agent_status['running'] else _RED};")
        
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
        bridge_detail = bridge.get("detail") if isinstance(bridge.get("detail"), dict) else {}
        bridge_port = bridge_detail.get("port") or "34567"
        default_email_label = "none"
        accounts_payload = self.client.get_email_accounts()
        if isinstance(accounts_payload, dict) and accounts_payload.get("success") is not False:
            default_id = accounts_payload.get("default_account_id")
            for account in accounts_payload.get("accounts") or []:
                if account.get("account_id") == default_id:
                    default_email_label = str(account.get("label") or account.get("email_address") or "default")
                    break
        
        cards_data = {
            "backend": (
                "connected" if backend.get("connected") else "error",
                f"Model: {backend.get('model') or 'unknown'} | Connected: {'yes' if backend.get('connected') else 'no'}",
            ),
            "bridge": (
                "connected" if bridge.get("connected") else "error",
                f"Status: {'connected' if bridge.get('connected') else 'disconnected'} | Port: {bridge_port}",
            ),
            "email": (
                "configured" if email.get("configured") else "warning",
                f"Configured accounts: {int(email.get('accounts') or 0)} | Default account: {default_email_label}",
            ),
            "assistant": ("active", f"Active assistant: {(overview.get('active_assistant') or 'mashbak').title()}"),
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
        dashboard.mark_refreshed()
    
    def _condense_detail(self, text: str, max_len: int = 84) -> str:
        """Condense detail text with ellipsis."""
        cleaned = " ".join(str(text or "").split())
        if len(cleaned) <= max_len:
            return cleaned or "-"
        return cleaned[: max_len - 3].rstrip() + "..."

    def _format_action_result_summary(self, result: dict) -> str:
        """Create a clean result summary for operator display."""
        tool = str(result.get("tool_name") or "conversation")
        success = bool(result.get("success"))
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        lines = [f"Result: {'Success' if success else 'Failed'}", f"Tool: {tool}"]
        if result.get("request_id"):
            lines.append(f"Request ID: {result.get('request_id')}")

        task = data.get("task") if isinstance(data.get("task"), dict) else None
        if task:
            lines.append(f"Task: {task.get('task_id')} ({task.get('status')})")

        approval = data.get("approval") if isinstance(data.get("approval"), dict) else None
        if approval:
            lines.extend([
                "",
                "Approval Required",
                f"Approval ID: {approval.get('approval_id')}",
                f"Reason: {approval.get('reason')}",
            ])

        if tool == "capture_screenshot":
            lines.append(f"Screenshot Path: {data.get('path') or '-'}")
        elif tool in {"send_email", "draft_email_reply"}:
            lines.append(f"Email Target: {data.get('to') or '-'}")
            if data.get("subject"):
                lines.append(f"Subject: {data.get('subject')}")
            if data.get("path"):
                lines.append(f"Draft Path: {data.get('path')}")
        elif tool in {"create_file", "create_folder", "edit_file", "copy_file", "move_file", "delete_file", "generate_homepage"}:
            for key in ("created_path", "deleted_path", "path", "destination", "entry_file", "project_path"):
                if data.get(key):
                    lines.append(f"{key.replace('_', ' ').title()}: {data.get(key)}")
            if data.get("created_files"):
                lines.append("Created Files:")
                for item in (data.get("created_files") or [])[:6]:
                    lines.append(f"- {item}")
        elif tool == "web_search":
            query = data.get("query") or "-"
            lines.append(f"Search Query: {query}")
            results = data.get("results") if isinstance(data.get("results"), list) else []
            lines.append(f"Result Count: {len(results)}")
            for item in results[:3]:
                title = str((item or {}).get("title") or "Result")
                lines.append(f"- {self._condense_detail(title, 90)}")
        elif tool == "generate_homepage":
            if data.get("entry_file"):
                lines.append(f"Homepage Entry: {data.get('entry_file')}")
            if data.get("project_path"):
                lines.append(f"Project Path: {data.get('project_path')}")

        if result.get("error"):
            lines.append(f"Error: {result.get('error')}")
        return "\n".join(lines)

    def _format_row_detail(self, row: dict[str, Any], keys: list[str]) -> str:
        lines = []
        for key in keys:
            value = row.get(key)
            if value is None or value == "":
                continue
            lines.append(f"{key.replace('_', ' ').title()}: {value}")
        return "\n".join(lines) if lines else "No details available."

    def _set_combo_value(self, combo: QComboBox, value: Any):
        text = str(value or "").strip()
        if not text:
            combo.setCurrentIndex(0)
            return
        idx = combo.findText(text)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        combo.addItem(text)
        combo.setCurrentIndex(combo.count() - 1)
    
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
        total_members = int(counts.get("approved", 0)) + int(counts.get("pending", 0)) + int(counts.get("blocked", 0))
        page.bucherim_empty_label.setText("No members recorded yet." if total_members == 0 else "")

        responses = bucherim.get("responses") or {}
        self.response_templates = list(sorted((str(key), str(value)) for key, value in responses.items()))
        page.responses_table.setRowCount(0)
        for idx, (key, value) in enumerate(self.response_templates):
            page.responses_table.insertRow(idx)
            page.responses_table.setItem(idx, 0, QTableWidgetItem(str(key)))
            page.responses_table.setItem(idx, 1, QTableWidgetItem(self._condense_detail(str(value), 220)))
        if self.response_templates:
            page.responses_table.selectRow(0)
            self.on_template_row_selected()
        else:
            page.responses_detail.setPlainText("No response templates configured.")

    def on_template_row_selected(self):
        page = self.pages.get("Assistants")
        if not page:
            return
        row = page.responses_table.currentRow()
        if row < 0 or row >= len(self.response_templates):
            page.responses_detail.setPlainText("No template selected")
            return
        key, value = self.response_templates[row]
        page.responses_detail.setPlainText(f"Template: {key}\n\n{value}")

    def on_template_context_menu(self, pos: QPoint):
        page = self.pages.get("Assistants")
        if not page:
            return
        item = page.responses_table.itemAt(pos)
        if item is None:
            return
        row = page.responses_table.row(item)
        if row < 0 or row >= len(self.response_templates):
            return

        menu = QMenu(page.responses_table)
        menu.setStyleSheet(
            "QMenu { background: white; border: 1px solid #dde3ef; }"
            "QMenu::item { padding: 6px 20px; } "
            "QMenu::item:selected { background: #eaf2ff; color: #0a3069; }"
        )
        edit_action = QAction("Edit Template", menu)
        edit_action.triggered.connect(lambda: self.edit_assistant_template(row))
        menu.addAction(edit_action)
        menu.exec(page.responses_table.viewport().mapToGlobal(pos))

    def edit_assistant_template(self, row: int):
        page = self.pages.get("Assistants")
        if not page:
            return
        if row < 0 or row >= len(self.response_templates):
            return
        key, current_text = self.response_templates[row]

        dialog = QDialog(self.window)
        dialog.setWindowTitle("Edit Response Template")
        dialog.setModal(True)
        dialog.setMinimumWidth(680)
        layout = QVBoxLayout(dialog)
        layout.addWidget(create_label(f"Template: {key}", 10, bold=True))

        editor = QPlainTextEdit()
        editor.setPlainText(current_text)
        editor.setStyleSheet("background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 6px;")
        layout.addWidget(editor)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        save_btn = buttons.button(QDialogButtonBox.Save)
        save_btn.setEnabled(False)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        def _on_changed():
            save_btn.setEnabled(editor.toPlainText().strip() != current_text.strip())

        editor.textChanged.connect(_on_changed)

        if dialog.exec() != QDialog.Accepted:
            return

        updated_text = editor.toPlainText().strip()
        result = self.client.update_assistant_template(key, updated_text)
        if isinstance(result, dict) and result.get("success") is not False:
            page.responses_detail.setPlainText(f"Template: {key}\n\n{updated_text}")
            self.refresh_assistants()
            return
        page.responses_detail.setPlainText(str((result or {}).get("error") or "Failed to update template."))
    
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
            suffix = "  [DEFAULT]" if account.get("account_id") == default_id else ""
            item = QListWidgetItem(label + suffix)
            item.setData(Qt.UserRole, account)
            page.email_accounts_widget.addItem(item)

        if accounts:
            page.email_accounts_widget.setCurrentRow(0)
            page.email_accounts_empty.setText("")
            page.email_result.setPlainText(f"Configured {len(accounts)} account(s). Select one to edit or test.")
            page.email_status.setText(f"Email status: {len(accounts)} account(s) configured")
            page.email_status.setStyleSheet(f"color: {_GREEN};")
        else:
            self.new_email_account()
            page.email_accounts_empty.setText("No configured email accounts.")
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
        page.routing_result.setPlainText("Routing lists updated.")
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
            page.routing_result.setPlainText(str(payload.get("error") or "Unable to load selected number details."))
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
        blocked = payload.get("blocked_attempts") or []
        for idx, row in enumerate(blocked):
            page.blocked_table.insertRow(idx)
            page.blocked_table.setItem(idx, 0, QTableWidgetItem(str(row.get("timestamp") or "")))
            page.blocked_table.setItem(idx, 1, QTableWidgetItem(str(row.get("tool") or "")))
            page.blocked_table.setItem(idx, 2, QTableWidgetItem(str(row.get("path") or "-")))
        page.blocked_empty_label.setVisible(not bool(blocked))
    
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
        page.projects_detail.setPlainText(
            self._format_row_detail(
                selected,
                ["timestamp", "requested_action", "selected_tool", "state", "target", "source", "details", "request_id"],
            )
        )
    
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
            page.activity_meta.setPlainText("No recent assistant activity.")
            page.activity_summary.setPlainText("No activity yet")
            page.activity_raw.setPlainText("{}")
            self.last_activity_detail_text = "No recent assistant activity."
        else:
            page.activity_table.selectRow(0)

        for idx, row in enumerate(self.activity_rows):
            state_value = str(row.get("state") or "").lower()
            tint = None
            dot = ""
            if state_value in {"success", "completed"}:
                tint = QColor("#eaf7ee")
                dot = "● "
            elif state_value in {"failure", "error"}:
                tint = QColor("#fff1f0")
                dot = "● "
            elif state_value == "blocked":
                tint = QColor("#fff7ed")
                dot = "● "
            elif state_value in {"pending", "received"}:
                tint = QColor("#fefce8")
                dot = "● "
            
            # Color the state cell text for quick scanning
            state_item = page.activity_table.item(idx, 5)
            if state_item and dot:
                state_item.setText(dot + state_item.text())
                fg_map = {
                    "success": _GREEN, "completed": _GREEN,
                    "failure": _RED, "error": _RED,
                    "blocked": _AMBER,
                    "pending": _YELLOW, "received": _SLATE,
                }
                fg = fg_map.get(state_value, _SLATE)
                state_item.setForeground(QColor(fg))
            
            if tint is None:
                continue
            for col in range(page.activity_table.columnCount()):
                item = page.activity_table.item(idx, col)
                if item is not None:
                    item.setBackground(tint)

    def on_activity_row_selected(self):
        """Show selected activity event details."""
        page = self.pages.get("Activity / Audit")
        if not page:
            return
        row = page.activity_table.currentRow()
        if row < 0 or row >= len(self.activity_rows):
            return
        selected = self.activity_rows[row]
        # Build structured event information block
        lines = ["Event Information", "-" * 40]
        for field, label in [
            ("timestamp", "Timestamp"),
            ("event_type", "Event"),
            ("assistant", "Assistant"),
            ("requested_action", "Action"),
            ("selected_tool", "Tool"),
            ("state", "State"),
            ("target", "Target"),
            ("source", "Source"),
            ("request_id", "Request ID"),
        ]:
            v = selected.get(field)
            if v:
                lines.append(f"{label}: {v}")
        metadata = "\n".join(lines)
        summary = self._condense_detail(str(selected.get("details") or "No details available."), 320)
        raw_block = selected.get("raw_event") if isinstance(selected.get("raw_event"), dict) else selected
        page.activity_meta.setPlainText(metadata)
        page.activity_summary.setPlainText(f"Result Summary: {summary}")
        page.activity_raw.setPlainText(json.dumps(raw_block, indent=2, ensure_ascii=True))
        self.last_activity_detail_text = f"Metadata\n{metadata}\n\nResult Summary\n{summary}\n\nRaw Output\n{json.dumps(raw_block, indent=2, ensure_ascii=True)}"

    def copy_activity_details(self):
        if not self.last_activity_detail_text:
            return
        app = QApplication.instance()
        if app:
            app.clipboard().setText(self.last_activity_detail_text)

    def refresh_personal_context(self):
        """Load personal context data from backend."""
        if not self.is_unlocked:
            return
        page = self.pages.get("Personal Context")
        if not page:
            return
        self._loading_personal_context = True
        payload = self.client.get_personal_context()
        if not isinstance(payload, dict):
            self._loading_personal_context = False
            return
        if payload.get("success") is False:
            page.status_label.setText(str(payload.get("error") or "Unable to load personal context."))
            page.status_label.setStyleSheet(f"color: {_RED};")
            self._loading_personal_context = False
            return
        profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
        prefs = payload.get("preferences") if isinstance(payload.get("preferences"), dict) else {}
        page.profile_name.setText(str(profile.get("name") or ""))
        page.profile_tone.setText(str(profile.get("preferred_tone") or ""))
        page.profile_style.setText(str(profile.get("response_style") or ""))
        page.profile_notes.setPlainText(str(profile.get("notes") or ""))
        page.people_text.setPlainText(json.dumps(payload.get("people") or [], indent=2, ensure_ascii=True))
        page.routines_text.setPlainText(json.dumps(payload.get("routines") or [], indent=2, ensure_ascii=True))
        page.projects_text.setPlainText(json.dumps(payload.get("projects") or [], indent=2, ensure_ascii=True))
        self._set_combo_value(page.pref_response_length, prefs.get("response_length") or "balanced")
        self._set_combo_value(page.pref_notification_style, prefs.get("notification_style") or "normal")
        self._set_combo_value(page.pref_automation, prefs.get("automation_aggressiveness") or "safe")
        page.pref_notes.setPlainText(str(prefs.get("notes") or ""))
        page.status_label.setText("Loaded personal context.")
        page.status_label.setStyleSheet(f"color: {_GREEN};")
        page.save_button.setEnabled(False)
        self._loading_personal_context = False

    def _refresh_personal_context_silent(self):
        """Refresh personal context without overwriting status message."""
        page = self.pages.get("Personal Context")
        if not page or not self.is_unlocked:
            return
        self._loading_personal_context = True
        payload = self.client.get_personal_context()
        if not isinstance(payload, dict) or payload.get("success") is False:
            self._loading_personal_context = False
            return
        profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
        prefs = payload.get("preferences") if isinstance(payload.get("preferences"), dict) else {}
        page.profile_name.setText(str(profile.get("name") or ""))
        page.profile_tone.setText(str(profile.get("preferred_tone") or ""))
        page.profile_style.setText(str(profile.get("response_style") or ""))
        page.profile_notes.setPlainText(str(profile.get("notes") or ""))
        page.people_text.setPlainText(json.dumps(payload.get("people") or [], indent=2, ensure_ascii=True))
        page.routines_text.setPlainText(json.dumps(payload.get("routines") or [], indent=2, ensure_ascii=True))
        page.projects_text.setPlainText(json.dumps(payload.get("projects") or [], indent=2, ensure_ascii=True))
        self._set_combo_value(page.pref_response_length, prefs.get("response_length") or "balanced")
        self._set_combo_value(page.pref_notification_style, prefs.get("notification_style") or "normal")
        self._set_combo_value(page.pref_automation, prefs.get("automation_aggressiveness") or "safe")
        page.pref_notes.setPlainText(str(prefs.get("notes") or ""))
        page.save_button.setEnabled(False)
        self._loading_personal_context = False

    def save_personal_context(self):
        """Save personal context from editor widgets."""
        page = self.pages.get("Personal Context")
        if not page:
            return
        try:
            payload = {
                "profile": {
                    "name": page.profile_name.text().strip(),
                    "preferred_tone": page.profile_tone.text().strip(),
                    "response_style": page.profile_style.text().strip(),
                    "notes": page.profile_notes.toPlainText().strip(),
                },
                "people": json.loads(page.people_text.toPlainText() or "[]"),
                "routines": json.loads(page.routines_text.toPlainText() or "[]"),
                "projects": json.loads(page.projects_text.toPlainText() or "[]"),
                "preferences": {
                    "response_length": page.pref_response_length.currentText().strip(),
                    "notification_style": page.pref_notification_style.currentText().strip(),
                    "automation_aggressiveness": page.pref_automation.currentText().strip(),
                    "notes": page.pref_notes.toPlainText().strip(),
                },
            }
            if not isinstance(payload["people"], list):
                raise ValueError("People must be a JSON array.")
            if not isinstance(payload["routines"], list):
                raise ValueError("Routines must be a JSON array.")
            if not isinstance(payload["projects"], list):
                raise ValueError("Projects must be a JSON array.")
        except json.JSONDecodeError as exc:
            page.status_label.setText(f"Invalid JSON: {exc}")
            page.status_label.setStyleSheet(f"color: {_RED};")
            return
        except ValueError as exc:
            page.status_label.setText(str(exc))
            page.status_label.setStyleSheet(f"color: {_RED};")
            return
        result = self.client.save_personal_context(payload)
        if isinstance(result, dict) and result.get("success") is not False:
            saved_at = result.get("saved_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            page.status_label.setText("Personal context saved.")
            page.status_label.setStyleSheet(f"color: {_GREEN};")
            page.last_saved_label.setText(f"Last saved: {saved_at}")
            page.save_button.setEnabled(False)
            # Refresh after a short delay so the success message stays visible
            QTimer.singleShot(1800, self._refresh_personal_context_silent)
            return
        page.status_label.setText(str((result or {}).get("error") or "Save failed"))
        page.status_label.setStyleSheet(f"color: {_RED};")

    def refresh_tools_permissions(self):
        """Refresh tools permissions, pending approvals, and recent tasks."""
        if not self.is_unlocked:
            return
        page = self.pages.get("Tools & Permissions")
        if not page:
            return

        payload = self.client.get_tools_permissions()
        if isinstance(payload, dict) and payload.get("success") is False:
            page.result_text.setPlainText(str(payload.get("error") or "Unable to load tool permissions."))
            return
        tools = (payload or {}).get("tools") or {}
        self.tool_permission_rows = list(sorted(tools.items(), key=lambda item: item[0]))
        page.tools_table.setRowCount(0)
        for idx, (name, cfg) in enumerate(self.tool_permission_rows):
            page.tools_table.insertRow(idx)
            values = [
                name,
                str(cfg.get("description") or ""),
                str(bool(cfg.get("enabled", True))),
                ",".join(cfg.get("allowed_sources") or []),
                str(bool(cfg.get("requires_approval", False))),
                str(bool(cfg.get("requires_unlocked_desktop", False))),
                str(cfg.get("scope") or "default"),
            ]
            for col, value in enumerate(values):
                page.tools_table.setItem(idx, col, QTableWidgetItem(value))
        if self.tool_permission_rows:
            page.tools_table.selectRow(0)

        approvals = self.client.get_approvals(limit=80, status="pending")
        if isinstance(approvals, dict) and approvals.get("success") is False:
            page.result_text.setPlainText(str(approvals.get("error") or "Unable to load pending approvals."))
            return
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
        if self.approval_rows:
            page.approvals_table.selectRow(0)

        tasks = self.client.get_tasks(limit=80)
        if isinstance(tasks, dict) and tasks.get("success") is False:
            page.result_text.setPlainText(str(tasks.get("error") or "Unable to load tasks."))
            return
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
        page.tasks_empty.setVisible(not bool(task_rows))
        page.result_text.setPlainText(
            f"Loaded {len(self.tool_permission_rows)} tools, {len(self.approval_rows)} pending approvals, and {len(task_rows)} recent tasks."
        )
        if not self.tool_permission_rows:
            page.result_text.setPlainText("No tools registered.")
        elif not self.approval_rows:
            page.result_text.appendPlainText("\nNo approvals pending.")

    def on_tool_permission_selected(self):
        page = self.pages.get("Tools & Permissions")
        if not page:
            return
        idx = page.tools_table.currentRow()
        if idx < 0 or idx >= len(self.tool_permission_rows):
            return
        name, cfg = self.tool_permission_rows[idx]
        self.selected_tool_name = name
        self._loading_tool_form = True
        page.tool_enabled.setChecked(bool(cfg.get("enabled", True)))
        page.tool_requires_approval.setChecked(bool(cfg.get("requires_approval", False)))
        page.tool_requires_unlock.setChecked(bool(cfg.get("requires_unlocked_desktop", False)))
        allowed_sources = cfg.get("allowed_sources") or []
        page.tool_sources.setText(",".join(allowed_sources))
        lines = [
            f"Tool: {name}",
            f"Enabled: {bool(cfg.get('enabled', True))}",
            f"Requires approval: {bool(cfg.get('requires_approval', False))}",
            f"Requires unlocked desktop: {bool(cfg.get('requires_unlocked_desktop', False))}",
            f"Allowed sources: {', '.join(allowed_sources) if allowed_sources else 'all'}",
            f"Scope: {cfg.get('scope') or 'default'}",
        ]
        page.result_text.setPlainText("\n".join(lines))
        page.apply_button.setEnabled(False)
        self._loading_tool_form = False

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
        if isinstance(result, dict) and result.get("success"):
            page.result_text.setPlainText(f"Updated tool policy for {self.selected_tool_name}.")
            page.apply_button.setEnabled(False)
        else:
            page.result_text.setPlainText(str((result or {}).get("error") or "Failed to update tool policy."))
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
        detail = self._format_row_detail(
            row,
            ["approval_id", "tool_name", "source", "sender", "status", "reason", "created_at", "requested_action"],
        )
        status = str(row.get("status") or "pending").lower()
        if status == "pending":
            detail += "\n\nNext step: Approve, then Run."
        elif status == "approved":
            detail += "\n\nNext step: Run."
        page.result_text.setPlainText(detail)

    def approve_selected_action(self):
        page = self.pages.get("Tools & Permissions")
        if not page:
            return
        if not self.selected_approval_id:
            page.result_text.setPlainText("Select an approval from the list first.")
            return
        result = self.client.approve_approval(self.selected_approval_id)
        if isinstance(result, dict) and result.get("success"):
            page.result_text.setPlainText(f"Approval {self.selected_approval_id} approved. Use Run to execute it.")
        else:
            page.result_text.setPlainText(str((result or {}).get("error") or "Failed to approve request."))
        self.refresh_tools_permissions()
        self.refresh_activity_audit()

    def run_selected_action(self):
        page = self.pages.get("Tools & Permissions")
        if not page:
            return
        if not self.selected_approval_id:
            page.result_text.setPlainText("Select an approval from the list first.")
            return
        result = self.client.run_approved_action(self.selected_approval_id)
        if isinstance(result, dict) and result.get("success"):
            tool = (result.get("result") or {}).get("tool_name") if isinstance(result.get("result"), dict) else ""
            page.result_text.setPlainText(
                f"Executed approved request {self.selected_approval_id}" + (f" using {tool}." if tool else ".")
            )
        else:
            page.result_text.setPlainText(str((result or {}).get("error") or "Failed to run approved request."))
        self.refresh_tools_permissions()
        self.refresh_activity_audit()

    def reject_selected_action(self):
        page = self.pages.get("Tools & Permissions")
        if not page:
            return
        if not self.selected_approval_id:
            page.result_text.setPlainText("Select an approval from the list first.")
            return
        result = self.client.reject_approval(self.selected_approval_id)
        if isinstance(result, dict) and result.get("success"):
            page.result_text.setPlainText(f"Approval {self.selected_approval_id} rejected.")
        else:
            page.result_text.setPlainText(str((result or {}).get("error") or "Failed to reject request."))
        self.refresh_tools_permissions()
    
    def refresh_logs(self):
        """Refresh logs display."""
        if not self.is_unlocked:
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
            categories=[c.strip() for c in page.email_categories.text().split(",") if c.strip()] or None,
            default_category=page.email_default_category.currentText().strip() or None,
        )
        page.email_result.setPlainText("Email account saved." if payload.get("success", True) else str(payload.get("error") or "Save failed."))
        if payload.get("success") is False:
            page.email_status.setText("Email status: save failed")
            page.email_status.setStyleSheet(f"color: {_RED};")
            return
        page.email_password.clear()
        page.save_account_btn.setEnabled(False)
        self.refresh_email_config_view()
    
    def test_email_connection(self):
        """Test the selected email account."""
        page = self.pages.get("Communications")
        if not page:
            return
        payload = self.client.test_email_connection(page.current_email_account_id)
        message = str(payload.get("message") or payload.get("error") or "Connection test completed.")
        lower = message.lower()
        if payload.get("success"):
            page.email_result.setPlainText(f"Connection successful\n\n{message}")
            page.email_status.setText("Email status: connection successful")
            page.email_status.setStyleSheet(f"color: {_GREEN};")
        else:
            if "auth" in lower or "login" in lower or "credential" in lower:
                page.email_result.setPlainText(f"Authentication failed\n\n{message}")
            elif "unreachable" in lower or "timed out" in lower or "timeout" in lower or "refused" in lower:
                page.email_result.setPlainText(f"Server unreachable\n\n{message}")
            else:
                page.email_result.setPlainText(message)
            page.email_status.setText("Email status: connection failed")
            page.email_status.setStyleSheet(f"color: {_RED};")

    def new_email_account(self):
        """Reset the email form for a new account."""
        page = self.pages.get("Communications")
        if not page:
            return
        self._loading_email_form = True
        page.current_email_account_id = None
        page.email_label.clear()
        page.email_address.clear()
        page.email_password.clear()
        page.email_imap_host.clear()
        page.email_imap_port.setText("993")
        page.email_mailbox.setText("INBOX")
        page.email_make_default.setChecked(False)
        page.email_categories.clear()
        page.email_default_category.setCurrentIndex(0)
        page.save_account_btn.setEnabled(False)
        self._loading_email_form = False

    def on_email_account_selected(self, current, previous=None):
        """Load the selected email account into the form."""
        del previous
        page = self.pages.get("Communications")
        if not page or current is None:
            return
        self._loading_email_form = True
        account = current.data(Qt.UserRole) or {}
        page.current_email_account_id = account.get("account_id")
        page.email_label.setText(str(account.get("label") or ""))
        page.email_address.setText(str(account.get("email_address") or ""))
        page.email_password.clear()
        page.email_imap_host.setText(str(account.get("imap_host") or ""))
        page.email_imap_port.setText(str(account.get("imap_port") or "993"))
        page.email_mailbox.setText(str(account.get("mailbox") or "INBOX"))
        page.email_make_default.setChecked(bool(account.get("is_default")))
        page.email_password.setPlaceholderText("Saved password hidden. Enter to replace.")
        # Load categories metadata
        cats = account.get("categories") or []
        page.email_categories.setText(", ".join(cats) if cats else "")
        default_cat = str(account.get("default_category") or "Primary")
        idx = page.email_default_category.findText(default_cat)
        if idx >= 0:
            page.email_default_category.setCurrentIndex(idx)
        page.save_account_btn.setEnabled(False)
        self._loading_email_form = False

    def set_default_email_account(self):
        """Set the selected email account as default."""
        page = self.pages.get("Communications")
        if not page or not page.current_email_account_id:
            return
        payload = self.client.set_default_email_account(page.current_email_account_id)
        page.email_result.setPlainText("Default email account updated." if payload.get("success", True) else str(payload.get("error") or "Update failed."))
        self.refresh_email_config_view()

    def delete_email_account(self):
        """Delete the selected email account."""
        page = self.pages.get("Communications")
        if not page or not page.current_email_account_id:
            return
        payload = self.client.delete_email_account(page.current_email_account_id)
        page.email_result.setPlainText("Email account deleted." if payload.get("success", True) else str(payload.get("error") or "Delete failed."))
        self.refresh_email_config_view()
    
    def add_allowed_directory(self):
        """Add an allowed directory via dialog."""
        page = self.pages.get("Files & Permissions")
        if not page:
            return
        dialog = QDialog(self.window)
        dialog.setWindowTitle("Add Allowed Directory")
        dialog.setModal(True)
        dialog.setMinimumWidth(560)
        outer = QVBoxLayout(dialog)
        outer.addWidget(create_label("Path", 10, bold=True))
        input_line = QLineEdit("C:\\")
        outer.addWidget(input_line)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        add_btn = buttons.button(QDialogButtonBox.Ok)
        add_btn.setText("Add")
        add_btn.setEnabled(False)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        outer.addWidget(buttons)

        def _toggle_add_enabled():
            add_btn.setEnabled(bool(input_line.text().strip()))

        input_line.textChanged.connect(_toggle_add_enabled)
        _toggle_add_enabled()

        if dialog.exec() != QDialog.Accepted:
            return
        value = input_line.text().strip()
        existing = [page.allowed_list.item(i).text() for i in range(page.allowed_list.count())]
        if value in existing:
            page.path_test_result.setText(f"Directory already in allowed list.")
            return
        existing.append(value)
        payload = self.client.save_files_policy(existing)
        if payload.get("success") is not False:
            page.path_test_result.setText(f"Added: {value}")
            page.path_test_result.setStyleSheet(f"color: {_GREEN};")
            self.refresh_files_policy()
        else:
            page.path_test_result.setText(str(payload.get("error") or "Save failed."))
            page.path_test_result.setStyleSheet(f"color: {_RED};")
    
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
        page.path_test_result.setText("Directory removed from allowed list." if payload.get("success") is not False else str(payload.get("error") or "Save failed."))
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
        normalized = str(payload.get("normalized_path") or "-")
        page.path_test_result.setText(
            ("Allowed" if allowed else "Blocked")
            + f" | Normalized path: {normalized} | Reason: {reason}"
        )
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
        page.routing_result.setPlainText(f"Approved {phone}." if payload.get("success") else str(payload.get("error") or "Approval failed."))
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
        page.routing_result.setPlainText(f"Blocked {phone}." if payload.get("success") else str(payload.get("error") or "Block failed."))
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
            chat_page.activity_list.setPlainText("No activity yet")
    
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
