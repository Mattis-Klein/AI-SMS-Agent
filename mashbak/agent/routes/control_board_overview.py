from __future__ import annotations

from fastapi import APIRouter, Header

try:
    from ..api_auth import authenticate_request
except ImportError:  # pragma: no cover - script-mode fallback
    from api_auth import authenticate_request


def register_overview_routes(router: APIRouter, runtime, service) -> None:
    @router.get("/control-board/overview")
    def control_board_overview(x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.overview()

    @router.get("/control-board/activity")
    def control_board_activity(
        limit: int = 100,
        event_types: str = "",
        sources: str = "",
        tool_name: str = "",
        state: str = "",
        query: str = "",
        x_api_key: str = Header(None),
    ):
        authenticate_request(runtime, x_api_key)
        return service.activity(
            limit=limit,
            event_types=event_types,
            sources=sources,
            tool_name=tool_name,
            state=state,
            query=query,
        )
