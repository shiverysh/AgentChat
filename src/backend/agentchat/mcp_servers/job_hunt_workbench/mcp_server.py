import asyncio

from mcp.server.fastmcp import FastMCP

from agentchat.settings import init_app_settings

asyncio.run(init_app_settings("agentchat/config.yaml"))

from agentchat.schemas.job_hunt_workspace import (  # noqa: E402
    CreateInterviewPlanReq,
    RecordJobApplicationReq,
    SaveFollowupNotesReq,
    SaveResumeVersionReq,
)
from agentchat.services.job_hunt_workspace import JobHuntWorkspaceService  # noqa: E402

mcp = FastMCP("Job Hunt Workbench MCP")


def _format_saved_message(result: dict) -> str:
    saved_item = result.get("saved_item", {}) if isinstance(result, dict) else {}
    tags = saved_item.get("tags") or []
    tag_text = f"\n标签：{', '.join(tags)}" if tags else ""
    status = saved_item.get("status") or ""
    status_text = f"\n状态：{status}" if status else ""

    return (
        f"{result.get('message', '已保存')}\n"
        f"标题：{saved_item.get('title', '')}\n"
        f"类型：{saved_item.get('item_type', '')}\n"
        f"摘要：{saved_item.get('summary', '')}"
        f"{status_text}"
        f"{tag_text}"
    ).strip()


@mcp.tool()
async def save_resume_version(
    current_user_id: str,
    content: str,
    title: str = "",
    target_role: str = "",
    source_summary: str = "",
    highlight_keywords: list[str] | None = None,
) -> str:
    """保存一版简历改写结果到求职工作台。

    Args:
        current_user_id: 当前用户 ID，由宿主 Agent 自动注入。
        content: 需要保存的简历正文内容。
        title: 简历版本标题，可为空。
        target_role: 目标岗位名称，可为空。
        source_summary: 对这版简历的简短说明。
        highlight_keywords: 强化关键词列表。
    """
    result = await JobHuntWorkspaceService.save_resume_version(
        SaveResumeVersionReq(
            current_user_id=current_user_id,
            content=content,
            title=title,
            target_role=target_role,
            source_summary=source_summary,
            highlight_keywords=highlight_keywords or [],
        )
    )
    return _format_saved_message(result)


@mcp.tool()
async def record_job_application(
    current_user_id: str,
    position: str,
    company: str = "待补充",
    status: str = "待投递",
    jd_url: str = "",
    notes: str = "",
    match_summary: str = "",
) -> str:
    """记录一条岗位投递信息。

    Args:
        current_user_id: 当前用户 ID，由宿主 Agent 自动注入。
        position: 岗位名称。
        company: 公司名称。
        status: 当前投递状态。
        jd_url: 岗位链接。
        notes: 备注信息。
        match_summary: 匹配摘要。
    """
    result = await JobHuntWorkspaceService.record_job_application(
        RecordJobApplicationReq(
            current_user_id=current_user_id,
            position=position,
            company=company,
            status=status,
            jd_url=jd_url,
            notes=notes,
            match_summary=match_summary,
        )
    )
    return _format_saved_message(result)


@mcp.tool()
async def create_interview_plan(
    current_user_id: str,
    target_role: str,
    title: str = "",
    company: str = "",
    focus_points: list[str] | None = None,
    preparation_actions: list[str] | None = None,
    schedule_suggestion: str = "",
) -> str:
    """把面试追问结果整理成一份面试准备计划。

    Args:
        current_user_id: 当前用户 ID，由宿主 Agent 自动注入。
        target_role: 目标岗位。
        title: 面试计划标题，可为空。
        company: 公司名称。
        focus_points: 重点准备内容列表。
        preparation_actions: 准备动作清单。
        schedule_suggestion: 节奏建议。
    """
    result = await JobHuntWorkspaceService.create_interview_plan(
        CreateInterviewPlanReq(
            current_user_id=current_user_id,
            target_role=target_role,
            title=title,
            company=company,
            focus_points=focus_points or [],
            preparation_actions=preparation_actions or [],
            schedule_suggestion=schedule_suggestion,
        )
    )
    return _format_saved_message(result)


@mcp.tool()
async def save_followup_notes(
    current_user_id: str,
    notes: str,
    title: str = "",
    target_role: str = "",
    tags: list[str] | None = None,
    question_count: int = 0,
) -> str:
    """保存一份面试追问笔记。

    Args:
        current_user_id: 当前用户 ID，由宿主 Agent 自动注入。
        notes: 追问笔记正文。
        title: 笔记标题，可为空。
        target_role: 目标岗位。
        tags: 笔记标签列表。
        question_count: 追问数量。
    """
    result = await JobHuntWorkspaceService.save_followup_notes(
        SaveFollowupNotesReq(
            current_user_id=current_user_id,
            notes=notes,
            title=title,
            target_role=target_role,
            tags=tags or [],
            question_count=question_count,
        )
    )
    return _format_saved_message(result)


if __name__ == "__main__":
    mcp.run(transport="stdio")
