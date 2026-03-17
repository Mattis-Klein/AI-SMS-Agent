from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

try:
    from ..api_auth import authenticate_request
    from ..api_models import AssistantTemplateUpdateRequest, RoutingApproveRequest, RoutingDeactivateRequest
except ImportError:  # pragma: no cover - script-mode fallback
    from api_auth import authenticate_request
    from api_models import AssistantTemplateUpdateRequest, RoutingApproveRequest, RoutingDeactivateRequest


def register_assistants_routes(router: APIRouter, runtime, service) -> None:
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

    @router.post("/control-board/assistants/template/update")
    def control_board_assistants_template_update(req: AssistantTemplateUpdateRequest, x_api_key: str = Header(None)):
        authenticate_request(runtime, x_api_key)
        try:
            return service.update_assistant_template(req.template_key, req.template_text)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
