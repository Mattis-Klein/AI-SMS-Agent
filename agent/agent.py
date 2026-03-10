"""
AI-SMS-Agent FastAPI application

Tool-based architecture for executing safe commands via SMS.
All requests are routed through the tool dispatcher, which validates
inputs and logs all activities.
"""

from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from runtime import create_runtime


# ============================================================================
# Initialization
# ============================================================================

app = FastAPI(title="AI-SMS-Agent", version="2.0.0")
runtime = create_runtime()


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
    if api_key != runtime.api_key:
        runtime.logger.log_error(
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
        "workspace": str(runtime.workspace),
        "tools_loaded": len(runtime.registry.list_all()),
        "version": "2.0.0",
    }


@app.get("/tools")
def list_tools(x_api_key: str = Header(None)):
    """List all available tools with descriptions"""
    authenticate(x_api_key)
    
    return {
        "tools": runtime.registry.get_all_info(),
        "count": len(runtime.registry.list_all()),
    }


@app.get("/tools/{tool_name}")
def get_tool_info(tool_name: str, x_api_key: str = Header(None)):
    """Get information about a specific tool"""
    authenticate(x_api_key)
    
    info = runtime.registry.get_info(tool_name)
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

    result = await runtime.execute_tool(
        tool_name=req.tool_name,
        args=req.args,
        sender=x_sender or "unknown",
        request_id=x_request_id,
    )

    if result["tool_name"] is None and "not found" in (result.get("error") or ""):
        raise HTTPException(status_code=404, detail=result["error"])

    trace = result.get("trace") or {}
    if not result["success"] and trace.get("validation_status") == "failed":
        raise HTTPException(status_code=400, detail=result["error"])

    return {
        "success": result["success"],
        "tool_name": result["tool_name"],
        "output": result["output"],
        "error": result["error"],
        "request_id": result["request_id"],
        "trace": result.get("trace"),
    }


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

    result = await runtime.execute_nl(
        message=req.message,
        sender=x_sender or "unknown",
        request_id=x_request_id,
    )
    
    # Format response
    return {
        "success": result["success"],
        "tool_name": result["tool_name"],
        "output": result["output"],
        "error": result["error"],
        "request_id": result["request_id"],
        "sender": x_sender or "unknown",
        "trace": result.get("trace"),
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
    runtime.logger.log(
        event_type="startup",
        tools_loaded=len(runtime.registry.list_all()),
        workspace=str(runtime.workspace),
    )


@app.on_event("shutdown")
def shutdown():
    """Log shutdown"""
    runtime.logger.log(event_type="shutdown")