from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

try:
    from ..api_auth import authenticate_request
    from ..api_models import BucherimSmsRequest, ExecuteNaturalLanguageRequest, ExecuteToolRequest
except ImportError:  # pragma: no cover - script-mode fallback
    from api_auth import authenticate_request
    from api_models import BucherimSmsRequest, ExecuteNaturalLanguageRequest, ExecuteToolRequest


def create_execution_router(runtime) -> APIRouter:
    router = APIRouter(tags=["execution"])

    @router.post("/execute")
    async def execute_tool(
        req: ExecuteToolRequest,
        x_api_key: str = Header(None),
        x_request_id: str = Header(None),
        x_sender: str = Header(None),
        x_source: str = Header(None),
    ):
        authenticate_request(runtime, x_api_key, x_request_id)
        result = await runtime.execute_tool(
            tool_name=req.tool_name,
            args=req.args,
            sender=x_sender or "unknown",
            request_id=x_request_id,
            source=x_source,
        )
        if result["tool_name"] is None and "not found" in (result.get("error") or ""):
            raise HTTPException(status_code=404, detail=result["error"])
        if not result["success"] and "not allowed" in (result.get("error") or ""):
            raise HTTPException(status_code=403, detail=result["error"])
        trace = result.get("trace") or {}
        if not result["success"] and trace.get("validation_status") == "failed":
            raise HTTPException(status_code=400, detail=result["error"])
        return {
            "success": result["success"],
            "tool_name": result["tool_name"],
            "output": result["output"],
            "error": result["error"],
            "error_type": result.get("error_type"),
            "missing_config_fields": result.get("missing_config_fields"),
            "remediation": result.get("remediation"),
            "request_id": result["request_id"],
            "source": result.get("source", x_source or "unknown"),
            "trace": result.get("trace"),
        }

    @router.post("/execute-nl")
    async def execute_natural_language(
        req: ExecuteNaturalLanguageRequest,
        x_api_key: str = Header(None),
        x_request_id: str = Header(None),
        x_sender: str = Header(None),
        x_source: str = Header(None),
    ):
        authenticate_request(runtime, x_api_key, x_request_id)
        result = await runtime.execute_nl(
            message=req.message,
            sender=x_sender or "unknown",
            request_id=x_request_id,
            source=x_source,
            owner_unlocked=req.owner_unlocked,
        )
        return {
            "success": result["success"],
            "tool_name": result["tool_name"],
            "output": result["output"],
            "error": result["error"],
            "error_type": result.get("error_type"),
            "missing_config_fields": result.get("missing_config_fields"),
            "remediation": result.get("remediation"),
            "request_id": result["request_id"],
            "sender": x_sender or "unknown",
            "source": result.get("source", x_source or "unknown"),
            "data": result.get("data"),
            "trace": result.get("trace"),
        }

    @router.post("/bucherim/sms")
    async def execute_bucherim_sms(req: BucherimSmsRequest, x_api_key: str = Header(None), x_request_id: str = Header(None)):
        authenticate_request(runtime, x_api_key, x_request_id)
        result = await runtime.execute_bucherim_sms(
            sender=req.from_number,
            recipient=req.to_number,
            body=req.body,
            request_id=x_request_id or "unknown",
            message_sid=req.message_sid,
            account_sid=req.account_sid,
            media=[item.model_dump() for item in req.media],
        )
        return {
            "success": True,
            "reply": result.get("reply", ""),
            "full_reply": result.get("full_reply", result.get("reply", "")),
            "status": result.get("status"),
            "response_mode": result.get("response_mode"),
            "normalized_sender": result.get("normalized_sender"),
            "normalized_recipient": result.get("normalized_recipient"),
            "media_count": result.get("media_count", 0),
            "outbound_media": result.get("outbound_media", []),
            "request_id": x_request_id or "unknown",
        }

    @router.post("/run")
    async def run_legacy_command(
        tool_name: str = None,
        args: dict = None,
        x_api_key: str = Header(None),
        x_request_id: str = Header(None),
        x_sender: str = Header(None),
        x_source: str = Header(None),
    ):
        authenticate_request(runtime, x_api_key, x_request_id)
        req = ExecuteToolRequest(tool_name=tool_name, args=args or {})
        return await execute_tool(req, x_api_key=x_api_key, x_request_id=x_request_id, x_sender=x_sender, x_source=x_source)

    return router