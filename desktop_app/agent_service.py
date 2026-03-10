"""Manages local FastAPI agent lifecycle for desktop app usage."""

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


class AgentService:
    def __init__(self, project_root: Path, host: str = "127.0.0.1", port: int = 8787):
        self.project_root = project_root
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.process: subprocess.Popen | None = None
        self.started_by_app = False
        self.api_key = self._resolve_api_key()

    def start(self) -> None:
        if self._is_healthy():
            return

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

        deadline = time.time() + 12
        while time.time() < deadline:
            if self._is_healthy():
                return
            if self.process.poll() is not None:
                raise RuntimeError("Embedded agent process exited during startup")
            time.sleep(0.2)

        raise RuntimeError("Timed out waiting for embedded agent startup")

    def stop(self) -> None:
        if not self.started_by_app or not self.process:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None

    def _resolve_api_key(self) -> str:
        env_key = os.getenv("AGENT_API_KEY")
        if env_key:
            return env_key

        env_file = self.project_root / "agent" / ".env"
        if env_file.exists():
            for raw in env_file.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() == "AGENT_API_KEY" and value.strip():
                    return value.strip()

        return "desktop-local-default-key"

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
