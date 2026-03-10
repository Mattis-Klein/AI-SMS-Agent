from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import platform
import psutil

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def load_config() -> dict:
    """Load configuration from config.json"""
    config_path = BASE_DIR / "config.json"
    if not config_path.exists():
        return {}
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[agent] Warning: Failed to load config.json: {e}")
        return {}


load_env_file(BASE_DIR / ".env")
CONFIG = load_config()

WORKSPACE = Path(os.getenv("AGENT_WORKSPACE", str(BASE_DIR / "workspace"))).resolve()
LOG_FILE = WORKSPACE / "logs" / "agent.log"
API_KEY = os.getenv("AGENT_API_KEY", "")

if not API_KEY:
    raise RuntimeError("AGENT_API_KEY is required. Set it in agent/.env or the environment.")

for required_dir in (WORKSPACE, WORKSPACE / "inbox", WORKSPACE / "outbox", WORKSPACE / "logs"):
    required_dir.mkdir(parents=True, exist_ok=True)

# Load allowed commands from config
ALLOWED_COMMANDS = CONFIG.get("allowed_commands", {})
ALLOWED_DIRECTORIES = [Path(d) for d in CONFIG.get("allowed_directories", [])]
SECURITY_CONFIG = CONFIG.get("security", {})
MAX_FILE_SIZE = SECURITY_CONFIG.get("max_file_size_bytes", 10485760)
BLOCKED_EXTENSIONS = set(SECURITY_CONFIG.get("blocked_extensions", []))


class ReadFile(BaseModel):
    path: str

class WriteFile(BaseModel):
    path: str
    content: str
    overwrite: bool = False

class RunCmd(BaseModel):
    name: str
    args: dict = {}

class CommandListRequest(BaseModel):
    pass


def log_event(event):
    """Log events with timestamp in JSON format"""
    event["time"] = datetime.now().isoformat(timespec="seconds")
    event["hostname"] = platform.node()
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except Exception as e:
        print(f"[agent] Error writing to log: {e}")


def auth(key, request_id=None):
    """Authenticate API requests"""
    if key != API_KEY:
        log_event({"request_id": request_id, "action": "auth_failed", "status": "error"})
        raise HTTPException(status_code=401, detail="Unauthorized")


def is_safe_path(user_path: str, request_id: str = None) -> tuple[bool, str]:
    """
    Validate that a path is safe to access.
    Returns (is_safe, resolved_path)
    """
    try:
        # Check for blocked extensions
        extension = Path(user_path).suffix.lower()
        if extension in BLOCKED_EXTENSIONS:
            log_event({
                "request_id": request_id, 
                "action": "blocked_extension",
                "path": user_path,
                "extension": extension,
                "status": "blocked"
            })
            return False, f"Blocked file extension: {extension}"
        
        # First try workspace-relative path
        resolved = (WORKSPACE / user_path).resolve()
        if WORKSPACE in resolved.parents or resolved == WORKSPACE:
            return True, str(resolved)
        
        # Check if path is in allowed directories
        resolved = Path(user_path).resolve()
        for allowed_dir in ALLOWED_DIRECTORIES:
            if allowed_dir in resolved.parents or resolved == allowed_dir:
                return True, str(resolved)
        
        log_event({
            "request_id": request_id,
            "action": "invalid_path",
            "path": user_path,
            "resolved": str(resolved),
            "status": "blocked"
        })
        return False, "Path is not in allowed directories"
        
    except Exception as e:
        log_event({
            "request_id": request_id,
            "action": "path_validation_error",
            "path": user_path,
            "error": str(e),
            "status": "error"
        })
        return False, f"Path validation error: {str(e)}"


def safe_path(user_path, request_id=None):
    """Legacy compatibility function"""
    is_safe, result = is_safe_path(user_path, request_id)
    if not is_safe:
        raise HTTPException(status_code=400, detail=result)
    return Path(result)


def build_command(cmd_config: dict, args: dict, request_id: str = None) -> list:
    """
    Build a command from configuration, substituting placeholders with arguments.
    """
    command = cmd_config.get("command", [])
    if not command:
        return []
    
    # Substitute placeholders
    result = []
    for part in command:
        if "{workspace}" in part:
            part = part.replace("{workspace}", str(WORKSPACE))
        if "{path}" in part and "path" in args:
            # Validate the path if required
            if cmd_config.get("validate_path", False):
                is_safe, validated_path = is_safe_path(args["path"], request_id)
                if not is_safe:
                    raise HTTPException(status_code=400, detail=validated_path)
                part = part.replace("{path}", validated_path)
            else:
                part = part.replace("{path}", args["path"])
        
        result.append(part)
    
    return result


@app.get("/health")
def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "workspace": str(WORKSPACE),
        "commands_loaded": len(ALLOWED_COMMANDS)
    }


@app.get("/commands")
def list_commands(x_api_key: str = Header(None), x_request_id: str = Header(None)):
    """List all available commands"""
    auth(x_api_key, x_request_id)
    log_event({
        "request_id": x_request_id,
        "action": "list_commands",
        "status": "success"
    })
    
    return {
        "commands": {
            name: {
                "description": cmd.get("description", ""),
                "requires_args": cmd.get("requires_args", False)
            }
            for name, cmd in ALLOWED_COMMANDS.items()
        }
    }


@app.post("/read")
def read_file(
    req: ReadFile,
    x_api_key: str = Header(None),
    x_request_id: str = Header(None),
    x_sender: str = Header(None)
):
    """Read a file from workspace or allowed directories"""
    auth(x_api_key, x_request_id)
    p = safe_path(req.path, x_request_id)
    
    if not p.exists() or not p.is_file():
        log_event({
            "request_id": x_request_id,
            "sender": x_sender,
            "action": "read_missing",
            "path": str(p),
            "status": "error"
        })
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check file size
    if p.stat().st_size > MAX_FILE_SIZE:
        log_event({
            "request_id": x_request_id,
            "sender": x_sender,
            "action": "read_file_too_large",
            "path": str(p),
            "size": p.stat().st_size,
            "status": "error"
        })
        raise HTTPException(status_code=400, detail="File too large")
    
    log_event({
        "request_id": x_request_id,
        "sender": x_sender,
        "action": "read",
        "path": str(p),
        "size": p.stat().st_size,
        "status": "success"
    })
    return {"path": str(p), "content": p.read_text(encoding="utf-8", errors="replace")}


@app.post("/write")
def write_file(
    req: WriteFile,
    x_api_key: str = Header(None),
    x_request_id: str = Header(None),
    x_sender: str = Header(None)
):
    """Write a file to workspace or allowed directories"""
    auth(x_api_key, x_request_id)
    p = safe_path(req.path, x_request_id)

    if p.exists() and not req.overwrite:
        log_event({
            "request_id": x_request_id,
            "sender": x_sender,
            "action": "write_exists",
            "path": str(p),
            "status": "error"
        })
        raise HTTPException(status_code=409, detail="File exists")

    # Check content size
    content_size = len(req.content.encode("utf-8"))
    if content_size > MAX_FILE_SIZE:
        log_event({
            "request_id": x_request_id,
            "sender": x_sender,
            "action": "write_content_too_large",
            "path": str(p),
            "size": content_size,
            "status": "error"
        })
        raise HTTPException(status_code=400, detail="Content too large")

    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(req.content, encoding="utf-8")

    log_event({
        "request_id": x_request_id,
        "sender": x_sender,
        "action": "write",
        "path": str(p),
        "overwrite": req.overwrite,
        "bytes": content_size,
        "status": "success"
    })
    return {"success": True, "path": str(p)}


@app.post("/run")
def run_command(
    req: RunCmd,
    x_api_key: str = Header(None),
    x_request_id: str = Header(None),
    x_sender: str = Header(None)
):
    """Execute a whitelisted command"""
    auth(x_api_key, x_request_id)

    if req.name not in ALLOWED_COMMANDS:
        available_commands = ", ".join(ALLOWED_COMMANDS.keys())
        log_event({
            "request_id": x_request_id,
            "sender": x_sender,
            "action": "command_rejected",
            "name": req.name,
            "status": "blocked"
        })
        raise HTTPException(
            status_code=400,
            detail=f"Command '{req.name}' not allowed. Available: {available_commands}"
        )

    cmd_config = ALLOWED_COMMANDS[req.name]
    
    # Check if command requires arguments
    if cmd_config.get("requires_args", False) and not req.args:
        log_event({
            "request_id": x_request_id,
            "sender": x_sender,
            "action": "command_missing_args",
            "name": req.name,
            "status": "error"
        })
        raise HTTPException(status_code=400, detail=f"Command '{req.name}' requires arguments")

    try:
        cmd = build_command(cmd_config, req.args, x_request_id)
    except HTTPException as e:
        log_event({
            "request_id": x_request_id,
            "sender": x_sender,
            "action": "command_build_failed",
            "name": req.name,
            "error": str(e.detail),
            "status": "error"
        })
        raise

    log_event({
        "request_id": x_request_id,
        "sender": x_sender,
        "action": "command_start",
        "name": req.name,
        "command": " ".join(cmd),
        "status": "running"
    })

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(WORKSPACE)
        )
    except subprocess.TimeoutExpired:
        log_event({
            "request_id": x_request_id,
            "sender": x_sender,
            "action": "command_timeout",
            "name": req.name,
            "status": "error"
        })
        raise HTTPException(status_code=408, detail="Command timed out after 30 seconds")
    except Exception as e:
        log_event({
            "request_id": x_request_id,
            "sender": x_sender,
            "action": "command_error",
            "name": req.name,
            "error": str(e),
            "status": "error"
        })
        raise HTTPException(status_code=500, detail=f"Command execution failed: {str(e)}")

    log_event({
        "request_id": x_request_id,
        "sender": x_sender,
        "action": "command_complete",
        "name": req.name,
        "return_code": result.returncode,
        "status": "success" if result.returncode == 0 else "failed"
    })

    return {
        "name": req.name,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "code": result.returncode
    }