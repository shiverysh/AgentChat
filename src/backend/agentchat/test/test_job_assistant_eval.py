import unittest

from agentchat.evals.job_assistant.compare import build_comparison_report
from agentchat.evals.job_assistant.scorer import score_case, summarize_scores
from agentchat.evals.job_assistant.scorer import merge_case_score


class JobAssistantEvalTestCase(unittest.TestCase):

    def test_resume_match_scoring(self):
        case = {
            "id": "resume_match_demo",
            "tool": "resume_match",
            "expectations": {
                "expected_keywords": ["Python", "LangGraph", "MCP"],
                "expected_missing_keywords": ["评测"],
                "expected_score_range": [60, 100],
                "min_matched_strengths": 2,
                "min_missing_requirements": 1,
                "min_revision_suggestions": 2,
                "min_interview_focus": 2,
                "pass_threshold": 0.7,
            },
        }
        result = {
            "overall_summary": "候选人与岗位方向高度相关，具备 Python、LangGraph 和 MCP 经验。",
            "match_score": 78,
            "matched_strengths": ["熟悉 Python", "具备 LangGraph 工作流经验"],
            "missing_requirements": ["缺少系统化评测经验"],
            "revision_suggestions": ["补充评测方案", "强化项目量化结果"],
            "interview_focus": ["Agent 设计", "工具调用链路"],
        }

        scored = score_case(case, result)
        self.assertGreaterEqual(scored["overall_score"], 0.7)
        self.assertTrue(scored["passed"])

    def test_resume_rewrite_penalizes_fabrication(self):
        case = {
            "id": "resume_rewrite_demo",
            "tool": "resume_rewrite",
            "expectations": {
                "expected_keywords": ["Tool Calling", "MCP"],
                "source_facts": ["Python", "FastAPI"],
                "forbidden_keywords": ["自研大模型"],
                "min_detected_issues": 1,
                "min_rewritten_resume": 2,
                "min_supplement_suggestions": 1,
                "min_highlight_keywords": 2,
            },
        }
        result = {
            "overall_strategy": "围绕 Tool Calling 和 MCP 重写项目经历。",
            "detected_issues": ["表述偏泛"],
            "rewritten_resume": ["使用 Python 与 FastAPI 完成 Agent 应用改造", "封装 Tool Calling 与 MCP 集成链路"],
            "supplement_suggestions": ["补充量化指标"],
            "highlight_keywords": ["Tool Calling", "MCP", "自研大模型"],
        }

        scored = score_case(case, result)
        self.assertLess(scored["metric_scores"]["fabrication_penalty"], 1.0)

    def test_summary_aggregation(self):
        summary = summarize_scores([
            {"tool": "resume_match", "overall_score": 0.8, "passed": True},
            {"tool": "resume_match", "overall_score": 0.6, "passed": False},
            {"tool": "resume_rewrite", "overall_score": 0.9, "passed": True},
        ])
        self.assertEqual(summary["total_cases"], 3)
        self.assertEqual(summary["passed_cases"], 2)
        self.assertIn("resume_match", summary["tool_summary"])

    def test_merge_case_score_with_judge(self):
        merged = merge_case_score(
            {
                "case_id": "demo",
                "tool": "resume_match",
                "overall_score": 0.8,
                "rule_score": 0.8,
                "pass_threshold": 0.7,
                "passed": True,
                "metric_scores": {"a": 0.8},
                "judge_metric_scores": {},
                "notes": [],
            },
            judge_case_score={
                "overall_score": 0.5,
                "metric_scores": {"jd_alignment": 0.5},
                "summary": "Judge 认为还有优化空间",
                "strengths": ["贴合岗位"],
                "weaknesses": ["建议不够具体"],
            },
            judge_weight=0.4,
        )
        self.assertAlmostEqual(merged["overall_score"], 0.68, places=2)
        self.assertEqual(merged["judge_score"], 0.5)
        self.assertIn("Judge 摘要", merged["notes"][0])

    def test_compare_report(self):
        comparison = build_comparison_report(
            {
                "run_label": "v2",
                "summary": {
                    "average_score": 0.82,
                    "rule_average_score": 0.78,
                    "judge_average_score": 0.9,
                    "pass_rate": 0.8,
                    "runtime": {
                        "average_elapsed_seconds": 1.2,
                        "tool_runtime": {
                            "resume_match": {"average_elapsed_seconds": 1.0},
                        },
                    },
                    "tool_summary": {
                        "resume_match": {
                            "average_score": 0.8,
                            "rule_average_score": 0.75,
                            "judge_average_score": 0.88,
                            "pass_rate": 0.8,
                        },
                    },
                },
            },
            {
                "run_label": "baseline",
                "summary": {
                    "average_score": 0.72,
                    "rule_average_score": 0.7,
                    "judge_average_score": 0.8,
                    "pass_rate": 0.6,
                    "runtime": {
                        "average_elapsed_seconds": 1.5,
                        "tool_runtime": {
                            "resume_match": {"average_elapsed_seconds": 1.4},
                        },
                    },
                    "tool_summary": {
                        "resume_match": {
                            "average_score": 0.7,
                            "rule_average_score": 0.68,
                            "judge_average_score": 0.8,
                            "pass_rate": 0.6,
                        },
                    },
                },
            },
        )
        self.assertEqual(comparison["current_label"], "v2")
        self.assertAlmostEqual(comparison["overall_delta"]["average_score_delta"], 0.1, places=2)
        self.assertIn("resume_match", comparison["tool_deltas"])


if __name__ == "__main__":
    unittest.main()
