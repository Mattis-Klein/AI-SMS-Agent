"""Entry point for local desktop app.

Desktop transport is local-only and never sends SMS replies.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from tkinter import Tk

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    # Prefer repo root when running dist/Mashbak.exe in-place, otherwise use bundle temp dir.
    exe_repo_root = Path(sys.executable).resolve().parent.parent
    if (exe_repo_root / "agent").exists() and (exe_repo_root / "desktop_app").exists():
        ROOT_DIR = exe_repo_root
    else:
        ROOT_DIR = Path(sys._MEIPASS)
else:
    ROOT_DIR = Path(__file__).resolve().parent.parent
AGENT_DIR = ROOT_DIR / "agent"

for import_path in (ROOT_DIR, ROOT_DIR / "desktop_app"):
    import_path_text = str(import_path)
    if import_path_text not in sys.path:
        sys.path.insert(0, import_path_text)

from agent.runtime import create_runtime  # noqa: E402
from agent.config_loader import ConfigLoader  # noqa: E402
from agent_client import AgentClient  # noqa: E402
from agent_service import AgentService  # noqa: E402
from ui import DesktopControlApp  # noqa: E402


def _resolve_setting(key: str, default: str | None = None) -> str | None:
    ConfigLoader.load(reload=True)
    value = ConfigLoader.get(key)
    if value:
        return value

    if default is not None:
        print(f"[desktop] {key} not set. Using fallback value.", file=sys.stderr)
        return default

    return None


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
        result = client.execute_nl("check my inbox", sender="desktop-service-smoke", owner_unlocked=True)
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
    local_app_pin = _resolve_setting("LOCAL_APP_PIN", default="5421")

    runtime = create_runtime(AGENT_DIR)
    client = AgentClient(base_url=service.base_url, api_key=service.api_key)

    root = Tk()
    app = DesktopControlApp(
        root,
        client,
        runtime.summary(),
        local_app_pin=local_app_pin,
    )
    root.after(15000, schedule_refresh, app)
    try:
        root.mainloop()
    finally:
        service.stop()


if __name__ == "__main__":
    main()
