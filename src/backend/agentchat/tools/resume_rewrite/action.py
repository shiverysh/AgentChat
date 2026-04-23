import json
from typing import Any

from langchain.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from loguru import logger

from agentchat.core.models.manager import ModelManager
from agentchat.prompts.tool import RESUME_REWRITE_PROMPT
from agentchat.utils.helpers import fix_json_text


@tool("resume_rewrite", parse_docstring=True)
def resume_rewrite(
    resume_content: str,
    target_role: str = "大模型应用开发实习生",
    job_description: str = "",
):
    """
    将简历或项目经历改写成更适合目标岗位投递的版本。

    Args:
        resume_content (str): 待改写的简历内容、项目经历或技能描述。
        target_role (str): 目标岗位名称，默认是大模型应用开发实习生。
        job_description (str): 可选的岗位 JD 文本，提供后会结合岗位关键词进行改写。

    Returns:
        str: 包含问题诊断、可复用改写版本和补充建议的结果。
    """
    return _resume_rewrite(resume_content, target_role, job_description)


def generate_resume_rewrite_result(
    resume_content: str,
    target_role: str = "大模型应用开发实习生",
    job_description: str = "",
) -> dict[str, Any]:
    if not resume_content.strip():
        raise ValueError("请先提供需要改写的简历内容或项目经历，我才能帮您生成可直接复用的版本。")

    prompt = RESUME_REWRITE_PROMPT.format(
        target_role=target_role,
        job_description=job_description.strip() or "未提供岗位 JD，请按目标岗位的通用要求进行改写。",
        resume_content=resume_content,
    )

    model = ModelManager.get_conversation_model().bind(
        response_format={"type": "json_object"}
    )
    response = model.invoke(
        [SystemMessage(content="你是一名严谨的求职顾问。"), HumanMessage(content=prompt)],
        config={"callbacks": _get_usage_callbacks()},
    )
    result = _parse_resume_rewrite_response(response.content)
    return _normalize_resume_rewrite_result(result, target_role)


def _resume_rewrite(resume_content: str, target_role: str, job_description: str) -> str:
    try:
        normalized_result = generate_resume_rewrite_result(
            resume_content=resume_content,
            target_role=target_role,
            job_description=job_description,
        )
        _emit_resume_rewrite_card(normalized_result)
        return _format_resume_rewrite_result(normalized_result, target_role)
    except Exception as err:
        logger.error(f"resume_rewrite tool failed: {err}")
        return f"简历改写暂时失败，请稍后重试。错误信息：{err}"


def _get_usage_callbacks() -> list[Any]:
    try:
        from agentchat.core.callbacks import usage_metadata_callback
        return [usage_metadata_callback]
    except Exception as err:
        logger.warning(f"usage metadata callback unavailable: {err}")
        return []


def _parse_resume_rewrite_response(content: str) -> dict[str, Any]:
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


def _normalize_resume_rewrite_result(result: dict[str, Any], target_role: str) -> dict[str, Any]:
    overall_strategy = result.get("overall_strategy", "已按目标岗位方向完成基础改写。")
    if not isinstance(overall_strategy, str) or not overall_strategy.strip():
        overall_strategy = "已按目标岗位方向完成基础改写。"

    return {
        "target_role": target_role,
        "overall_strategy": overall_strategy.strip(),
        "detected_issues": _normalize_items(result.get("detected_issues", []), limit=5),
        "rewritten_resume": _normalize_items(result.get("rewritten_resume", []), limit=6),
        "supplement_suggestions": _normalize_items(result.get("supplement_suggestions", []), limit=5),
        "highlight_keywords": _normalize_items(result.get("highlight_keywords", []), limit=5),
    }


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


def _emit_resume_rewrite_card(result: dict[str, Any]) -> None:
    try:
        writer = get_stream_writer()
    except Exception:
        writer = None

    if not writer:
        return

    writer({
        "status": "END",
        "title": "简历改写结果卡片",
        "message": "已生成结构化的简历改写结果。",
        "event_type": "resume_rewrite_result",
        "tool_name": "resume_rewrite",
        "structured_data": result,
    })


def _format_resume_rewrite_result(result: dict[str, Any], target_role: str) -> str:
    return (
        f"{target_role} 简历改写建议\n"
        f"改写思路：{result.get('overall_strategy')}\n\n"
        "当前问题：\n"
        f"{_format_bullet_section(result.get('detected_issues', []), '当前描述偏泛，建议补足业务场景、技术方案和结果指标。')}\n\n"
        "可直接复用的改写版本：\n"
        f"{_format_numbered_section(result.get('rewritten_resume', []), '请补充更具体的项目职责、技术栈和量化结果后再改写。')}\n\n"
        "建议补充的信息：\n"
        f"{_format_bullet_section(result.get('supplement_suggestions', []), '优先补充个人贡献、效果指标和关键技术决策。')}\n\n"
        "建议强化的关键词：\n"
        f"{_format_bullet_section(result.get('highlight_keywords', []), '可补充 Agent、工具调用、RAG、工作流编排等岗位相关关键词。')}"
    )
