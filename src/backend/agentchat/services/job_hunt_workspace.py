import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from agentchat.database.dao.job_hunt_workspace import JobHuntWorkspaceDao
from agentchat.database.models.job_hunt_workspace import JobHuntWorkspaceItem
from agentchat.schemas.job_hunt_workspace import (
    CreateInterviewPlanReq,
    RecordJobApplicationReq,
    SaveFollowupNotesReq,
    SaveResumeVersionReq,
)

JOB_HUNT_MCP_SERVER_NAME = "求职工作台"
JOB_HUNT_MCP_AS_TOOL_NAME = "job_hunt_board"
JOB_HUNT_MCP_DESCRIPTION = (
    "当用户需要保存简历版本、记录投递、生成面试计划或保存追问笔记时使用。"
    "子智能体可以调用多个自身工具，所以将用户问题整合询问一次即可。"
)
JOB_HUNT_STDIO_URL = "stdio://job-hunt-workbench"


def _get_backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_job_hunt_stdio_config() -> dict[str, Any]:
    backend_root = _get_backend_root()
    python_path = str(backend_root)
    existing_python_path = os.environ.get("PYTHONPATH", "").strip()
    merged_python_path = (
        f"{python_path}{os.pathsep}{existing_python_path}"
        if existing_python_path
        else python_path
    )

    return {
        "command": sys.executable,
        "args": ["-m", "agentchat.mcp_servers.job_hunt_workbench.mcp_server"],
        "cwd": python_path,
        "env": {
            "PYTHONPATH": merged_python_path,
        },
    }


def _body_property(
    prop_type: str,
    description: str,
    *,
    default: Any | None = None,
    items: dict[str, Any] | None = None,
) -> dict[str, Any]:
    property_schema: dict[str, Any] = {
        "type": prop_type,
        "description": description,
        "x-position": "body",
    }
    if default is not None:
        property_schema["default"] = default
    if items is not None:
        property_schema["items"] = items
    return property_schema


def get_job_hunt_mcp_tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "name": "save_resume_version",
            "description": "保存一版简历改写结果到求职工作台，便于后续继续投递或复盘。",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_user_id": _body_property("string", "系统自动注入的当前用户 ID，无需手动填写。"),
                    "title": _body_property("string", "简历版本标题，可为空。", default=""),
                    "target_role": _body_property("string", "该版本对应的目标岗位。", default=""),
                    "content": _body_property("string", "需要保存的简历正文内容。"),
                    "source_summary": _body_property("string", "对该版本的简短说明。", default=""),
                    "highlight_keywords": _body_property(
                        "array",
                        "该版本强化的关键词列表。",
                        default=[],
                        items={"type": "string"},
                    ),
                },
                "required": ["current_user_id", "content"],
                "additionalProperties": False,
            },
        },
        {
            "name": "record_job_application",
            "description": "记录一条岗位投递信息，包括公司、岗位、状态和备注。",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_user_id": _body_property("string", "系统自动注入的当前用户 ID，无需手动填写。"),
                    "company": _body_property("string", "公司名称。", default="待补充"),
                    "position": _body_property("string", "岗位名称。"),
                    "status": _body_property("string", "当前投递状态。", default="待投递"),
                    "jd_url": _body_property("string", "岗位 JD 链接。", default=""),
                    "notes": _body_property("string", "补充备注。", default=""),
                    "match_summary": _body_property("string", "匹配分析摘要。", default=""),
                },
                "required": ["current_user_id", "position"],
                "additionalProperties": False,
            },
        },
        {
            "name": "create_interview_plan",
            "description": "把面试追问结果整理成一份可执行的面试准备计划。",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_user_id": _body_property("string", "系统自动注入的当前用户 ID，无需手动填写。"),
                    "title": _body_property("string", "面试计划标题，可为空。", default=""),
                    "target_role": _body_property("string", "目标岗位。"),
                    "company": _body_property("string", "公司名称。", default=""),
                    "focus_points": _body_property(
                        "array",
                        "面试重点列表。",
                        default=[],
                        items={"type": "string"},
                    ),
                    "preparation_actions": _body_property(
                        "array",
                        "建议准备动作清单。",
                        default=[],
                        items={"type": "string"},
                    ),
                    "schedule_suggestion": _body_property("string", "准备节奏建议。", default=""),
                },
                "required": ["current_user_id", "target_role"],
                "additionalProperties": False,
            },
        },
        {
            "name": "save_followup_notes",
            "description": "保存一份面试追问笔记，便于后续持续复盘和演练。",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_user_id": _body_property("string", "系统自动注入的当前用户 ID，无需手动填写。"),
                    "title": _body_property("string", "笔记标题，可为空。", default=""),
                    "target_role": _body_property("string", "目标岗位。", default=""),
                    "notes": _body_property("string", "需要保存的追问笔记正文。"),
                    "tags": _body_property(
                        "array",
                        "笔记标签列表。",
                        default=[],
                        items={"type": "string"},
                    ),
                    "question_count": _body_property("integer", "追问数量。", default=0),
                },
                "required": ["current_user_id", "notes"],
                "additionalProperties": False,
            },
        },
    ]


def get_job_hunt_mcp_server_params() -> list[dict[str, Any]]:
    return [
        {
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": {
                "type": tool["parameters"]["type"],
                "properties": {
                    key: {
                        schema_key: schema_value
                        for schema_key, schema_value in value.items()
                        if schema_key != "x-position"
                    }
                    for key, value in tool["parameters"]["properties"].items()
                },
                "required": tool["parameters"].get("required", []),
                "additionalProperties": tool["parameters"].get("additionalProperties", False),
            },
        }
        for tool in get_job_hunt_mcp_tool_specs()
    ]


def get_job_hunt_mcp_tool_names() -> list[str]:
    return [tool["name"] for tool in get_job_hunt_mcp_tool_specs()]


class JobHuntWorkspaceService:
    @classmethod
    async def save_resume_version(cls, req: SaveResumeVersionReq) -> dict[str, Any]:
        title = req.title.strip() or cls._build_resume_version_title(req.target_role)
        summary = req.source_summary.strip() or cls._truncate(req.content, 96)
        item = await JobHuntWorkspaceDao.create_item(
            JobHuntWorkspaceItem(
                user_id=req.current_user_id,
                item_type="resume_version",
                title=title,
                summary=summary,
                content=req.content.strip(),
                tags=req.highlight_keywords,
                payload={
                    "target_role": req.target_role.strip(),
                    "highlight_keywords": req.highlight_keywords,
                },
            )
        )
        return cls._build_saved_response("已保存简历版本", item)

    @classmethod
    async def record_job_application(cls, req: RecordJobApplicationReq) -> dict[str, Any]:
        company = req.company.strip() or "待补充"
        position = req.position.strip()
        title = f"{company} / {position}"
        summary = req.notes.strip() or req.match_summary.strip() or f"当前状态：{req.status.strip() or '待投递'}"
        item = await JobHuntWorkspaceDao.create_item(
            JobHuntWorkspaceItem(
                user_id=req.current_user_id,
                item_type="job_application",
                title=title,
                summary=summary,
                content=req.match_summary.strip(),
                status=req.status.strip() or "待投递",
                payload={
                    "company": company,
                    "position": position,
                    "jd_url": req.jd_url.strip(),
                    "notes": req.notes.strip(),
                },
            )
        )
        return cls._build_saved_response("已记录岗位投递", item)

    @classmethod
    async def create_interview_plan(cls, req: CreateInterviewPlanReq) -> dict[str, Any]:
        title = req.title.strip() or f"{req.target_role.strip()} 面试计划"
        summary = req.schedule_suggestion.strip() or "已生成一份新的面试准备计划。"
        content = "\n".join(
            part for part in [
                "面试重点：\n" + "\n".join(f"- {item}" for item in req.focus_points) if req.focus_points else "",
                "准备动作：\n" + "\n".join(f"- {item}" for item in req.preparation_actions) if req.preparation_actions else "",
                f"节奏建议：{req.schedule_suggestion.strip()}" if req.schedule_suggestion.strip() else "",
            ]
            if part
        ).strip()
        item = await JobHuntWorkspaceDao.create_item(
            JobHuntWorkspaceItem(
                user_id=req.current_user_id,
                item_type="interview_plan",
                title=title,
                summary=summary,
                content=content,
                payload={
                    "target_role": req.target_role.strip(),
                    "company": req.company.strip(),
                    "focus_points": req.focus_points,
                    "preparation_actions": req.preparation_actions,
                    "schedule_suggestion": req.schedule_suggestion.strip(),
                },
            )
        )
        return cls._build_saved_response("已创建面试计划", item)

    @classmethod
    async def save_followup_notes(cls, req: SaveFollowupNotesReq) -> dict[str, Any]:
        title = req.title.strip() or cls._build_followup_note_title(req.target_role)
        summary = cls._truncate(req.notes, 96)
        item = await JobHuntWorkspaceDao.create_item(
            JobHuntWorkspaceItem(
                user_id=req.current_user_id,
                item_type="followup_note",
                title=title,
                summary=summary,
                content=req.notes.strip(),
                tags=req.tags,
                payload={
                    "target_role": req.target_role.strip(),
                    "tags": req.tags,
                    "question_count": req.question_count,
                },
            )
        )
        return cls._build_saved_response("已保存追问笔记", item)

    @classmethod
    async def list_workspace_items(cls, user_id: str, limit: int = 24) -> dict[str, Any]:
        items = await JobHuntWorkspaceDao.list_items_by_user(user_id, max(1, min(limit, 100)))
        normalized_items = [cls._normalize_item(item) for item in items]
        stats = {
            "total": len(normalized_items),
            "resume_version": sum(1 for item in normalized_items if item["item_type"] == "resume_version"),
            "job_application": sum(1 for item in normalized_items if item["item_type"] == "job_application"),
            "interview_plan": sum(1 for item in normalized_items if item["item_type"] == "interview_plan"),
            "followup_note": sum(1 for item in normalized_items if item["item_type"] == "followup_note"),
        }
        return {
            "stats": stats,
            "items": normalized_items,
        }

    @classmethod
    async def delete_workspace_item(cls, user_id: str, item_id: str) -> None:
        await JobHuntWorkspaceDao.delete_item(item_id, user_id)

    @classmethod
    def _build_saved_response(cls, message: str, item: JobHuntWorkspaceItem) -> dict[str, Any]:
        return {
            "message": message,
            "saved_item": cls._normalize_item(item),
        }

    @classmethod
    def _normalize_item(cls, item: JobHuntWorkspaceItem) -> dict[str, Any]:
        data = item.to_dict()
        data["display_time"] = cls._format_display_time(item.create_time)
        return data

    @staticmethod
    def _build_resume_version_title(target_role: str) -> str:
        normalized_role = target_role.strip() or "简历"
        return f"{normalized_role} 版本 {datetime.now().strftime('%m-%d %H:%M')}"

    @staticmethod
    def _build_followup_note_title(target_role: str) -> str:
        normalized_role = target_role.strip() or "项目"
        return f"{normalized_role} 追问笔记"

    @staticmethod
    def _truncate(text: str, max_length: int) -> str:
        normalized = (text or "").strip()
        if len(normalized) <= max_length:
            return normalized
        return normalized[:max_length].rstrip() + "..."

    @staticmethod
    def _format_display_time(value: datetime | None) -> str:
        if not value:
            return ""
        return value.strftime("%m-%d %H:%M")
