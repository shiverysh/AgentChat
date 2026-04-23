from __future__ import annotations

from typing import Any


def build_comparison_report(current_report: dict[str, Any], baseline_report: dict[str, Any]) -> dict[str, Any]:
    current_summary = current_report.get("summary", {})
    baseline_summary = baseline_report.get("summary", {})

    comparison = {
        "current_label": _report_label(current_report),
        "baseline_label": _report_label(baseline_report),
        "overall_delta": {
            "average_score_delta": _round(
                current_summary.get("average_score", 0.0) - baseline_summary.get("average_score", 0.0)
            ),
            "rule_average_score_delta": _round(
                current_summary.get("rule_average_score", current_summary.get("average_score", 0.0))
                - baseline_summary.get("rule_average_score", baseline_summary.get("average_score", 0.0))
            ),
            "pass_rate_delta": _round(
                current_summary.get("pass_rate", 0.0) - baseline_summary.get("pass_rate", 0.0)
            ),
            "average_elapsed_seconds_delta": _round(
                (current_summary.get("runtime") or {}).get("average_elapsed_seconds", 0.0)
                - (baseline_summary.get("runtime") or {}).get("average_elapsed_seconds", 0.0)
            ),
        },
        "tool_deltas": _build_tool_deltas(current_summary, baseline_summary),
    }

    if current_summary.get("judge_average_score") is not None or baseline_summary.get("judge_average_score") is not None:
        comparison["overall_delta"]["judge_average_score_delta"] = _round(
            (current_summary.get("judge_average_score") or 0.0)
            - (baseline_summary.get("judge_average_score") or 0.0)
        )

    return comparison


def format_comparison_markdown(comparison: dict[str, Any]) -> str:
    lines = [
        "# 求职助手 Eval 版本对比",
        "",
        f"- 当前版本：`{comparison['current_label']}`",
        f"- 对比基线：`{comparison['baseline_label']}`",
        "",
        "## 总体变化",
        "",
        f"- 综合平均分变化：{_format_delta(comparison['overall_delta']['average_score_delta'])}",
        f"- 规则平均分变化：{_format_delta(comparison['overall_delta']['rule_average_score_delta'])}",
        f"- 通过率变化：{_format_delta(comparison['overall_delta']['pass_rate_delta'], percent=True)}",
        f"- 单样例平均耗时变化：{_format_delta(comparison['overall_delta']['average_elapsed_seconds_delta'], suffix='s')}",
    ]

    judge_delta = comparison["overall_delta"].get("judge_average_score_delta")
    if judge_delta is not None:
        lines.append(f"- Judge 平均分变化：{_format_delta(judge_delta)}")

    lines.extend([
        "",
        "## 各 Tool 变化",
        "",
    ])

    for tool_name, delta in comparison["tool_deltas"].items():
        block = [
            f"### {tool_name}",
            "",
            f"- 综合平均分变化：{_format_delta(delta['average_score_delta'])}",
            f"- 规则平均分变化：{_format_delta(delta['rule_average_score_delta'])}",
            f"- 通过率变化：{_format_delta(delta['pass_rate_delta'], percent=True)}",
            f"- 平均耗时变化：{_format_delta(delta['average_elapsed_seconds_delta'], suffix='s')}",
        ]
        if delta.get("judge_average_score_delta") is not None:
            block.append(f"- Judge 平均分变化：{_format_delta(delta['judge_average_score_delta'])}")
        lines.extend([
            *block,
            "",
        ])

    return "\n".join(lines).strip() + "\n"


def _build_tool_deltas(current_summary: dict[str, Any], baseline_summary: dict[str, Any]) -> dict[str, Any]:
    current_tools = current_summary.get("tool_summary", {})
    baseline_tools = baseline_summary.get("tool_summary", {})
    tool_names = sorted(set(current_tools) | set(baseline_tools))

    current_runtime = (current_summary.get("runtime") or {}).get("tool_runtime", {})
    baseline_runtime = (baseline_summary.get("runtime") or {}).get("tool_runtime", {})

    result: dict[str, Any] = {}
    for tool_name in tool_names:
        current_tool = current_tools.get(tool_name, {})
        baseline_tool = baseline_tools.get(tool_name, {})
        tool_delta = {
            "average_score_delta": _round(
                current_tool.get("average_score", 0.0) - baseline_tool.get("average_score", 0.0)
            ),
            "rule_average_score_delta": _round(
                current_tool.get("rule_average_score", current_tool.get("average_score", 0.0))
                - baseline_tool.get("rule_average_score", baseline_tool.get("average_score", 0.0))
            ),
            "pass_rate_delta": _round(
                current_tool.get("pass_rate", 0.0) - baseline_tool.get("pass_rate", 0.0)
            ),
            "average_elapsed_seconds_delta": _round(
                current_runtime.get(tool_name, {}).get("average_elapsed_seconds", 0.0)
                - baseline_runtime.get(tool_name, {}).get("average_elapsed_seconds", 0.0)
            ),
        }
        if current_tool.get("judge_average_score") is not None or baseline_tool.get("judge_average_score") is not None:
            tool_delta["judge_average_score_delta"] = _round(
                (current_tool.get("judge_average_score") or 0.0)
                - (baseline_tool.get("judge_average_score") or 0.0)
            )
        result[tool_name] = tool_delta
    return result


def _report_label(report_payload: dict[str, Any]) -> str:
    return (
        report_payload.get("run_label")
        or report_payload.get("generated_at")
        or "unknown"
    )


def _format_delta(value: float, percent: bool = False, suffix: str = "") -> str:
    if percent:
        value = value * 100
        suffix = "%"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}{suffix}"


def _round(value: float) -> float:
    return round(float(value), 4)
