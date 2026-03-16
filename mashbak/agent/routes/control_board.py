from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

try:
    from ..api_auth import authenticate_request
    from ..api_models import (
        EmailAccountActionRequest,
        EmailAccountSaveRequest,
        FilesPolicySaveRequest,
        PathTestRequest,
        RoutingApproveRequest,
        RoutingDeactivateRequest,
    )
    from ..services.control_board import ControlBoardService
except ImportError:  # pragma: no cover - script-mode fallback
    from api_auth import authenticate_request
    from api_models import (
        EmailAccountActionRequest,
        EmailAccountSaveRequest,
        FilesPolicySaveRequest,
        PathTestRequest,
        RoutingApproveRequest,
        RoutingDeactivateRequest,
    )
    from services.control_board import ControlBoardService


def create_control_board_router(runtime) -> APIRouter:
    router = APIRouter(tags=["control-board"])
    service = ControlBoardService(runtime)

    @router.get("/control-board/overview")
    def control_board_overview(x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.overview()

    @router.get("/control-board/activity")
    def control_board_activity(limit: int = 100, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.activity(limit=limit)

    @router.get("/control-board/email-accounts")
    def control_board_email_accounts(x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.email_accounts_summary()

    @router.post("/control-board/email-accounts/save")
    def control_board_email_accounts_save(req: EmailAccountSaveRequest, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.save_email_account(**req.model_dump())

    @router.post("/control-board/email-accounts/delete")
    def control_board_email_accounts_delete(req: EmailAccountActionRequest, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.delete_email_account(req.account_id)

    @router.post("/control-board/email-accounts/set-default")
    def control_board_email_accounts_set_default(req: EmailAccountActionRequest, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.set_default_email_account(req.account_id)

    @router.post("/control-board/email-accounts/test")
    def control_board_email_accounts_test(req: EmailAccountActionRequest, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.test_email_account(req.account_id)

    @router.get("/control-board/email-config")
    def control_board_email_config_compat(x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        payload = service.email_accounts_summary()
        default_id = payload.get("default_account_id")
        account = next((row for row in payload.get("accounts") or [] if row.get("account_id") == default_id), None)
        if not account:
            return {
                "provider": "imap",
                "email_address": "",
                "password_set": False,
                "imap_host": "",
                "imap_port": 993,
                "use_ssl": True,
                "mailbox": "INBOX",
            }
        return {
            "provider": account.get("provider") or "imap",
            "email_address": account.get("email_address") or "",
            "password_set": bool(account.get("password_set")),
            "imap_host": account.get("imap_host") or "",
            "imap_port": account.get("imap_port") or 993,
            "use_ssl": bool(account.get("use_ssl", True)),
            "mailbox": account.get("mailbox") or "INBOX",
            "account_id": account.get("account_id"),
        }

    @router.post("/control-board/email-config/save")
    def control_board_email_save_compat(req: EmailAccountSaveRequest, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.save_email_account(**req.model_dump())

    @router.post("/control-board/email-config/test")
    def control_board_email_test_compat(x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        payload = service.email_accounts_summary()
        return service.test_email_account(payload.get("default_account_id"))

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

    @router.get("/control-board/assistants")
    def control_board_assistants(x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.assistants()

    @router.get("/control-board/routing")
    def control_board_routing(x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        return service.routing()

    @router.get("/control-board/routing/member/{phone_number}")
    def control_board_routing_member(phone_number: str, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        try:
            return service.routing_member(phone_number)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.post("/control-board/routing/approve")
    def control_board_routing_approve(req: RoutingApproveRequest, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        try:
            return {"success": True, **service.approve_member(req.phone_number)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.post("/control-board/routing/block")
    def control_board_routing_block(req: RoutingDeactivateRequest, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        try:
            return {"success": True, **service.block_member(req.phone_number)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.post("/control-board/routing/deactivate")
    def control_board_routing_deactivate(req: RoutingDeactivateRequest, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        try:
            return {"success": True, **service.block_member(req.phone_number)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    return router