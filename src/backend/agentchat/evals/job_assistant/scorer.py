from __future__ import annotations

from statistics import mean
from typing import Any


def score_case(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    tool_name = case["tool"]
    if tool_name == "resume_match":
        return _score_resume_match(case, result)
    if tool_name == "resume_rewrite":
        return _score_resume_rewrite(case, result)
    if tool_name == "interview_followup":
        return _score_interview_followup(case, result)
    raise ValueError(f"unsupported eval tool: {tool_name}")


def summarize_scores(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    if not case_results:
        return {
            "total_cases": 0,
            "passed_cases": 0,
            "pass_rate": 0.0,
            "average_score": 0.0,
            "tool_summary": {},
        }

    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in case_results:
        grouped.setdefault(item["tool"], []).append(item)

    tool_summary: dict[str, Any] = {}
    for tool_name, items in grouped.items():
        judge_scores = [item["judge_score"] for item in items if item.get("judge_score") is not None]
        tool_summary[tool_name] = {
            "case_count": len(items),
            "passed_cases": sum(1 for item in items if item["passed"]),
            "pass_rate": _round(sum(1 for item in items if item["passed"]) / len(items)),
            "average_score": _round(mean(item["overall_score"] for item in items)),
            "rule_average_score": _round(mean(item.get("rule_score", item["overall_score"]) for item in items)),
            "judge_average_score": _round(mean(judge_scores)) if judge_scores else None,
        }

    judge_scores = [item["judge_score"] for item in case_results if item.get("judge_score") is not None]
    return {
        "total_cases": len(case_results),
        "passed_cases": sum(1 for item in case_results if item["passed"]),
        "pass_rate": _round(sum(1 for item in case_results if item["passed"]) / len(case_results)),
        "average_score": _round(mean(item["overall_score"] for item in case_results)),
        "rule_average_score": _round(mean(item.get("rule_score", item["overall_score"]) for item in case_results)),
        "judge_average_score": _round(mean(judge_scores)) if judge_scores else None,
        "judge_enabled": bool(judge_scores),
        "tool_summary": tool_summary,
    }


def format_markdown_report(summary: dict[str, Any], case_results: list[dict[str, Any]]) -> str:
    lines = [
        "# 求职助手 Agent Eval 报告",
        "",
        "## 总览",
        "",
        f"- 总样例数：{summary['total_cases']}",
        f"- 通过样例数：{summary['passed_cases']}",
        f"- 通过率：{_format_percent(summary['pass_rate'])}",
        f"- 综合平均得分：{summary['average_score']:.2f}",
        f"- 规则平均得分：{summary.get('rule_average_score', summary['average_score']):.2f}",
    ]
    if summary.get("judge_enabled") and summary.get("judge_average_score") is not None:
        lines.append(f"- Judge 平均得分：{summary['judge_average_score']:.2f}")

    runtime = summary.get("runtime") or {}
    if runtime:
        lines.extend([
            "",
            "## 运行耗时",
            "",
            f"- 单样例平均耗时：{runtime.get('average_elapsed_seconds', 0.0):.2f}s",
            f"- 最慢样例耗时：{runtime.get('max_elapsed_seconds', 0.0):.2f}s",
        ])

    lines.extend([
        "",
        "## 分能力汇总",
        "",
    ])

    for tool_name, tool_summary in summary["tool_summary"].items():
        block = [
            f"### {tool_name}",
            "",
            f"- 样例数：{tool_summary['case_count']}",
            f"- 通过率：{_format_percent(tool_summary['pass_rate'])}",
            f"- 综合平均得分：{tool_summary['average_score']:.2f}",
            f"- 规则平均得分：{tool_summary.get('rule_average_score', tool_summary['average_score']):.2f}",
        ]
        if tool_summary.get("judge_average_score") is not None:
            block.append(f"- Judge 平均得分：{tool_summary['judge_average_score']:.2f}")
        tool_runtime = runtime.get("tool_runtime", {}).get(tool_name)
        if tool_runtime:
            block.append(f"- 平均耗时：{tool_runtime.get('average_elapsed_seconds', 0.0):.2f}s")
        lines.extend([
            *block,
            "",
        ])

    lines.extend([
        "## 样例明细",
        "",
    ])

    for item in case_results:
        block = [
            f"### {item['case_id']}",
            "",
            f"- Tool：`{item['tool']}`",
            f"- 综合得分：{item['overall_score']:.2f}",
            f"- 规则得分：{item.get('rule_score', item['overall_score']):.2f}",
            f"- 结果：{'PASS' if item['passed'] else 'FAIL'}",
            f"- 阈值：{item['pass_threshold']:.2f}",
        ]
        if item.get("judge_score") is not None:
            block.append(f"- Judge 得分：{item['judge_score']:.2f}")
        block.extend([
            "",
            "**规则指标**",
            "",
            "| 指标 | 分数 |",
            "| --- | --- |",
        ])
        lines.extend(block)
        for metric_name, score in item["metric_scores"].items():
            lines.append(f"| {metric_name} | {score:.2f} |")
        if item.get("judge_metric_scores"):
            lines.extend([
                "",
                "**Judge 指标**",
                "",
                "| 指标 | 分数 |",
                "| --- | --- |",
            ])
            for metric_name, score in item["judge_metric_scores"].items():
                lines.append(f"| {metric_name} | {score:.2f} |")
        if item.get("notes"):
            lines.extend([
                "",
                "**说明**",
                "",
            ])
            lines.extend([f"- {note}" for note in item["notes"]])
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _score_resume_match(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    expectations = case.get("expectations", {})
    full_text = "\n".join([
        result.get("overall_summary", ""),
        *result.get("matched_strengths", []),
        *result.get("missing_requirements", []),
        *result.get("revision_suggestions", []),
        *result.get("interview_focus", []),
    ])
    missing_text = "\n".join(result.get("missing_requirements", []))

    metric_scores = {
        "match_score_range": _range_score(result.get("match_score", 0), expectations.get("expected_score_range")),
        "matched_strengths_count": _minimum_count_score(
            result.get("matched_strengths", []),
            expectations.get("min_matched_strengths", 2),
        ),
        "missing_requirements_count": _minimum_count_score(
            result.get("missing_requirements", []),
            expectations.get("min_missing_requirements", 2),
        ),
        "revision_suggestions_count": _minimum_count_score(
            result.get("revision_suggestions", []),
            expectations.get("min_revision_suggestions", 2),
        ),
        "interview_focus_count": _minimum_count_score(
            result.get("interview_focus", []),
            expectations.get("min_interview_focus", 2),
        ),
        "expected_keyword_coverage": _coverage_score(full_text, expectations.get("expected_keywords", [])),
        "missing_keyword_coverage": _coverage_score(missing_text, expectations.get("expected_missing_keywords", [])),
        "summary_presence": 1.0 if result.get("overall_summary", "").strip() else 0.0,
    }
    notes = _build_basic_notes(case, result, metric_scores)
    return _pack_case_score(case, metric_scores, notes)


def _score_resume_rewrite(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    expectations = case.get("expectations", {})
    rewritten_text = "\n".join(result.get("rewritten_resume", []))
    full_text = "\n".join([
        result.get("overall_strategy", ""),
        *result.get("detected_issues", []),
        *result.get("rewritten_resume", []),
        *result.get("supplement_suggestions", []),
        *result.get("highlight_keywords", []),
    ])

    metric_scores = {
        "detected_issues_count": _minimum_count_score(
            result.get("detected_issues", []),
            expectations.get("min_detected_issues", 2),
        ),
        "rewritten_resume_count": _minimum_count_score(
            result.get("rewritten_resume", []),
            expectations.get("min_rewritten_resume", 3),
        ),
        "supplement_suggestions_count": _minimum_count_score(
            result.get("supplement_suggestions", []),
            expectations.get("min_supplement_suggestions", 2),
        ),
        "highlight_keywords_count": _minimum_count_score(
            result.get("highlight_keywords", []),
            expectations.get("min_highlight_keywords", 3),
        ),
        "expected_keyword_coverage": _coverage_score(full_text, expectations.get("expected_keywords", [])),
        "source_fact_retention": _coverage_score(rewritten_text, expectations.get("source_facts", [])),
        "fabrication_penalty": _absence_score(full_text, expectations.get("forbidden_keywords", [])),
        "strategy_presence": 1.0 if result.get("overall_strategy", "").strip() else 0.0,
    }
    notes = _build_basic_notes(case, result, metric_scores)
    return _pack_case_score(case, metric_scores, notes)


def _score_interview_followup(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    expectations = case.get("expectations", {})
    pairs = result.get("question_answer_pairs", [])
    qa_text = "\n".join(
        f"{item.get('dimension', '')}\n{item.get('question', '')}\n{item.get('answer_outline', '')}\n{item.get('why_it_matters', '')}"
        for item in pairs
    )
    full_text = "\n".join([
        result.get("overall_summary", ""),
        qa_text,
        *result.get("deep_dive_points", []),
        *result.get("risk_points", []),
    ])

    answered_pairs = [
        item for item in pairs
        if isinstance(item.get("answer_outline"), str) and item.get("answer_outline", "").strip()
    ]
    metric_scores = {
        "question_count": _minimum_count_score(pairs, expectations.get("min_questions", 3)),
        "answer_outline_completeness": _ratio_score(len(answered_pairs), max(len(pairs), 1)),
        "deep_dive_points_count": _minimum_count_score(
            result.get("deep_dive_points", []),
            expectations.get("min_deep_dive_points", 2),
        ),
        "risk_points_count": _minimum_count_score(
            result.get("risk_points", []),
            expectations.get("min_risk_points", 2),
        ),
        "topic_coverage": _coverage_score(full_text, expectations.get("expected_topics", [])),
        "summary_presence": 1.0 if result.get("overall_summary", "").strip() else 0.0,
    }
    notes = _build_basic_notes(case, result, metric_scores)
    return _pack_case_score(case, metric_scores, notes)


def _pack_case_score(case: dict[str, Any], metric_scores: dict[str, float], notes: list[str]) -> dict[str, Any]:
    overall_score = _round(mean(metric_scores.values())) if metric_scores else 0.0
    pass_threshold = float(case.get("expectations", {}).get("pass_threshold", 0.7))
    return {
        "case_id": case["id"],
        "tool": case["tool"],
        "overall_score": overall_score,
        "rule_score": overall_score,
        "judge_score": None,
        "pass_threshold": pass_threshold,
        "passed": overall_score >= pass_threshold,
        "metric_scores": {name: _round(score) for name, score in metric_scores.items()},
        "judge_metric_scores": {},
        "notes": notes,
    }


def merge_case_score(
    rule_case_score: dict[str, Any],
    judge_case_score: dict[str, Any] | None = None,
    judge_weight: float = 0.35,
) -> dict[str, Any]:
    merged = dict(rule_case_score)
    merged["rule_score"] = rule_case_score.get("rule_score", rule_case_score.get("overall_score", 0.0))
    merged["judge_score"] = None
    merged["judge_metric_scores"] = {}
    merged["judge_summary"] = ""

    if not judge_case_score:
        return merged

    judge_weight = min(max(judge_weight, 0.0), 1.0)
    rule_weight = 1.0 - judge_weight
    judge_score = float(judge_case_score.get("overall_score", 0.0))
    merged["judge_score"] = _round(judge_score)
    merged["judge_metric_scores"] = {
        name: _round(score) for name, score in (judge_case_score.get("metric_scores") or {}).items()
    }
    merged["judge_summary"] = judge_case_score.get("summary", "")
    merged["overall_score"] = _round(merged["rule_score"] * rule_weight + judge_score * judge_weight)
    merged["passed"] = merged["overall_score"] >= merged["pass_threshold"]

    notes = list(merged.get("notes", []))
    if judge_case_score.get("summary"):
        notes.append(f"Judge 摘要：{judge_case_score['summary']}")
    strengths = judge_case_score.get("strengths") or []
    weaknesses = judge_case_score.get("weaknesses") or []
    if strengths:
        notes.append(f"Judge 优势：{'；'.join(strengths[:2])}")
    if weaknesses:
        notes.append(f"Judge 不足：{'；'.join(weaknesses[:2])}")
    merged["notes"] = notes
    return merged


def _build_basic_notes(case: dict[str, Any], result: dict[str, Any], metric_scores: dict[str, float]) -> list[str]:
    notes: list[str] = []
    low_metrics = [name for name, score in metric_scores.items() if score < 0.6]
    if low_metrics:
        notes.append(f"低分指标：{', '.join(low_metrics)}")

    if case["tool"] == "resume_match":
        notes.append(f"输出匹配度：{result.get('match_score', 0)}/100")
    if case["tool"] == "interview_followup":
        notes.append(f"生成追问数：{len(result.get('question_answer_pairs', []))}")
    return notes


def _minimum_count_score(items: list[Any], minimum: int) -> float:
    return _ratio_score(len(items), max(minimum, 1))


def _ratio_score(value: int | float, target: int | float) -> float:
    if target <= 0:
        return 1.0
    return min(float(value) / float(target), 1.0)


def _coverage_score(text: str, keywords: list[str]) -> float:
    if not keywords:
        return 1.0
    normalized_text = text.lower()
    hits = sum(1 for keyword in keywords if keyword.lower() in normalized_text)
    return _round(hits / len(keywords))


def _absence_score(text: str, forbidden_keywords: list[str]) -> float:
    if not forbidden_keywords:
        return 1.0
    normalized_text = text.lower()
    hits = sum(1 for keyword in forbidden_keywords if keyword.lower() in normalized_text)
    return _round(max(len(forbidden_keywords) - hits, 0) / len(forbidden_keywords))


def _range_score(value: Any, expected_range: list[float] | tuple[float, float] | None) -> float:
    if not expected_range or len(expected_range) != 2:
        return 1.0

    try:
        numeric_value = float(value)
        min_value = float(expected_range[0])
        max_value = float(expected_range[1])
    except (TypeError, ValueError):
        return 0.0

    if min_value <= numeric_value <= max_value:
        return 1.0

    span = max(max_value - min_value, 1.0)
    if numeric_value < min_value:
        return _round(max(0.0, 1.0 - (min_value - numeric_value) / span))
    return _round(max(0.0, 1.0 - (numeric_value - max_value) / span))


def _round(value: float) -> float:
    return round(float(value), 4)


def _format_percent(value: float) -> str:
    return f"{value * 100:.1f}%"
