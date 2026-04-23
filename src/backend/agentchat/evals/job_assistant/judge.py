from __future__ import annotations

import json
from statistics import mean
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agentchat.core.models.manager import ModelManager
from agentchat.utils.helpers import fix_json_text


JUDGE_METRICS = {
    "resume_match": [
        "jd_alignment",
        "gap_detection",
        "suggestion_actionability",
        "factual_grounding",
    ],
    "resume_rewrite": [
        "role_alignment",
        "factual_preservation",
        "rewrite_quality",
        "keyword_strength",
    ],
    "interview_followup": [
        "question_depth",
        "answer_framework_quality",
        "role_relevance",
        "risk_awareness",
    ],
}


def judge_case(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    tool_name = case["tool"]
    metric_names = JUDGE_METRICS.get(tool_name)
    if not metric_names:
        raise ValueError(f"unsupported judge tool: {tool_name}")

    model = ModelManager.get_conversation_model().bind(
        response_format={"type": "json_object"}
    )
    prompt = _build_judge_prompt(case, result, metric_names)
    response = model.invoke(
        [
            SystemMessage(content=_build_judge_system_prompt()),
            HumanMessage(content=prompt),
        ]
    )
    parsed = _parse_judge_response(response.content)
    normalized_metrics = _normalize_judge_metrics(parsed.get("metric_scores"), metric_names)

    return {
        "overall_score": round(mean(normalized_metrics.values()), 4) if normalized_metrics else 0.0,
        "metric_scores": normalized_metrics,
        "summary": _normalize_text(parsed.get("summary")),
        "strengths": _normalize_text_list(parsed.get("strengths")),
        "weaknesses": _normalize_text_list(parsed.get("weaknesses")),
    }


def _build_judge_system_prompt() -> str:
    return (
        "你是一名严格的大模型应用评测器。"
        "你需要基于输入样例、期望要求与 Agent 输出结果，对结果质量进行客观评分。"
        "禁止因为措辞华丽而给高分，必须优先看是否贴合岗位、是否保留事实、是否有可执行性。"
        "输出必须是 JSON。"
    )


def _build_judge_prompt(case: dict[str, Any], result: dict[str, Any], metric_names: list[str]) -> str:
    return (
        "请根据以下信息对 Agent 结果打分。\n\n"
        f"Tool: {case['tool']}\n"
        f"目标岗位: {case.get('target_role', '大模型应用开发实习生')}\n"
        f"评测样例: {json.dumps(case, ensure_ascii=False, indent=2)}\n\n"
        f"Agent 输出: {json.dumps(result, ensure_ascii=False, indent=2)}\n\n"
        "请返回 JSON，格式如下：\n"
        "{\n"
        '  "summary": "一句话总结",\n'
        '  "metric_scores": {\n'
        + "".join(f'    "{name}": 0.0,\n' for name in metric_names)
        + "  },\n"
        '  "strengths": ["优点1", "优点2"],\n'
        '  "weaknesses": ["不足1", "不足2"]\n'
        "}\n\n"
        "要求：\n"
        f"1. 只评价这些指标：{', '.join(metric_names)}\n"
        "2. 每个分数范围 0 到 1\n"
        "3. 分数必须体现严格区分，避免全部给高分\n"
        "4. strengths/weaknesses 每项不超过 2 条"
    )


def _parse_judge_response(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return json.loads(fix_json_text(content))


def _normalize_judge_metrics(metric_scores: Any, expected_names: list[str]) -> dict[str, float]:
    if not isinstance(metric_scores, dict):
        return {name: 0.0 for name in expected_names}

    normalized: dict[str, float] = {}
    for name in expected_names:
        value = metric_scores.get(name, 0.0)
        try:
            normalized[name] = round(min(max(float(value), 0.0), 1.0), 4)
        except (TypeError, ValueError):
            normalized[name] = 0.0
    return normalized


def _normalize_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _normalize_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            items.append(item.strip())
        if len(items) >= 2:
            break
    return items
