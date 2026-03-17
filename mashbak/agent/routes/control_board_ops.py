from __future__ import annotations

from fastapi import APIRouter, Header

try:
    from ..api_auth import authenticate_request
    from ..api_models import ApprovalActionRequest, PersonalContextSaveRequest, ToolPermissionUpdateRequest
except ImportError:  # pragma: no cover - script-mode fallback
    from api_auth import authenticate_request
    from api_models import ApprovalActionRequest, PersonalContextSaveRequest, ToolPermissionUpdateRequest


def register_ops_routes(router: APIRouter, runtime, service) -> None:
    @router.get("/control-board/tools-permissions")
    def control_board_tools_permissions(x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.tools_permissions()

    @router.get("/control-board/tools_permissions")
    def control_board_tools_permissions_alias(x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.tools_permissions()

    @router.post("/control-board/tools-permissions/update")
    def control_board_tools_permissions_update(req: ToolPermissionUpdateRequest, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        settings = {
            "enabled": req.enabled,
            "allowed_sources": req.allowed_sources,
            "requires_approval": req.requires_approval,
            "requires_unlocked_desktop": req.requires_unlocked_desktop,
            "scope": req.scope,
        }
        clean = {k: v for k, v in settings.items() if v is not None}
        return service.update_tool_permission(req.tool_name, clean)

    @router.post("/control-board/tools_permissions/update")
    def control_board_tools_permissions_update_alias(req: ToolPermissionUpdateRequest, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        settings = {
            "enabled": req.enabled,
            "allowed_sources": req.allowed_sources,
            "requires_approval": req.requires_approval,
            "requires_unlocked_desktop": req.requires_unlocked_desktop,
            "scope": req.scope,
        }
        clean = {k: v for k, v in settings.items() if v is not None}
        return service.update_tool_permission(req.tool_name, clean)

    @router.get("/control-board/approvals")
    def control_board_approvals(limit: int = 80, status: str = "", x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.approvals(limit=limit, status=status)

    @router.post("/control-board/approvals/approve-run")
    async def control_board_approvals_approve_run(req: ApprovalActionRequest, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return await service.approve_and_run(req.approval_id, reviewer=req.reviewer)

    @router.post("/control-board/approvals/approve")
    def control_board_approvals_approve(req: ApprovalActionRequest, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.approve_approval(req.approval_id, reviewer=req.reviewer)

    @router.post("/control-board/approvals/run")
    async def control_board_approvals_run(req: ApprovalActionRequest, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return await service.run_approved(req.approval_id, reviewer=req.reviewer)

    @router.post("/control-board/approvals/reject")
    def control_board_approvals_reject(req: ApprovalActionRequest, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.reject_approval(req.approval_id, reviewer=req.reviewer)

    @router.get("/control-board/tasks")
    def control_board_tasks(limit: int = 80, status: str = "", x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.tasks(limit=limit, status=status)

    @router.get("/control-board/personal-context")
    def control_board_personal_context(x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.get_personal_context()

    @router.get("/control-board/personal_context")
    def control_board_personal_context_alias(x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.get_personal_context()

    @router.post("/control-board/personal-context/save")
    def control_board_personal_context_save(req: PersonalContextSaveRequest, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.save_personal_context(req.model_dump())

    @router.post("/control-board/personal_context/save")
    def control_board_personal_context_save_alias(req: PersonalContextSaveRequest, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.save_personal_context(req.model_dump())
