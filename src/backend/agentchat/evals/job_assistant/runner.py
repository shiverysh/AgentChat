from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from agentchat.evals.job_assistant.compare import build_comparison_report, format_comparison_markdown
from agentchat.evals.job_assistant.judge import judge_case
from agentchat.evals.job_assistant.scorer import (
    format_markdown_report,
    merge_case_score,
    score_case,
    summarize_scores,
)
from agentchat.settings import init_app_settings
from agentchat.tools.interview_followup.action import generate_interview_followup_result
from agentchat.tools.resume_match.action import generate_resume_match_result
from agentchat.tools.resume_rewrite.action import generate_resume_rewrite_result


ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_CASES_PATH = Path(__file__).resolve().with_name("cases.json")
DEFAULT_JSON_OUTPUT = ROOT_DIR / "reports" / "job_assistant_eval" / "latest.json"
DEFAULT_MARKDOWN_OUTPUT = ROOT_DIR / "reports" / "job_assistant_eval" / "latest.md"
DEFAULT_HISTORY_DIR = ROOT_DIR / "reports" / "job_assistant_eval" / "history"
DEFAULT_COMPARE_DIR = ROOT_DIR / "reports" / "job_assistant_eval" / "compare"

ProgressCallback = Callable[[dict[str, Any]], None]


@dataclass(slots=True)
class EvalRunConfig:
    config: str = "agentchat/config.yaml"
    cases: str = str(DEFAULT_CASES_PATH)
    tool: str | None = None
    json_output: str = str(DEFAULT_JSON_OUTPUT)
    markdown_output: str = str(DEFAULT_MARKDOWN_OUTPUT)
    enable_judge: bool = False
    judge_weight: float = 0.35
    run_label: str | None = None
    baseline_report: str | None = None
    compare_latest: bool = False
    verbose: bool = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run evaluation for the job assistant tools.")
    parser.add_argument(
        "--config",
        default="agentchat/config.yaml",
        help="Path to backend config.yaml used for model initialization.",
    )
    parser.add_argument(
        "--cases",
        default=str(DEFAULT_CASES_PATH),
        help="Path to the evaluation cases JSON file.",
    )
    parser.add_argument(
        "--tool",
        choices=["resume_match", "resume_rewrite", "interview_followup"],
        help="Only run one specific tool.",
    )
    parser.add_argument(
        "--json-output",
        default=str(DEFAULT_JSON_OUTPUT),
        help="Path to save the JSON evaluation report.",
    )
    parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_MARKDOWN_OUTPUT),
        help="Path to save the Markdown evaluation report.",
    )
    parser.add_argument(
        "--enable-judge",
        action="store_true",
        help="Enable LLM-as-a-Judge scoring in addition to rule-based scoring.",
    )
    parser.add_argument(
        "--judge-weight",
        type=float,
        default=0.35,
        help="Judge score weight in the final combined score. Rule score weight will be 1 - judge_weight.",
    )
    parser.add_argument(
        "--run-label",
        help="Optional version label, for example baseline / v1 / v2.",
    )
    parser.add_argument(
        "--baseline-report",
        help="Path to a previous JSON report used for version comparison.",
    )
    parser.add_argument(
        "--compare-latest",
        action="store_true",
        help="Compare current run against the existing latest.json before overwriting it.",
    )
    return parser.parse_args()


def load_cases(case_path: str, tool_name: str | None = None) -> list[dict[str, Any]]:
    cases = json.loads(Path(case_path).read_text(encoding="utf-8"))
    if tool_name:
        return [case for case in cases if case.get("tool") == tool_name]
    return cases


def run_case(case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], float]:
    start = perf_counter()
    tool_name = case["tool"]

    if tool_name == "resume_match":
        result = generate_resume_match_result(
            job_description=case["job_description"],
            resume_content=case["resume_content"],
            target_role=case.get("target_role", "大模型应用开发实习生"),
        )
    elif tool_name == "resume_rewrite":
        result = generate_resume_rewrite_result(
            resume_content=case["resume_content"],
            target_role=case.get("target_role", "大模型应用开发实习生"),
            job_description=case.get("job_description", ""),
        )
    elif tool_name == "interview_followup":
        result = generate_interview_followup_result(
            project_content=case["project_content"],
            target_role=case.get("target_role", "大模型应用开发实习生"),
            job_description=case.get("job_description", ""),
        )
    else:
        raise ValueError(f"unsupported eval tool: {tool_name}")

    elapsed = perf_counter() - start
    case_score = score_case(case, result)
    return case_score, result, elapsed


def save_report(path: str, content: str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def load_report(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def summarize_runtime(raw_results: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [item for item in raw_results if "elapsed_seconds" in item and "error" not in item]
    if not successful:
        return {
            "average_elapsed_seconds": 0.0,
            "max_elapsed_seconds": 0.0,
            "tool_runtime": {},
        }

    tool_runtime: dict[str, Any] = {}
    for item in successful:
        tool_runtime.setdefault(item["tool"], []).append(float(item.get("elapsed_seconds", 0.0)))

    return {
        "average_elapsed_seconds": round(
            sum(item["elapsed_seconds"] for item in successful) / len(successful), 4
        ),
        "max_elapsed_seconds": round(max(item["elapsed_seconds"] for item in successful), 4),
        "tool_runtime": {
            tool_name: {
                "average_elapsed_seconds": round(sum(values) / len(values), 4),
                "max_elapsed_seconds": round(max(values), 4),
            }
            for tool_name, values in tool_runtime.items()
        },
    }


def build_history_paths(run_id: str) -> tuple[Path, Path]:
    return (
        DEFAULT_HISTORY_DIR / f"{run_id}.json",
        DEFAULT_HISTORY_DIR / f"{run_id}.md",
    )


def sanitize_label(label: str) -> str:
    normalized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in label.strip())
    normalized = normalized.strip("_")
    return normalized or "eval_run"


def run_evaluation(
    config: EvalRunConfig,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    resolved_config_path = _resolve_config_path(config.config)
    _emit_progress(progress_callback, {
        "stage": "initializing",
        "message": "正在加载评测配置",
    })
    asyncio.run(init_app_settings(resolved_config_path))

    baseline_payload = None
    if config.baseline_report:
        baseline_payload = load_report(config.baseline_report)
    elif config.compare_latest and Path(config.json_output).exists():
        baseline_payload = load_report(config.json_output)

    cases = load_cases(config.cases, config.tool)
    if not cases:
        raise ValueError("未找到可执行的评测样例，请检查 cases 文件或 tool 过滤参数。")

    generated_at = datetime.now().isoformat(timespec="seconds")
    run_label = sanitize_label(config.run_label or "eval_run")
    run_id = f"{run_label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    case_results: list[dict[str, Any]] = []
    raw_results: list[dict[str, Any]] = []
    total_cases = len(cases)

    _emit_progress(progress_callback, {
        "stage": "running",
        "message": f"Eval 已启动，共 {total_cases} 条样例",
        "run_id": run_id,
        "run_label": run_label,
        "total_cases": total_cases,
        "completed_cases": 0,
        "percent": 0.0,
    })

    for index, case in enumerate(cases, start=1):
        _emit_progress(progress_callback, {
            "stage": "running",
            "message": f"正在评测 {case['tool']} / {case['id']}",
            "run_id": run_id,
            "run_label": run_label,
            "total_cases": total_cases,
            "completed_cases": index - 1,
            "current_index": index,
            "current_case_id": case["id"],
            "current_tool": case["tool"],
            "percent": round((index - 1) / total_cases, 4),
        })
        try:
            rule_case_score, result, elapsed = run_case(case)
            judge_result = None
            judge_error = None
            if config.enable_judge:
                try:
                    judge_result = judge_case(case, result)
                except Exception as err:
                    judge_error = str(err)
            case_score = merge_case_score(
                rule_case_score,
                judge_case_score=judge_result,
                judge_weight=config.judge_weight,
            )
            if judge_error:
                case_score["notes"] = list(case_score.get("notes", [])) + [f"Judge 执行失败：{judge_error}"]

            raw_results.append({
                "case_id": case["id"],
                "tool": case["tool"],
                "elapsed_seconds": round(elapsed, 4),
                "result": result,
                "judge_result": judge_result,
                "judge_error": judge_error,
            })
            case_log_message = (
                f"[{case['tool']}] {case['id']} -> "
                f"score={case_score['overall_score']:.2f} "
                f"pass={'yes' if case_score['passed'] else 'no'} "
                f"time={elapsed:.2f}s"
            )
            if config.verbose:
                print(case_log_message)
        except Exception as err:
            case_score = {
                "case_id": case["id"],
                "tool": case["tool"],
                "overall_score": 0.0,
                "rule_score": 0.0,
                "judge_score": None,
                "pass_threshold": float(case.get("expectations", {}).get("pass_threshold", 0.7)),
                "passed": False,
                "metric_scores": {
                    "execution_success": 0.0,
                },
                "judge_metric_scores": {},
                "notes": [f"执行失败：{err}"],
            }
            raw_results.append({
                "case_id": case["id"],
                "tool": case["tool"],
                "elapsed_seconds": 0.0,
                "error": str(err),
            })
            case_log_message = f"[{case['tool']}] {case['id']} -> failed: {err}"
            if config.verbose:
                print(case_log_message)

        case_results.append(case_score)
        _emit_progress(progress_callback, {
            "stage": "running",
            "message": case_log_message,
            "run_id": run_id,
            "run_label": run_label,
            "total_cases": total_cases,
            "completed_cases": index,
            "current_index": index,
            "current_case_id": case["id"],
            "current_tool": case["tool"],
            "percent": round(index / total_cases, 4),
            "last_case_result": {
                "case_id": case_score["case_id"],
                "tool": case_score["tool"],
                "overall_score": case_score["overall_score"],
                "passed": case_score["passed"],
            },
        })

    summary = summarize_scores(case_results)
    summary["runtime"] = summarize_runtime(raw_results)
    _emit_progress(progress_callback, {
        "stage": "saving",
        "message": "正在保存评测报告",
        "run_id": run_id,
        "run_label": run_label,
        "total_cases": total_cases,
        "completed_cases": total_cases,
        "percent": 1.0,
    })
    report_payload = {
        "generated_at": generated_at,
        "run_label": run_label,
        "run_id": run_id,
        "config_path": resolved_config_path,
        "case_file": config.cases,
        "judge_enabled": config.enable_judge,
        "judge_weight": config.judge_weight,
        "summary": summary,
        "cases": case_results,
        "raw_results": raw_results,
    }
    report_json_content = json.dumps(report_payload, ensure_ascii=False, indent=2)
    report_markdown_content = format_markdown_report(summary, case_results)
    save_report(config.json_output, report_json_content)
    save_report(config.markdown_output, report_markdown_content)

    history_json_path, history_markdown_path = build_history_paths(run_id)
    save_report(history_json_path, report_json_content)
    save_report(history_markdown_path, report_markdown_content)

    comparison_report_name = None
    if baseline_payload:
        _emit_progress(progress_callback, {
            "stage": "comparing",
            "message": "正在生成版本对比报告",
            "run_id": run_id,
            "run_label": run_label,
            "total_cases": total_cases,
            "completed_cases": total_cases,
            "percent": 1.0,
        })
        comparison_payload = build_comparison_report(report_payload, baseline_payload)
        baseline_label = sanitize_label(comparison_payload["baseline_label"])
        comparison_json_path = DEFAULT_COMPARE_DIR / f"{run_id}_vs_{baseline_label}.json"
        comparison_markdown_path = DEFAULT_COMPARE_DIR / f"{run_id}_vs_{baseline_label}.md"
        save_report(comparison_json_path, json.dumps(comparison_payload, ensure_ascii=False, indent=2))
        save_report(comparison_markdown_path, format_comparison_markdown(comparison_payload))
        comparison_report_name = comparison_json_path.name

    result = {
        "generated_at": generated_at,
        "run_label": run_label,
        "run_id": run_id,
        "judge_enabled": config.enable_judge,
        "judge_weight": config.judge_weight,
        "summary": summary,
        "latest_report_name": Path(config.json_output).name,
        "history_report_name": history_json_path.name,
        "comparison_report_name": comparison_report_name,
    }

    _emit_progress(progress_callback, {
        "stage": "completed",
        "message": "评测完成",
        "run_id": run_id,
        "run_label": run_label,
        "total_cases": total_cases,
        "completed_cases": total_cases,
        "percent": 1.0,
        "result": result,
    })

    if config.verbose:
        print("")
        print(
            f"Finished {summary['total_cases']} cases | "
            f"pass_rate={summary['pass_rate'] * 100:.1f}% | "
            f"avg_score={summary['average_score']:.2f}"
        )
        print(f"JSON report: {config.json_output}")
        print(f"Markdown report: {config.markdown_output}")
        print(f"History JSON: {history_json_path}")
        print(f"History Markdown: {history_markdown_path}")

    return result


def main() -> None:
    args = parse_args()
    config = EvalRunConfig(
        config=args.config,
        cases=args.cases,
        tool=args.tool,
        json_output=args.json_output,
        markdown_output=args.markdown_output,
        enable_judge=args.enable_judge,
        judge_weight=args.judge_weight,
        run_label=args.run_label,
        baseline_report=args.baseline_report,
        compare_latest=args.compare_latest,
        verbose=True,
    )
    run_evaluation(config)


def _resolve_config_path(config_path: str) -> str:
    path = Path(config_path)
    if path.is_absolute():
        return str(path)
    candidate = ROOT_DIR / path
    if candidate.exists():
        return str(candidate)
    return str(path)


def _emit_progress(
    progress_callback: ProgressCallback | None,
    payload: dict[str, Any],
) -> None:
    if progress_callback is None:
        return
    progress_callback(payload)


if __name__ == "__main__":
    main()
