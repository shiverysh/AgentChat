# 求职面试助手 Agent 评测方案

这份文档对应项目里已经落地的升级版 Eval 子系统，目标不是追求“学术上完整”的 Benchmark，而是让当前求职 Agent 项目具备：

- 可重复运行的固定样例集
- 可解释的规则打分
- 可选的 LLM-as-a-Judge 评分
- 可导出的评测报告
- 可对比的版本化历史结果
- 能写进简历和面试里的量化口径

## 当前落地范围

当前评测覆盖 3 个核心 Tool：

- `resume_match`
- `resume_rewrite`
- `interview_followup`

对应代码目录：

- `src/backend/agentchat/evals/job_assistant/cases.json`
- `src/backend/agentchat/evals/job_assistant/scorer.py`
- `src/backend/agentchat/evals/job_assistant/judge.py`
- `src/backend/agentchat/evals/job_assistant/compare.py`
- `src/backend/agentchat/evals/job_assistant/runner.py`

## 评测思路

当前采用的是“固定样例 + 规则评分 + 可选 Judge 模型”的组合方案。

原因很直接：

1. 你现在最需要的是一套能稳定跑通、能产出数字、能支持项目讲述的 Eval
2. 规则评分成本低、可解释性强，适合二开项目快速落地
3. LLM Judge 可以补充“贴合岗位 / 事实保真 / 建议质量”这类更接近真实主观评价的维度

## 样例集设计

当前内置 6 条样例：

- `resume_match` 2 条
- `resume_rewrite` 2 条
- `interview_followup` 2 条

每条样例包含：

- 输入内容
- 目标岗位
- 期望关键词
- 最低结构要求
- 通过阈值

这样做的价值是：

- 你每次改 Prompt、改 Tool、改链路后，都能复跑同一组样例
- 可以直接比较不同版本的平均分、通过率和分能力得分

## 当前量化指标

当前报告里会同时输出三类指标：

- 规则得分
- Judge 得分（开启 `--enable-judge` 时）
- 单样例耗时 / 各 Tool 平均耗时

### `resume_match`

- 匹配分是否落在合理区间
- 已匹配优势数量
- 缺口数量
- 修改建议数量
- 面试重点数量
- 岗位关键词覆盖率
- 缺口关键词覆盖率

### `resume_rewrite`

- 问题诊断数量
- 改写结果数量
- 补充建议数量
- 强化关键词数量
- 岗位关键词覆盖率
- 原始事实保留率
- 疑似编造惩罚

### `interview_followup`

- 追问数量
- 回答框架完整度
- 深挖点数量
- 风险点数量
- 预期主题覆盖率

## 如何运行

在后端目录执行：

```bash
cd src/backend
./.venv/bin/python -m agentchat.evals.job_assistant.runner
```

如果只想跑某一个 Tool：

```bash
./.venv/bin/python -m agentchat.evals.job_assistant.runner --tool resume_match
```

如果想启用 Judge 并标记版本号：

```bash
./.venv/bin/python -m agentchat.evals.job_assistant.runner \
  --enable-judge \
  --judge-weight 0.35 \
  --run-label v1
```

如果想和上一次结果做对比：

```bash
./.venv/bin/python -m agentchat.evals.job_assistant.runner \
  --enable-judge \
  --run-label v2 \
  --compare-latest
```

默认会输出两份报告：

- `src/backend/reports/job_assistant_eval/latest.json`
- `src/backend/reports/job_assistant_eval/latest.md`

同时还会保留版本历史：

- `src/backend/reports/job_assistant_eval/history/`
- `src/backend/reports/job_assistant_eval/compare/`

## 报告里能看到什么

JSON / Markdown 报告里会包含：

- 总样例数
- 通过样例数
- 总通过率
- 平均得分
- 规则平均得分
- Judge 平均得分
- 各 Tool 平均得分
- 各 Tool 平均耗时
- 每条样例的分项指标

这意味着你后续可以讲非常具体的话：

`我给求职 Agent 增加了一套固定样例 Eval，覆盖简历匹配、简历改写和面试追问 3 个核心 Tool，并引入规则评分、LLM Judge 和版本对比报告，对通过率、平均分和耗时进行持续追踪。`

## 适合写进简历的量化口径

这套 Eval 跑起来后，比较适合写的数字是：

- 固定评测样例数
- 三个核心 Tool 的平均得分
- 样例整体通过率
- Judge 评分结果
- 平均耗时
- 单项指标提升情况

例如：

- `构建覆盖 3 个核心 Tool 的固定样例 Eval，支持对 6 条场景样例进行自动评分、Judge 复核与通过率统计`
- `沉淀版本化评测报告，支持对平均分、通过率和单样例耗时进行前后版本对比`

## 后续可继续升级

当前这版已经足够写进简历，但如果继续打磨，还可以再加三步：

### 1. 在线调用统计

把真实用户调用链路里的：

- Tool 成功率
- 平均耗时
- 错误率
- 最常调用 Tool

一起纳入看板。

### 2. 前端评测看板

把 `latest.json` 和版本对比结果接到前端页面，展示：

- 各 Tool 平均分
- Judge / Rule 双评分
- 版本变化趋势
- 低分样例清单

### 3. 线上结果抽样复核

从真实对话里抽样一部分结果进入人工或 Judge 复核，避免只在离线样例上优化。

## 总结

这个项目完全适合加入 Agent 评测策略，而且很值得做。

因为一旦有了 Eval，你的项目叙述就能从：

`我做了一个求职 Agent`

升级成：

`我不仅做了 Agent 工作流和 Tool/MCP 集成，还补了固定样例评测与自动评分机制，用来量化不同版本在简历匹配、改写和面试追问任务上的效果。`
