from __future__ import annotations

from fastapi import APIRouter

try:
    from .control_board_assistants import register_assistants_routes
    from .control_board_email import register_email_routes
    from .control_board_files import register_files_routes
    from .control_board_ops import register_ops_routes
    from .control_board_overview import register_overview_routes
    from ..services.control_board import ControlBoardService
except ImportError:  # pragma: no cover - script-mode fallback
    from routes.control_board_assistants import register_assistants_routes
    from routes.control_board_email import register_email_routes
    from routes.control_board_files import register_files_routes
    from routes.control_board_ops import register_ops_routes
    from routes.control_board_overview import register_overview_routes
    from services.control_board import ControlBoardService


def create_control_board_router(runtime) -> APIRouter:
    router = APIRouter(tags=["control-board"])
    service = ControlBoardService(runtime)

    register_overview_routes(router, runtime, service)
    register_email_routes(router, runtime, service)
    register_files_routes(router, runtime, service)
    register_assistants_routes(router, runtime, service)
    register_ops_routes(router, runtime, service)

    return router