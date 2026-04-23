from fastapi import APIRouter, Depends, Query

from agentchat.api.responses.builder import UnifiedResponseModel, resp_200
from agentchat.api.services.user import UserPayload, get_login_user
from agentchat.schemas.job_hunt_workspace import (
    CreateInterviewPlanReq,
    RecordJobApplicationReq,
    SaveFollowupNotesReq,
    SaveResumeVersionReq,
)
from agentchat.services.job_hunt_workspace import JobHuntWorkspaceService

router = APIRouter(prefix="/job_hunt/workbench", tags=["Job-Hunt-Workbench"])


@router.get("", response_model=UnifiedResponseModel)
async def get_job_hunt_workbench(
    limit: int = Query(default=24, ge=1, le=100),
    login_user: UserPayload = Depends(get_login_user),
):
    data = await JobHuntWorkspaceService.list_workspace_items(login_user.user_id, limit)
    return resp_200(data=data)


@router.delete("/{item_id}", response_model=UnifiedResponseModel)
async def delete_job_hunt_workbench_item(
    item_id: str,
    login_user: UserPayload = Depends(get_login_user),
):
    await JobHuntWorkspaceService.delete_workspace_item(login_user.user_id, item_id)
    return resp_200(message="删除成功")


@router.post("/mcp/save_resume_version", include_in_schema=False)
async def mcp_save_resume_version(req: SaveResumeVersionReq):
    return await JobHuntWorkspaceService.save_resume_version(req)


@router.post("/mcp/record_job_application", include_in_schema=False)
async def mcp_record_job_application(req: RecordJobApplicationReq):
    return await JobHuntWorkspaceService.record_job_application(req)


@router.post("/mcp/create_interview_plan", include_in_schema=False)
async def mcp_create_interview_plan(req: CreateInterviewPlanReq):
    return await JobHuntWorkspaceService.create_interview_plan(req)


@router.post("/mcp/save_followup_notes", include_in_schema=False)
async def mcp_save_followup_notes(req: SaveFollowupNotesReq):
    return await JobHuntWorkspaceService.save_followup_notes(req)
