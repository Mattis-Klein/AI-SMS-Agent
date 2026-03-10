"""Minimal local desktop control panel for AI-SMS-Agent.

This app runs locally (Tkinter) and uses the same dispatcher/interpreter/tool
pipeline as SMS by calling shared AgentRuntime directly. It does not call the
Twilio bridge for message handling, so local chats never send SMS replies.
"""

import asyncio
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path
from tkinter import END, LEFT, RIGHT, BOTH, X, Y, Tk, Text
from tkinter import ttk

from runtime import create_runtime


class DesktopControlApp:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("AI-SMS-Agent Local Console")
        self.root.geometry("1180x760")

        self.runtime = create_runtime()
        self.activity = []

        self.agent_log_file = self.runtime.workspace / "logs" / "agent.log"
        self.bridge_log_file = self.runtime.base_dir.parent / "sms-bridge" / "logs" / "bridge.log"

        self._build_ui()
        self.refresh_status()
        self.refresh_logs()

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=BOTH, expand=True)

        console_tab = ttk.Frame(notebook)
        status_tab = ttk.Frame(notebook)
        logs_tab = ttk.Frame(notebook)

        notebook.add(console_tab, text="Console")
        notebook.add(status_tab, text="Status")
        notebook.add(logs_tab, text="Logs")

        self._build_console_tab(console_tab)
        self._build_status_tab(status_tab)
        self._build_logs_tab(logs_tab)

    def _build_console_tab(self, parent: ttk.Frame) -> None:
        input_frame = ttk.Frame(parent)
        input_frame.pack(fill=X, padx=10, pady=10)

        ttk.Label(input_frame, text="Message").pack(anchor="w")
        self.message_entry = ttk.Entry(input_frame)
        self.message_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
        self.message_entry.bind("<Return>", lambda _event: self.on_send())

        self.send_button = ttk.Button(input_frame, text="Send", command=self.on_send)
        self.send_button.pack(side=RIGHT)

        details_frame = ttk.LabelFrame(parent, text="Execution Details")
        details_frame.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))
        self.details_text = Text(details_frame, height=20, wrap="word")
        self.details_text.pack(fill=BOTH, expand=True, padx=8, pady=8)

        result_frame = ttk.LabelFrame(parent, text="Final Result")
        result_frame.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))
        self.result_text = Text(result_frame, height=8, wrap="word")
        self.result_text.pack(fill=BOTH, expand=True, padx=8, pady=8)

        activity_frame = ttk.LabelFrame(parent, text="Recent Activity")
        activity_frame.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))
        self.activity_list = Text(activity_frame, height=8, wrap="none")
        self.activity_list.pack(fill=BOTH, expand=True, padx=8, pady=8)

    def _build_status_tab(self, parent: ttk.Frame) -> None:
        actions = ttk.Frame(parent)
        actions.pack(fill=X, padx=10, pady=10)

        ttk.Button(actions, text="Refresh Status", command=self.refresh_status).pack(side=LEFT)

        status_frame = ttk.LabelFrame(parent, text="Service Status")
        status_frame.pack(fill=X, padx=10, pady=(0, 10))

        self.status_text = Text(status_frame, height=10, wrap="word")
        self.status_text.pack(fill=BOTH, expand=True, padx=8, pady=8)

        tools_frame = ttk.LabelFrame(parent, text="Registered Tools")
        tools_frame.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        self.tools_text = Text(tools_frame, height=12, wrap="word")
        self.tools_text.pack(fill=BOTH, expand=True, padx=8, pady=8)

        config_frame = ttk.LabelFrame(parent, text="Configuration Summary")
        config_frame.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        self.config_text = Text(config_frame, height=12, wrap="word")
        self.config_text.pack(fill=BOTH, expand=True, padx=8, pady=8)

    def _build_logs_tab(self, parent: ttk.Frame) -> None:
        actions = ttk.Frame(parent)
        actions.pack(fill=X, padx=10, pady=10)

        ttk.Button(actions, text="Refresh Logs", command=self.refresh_logs).pack(side=LEFT)

        agent_logs_frame = ttk.LabelFrame(parent, text="Recent Agent Logs")
        agent_logs_frame.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        self.agent_logs_text = Text(agent_logs_frame, height=12, wrap="none")
        self.agent_logs_text.pack(fill=BOTH, expand=True, padx=8, pady=8)

        bridge_logs_frame = ttk.LabelFrame(parent, text="Recent Bridge Logs")
        bridge_logs_frame.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        self.bridge_logs_text = Text(bridge_logs_frame, height=12, wrap="none")
        self.bridge_logs_text.pack(fill=BOTH, expand=True, padx=8, pady=8)

    def on_send(self) -> None:
        message = self.message_entry.get().strip()
        if not message:
            return

        self.send_button.configure(state="disabled")
        self._set_text(self.details_text, "Running...\n")
        self._set_text(self.result_text, "")

        thread = threading.Thread(target=self._run_message, args=(message,), daemon=True)
        thread.start()

    def _run_message(self, message: str) -> None:
        try:
            result = asyncio.run(self.runtime.execute_nl(message=message, sender="local-desktop"))
            self.root.after(0, lambda: self._display_result(message, result))
        except Exception as exc:
            self.root.after(0, lambda: self._display_error(str(exc)))

    def _display_result(self, message: str, result: dict) -> None:
        self.send_button.configure(state="normal")
        self.message_entry.delete(0, END)

        trace = result.get("trace", {})
        detail_lines = [
            f"Raw Request: {trace.get('raw_request', message)}",
            f"Interpreted Intent: {trace.get('interpreted_intent')}",
            f"Selected Tool: {trace.get('selected_tool')}",
            f"Interpreted Args: {json.dumps(trace.get('interpreted_args', {}), ensure_ascii=True)}",
            f"Validation Status: {trace.get('validation_status')}",
            f"Validated Args: {json.dumps(trace.get('validated_arguments'), ensure_ascii=True)}",
            f"Execution Status: {trace.get('execution_status')}",
            f"Request ID: {result.get('request_id')}",
        ]
        self._set_text(self.details_text, "\n".join(detail_lines))

        if result.get("success"):
            final_text = result.get("output") or "Command executed successfully."
        else:
            final_text = result.get("error") or "Request failed."
        self._set_text(self.result_text, final_text)

        activity_line = f"{result.get('request_id')} | tool={result.get('tool_name')} | success={result.get('success')} | msg={message}"
        self.activity.insert(0, activity_line)
        self.activity = self.activity[:30]
        self._set_text(self.activity_list, "\n".join(self.activity))

        self.refresh_logs()

    def _display_error(self, error_text: str) -> None:
        self.send_button.configure(state="normal")
        self._set_text(self.details_text, "Execution Error")
        self._set_text(self.result_text, error_text)

    def refresh_status(self) -> None:
        summary = self.runtime.summary()

        agent_status = self._check_http_health("http://127.0.0.1:8787/health")
        bridge_status = self._check_http_health("http://127.0.0.1:34567/health")

        status_lines = [
            f"FastAPI Agent Service: {'running' if agent_status['running'] else 'not detected'}",
            f"SMS Bridge Service: {'running' if bridge_status['running'] else 'not detected'}",
            f"Agent Health Detail: {agent_status['detail']}",
            f"Bridge Health Detail: {bridge_status['detail']}",
        ]
        self._set_text(self.status_text, "\n".join(status_lines))

        tool_lines = [f"- {name}" for name in summary["registered_tools"]]
        self._set_text(self.tools_text, "\n".join(tool_lines))

        config_lines = [
            f"Workspace: {summary['workspace']}",
            "Allowed Directories:",
        ]
        config_lines.extend([f"  - {item}" for item in summary["allowed_directories"]])
        config_lines.append(f"Allowed Tools: {summary['allowed_tools']}")
        self._set_text(self.config_text, "\n".join(config_lines))

    def refresh_logs(self) -> None:
        agent_lines = self._tail_file(self.agent_log_file, max_lines=30)
        bridge_lines = self._tail_file(self.bridge_log_file, max_lines=30)

        self._set_text(self.agent_logs_text, "\n".join(agent_lines) if agent_lines else "No agent logs yet.")
        self._set_text(self.bridge_logs_text, "\n".join(bridge_lines) if bridge_lines else "No bridge logs yet.")

    def _tail_file(self, path: Path, max_lines: int = 30) -> list[str]:
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            return lines[-max_lines:]
        except Exception as exc:
            return [f"Failed to read {path}: {exc}"]

    def _check_http_health(self, url: str) -> dict:
        try:
            with urllib.request.urlopen(url, timeout=1.2) as response:
                raw = response.read().decode("utf-8", errors="replace")
                detail = raw.strip().replace("\n", " ")
                return {"running": response.status == 200, "detail": detail[:180]}
        except urllib.error.URLError as exc:
            return {"running": False, "detail": str(exc.reason)}
        except Exception as exc:
            return {"running": False, "detail": str(exc)}

    def _set_text(self, widget: Text, value: str) -> None:
        widget.delete("1.0", END)
        widget.insert("1.0", value)


def main() -> None:
    root = Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    app = DesktopControlApp(root)
    root.after(15000, _schedule_refresh, app)
    root.mainloop()


def _schedule_refresh(app: DesktopControlApp) -> None:
    app.refresh_status()
    app.refresh_logs()
    app.root.after(15000, _schedule_refresh, app)


if __name__ == "__main__":
    main()
