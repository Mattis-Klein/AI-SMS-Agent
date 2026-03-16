from __future__ import annotations

from typing import Optional

from fastapi import HTTPException


def authenticate_request(runtime, api_key: Optional[str], request_id: Optional[str] = None) -> None:
    if api_key != runtime.api_key:
        runtime.logger.log_error(
            request_id=request_id or "unknown",
            error_type="auth_failed",
            error_message="Invalid API key",
        )
        raise HTTPException(status_code=401, detail="Unauthorized")