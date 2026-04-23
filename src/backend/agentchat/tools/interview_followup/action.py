import json
from typing import Any

from langchain.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from loguru import logger

from agentchat.core.models.manager import ModelManager
from agentchat.prompts.tool import INTERVIEW_FOLLOWUP_PROMPT
from agentchat.utils.helpers import fix_json_text


@tool("interview_followup", parse_docstring=True)
def interview_followup(
    project_content: str,
    target_role: str = "大模型应用开发实习生",
    job_description: str = "",
):
    """
    根据项目经历生成面试官追问点和回答框架。

    Args:
        project_content (str): 项目经历、实习经历或待准备面试的内容。
        target_role (str): 目标岗位名称，默认是大模型应用开发实习生。
        job_description (str): 可选的岗位 JD 文本，提供后会结合岗位要求生成追问。

    Returns:
        str: 包含高频追问、作答框架和风险提示的面试准备结果。
    """
    return _interview_followup(project_content, target_role, job_description)


def generate_interview_followup_result(
    project_content: str,
    target_role: str = "大模型应用开发实习生",
    job_description: str = "",
) -> dict[str, Any]:
    if not project_content.strip():
        raise ValueError("请先提供需要准备面试的项目经历或简历内容，我才能帮您生成追问和回答框架。")

    prompt = INTERVIEW_FOLLOWUP_PROMPT.format(
        target_role=target_role,
        job_description=job_description.strip() or "未提供岗位 JD，请按目标岗位的通用考察方向进行追问设计。",
        project_content=project_content,
    )

    model = ModelManager.get_conversation_model().bind(
        response_format={"type": "json_object"}
    )
    response = model.invoke(
        [SystemMessage(content="你是一名严谨的面试辅导助手。"), HumanMessage(content=prompt)],
        config={"callbacks": _get_usage_callbacks()},
    )
    result = _parse_interview_followup_response(response.content)
    return _normalize_interview_followup_result(result, target_role)


def _interview_followup(project_content: str, target_role: str, job_description: str) -> str:
    try:
        normalized_result = generate_interview_followup_result(
            project_content=project_content,
            target_role=target_role,
            job_description=job_description,
        )
        _emit_interview_followup_card(normalized_result)
        return _format_interview_followup_result(normalized_result, target_role)
    except Exception as err:
        logger.error(f"interview_followup tool failed: {err}")
        return f"面试追问生成暂时失败，请稍后重试。错误信息：{err}"


def _get_usage_callbacks() -> list[Any]:
    try:
        from agentchat.core.callbacks import usage_metadata_callback
        return [usage_metadata_callback]
    except Exception as err:
        logger.warning(f"usage metadata callback unavailable: {err}")
        return []


def _parse_interview_followup_response(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        fixed_content = fix_json_text(content)
        return json.loads(fixed_content)


def _normalize_items(items: Any, limit: int = 6) -> list[str]:
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


def _normalize_interview_pairs(items: Any, limit: int = 5) -> list[dict[str, str]]:
    if not isinstance(items, list):
        return []

    normalized_items = []
    for item in items:
        if not isinstance(item, dict):
            continue

        question = item.get("question", "")
        answer_outline = item.get("answer_outline", "")
        dimension = item.get("dimension", "")
        why_it_matters = item.get("why_it_matters", "")

        if not isinstance(question, str) or not question.strip():
            continue

        normalized_items.append({
            "dimension": dimension.strip() if isinstance(dimension, str) else "",
            "question": question.strip(),
            "answer_outline": answer_outline.strip() if isinstance(answer_outline, str) else "",
            "why_it_matters": why_it_matters.strip() if isinstance(why_it_matters, str) else "",
        })

        if len(normalized_items) >= limit:
            break

    return normalized_items


def _normalize_interview_followup_result(result: dict[str, Any], target_role: str) -> dict[str, Any]:
    overall_summary = result.get("overall_summary", "已按目标岗位整理主要追问方向。")
    if not isinstance(overall_summary, str) or not overall_summary.strip():
        overall_summary = "已按目标岗位整理主要追问方向。"

    return {
        "target_role": target_role,
        "overall_summary": overall_summary.strip(),
        "question_answer_pairs": _normalize_interview_pairs(result.get("question_answer_pairs", []), limit=5),
        "deep_dive_points": _normalize_items(result.get("deep_dive_points", []), limit=5),
        "risk_points": _normalize_items(result.get("risk_points", []), limit=5),
    }


def _format_bullet_section(items: list[str], fallback: str) -> str:
    valid_items = [item.strip() for item in items if isinstance(item, str) and item.strip()]
    if not valid_items:
        return f"- {fallback}"
    return "\n".join(f"- {item}" for item in valid_items)


def _format_question_answer_pairs(items: list[dict[str, str]]) -> str:
    if not items:
        return (
            "1. 问题：请详细说明项目中你的核心职责和个人贡献。\n"
            "   作答框架：按业务背景、技术方案、个人动作、结果指标展开。"
        )

    formatted_items = []
    for idx, item in enumerate(items, start=1):
        dimension_prefix = f"[{item['dimension']}] " if item.get("dimension") else ""
        question = item.get("question", "")
        answer_outline = item.get("answer_outline", "") or "请结合业务背景、技术方案、个人贡献和结果指标组织回答。"
        why_it_matters = item.get("why_it_matters", "")

        block = [
            f"{idx}. 问题：{dimension_prefix}{question}",
            f"   作答框架：{answer_outline}",
        ]
        if why_it_matters:
            block.append(f"   面试官意图：{why_it_matters}")
        formatted_items.append("\n".join(block))

    return "\n".join(formatted_items)


def _emit_interview_followup_card(result: dict[str, Any]) -> None:
    try:
        writer = get_stream_writer()
    except Exception:
        writer = None

    if not writer:
        return

    writer({
        "status": "END",
        "title": "面试追问结果卡片",
        "message": "已生成结构化的面试追问结果。",
        "event_type": "interview_followup_result",
        "tool_name": "interview_followup",
        "structured_data": result,
    })


def _format_interview_followup_result(result: dict[str, Any], target_role: str) -> str:
    return (
        f"{target_role} 面试追问准备\n"
        f"整体判断：{result.get('overall_summary')}\n\n"
        "高频追问与作答框架：\n"
        f"{_format_question_answer_pairs(result.get('question_answer_pairs', []))}\n\n"
        "建议深挖的技术点：\n"
        f"{_format_bullet_section(result.get('deep_dive_points', []), '优先准备 Agent 设计、工具调用链路、RAG 或工作流编排的技术细节。')}\n\n"
        "容易被追问或质疑的风险点：\n"
        f"{_format_bullet_section(result.get('risk_points', []), '注意避免只讲概念，不讲个人贡献、决策依据和结果指标。')}"
    )
