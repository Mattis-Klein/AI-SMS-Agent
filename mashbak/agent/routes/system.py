from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

try:
    from ..api_auth import authenticate_request
except ImportError:  # pragma: no cover - script-mode fallback
    from api_auth import authenticate_request


def create_system_router(runtime) -> APIRouter:
    router = APIRouter(tags=["system"])

    @router.get("/health")
    def health_check():
        return {
            "status": "ok",
            "workspace": str(runtime.workspace),
            "tools_loaded": len(runtime.registry.list_all()),
            "assistant_ai_enabled": bool(runtime.openai_api_key),
            "assistant_model": runtime.openai_model,
            "model_response_max_tokens": runtime.model_response_max_tokens,
            "session_context_max_turns": runtime.session_context_turns,
            "tool_timeout_seconds": runtime.default_tool_timeout_seconds,
            "email_configured": bool(runtime.summary().get("email_configured")),
            "version": "2.0.0",
        }

    @router.get("/tools")
    def list_tools(x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return {"tools": runtime.registry.get_all_info(), "count": len(runtime.registry.list_all())}

    @router.get("/tools/{tool_name}")
    def get_tool_info(tool_name: str, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        info = runtime.registry.get_info(tool_name)
        if not info:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
        return info

    @router.get("/session/{session_id}")
    def get_session_context(session_id: str, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return runtime.session_context.public_summary(session_id)

    return router