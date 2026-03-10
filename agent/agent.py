"""
AI-SMS-Agent FastAPI application

Tool-based architecture for executing safe commands via SMS.
All requests are routed through the tool dispatcher, which validates
inputs and logs all activities.
"""

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from config import Config
from logger import StructuredLogger
from tools import ToolRegistry
from tools.builtin import ALL_BUILTIN_TOOLS
from dispatcher import Dispatcher, RequestContext
from interpreter import NaturalLanguageInterpreter


# ============================================================================
# Initialization
# ============================================================================

app = FastAPI(title="AI-SMS-Agent", version="2.0.0")

BASE_DIR = Path(__file__).resolve().parent


def load_env_file(env_path: Path) -> None:
    """Load environment variables from .env file before reading AGENT_* values."""
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


# Initialization order is intentional:
# 1) determine project root, 2) load .env, 3) read AGENT_* env vars,
# 4) initialize workspace paths/configuration.
load_env_file(BASE_DIR / ".env")

WORKSPACE = Path(os.getenv("AGENT_WORKSPACE", str(BASE_DIR / "workspace"))).resolve()
API_KEY = os.getenv("AGENT_API_KEY", "")

if not API_KEY:
    raise RuntimeError("AGENT_API_KEY is required. Set it in agent/.env or the environment.")

# Ensure workspace directories exist
for required_dir in (WORKSPACE, WORKSPACE / "inbox", WORKSPACE / "outbox", WORKSPACE / "logs"):
    required_dir.mkdir(parents=True, exist_ok=True)

# Initialize configuration
config = Config(BASE_DIR / "config.json")

# Initialize logger
logger = StructuredLogger(WORKSPACE / "logs" / "agent.log")

# Initialize tool registry
registry = ToolRegistry()
for tool in ALL_BUILTIN_TOOLS:
    registry.register(tool)

# Initialize interpreter and dispatcher
interpreter = NaturalLanguageInterpreter()
dispatcher = Dispatcher(registry, interpreter, logger)


# ============================================================================
# Request Models
# ============================================================================

class ExecuteToolRequest(BaseModel):
    """Request to execute a tool by name"""
    tool_name: str
    args: dict = {}


class ExecuteNaturalLanguageRequest(BaseModel):
    """Request to execute a natural language message"""
    message: str


# ============================================================================
# Authentication & Middleware
# ============================================================================

def authenticate(api_key: Optional[str], request_id: Optional[str] = None) -> None:
    """Authenticate API request"""
    if api_key != API_KEY:
        logger.log_error(
            request_id=request_id or "unknown",
            error_type="auth_failed",
            error_message="Invalid API key",
        )
        raise HTTPException(status_code=401, detail="Unauthorized")


# ============================================================================
# Health & Info Endpoints
# ============================================================================

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "workspace": str(WORKSPACE),
        "tools_loaded": len(registry.list_all()),
        "version": "2.0.0",
    }


@app.get("/tools")
def list_tools(x_api_key: str = Header(None)):
    """List all available tools with descriptions"""
    authenticate(x_api_key)
    
    return {
        "tools": registry.get_all_info(),
        "count": len(registry.list_all()),
    }


@app.get("/tools/{tool_name}")
def get_tool_info(tool_name: str, x_api_key: str = Header(None)):
    """Get information about a specific tool"""
    authenticate(x_api_key)
    
    info = registry.get_info(tool_name)
    if not info:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    
    return info


# ============================================================================
# Tool Execution Endpoints
# ============================================================================

@app.post("/execute")
async def execute_tool(
    req: ExecuteToolRequest,
    x_api_key: str = Header(None),
    x_request_id: str = Header(None),
    x_sender: str = Header(None),
):
    """
    Execute a tool directly by name with structured arguments.
    
    Example:
        POST /execute
        {
            "tool_name": "list_files",
            "args": {"path": "C:\\Users\\owner\\Documents"}
        }
    """
    authenticate(x_api_key, x_request_id)
    
    # Create request context
    context = RequestContext(
        sender=x_sender or "unknown",
        raw_message=f"execute: {req.tool_name}",
        workspace=WORKSPACE,
        allowed_directories=config.get_allowed_directories(),
        allowed_tools=config.get_allowed_tools(),
    )
    
    if x_request_id:
        context.request_id = x_request_id
    
    # Get tool
    if not registry.exists(req.tool_name):
        logger.log_error(
            request_id=context.request_id,
            error_type="unknown_tool",
            error_message=f"Tool not found: {req.tool_name}",
        )
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{req.tool_name}' not found. Available tools: {', '.join(registry.list_all())}",
        )
    
    tool = registry.get(req.tool_name)
    
    # Validate arguments
    is_valid, validation_error = tool.validate_args(req.args)
    if not is_valid:
        logger.log_error(
            request_id=context.request_id,
            error_type="invalid_arguments",
            error_message=validation_error,
        )
        raise HTTPException(status_code=400, detail=validation_error)
    
    # Execute tool
    try:
        exec_context = {
            "workspace": WORKSPACE,
            "allowed_directories": config.get_allowed_directories(),
            "request_id": context.request_id,
            "sender": context.sender,
            "logger": logger,
        }
        
        result = await tool.execute(req.args, exec_context)
        
        # Log execution
        logger.log_tool_execution(
            request_id=context.request_id,
            tool_name=req.tool_name,
            arguments=req.args,
            success=result.success,
            output=result.output,
            error=result.error,
            sender=context.sender,
        )
        
        return {
            "success": result.success,
            "tool_name": req.tool_name,
            "output": result.output,
            "error": result.error,
            "request_id": context.request_id,
        }
    
    except Exception as e:
        logger.log_error(
            request_id=context.request_id,
            error_type="execution_error",
            error_message=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(e)}")


@app.post("/execute-nl")
async def execute_natural_language(
    req: ExecuteNaturalLanguageRequest,
    x_api_key: str = Header(None),
    x_request_id: str = Header(None),
    x_sender: str = Header(None),
):
    """
    Execute a natural language request. The system interprets the message,
    selects an appropriate tool, validates inputs, and executes the tool.
    
    Example:
        POST /execute-nl
        {"message": "list files in my documents"}
    """
    authenticate(x_api_key, x_request_id)
    
    # Create request context
    context = RequestContext(
        sender=x_sender or "unknown",
        raw_message=req.message,
        workspace=WORKSPACE,
        allowed_directories=config.get_allowed_directories(),
        allowed_tools=config.get_allowed_tools(),
    )
    
    if x_request_id:
        context.request_id = x_request_id
    
    # Dispatch request through tool system
    result = await dispatcher.dispatch(context)
    
    # Format response
    return {
        "success": result["success"],
        "tool_name": result["tool_name"],
        "output": result["output"],
        "error": result["error"],
        "request_id": result["request_id"],
        "sender": context.sender,
    }


# ============================================================================
# Legacy Compatibility Endpoints
# ============================================================================

@app.post("/run")
async def run_legacy_command(
    tool_name: str = None,
    args: dict = None,
    x_api_key: str = Header(None),
    x_request_id: str = Header(None),
    x_sender: str = Header(None),
):
    """
    Legacy compatibility endpoint. Forwards to new /execute endpoint.
    """
    authenticate(x_api_key, x_request_id)
    
    req = ExecuteToolRequest(tool_name=tool_name, args=args or {})
    return await execute_tool(
        req,
        x_api_key=x_api_key,
        x_request_id=x_request_id,
        x_sender=x_sender,
    )


# ============================================================================
# Startup/Shutdown
# ============================================================================

@app.on_event("startup")
def startup():
    """Log startup"""
    logger.log(
        event_type="startup",
        tools_loaded=len(registry.list_all()),
        workspace=str(WORKSPACE),
    )


@app.on_event("shutdown")
def shutdown():
    """Log shutdown"""
    logger.log(event_type="shutdown")