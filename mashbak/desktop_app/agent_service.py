"""Manages local FastAPI agent lifecycle for desktop app usage."""

import importlib
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import uvicorn
from agent.config_loader import ConfigLoader


class AgentService:
    def __init__(self, project_root: Path, host: str = "127.0.0.1", port: int = 8787):
        self.project_root = project_root
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.process: subprocess.Popen | None = None
        self.server: uvicorn.Server | None = None
        self.server_thread: threading.Thread | None = None
        self.started_by_app = False
        self.api_key = self._resolve_api_key()

    def start(self) -> None:
        if self._is_healthy():
            if self._is_authorized(self.api_key) and self._has_required_control_board_routes(self.api_key):
                return

            # A different agent is already using this port with another key.
            # Move this desktop session to a free local port and start its own service.
            self.port = self._find_free_port(self.port + 1)
            self.base_url = f"http://{self.host}:{self.port}"

        if getattr(sys, "frozen", False):
            self._start_in_process()
        else:
            self._start_subprocess()

        deadline = time.time() + 12
        while time.time() < deadline:
            if self._is_healthy():
                return
            if self.process and self.process.poll() is not None:
                raise RuntimeError("Embedded agent process exited during startup")
            if self.server_thread and not self.server_thread.is_alive():
                raise RuntimeError("Embedded agent server thread exited during startup")
            time.sleep(0.2)

        raise RuntimeError("Timed out waiting for embedded agent startup")

    def _start_subprocess(self) -> None:
        env = os.environ.copy()
        env.setdefault("AGENT_API_KEY", self.api_key)

        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "agent.agent:app",
            "--app-dir",
            str(self.project_root),
            "--host",
            self.host,
            "--port",
            str(self.port),
        ]

        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        self.process = subprocess.Popen(
            cmd,
            cwd=str(self.project_root),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        self.started_by_app = True

    def _start_in_process(self) -> None:
        env = os.environ.copy()
        env.setdefault("AGENT_API_KEY", self.api_key)
        os.environ.setdefault("AGENT_API_KEY", env["AGENT_API_KEY"])

        for import_path in (self.project_root,):
            import_path_text = str(import_path)
            if import_path_text not in sys.path:
                sys.path.insert(0, import_path_text)

        try:
            app_module = importlib.import_module("agent.agent")
        except ImportError:
            app_module = importlib.import_module("agent")

        config = uvicorn.Config(
            app=app_module.app,
            host=self.host,
            port=self.port,
            log_level="warning",
            # In frozen GUI mode sys.stderr/sys.stdout may be None, and uvicorn's
            # default formatter initialization can crash when probing isatty().
            # Disable uvicorn's dictConfig path and rely on app-level logging.
            log_config=None,
            access_log=False,
        )
        self.server = uvicorn.Server(config)
        self.server_thread = threading.Thread(target=self.server.run, daemon=True)
        self.server_thread.start()
        self.started_by_app = True

    def stop(self) -> None:
        if not self.started_by_app:
            return

        if self.server:
            self.server.should_exit = True
            if self.server_thread:
                self.server_thread.join(timeout=5)
            self.server = None
            self.server_thread = None

        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None

    def _resolve_api_key(self) -> str:
        ConfigLoader.load(reload=True)
        env_key = (ConfigLoader.get("AGENT_API_KEY", "") or "").strip()
        if env_key:
            return env_key

        return "desktop-local-default-key"

    def _is_authorized(self, api_key: str) -> bool:
        headers = {"x-api-key": api_key}
        request = urllib.request.Request(f"{self.base_url}/tools", headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=1.2) as response:
                return response.status == 200
        except Exception:
            return False

    def _has_required_control_board_routes(self, api_key: str) -> bool:
        """Check minimal ops endpoints before reusing an already-running service."""
        headers = {"x-api-key": api_key}
        required_paths = [
            "/control-board/tools-permissions",
            "/control-board/personal-context",
        ]
        for path in required_paths:
            request = urllib.request.Request(f"{self.base_url}{path}", headers=headers, method="GET")
            try:
                with urllib.request.urlopen(request, timeout=1.2) as response:
                    if response.status != 200:
                        return False
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    return False
                if exc.code in {401, 403}:
                    return False
                continue
            except Exception:
                return False
        return True

    def _find_free_port(self, start_port: int) -> int:
        for port in range(start_port, start_port + 50):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.2)
                if sock.connect_ex((self.host, port)) != 0:
                    return port
        raise RuntimeError("Could not find a free local port for embedded agent service")

    def _is_healthy(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.base_url}/health", timeout=1.0) as response:
                return response.status == 200
        except Exception:
            return False

    def is_port_busy(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            return s.connect_ex((self.host, self.port)) == 0
