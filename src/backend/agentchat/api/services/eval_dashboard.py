from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from agentchat.evals.job_assistant.runner import EvalRunConfig, run_evaluation


class EvalDashboardService:
    REPORT_ROOT = Path(__file__).resolve().parents[3] / "reports" / "job_assistant_eval"
    LATEST_JSON = REPORT_ROOT / "latest.json"
    HISTORY_DIR = REPORT_ROOT / "history"
    COMPARE_DIR = REPORT_ROOT / "compare"

    @classmethod
    async def get_overview(cls) -> dict[str, Any]:
        latest_payload, latest_name, latest_is_history_fallback = cls._load_latest_payload()

        history_reports: list[dict[str, Any]] = []
        for report_file in cls._iter_report_files(cls.HISTORY_DIR):
            if latest_is_history_fallback and report_file.name == latest_name:
                continue
            payload = cls._safe_read_json(report_file)
            if payload is None:
                continue
            history_reports.append(cls._build_report_summary(payload, report_file))

        compare_reports: list[dict[str, Any]] = []
        for report_file in cls._iter_report_files(cls.COMPARE_DIR):
            payload = cls._safe_read_json(report_file)
            if payload is None:
                continue
            compare_reports.append(cls._build_compare_summary(payload, report_file))

        latest_summary = None
        if latest_payload is not None:
            latest_path = cls.HISTORY_DIR / latest_name if latest_is_history_fallback else cls.LATEST_JSON
            latest_summary = cls._build_report_summary(latest_payload, latest_path)

        return {
            "latest_report": latest_payload,
            "latest_summary": latest_summary,
            "history_reports": history_reports[:12],
            "compare_reports": compare_reports[:12],
        }

    @classmethod
    async def get_report(cls, category: str, report_name: str | None = None) -> dict[str, Any]:
        normalized_category = (category or "latest").strip().lower()
        if normalized_category == "latest":
            latest_payload, _, _ = cls._load_latest_payload()
            if latest_payload is None:
                raise FileNotFoundError("latest eval report not found")
            return latest_payload

        if normalized_category not in {"history", "compare"}:
            raise ValueError("unsupported report category")

        if not report_name:
            raise ValueError("report_name is required")

        target_dir = cls.HISTORY_DIR if normalized_category == "history" else cls.COMPARE_DIR
        target_path = cls._resolve_report_path(target_dir, report_name)
        payload = cls._safe_read_json(target_path)
        if payload is None:
            raise FileNotFoundError(f"report not found: {report_name}")
        return payload

    @classmethod
    def _load_latest_payload(cls) -> tuple[dict[str, Any] | None, str, bool]:
        latest_payload = cls._safe_read_json(cls.LATEST_JSON)
        if latest_payload is not None:
            return latest_payload, cls.LATEST_JSON.name, False

        history_files = cls._iter_report_files(cls.HISTORY_DIR)
        if not history_files:
            return None, "", False

        fallback_file = history_files[0]
        return cls._safe_read_json(fallback_file), fallback_file.name, True

    @classmethod
    def _iter_report_files(cls, target_dir: Path) -> list[Path]:
        if not target_dir.exists():
            return []
        return sorted(
            [path for path in target_dir.glob("*.json") if path.is_file()],
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )

    @classmethod
    def _safe_read_json(cls, target_path: Path) -> dict[str, Any] | None:
        try:
            if not target_path.exists():
                return None
            return json.loads(target_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    @classmethod
    def _build_report_summary(cls, payload: dict[str, Any], report_file: Path) -> dict[str, Any]:
        summary = payload.get("summary") or {}
        runtime = summary.get("runtime") or {}
        generated_at = payload.get("generated_at") or cls._format_mtime(report_file)

        return {
            "report_name": report_file.name,
            "run_id": payload.get("run_id") or report_file.stem,
            "run_label": payload.get("run_label") or payload.get("run_id") or report_file.stem,
            "generated_at": generated_at,
            "judge_enabled": bool(payload.get("judge_enabled")),
            "judge_weight": payload.get("judge_weight"),
            "total_cases": int(summary.get("total_cases", 0) or 0),
            "passed_cases": int(summary.get("passed_cases", 0) or 0),
            "pass_rate": float(summary.get("pass_rate", 0.0) or 0.0),
            "average_score": float(summary.get("average_score", 0.0) or 0.0),
            "rule_average_score": float(summary.get("rule_average_score", summary.get("average_score", 0.0)) or 0.0),
            "judge_average_score": cls._to_optional_float(summary.get("judge_average_score")),
            "average_elapsed_seconds": float(runtime.get("average_elapsed_seconds", 0.0) or 0.0),
        }

    @classmethod
    def _build_compare_summary(cls, payload: dict[str, Any], report_file: Path) -> dict[str, Any]:
        overall_delta = payload.get("overall_delta") or {}
        return {
            "report_name": report_file.name,
            "generated_at": payload.get("generated_at") or cls._format_mtime(report_file),
            "current_label": payload.get("current_label") or "current",
            "baseline_label": payload.get("baseline_label") or "baseline",
            "overall_delta": overall_delta,
            "tool_deltas": payload.get("tool_deltas") or {},
        }

    @classmethod
    def _resolve_report_path(cls, target_dir: Path, report_name: str) -> Path:
        safe_name = Path(report_name).name
        if not safe_name.endswith(".json"):
            safe_name = f"{safe_name}.json"
        return target_dir / safe_name

    @staticmethod
    def _format_mtime(report_file: Path) -> str:
        return datetime.fromtimestamp(report_file.stat().st_mtime).isoformat(timespec="seconds")

    @staticmethod
    def _to_optional_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class EvalDashboardRunService:
    _state_lock = Lock()
    _tasks: dict[str, dict[str, Any]] = {}
    _latest_task_id_by_user: dict[str, str] = {}
    _active_task_id: str | None = None
    _max_logs = 24
    _max_tasks = 12

    @classmethod
    async def start_run(cls, user_id: str, run_request: dict[str, Any]) -> dict[str, Any]:
        normalized_tool = cls._normalize_tool(run_request.get("tool"))
        created_at = datetime.now().isoformat(timespec="seconds")
        task_id = uuid.uuid4().hex

        task_state = {
            "task_id": task_id,
            "user_id": user_id,
            "status": "queued",
            "created_at": created_at,
            "started_at": None,
            "finished_at": None,
            "config": {
                "run_label": (run_request.get("run_label") or "manual_eval").strip() or "manual_eval",
                "tool": normalized_tool or "all",
                "enable_judge": bool(run_request.get("enable_judge", True)),
                "judge_weight": float(run_request.get("judge_weight", 0.35)),
                "compare_latest": bool(run_request.get("compare_latest", True)),
            },
            "progress": {
                "stage": "queued",
                "message": "任务已创建，等待执行",
                "total_cases": 0,
                "completed_cases": 0,
                "percent": 0.0,
                "current_index": 0,
                "current_case_id": None,
                "current_tool": None,
                "last_case_result": None,
            },
            "logs": [],
            "result": None,
            "error": None,
        }

        with cls._state_lock:
            active_task = cls._get_active_task_unlocked()
            if active_task and active_task.get("status") in {"queued", "running"}:
                raise RuntimeError("已有 Eval 任务正在运行，请等待当前任务结束后再发起新任务。")

            cls._append_log_unlocked(task_state, "任务已创建，等待执行")
            cls._tasks[task_id] = task_state
            cls._latest_task_id_by_user[user_id] = task_id
            cls._active_task_id = task_id
            cls._prune_tasks_unlocked()

        asyncio.create_task(cls._run_task(task_id))
        return cls._build_public_status(task_state)

    @classmethod
    async def get_status(cls, user_id: str, task_id: str | None = None) -> dict[str, Any]:
        with cls._state_lock:
            task_state = cls._resolve_task_unlocked(user_id, task_id)
            if task_state is None:
                return {
                    "task_id": None,
                    "status": "idle",
                    "created_at": None,
                    "started_at": None,
                    "finished_at": None,
                    "config": None,
                    "progress": None,
                    "logs": [],
                    "result": None,
                    "error": None,
                    "is_active": False,
                }
            return cls._build_public_status(task_state)

    @classmethod
    async def _run_task(cls, task_id: str) -> None:
        with cls._state_lock:
            task_state = cls._tasks.get(task_id)
            if not task_state:
                return
            task_state["status"] = "running"
            task_state["started_at"] = datetime.now().isoformat(timespec="seconds")
            task_state["progress"]["stage"] = "initializing"
            task_state["progress"]["message"] = "正在准备评测环境"
            cls._append_log_unlocked(task_state, "正在准备评测环境")

            run_config = EvalRunConfig(
                tool=None if task_state["config"]["tool"] == "all" else task_state["config"]["tool"],
                enable_judge=task_state["config"]["enable_judge"],
                judge_weight=task_state["config"]["judge_weight"],
                run_label=task_state["config"]["run_label"],
                compare_latest=task_state["config"]["compare_latest"],
                verbose=False,
            )

        loop = asyncio.get_running_loop()

        def progress_callback(payload: dict[str, Any]) -> None:
            loop.call_soon_threadsafe(cls._apply_progress_update, task_id, payload)

        try:
            result = await asyncio.to_thread(run_evaluation, run_config, progress_callback)
        except Exception as err:
            cls._mark_error(task_id, str(err))
            return

        cls._mark_success(task_id, result)

    @classmethod
    def _apply_progress_update(cls, task_id: str, payload: dict[str, Any]) -> None:
        with cls._state_lock:
            task_state = cls._tasks.get(task_id)
            if not task_state:
                return

            progress = task_state["progress"]
            for key in (
                "stage",
                "message",
                "total_cases",
                "completed_cases",
                "percent",
                "current_index",
                "current_case_id",
                "current_tool",
                "last_case_result",
            ):
                if key in payload:
                    progress[key] = payload[key]

            message = payload.get("message")
            if message:
                cls._append_log_unlocked(task_state, message)

            if "result" in payload:
                task_state["result"] = payload["result"]

    @classmethod
    def _mark_success(cls, task_id: str, result: dict[str, Any]) -> None:
        with cls._state_lock:
            task_state = cls._tasks.get(task_id)
            if not task_state:
                return
            task_state["status"] = "success"
            task_state["finished_at"] = datetime.now().isoformat(timespec="seconds")
            task_state["progress"]["stage"] = "completed"
            task_state["progress"]["message"] = "评测完成"
            task_state["progress"]["percent"] = 1.0
            task_state["result"] = result
            cls._append_log_unlocked(
                task_state,
                (
                    f"评测完成：{result['run_label']} | "
                    f"通过率 {result['summary']['pass_rate'] * 100:.1f}% | "
                    f"综合分 {result['summary']['average_score'] * 100:.1f}"
                ),
            )
            if cls._active_task_id == task_id:
                cls._active_task_id = None

    @classmethod
    def _mark_error(cls, task_id: str, error_message: str) -> None:
        with cls._state_lock:
            task_state = cls._tasks.get(task_id)
            if not task_state:
                return
            task_state["status"] = "error"
            task_state["finished_at"] = datetime.now().isoformat(timespec="seconds")
            task_state["progress"]["stage"] = "error"
            task_state["progress"]["message"] = error_message
            task_state["error"] = error_message
            cls._append_log_unlocked(task_state, f"评测失败：{error_message}")
            if cls._active_task_id == task_id:
                cls._active_task_id = None

    @classmethod
    def _resolve_task_unlocked(cls, user_id: str, task_id: str | None) -> dict[str, Any] | None:
        if task_id:
            task_state = cls._tasks.get(task_id)
            if task_state and task_state.get("user_id") == user_id:
                return task_state
            return None

        latest_task_id = cls._latest_task_id_by_user.get(user_id)
        if latest_task_id:
            return cls._tasks.get(latest_task_id)
        return None

    @classmethod
    def _get_active_task_unlocked(cls) -> dict[str, Any] | None:
        if not cls._active_task_id:
            return None
        return cls._tasks.get(cls._active_task_id)

    @classmethod
    def _append_log_unlocked(cls, task_state: dict[str, Any], message: str) -> None:
        task_state["logs"].append({
            "time": datetime.now().isoformat(timespec="seconds"),
            "message": message,
        })
        if len(task_state["logs"]) > cls._max_logs:
            task_state["logs"] = task_state["logs"][-cls._max_logs:]

    @classmethod
    def _build_public_status(cls, task_state: dict[str, Any]) -> dict[str, Any]:
        return {
            "task_id": task_state["task_id"],
            "status": task_state["status"],
            "created_at": task_state["created_at"],
            "started_at": task_state["started_at"],
            "finished_at": task_state["finished_at"],
            "config": dict(task_state["config"]),
            "progress": dict(task_state["progress"]),
            "logs": list(task_state["logs"]),
            "result": task_state["result"],
            "error": task_state["error"],
            "is_active": task_state["task_id"] == cls._active_task_id and task_state["status"] in {"queued", "running"},
        }

    @classmethod
    def _prune_tasks_unlocked(cls) -> None:
        if len(cls._tasks) <= cls._max_tasks:
            return

        removable_task_ids = [
            task_id
            for task_id, task in sorted(
                cls._tasks.items(),
                key=lambda item: item[1].get("created_at") or "",
            )
            if task_id != cls._active_task_id
        ]

        while len(cls._tasks) > cls._max_tasks and removable_task_ids:
            target_task_id = removable_task_ids.pop(0)
            cls._tasks.pop(target_task_id, None)
            for user_id, latest_task_id in list(cls._latest_task_id_by_user.items()):
                if latest_task_id == target_task_id:
                    cls._latest_task_id_by_user.pop(user_id, None)

    @staticmethod
    def _normalize_tool(tool_value: Any) -> str | None:
        normalized = str(tool_value or "all").strip().lower()
        if normalized in {"", "all"}:
            return None
        if normalized not in {"resume_match", "resume_rewrite", "interview_followup"}:
            raise ValueError("unsupported eval tool")
        return normalized
