# 求职面试助手知识库素材

这个目录提供一组可直接上传到 AgentChat 知识库的示例材料，便于把平台收敛成“求职面试助手”场景。

除了知识库素材外，这个目录现在也包含了后续优化路线文档，适合在继续二次开发时边看边改。

建议上传顺序：

1. `llm_app_intern_jd_sample.md`
2. `project_resume_writing_tips.md`
3. `interview_answer_framework.md`

建议绑定方式：

- Agent 名称：`求职面试助手`
- 工具：`简历匹配`、`简历改写`、`面试追问`、`联网搜索`
- 知识库：上传本目录中的 markdown 文件
- 简历包装：参考 `resume_packaging.md`

推荐演示链路：

1. 输入岗位 JD 和简历内容，触发 `resume_match` 工具做匹配分析。
2. 继续追问“这段项目经历怎么改成适合实习简历的版本”，触发 `resume_rewrite`。
3. 最后追问“面试官可能怎么问我这个项目”，触发 `interview_followup`。
4. 打开 `/dashboard` 的 `Agent Eval` 标签页，直接通过前端按钮一键触发 Eval 运行，并查看版本趋势、case 明细与版本对比。

推荐继续阅读的优化文档：

1. `optimization_roadmap.md`
2. `file_parsing_and_resume_ingestion.md`
3. `agent_workflow_upgrade.md`
4. `structured_output_and_evaluation.md`
5. `implementation_update_2026_04_21.md`
6. `mineru_tool_integration.md`
7. `mcp_job_workbench_integration.md`
8. `feishu_mcp_integration.md`
9. `agent_evaluation_strategy.md`
10. `agent_eval_interview_flow.md`
