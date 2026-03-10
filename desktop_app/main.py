"""Entry point for local desktop app.

Desktop transport is local-only and never sends SMS replies.
"""

import sys
from pathlib import Path
from tkinter import Tk
from tkinter import ttk

ROOT_DIR = Path(__file__).resolve().parent.parent
AGENT_DIR = ROOT_DIR / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from runtime import create_runtime  # noqa: E402
from ui import DesktopControlApp  # noqa: E402


def schedule_refresh(app: DesktopControlApp) -> None:
    app.refresh_status()
    app.refresh_logs()
    app.root.after(15000, schedule_refresh, app)


def main() -> None:
    runtime = create_runtime(AGENT_DIR)

    root = Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")

    app = DesktopControlApp(root, runtime)
    root.after(15000, schedule_refresh, app)
    root.mainloop()


if __name__ == "__main__":
    main()
