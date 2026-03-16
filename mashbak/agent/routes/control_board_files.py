from __future__ import annotations

from fastapi import APIRouter, Header

try:
    from ..api_auth import authenticate_request
    from ..api_models import FilesPolicySaveRequest, PathTestRequest
except ImportError:  # pragma: no cover - script-mode fallback
    from api_auth import authenticate_request
    from api_models import FilesPolicySaveRequest, PathTestRequest


def register_files_routes(router: APIRouter, runtime, service) -> None:
    @router.get("/control-board/files-policy")
    def control_board_files_policy(x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.files_policy()

    @router.post("/control-board/files-policy/save")
    def control_board_files_policy_save(req: FilesPolicySaveRequest, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.save_files_policy(req.allowed_directories)

    @router.post("/control-board/files-policy/test-path")
    def control_board_files_policy_test_path(req: PathTestRequest, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.test_path_allowed(req.path)
