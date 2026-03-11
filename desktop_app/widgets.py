"""Reusable Tkinter widget helpers for the local desktop console."""

from tkinter import BOTH, END, LEFT, RIGHT, X, Y, Text
from tkinter import scrolledtext, ttk


def labeled_text_area(parent: ttk.Frame, title: str, height: int = 10, wrap: str = "word") -> Text:
    frame = ttk.LabelFrame(parent, text=title)
    frame.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))
    text = Text(frame, height=height, wrap=wrap)
    text.pack(fill=BOTH, expand=True, padx=8, pady=8)
    return text


def labeled_scroll_text(
    parent,
    height: int = 10,
    font: tuple = ("Consolas", 9),
    wrap: str = "word",
) -> scrolledtext.ScrolledText:
    """Fill the parent frame with a ScrolledText widget (no LabelFrame wrapper)."""
    widget = scrolledtext.ScrolledText(
        parent, wrap=wrap, font=font,
        relief="flat", bd=0,
        height=height if height > 0 else 1,
    )
    widget.pack(fill=BOTH, expand=True)
    return widget


def action_bar(parent: ttk.Frame) -> ttk.Frame:
    frame = ttk.Frame(parent)
    frame.pack(fill=X, padx=10, pady=10)
    return frame


def add_refresh_button(parent: ttk.Frame, command, label: str = "Refresh") -> ttk.Button:
    button = ttk.Button(parent, text=label, command=command)
    button.pack(side=LEFT)
    return button


def set_text(widget: Text, value: str) -> None:
    widget.delete("1.0", END)
    widget.insert("1.0", value)
