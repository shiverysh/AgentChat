from fastapi import APIRouter, Depends, Query, HTTPException
from agentchat.api.services.dialog import DialogService
from agentchat.api.services.history import HistoryService
from agentchat.api.services.user import get_login_user, UserPayload
from agentchat.api.responses.builder import resp_200, resp_500, UnifiedResponseModel
from loguru import logger

router = APIRouter(tags=["History"])

@router.get("/history", response_model=UnifiedResponseModel)
async def get_dialog_history(dialog_id: str = Query(..., description="对话的ID", embed=True),
                             login_user: UserPayload = Depends(get_login_user)):
    try:
        await DialogService.verify_user_permission(dialog_id, login_user.user_id)
        results = await HistoryService.get_dialog_history(dialog_id=dialog_id)
        return resp_200(data=results)
    except HTTPException as err:
        return resp_500(code=err.status_code, message=str(err.detail))
    except Exception as err:
        logger.error(err)
        return resp_500(message=str(err))
