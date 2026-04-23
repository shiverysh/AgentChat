# 求职助手 Agent Eval 报告

## 总览

- 总样例数：6
- 通过样例数：6
- 通过率：100.0%
- 综合平均得分：0.94
- 规则平均得分：0.99
- Judge 平均得分：0.86

## 运行耗时

- 单样例平均耗时：70.33s
- 最慢样例耗时：96.78s

## 分能力汇总

### resume_match

- 样例数：2
- 通过率：100.0%
- 综合平均得分：0.95
- 规则平均得分：1.00
- Judge 平均得分：0.86
- 平均耗时：65.12s

### resume_rewrite

- 样例数：2
- 通过率：100.0%
- 综合平均得分：0.93
- 规则平均得分：0.99
- Judge 平均得分：0.83
- 平均耗时：62.49s

### interview_followup

- 样例数：2
- 通过率：100.0%
- 综合平均得分：0.95
- 规则平均得分：0.98
- Judge 平均得分：0.89
- 平均耗时：83.37s

## 样例明细

### resume_match_job_assistant

- Tool：`resume_match`
- 综合得分：0.96
- 规则得分：1.00
- 结果：PASS
- 阈值：0.72
- Judge 得分：0.88

**规则指标**

| 指标 | 分数 |
| --- | --- |
| match_score_range | 1.00 |
| matched_strengths_count | 1.00 |
| missing_requirements_count | 1.00 |
| revision_suggestions_count | 1.00 |
| interview_focus_count | 1.00 |
| expected_keyword_coverage | 1.00 |
| missing_keyword_coverage | 1.00 |
| summary_presence | 1.00 |

**Judge 指标**

| 指标 | 分数 |
| --- | --- |
| jd_alignment | 0.90 |
| gap_detection | 0.85 |
| suggestion_actionability | 0.82 |
| factual_grounding | 0.93 |

**说明**

- 输出匹配度：85/100
- Judge 摘要：Agent输出高度贴合岗位JD与简历事实，精准捕获预期的缺失项（评测、监控），技术建议具备强可执行性，整体逻辑严密且无事实捏造。
- Judge 优势：精准对齐JD核心职责与技术栈，明确命中预期缺失的‘评测’与‘监控’要求，匹配度评估客观准确。；修改建议与面试聚焦高度具体，直接给出LangSmith/OpenTelemetry接入、Few-shot/CoT调优、SSE容错降级等可落地技术方案。
- Judge 不足：缺失要求中存在少量超纲推断（如要求实习生在简历阶段展现LangGraph底层状态管理深度），对候选人略有苛责。；部分建议（如ATS关键词前置加粗）偏向通用求职技巧，与LLM应用开发的专业技术深度关联较弱。

### resume_match_api_agent

- Tool：`resume_match`
- 综合得分：0.95
- 规则得分：1.00
- 结果：PASS
- 阈值：0.68
- Judge 得分：0.85

**规则指标**

| 指标 | 分数 |
| --- | --- |
| match_score_range | 1.00 |
| matched_strengths_count | 1.00 |
| missing_requirements_count | 1.00 |
| revision_suggestions_count | 1.00 |
| interview_focus_count | 1.00 |
| expected_keyword_coverage | 1.00 |
| missing_keyword_coverage | 1.00 |
| summary_presence | 1.00 |

**Judge 指标**

| 指标 | 分数 |
| --- | --- |
| jd_alignment | 0.85 |
| gap_detection | 0.90 |
| suggestion_actionability | 0.90 |
| factual_grounding | 0.75 |

**说明**

- 输出匹配度：85/100
- Judge 摘要：输出精准覆盖JD核心技能与加分项，缺漏识别准确，建议具备高度实操性，但能力评估用词与打分略有拔高。
- Judge 优势：精准命中期望的关键词匹配与缺失项，结构化输出完整且严格对齐JD技术栈与岗位要求；修改建议与面试聚焦均提供具体技术路径与量化指标，具备强可执行性与岗位针对性
- Judge 不足：能力评估用词（如“熟练掌握”“深入实践”“掌握”）较简历原文的“使用/实践”存在明显拔高，事实保留度需收紧；匹配分数直接给出预期区间上限85分，未充分体现Function Calling与异常处理缺失带来的合理扣分，分数弹性不足

### resume_rewrite_job_assistant

- Tool：`resume_rewrite`
- 综合得分：0.94
- 规则得分：1.00
- 结果：PASS
- 阈值：0.72
- Judge 得分：0.82

**规则指标**

| 指标 | 分数 |
| --- | --- |
| detected_issues_count | 1.00 |
| rewritten_resume_count | 1.00 |
| supplement_suggestions_count | 1.00 |
| highlight_keywords_count | 1.00 |
| expected_keyword_coverage | 1.00 |
| source_fact_retention | 1.00 |
| fabrication_penalty | 1.00 |
| strategy_presence | 1.00 |

**Judge 指标**

| 指标 | 分数 |
| --- | --- |
| role_alignment | 0.82 |
| factual_preservation | 0.95 |
| rewrite_quality | 0.78 |
| keyword_strength | 0.72 |

**说明**

- Judge 摘要：严格遵循事实边界进行专业化改写，精准对齐岗位技术栈要求，但核心关键词未融入正文导致技术穿透力略有不足。
- Judge 优势：坚守事实底线，未强行编造未接触的技术框架，有效规避简历注水风险；改写逻辑清晰，将口语化描述精准转化为工程链路表达，并给出极具针对性的JD对齐建议
- Judge 不足：改写条目偏重宏观业务描述，缺乏对具体技术实现细节（如接口设计、并发/流式机制）的具象刻画；核心JD关键词仅置于高亮与建议模块，未以合理形式（如技术栈/熟悉项）渗入改写正文，影响ATS系统匹配度

### resume_rewrite_api_agent

- Tool：`resume_rewrite`
- 综合得分：0.93
- 规则得分：0.97
- 结果：PASS
- 阈值：0.70
- Judge 得分：0.85

**规则指标**

| 指标 | 分数 |
| --- | --- |
| detected_issues_count | 1.00 |
| rewritten_resume_count | 1.00 |
| supplement_suggestions_count | 1.00 |
| highlight_keywords_count | 1.00 |
| expected_keyword_coverage | 0.80 |
| source_fact_retention | 1.00 |
| fabrication_penalty | 1.00 |
| strategy_presence | 1.00 |

**Judge 指标**

| 指标 | 分数 |
| --- | --- |
| role_alignment | 0.90 |
| factual_preservation | 0.75 |
| rewrite_quality | 0.80 |
| keyword_strength | 0.95 |

**说明**

- Judge 摘要：该结果高度对齐岗位JD与技术关键词，改写专业且结构完整，但存在部分效果描述的合理推断（非原文事实）及单项目拆分过长的问题，需精简与事实核验后方可直接投递。
- Judge 优势：精准映射JD核心要求（工具调用、多步推理、向量检索、接口编排），术语使用高度专业且符合LLM应用开发工程范式。；诊断与补充建议极具实操性，明确指出了底层实现机制、优化对比指标等需补充的关键信息，指导性强。
- Judge 不足：事实保留存在轻微越界，原文仅描述功能实现，改写中添加了“提升稳定性与匹配精度”、“保障数据追溯能力”等结果性推断，非原始事实。；单个项目被拆分为5条简历要点，篇幅冗余，实际简历排版时需进一步合并为2-3条以保证版面紧凑与可执行性。

### interview_followup_job_assistant

- Tool：`interview_followup`
- 综合得分：0.96
- 规则得分：1.00
- 结果：PASS
- 阈值：0.72
- Judge 得分：0.90

**规则指标**

| 指标 | 分数 |
| --- | --- |
| question_count | 1.00 |
| answer_outline_completeness | 1.00 |
| deep_dive_points_count | 1.00 |
| risk_points_count | 1.00 |
| topic_coverage | 1.00 |
| summary_presence | 1.00 |

**Judge 指标**

| 指标 | 分数 |
| --- | --- |
| question_depth | 0.88 |
| answer_framework_quality | 0.85 |
| role_relevance | 0.95 |
| risk_awareness | 0.90 |

**说明**

- 生成追问数：5
- Judge 摘要：输出高度贴合LLM应用开发实习生岗位与给定项目背景，问题设计具备较强的工程实战深度，答案框架逻辑严密且可执行性强，风险识别覆盖技术、安全与数据评估全链路，完全达到并超出预期标准。
- Judge 优势：问题精准锚定项目技术栈（LangGraph/MCP/MinerU/SSE），深度结合状态流转、鉴权隔离、流式同步等工程核心难点，极具实战考察价值。；答案提纲采用“设计动机-实现路径-异常处理”的结构化逻辑，风险点覆盖网络拓扑、降级兜底与评估偏差，具备极强的防御性准备指导意义。
- Judge 不足：答案框架偏重宏观策略，缺乏对具体关键API调用、核心配置参数或代码片段的指引，实习生在实际应答时可能难以具象化落地。；效果评估维度虽提及LLM-as-a-Judge与离线测试集，但未明确标注Token成本约束与评判防幻觉校验的具体工程手段，对实习生实操的指导颗粒度可进一步细化。

### interview_followup_api_agent

- Tool：`interview_followup`
- 综合得分：0.93
- 规则得分：0.97
- 结果：PASS
- 阈值：0.70
- Judge 得分：0.88

**规则指标**

| 指标 | 分数 |
| --- | --- |
| question_count | 1.00 |
| answer_outline_completeness | 1.00 |
| deep_dive_points_count | 1.00 |
| risk_points_count | 1.00 |
| topic_coverage | 0.80 |
| summary_presence | 1.00 |

**Judge 指标**

| 指标 | 分数 |
| --- | --- |
| question_depth | 0.85 |
| answer_framework_quality | 0.80 |
| role_relevance | 0.95 |
| risk_awareness | 0.90 |

**说明**

- 生成追问数：5
- Judge 摘要：高度贴合岗位核心诉求与项目背景，技术链路覆盖完整且风险提示切中工程痛点；回答框架具备良好可执行性，但实操层面的量化指标与具体技术锚点略显不足，部分宏观架构问题对实习生略超纲。
- Judge 优势：精准对齐岗位JD与项目背景，全面覆盖工具召回、参数抽取、Milvus检索及多步异常处理等核心考点，技术追问逻辑严密且层层递进。；风险提示直击生产环境落地痛点（如Token成本失控、下游雪崩容灾、Schema变更同步），具备极强的实战避坑与自查指导价值。
- Judge 不足：部分问题（如十万级API架构演进与分片策略）偏向宏观系统容量规划，对实习生岗位的实际考察权重偏高，偏离日常开发职责。；回答框架虽结构清晰，但多依赖“说明/阐述”等动作指引，缺乏具体可量化的评估基线或Prompt/调参示例作为答题参考锚点。
