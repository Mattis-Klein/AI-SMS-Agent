"""Entry point for local desktop app.

Desktop transport is local-only and never sends SMS replies.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from tkinter import Tk
from tkinter import ttk

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    ROOT_DIR = Path(sys._MEIPASS)
else:
    ROOT_DIR = Path(__file__).resolve().parent.parent
AGENT_DIR = ROOT_DIR / "agent"

for import_path in (ROOT_DIR, ROOT_DIR / "desktop_app"):
    import_path_text = str(import_path)
    if import_path_text not in sys.path:
        sys.path.insert(0, import_path_text)

try:
    from agent.runtime import create_runtime  # noqa: E402
except ImportError:
    from runtime import create_runtime  # noqa: E402
from agent_client import AgentClient  # noqa: E402
from agent_service import AgentService  # noqa: E402
from ui import DesktopControlApp  # noqa: E402


def schedule_refresh(app: DesktopControlApp) -> None:
    app.refresh_status()
    app.refresh_logs()
    app.root.after(15000, schedule_refresh, app)


def run_smoke_test() -> int:
    os.environ.setdefault("AGENT_API_KEY", "desktop-smoke-key")
    runtime = create_runtime(AGENT_DIR)
    result = asyncio.run(runtime.execute_nl("check my inbox", sender="desktop-smoke"))
    print(result.get("success"), result.get("tool_name"), result.get("trace", {}).get("execution_status"))
    return 0


def run_ui_smoke() -> int:
    root = Tk()
    root.title("Mashbak UI Smoke")
    root.after(500, root.destroy)
    root.mainloop()
    print("ui-ok")
    return 0


def run_service_smoke() -> int:
    service = AgentService(ROOT_DIR)
    service.start()
    try:
        client = AgentClient(base_url=service.base_url, api_key=service.api_key)
        result = client.execute_nl("check my inbox", sender="desktop-service-smoke")
        print(result.get("success"), result.get("tool_name"), (result.get("trace") or {}).get("execution_status"))
        return 0 if result.get("tool_name") else 1
    finally:
        service.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Mashbak Desktop")
    parser.add_argument("--smoke-test", action="store_true", help="Run local dispatcher smoke test and exit")
    parser.add_argument("--ui-smoke", action="store_true", help="Launch Tk root briefly and exit")
    parser.add_argument("--service-smoke-test", action="store_true", help="Start embedded agent service and run local client test")
    args = parser.parse_args()

    if args.smoke_test:
        raise SystemExit(run_smoke_test())
    if args.ui_smoke:
        raise SystemExit(run_ui_smoke())
    if args.service_smoke_test:
        raise SystemExit(run_service_smoke())

    service = AgentService(ROOT_DIR)
    service.start()

    os.environ.setdefault("AGENT_API_KEY", service.api_key)
    runtime = create_runtime(AGENT_DIR)
    client = AgentClient(base_url=service.base_url, api_key=service.api_key)

    root = Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")

    app = DesktopControlApp(root, client, runtime.summary())
    root.after(15000, schedule_refresh, app)
    try:
        root.mainloop()
    finally:
        service.stop()


if __name__ == "__main__":
    main()
