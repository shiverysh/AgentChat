import json
from typing import Any

from langchain.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from loguru import logger

from agentchat.core.models.manager import ModelManager
from agentchat.prompts.tool import RESUME_MATCH_PROMPT
from agentchat.utils.helpers import fix_json_text


@tool("resume_match", parse_docstring=True)
def resume_match(
    job_description: str,
    resume_content: str,
    target_role: str = "大模型应用开发实习生",
):
    """
    分析岗位 JD 与简历内容的匹配度，并给出简历修改建议。

    Args:
        job_description (str): 目标岗位的 JD 文本或岗位要求。
        resume_content (str): 候选人的简历文本、项目经历或技能描述。
        target_role (str): 目标岗位名称，默认是大模型应用开发实习生。

    Returns:
        str: 一份结构化的岗位匹配分析报告，包含匹配度、优势、缺口和修改建议。
    """
    return _resume_match(job_description, resume_content, target_role)


def generate_resume_match_result(
    job_description: str,
    resume_content: str,
    target_role: str = "大模型应用开发实习生",
) -> dict[str, Any]:
    if not job_description.strip():
        raise ValueError("请先提供岗位 JD 文本，我才能帮您分析岗位匹配度。")

    if not resume_content.strip():
        raise ValueError("请先提供简历内容或项目经历，我才能帮您分析岗位匹配度。")

    prompt = RESUME_MATCH_PROMPT.format(
        target_role=target_role,
        job_description=job_description,
        resume_content=resume_content,
    )

    model = ModelManager.get_conversation_model().bind(
        response_format={"type": "json_object"}
    )
    response = model.invoke(
        [SystemMessage(content="你是一名严谨的求职顾问。"), HumanMessage(content=prompt)],
        config={"callbacks": _get_usage_callbacks()},
    )
    result = _parse_resume_match_response(response.content)
    return _normalize_resume_match_result(result, target_role)


def _resume_match(job_description: str, resume_content: str, target_role: str) -> str:
    try:
        normalized_result = generate_resume_match_result(
            job_description=job_description,
            resume_content=resume_content,
            target_role=target_role,
        )
        _emit_resume_match_card(normalized_result)
        return _format_resume_match_result(normalized_result, target_role)
    except Exception as err:
        logger.error(f"resume_match tool failed: {err}")
        return f"岗位匹配分析暂时失败，请稍后重试。错误信息：{err}"


def _get_usage_callbacks() -> list[Any]:
    try:
        from agentchat.core.callbacks import usage_metadata_callback
        return [usage_metadata_callback]
    except Exception as err:
        logger.warning(f"usage metadata callback unavailable: {err}")
        return []


def _parse_resume_match_response(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        fixed_content = fix_json_text(content)
        return json.loads(fixed_content)


def _normalize_items(items: Any, limit: int = 5) -> list[str]:
    if not isinstance(items, list):
        return []

    valid_items = []
    for item in items:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned:
                valid_items.append(cleaned)
        if len(valid_items) >= limit:
            break
    return valid_items


def _normalize_resume_match_result(result: dict[str, Any], target_role: str) -> dict[str, Any]:
    match_score = result.get("match_score", 0)
    try:
        match_score = int(match_score)
    except (TypeError, ValueError):
        match_score = 0

    match_score = max(0, min(100, match_score))

    overall_summary = result.get("overall_summary", "已完成岗位与简历的基础匹配分析。")
    if not isinstance(overall_summary, str) or not overall_summary.strip():
        overall_summary = "已完成岗位与简历的基础匹配分析。"

    return {
        "target_role": target_role,
        "overall_summary": overall_summary.strip(),
        "match_score": match_score,
        "matched_strengths": _normalize_items(result.get("matched_strengths", [])),
        "missing_requirements": _normalize_items(result.get("missing_requirements", [])),
        "revision_suggestions": _normalize_items(result.get("revision_suggestions", [])),
        "interview_focus": _normalize_items(result.get("interview_focus", [])),
    }


def _emit_resume_match_card(result: dict[str, Any]) -> None:
    try:
        writer = get_stream_writer()
    except Exception:
        writer = None

    if not writer:
        return

    writer({
        "status": "END",
        "title": "简历匹配分析卡片",
        "message": "已生成结构化的岗位匹配分析结果。",
        "event_type": "resume_match_result",
        "tool_name": "resume_match",
        "structured_data": result,
    })


def _format_bullet_section(items: list[str], fallback: str) -> str:
    valid_items = [item.strip() for item in items if isinstance(item, str) and item.strip()]
    if not valid_items:
        return f"- {fallback}"
    return "\n".join(f"- {item}" for item in valid_items)


def _format_numbered_section(items: list[str], fallback: str) -> str:
    valid_items = [item.strip() for item in items if isinstance(item, str) and item.strip()]
    if not valid_items:
        return f"1. {fallback}"
    return "\n".join(f"{idx}. {item}" for idx, item in enumerate(valid_items, start=1))


def _format_resume_match_result(result: dict[str, Any], target_role: str) -> str:
    match_score = result.get("match_score", 0)
    overall_summary = result.get("overall_summary", "已完成岗位与简历的基础匹配分析。")
    matched_strengths = result.get("matched_strengths", [])
    missing_requirements = result.get("missing_requirements", [])
    revision_suggestions = result.get("revision_suggestions", [])
    interview_focus = result.get("interview_focus", [])

    return (
        f"{target_role} 匹配分析\n"
        f"综合结论：{overall_summary}\n"
        f"匹配度：{match_score}/100\n\n"
        "已匹配优势：\n"
        f"{_format_bullet_section(matched_strengths, '当前简历中已有部分相关背景，可进一步突出岗位关键词。')}\n\n"
        "主要缺口：\n"
        f"{_format_bullet_section(missing_requirements, '暂未识别出明显缺口，建议继续结合项目结果量化表达。')}\n\n"
        "简历修改建议：\n"
        f"{_format_numbered_section(revision_suggestions, '优先补充与岗位关键词强相关的项目职责、技术栈和结果指标。')}\n\n"
        "面试准备重点：\n"
        f"{_format_bullet_section(interview_focus, '准备围绕项目背景、技术方案、效果指标和个人贡献展开说明。')}"
    )
