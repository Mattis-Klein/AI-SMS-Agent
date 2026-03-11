"""Reusable Tkinter widget helpers for the local desktop console."""

from tkinter import BOTH, END, LEFT, RIGHT, X, Y, Text
from tkinter import ttk


def make_scrolled_text(parent, wrap="word", font=("Segoe UI", 10), padx=0, pady=0, **kwargs) -> Text:
    """Create a Text widget with a vertical scrollbar packed into *parent*."""
    scrollbar = ttk.Scrollbar(parent, orient="vertical")
    scrollbar.pack(side=RIGHT, fill=Y, padx=(0, padx), pady=pady)
    text = Text(parent, wrap=wrap, font=font, yscrollcommand=scrollbar.set, **kwargs)
    text.pack(side=LEFT, fill=BOTH, expand=True, padx=(padx, 0), pady=pady)
    scrollbar.configure(command=text.yview)
    return text


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
) -> Text:
    """Fill the parent frame with a scrollable Text widget (no LabelFrame wrapper)."""
    scrollbar = ttk.Scrollbar(parent, orient="vertical")
    scrollbar.pack(side=RIGHT, fill=Y)
    text = Text(
        parent, wrap=wrap, font=font,
        relief="flat", bd=0,
        height=height if height > 0 else 1,
        yscrollcommand=scrollbar.set,
    )
    text.pack(side=LEFT, fill=BOTH, expand=True)
    scrollbar.configure(command=text.yview)
    return text


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
