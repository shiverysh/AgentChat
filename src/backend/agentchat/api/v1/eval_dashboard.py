from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from agentchat.api.responses.builder import resp_200
from agentchat.api.services.eval_dashboard import EvalDashboardRunService, EvalDashboardService
from agentchat.api.services.user import UserPayload, get_login_user
from agentchat.schemas.eval_dashboard import EvalRunRequest

router = APIRouter(tags=["Eval-Dashboard"])


@router.get("/eval_dashboard/overview", summary="获取 Agent Eval 看板总览")
async def get_eval_dashboard_overview(login_user: UserPayload = Depends(get_login_user)):
    try:
        _ = login_user.user_id
        result = await EvalDashboardService.get_overview()
        return resp_200(data=result)
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


@router.get("/eval_dashboard/report", summary="按类别获取 Agent Eval 报告详情")
async def get_eval_dashboard_report(
    category: Literal["latest", "history", "compare"] = Query(default="latest"),
    report_name: str | None = Query(default=None),
    login_user: UserPayload = Depends(get_login_user),
):
    try:
        _ = login_user.user_id
        result = await EvalDashboardService.get_report(category, report_name)
        return resp_200(data=result)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


@router.post("/eval_dashboard/run", summary="一键触发 Agent Eval 运行")
async def start_eval_dashboard_run(
    req: EvalRunRequest,
    login_user: UserPayload = Depends(get_login_user),
):
    try:
        result = await EvalDashboardRunService.start_run(
            user_id=login_user.user_id,
            run_request=req.model_dump(),
        )
        return resp_200(data=result)
    except RuntimeError as err:
        raise HTTPException(status_code=409, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))


@router.get("/eval_dashboard/run_status", summary="获取 Agent Eval 运行状态")
async def get_eval_dashboard_run_status(
    task_id: str | None = Query(default=None),
    login_user: UserPayload = Depends(get_login_user),
):
    try:
        result = await EvalDashboardRunService.get_status(
            user_id=login_user.user_id,
            task_id=task_id,
        )
        return resp_200(data=result)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
