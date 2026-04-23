# 求职工作台 MCP 集成说明

这份文档记录当前 `求职面试助手` 的 MCP 改造结果，以及这部分内容如何包装到简历和面试表达中。

## 当前实现结论

本轮已经把“求职工作台”从“类似 MCP 的内部封装”升级为真正的 `stdio MCP`：

- Agent 主流程仍然在 `GeneralAgent`
- 当需要保存简历版本、记录投递、生成面试计划、保存追问笔记时，会调用 `job_hunt_board`
- `job_hunt_board` 绑定的是一个独立启动的 `FastMCP` 子进程
- 子进程通过 `stdio` 暴露 4 个 MCP Tool
- Tool 执行后写入工作台数据表
- 前端工作台面板通过 REST API 拉取结构化结果做展示

这意味着现在项目里已经同时具备：

- Tool Calling
- MCP Calling
- 结构化数据落库
- 前端结果面板
- 执行轨迹可视化

## MCP 与普通 Tool 的边界

这次改造后，区别已经比较清楚：

- 普通 Tool：直接挂在主 Agent 上，本质是应用进程内能力
- MCP：主 Agent 通过 MCP Client 连接独立 MCP Server，再去调该 Server 暴露的工具

在这个项目里：

- `resume_match`、`resume_rewrite`、`interview_followup`、`mineru_parse` 属于普通 Tool
- `save_resume_version`、`record_job_application`、`create_interview_plan`、`save_followup_notes` 属于 MCP Tool

所以现在不是“名字换成 MCP”，而是架构上确实多了一层标准化协议调用。

## 当前架构

完整链路如下：

`上传简历 -> MinerU 解析 -> 简历匹配/改写/面试追问 -> Agent 决策调用 job_hunt_board -> stdio MCP Server 执行 MCP Tool -> 工作台表落库 -> 前端工作台面板刷新展示`

执行轨迹里可以看到两层事件：

- `MCP 调用`
- `MCP 工具`

这两层信息能明显体现出 Agent 不是只在“回答问题”，而是在调度能力并落地结果。

## 本轮落地内容

### 1. 独立 stdio MCP Server

新增独立 MCP 服务进程：

- `src/backend/agentchat/mcp_servers/job_hunt_workbench/mcp_server.py`

采用 `FastMCP` 暴露 4 个工具：

- `save_resume_version`
- `record_job_application`
- `create_interview_plan`
- `save_followup_notes`

服务启动方式是：

- `python -m agentchat.mcp_servers.job_hunt_workbench.mcp_server`

### 2. stdio 配置生成与系统注册

相关核心文件：

- `src/backend/agentchat/services/job_hunt_workspace.py`
- `src/backend/agentchat/database/init_data.py`

启动时会自动：

1. 生成 `stdio` 连接配置
2. 把 `求职工作台` 写入系统 MCP Server
3. 将其绑定到默认 `求职面试助手`

### 3. MCP Client 适配

相关文件：

- `src/backend/agentchat/utils/convert.py`
- `src/backend/agentchat/core/agents/mcp_agent.py`
- `src/backend/agentchat/core/agents/general_agent.py`

本轮补上了：

- `stdio` 类型 MCP 配置解析
- 主 Agent 根据不同传输方式动态构建 MCPConfig
- MCP Tool 调用阶段的事件埋点和日志输出
- `current_user_id` 自动注入

### 4. 前端工作台面板与轨迹展示

前端不是只展示 Markdown，而是有可见页面承接：

- `src/frontend/src/components/jobWorkbenchPanel/JobWorkbenchPanel.vue`
- `src/frontend/src/pages/conversation/chatPage/chatPage.vue`
- `src/frontend/src/apis/job-hunt-workbench.ts`

同时配合已有卡片动作按钮，实现：

- 简历匹配后记录岗位投递
- 简历改写后保存简历版本
- 面试追问后生成面试计划
- 面试追问后保存追问笔记

## 如何演示

推荐按下面顺序演示：

1. 进入 `求职面试助手`
2. 上传简历并触发岗位匹配
3. 继续做简历改写或面试追问
4. 点击结果卡片上的工作台动作按钮
5. 观察执行轨迹中是否出现 `MCP 调用` 和 `MCP 工具`
6. 观察顶部 `求职工作台` 面板是否出现新的结构化记录

如果这条链路打通，你在面试里就可以明确说明：

- 主 Agent 负责理解任务和调度能力
- 业务分析类能力走普通 Tool
- 结果沉淀类能力走 MCP
- 最终结果会落库并回显到前端

## 简历包装建议

建议按“基于开源 AgentChat 的二次开发”来写，不要包装成从零搭建整个平台。

### 一句话版

`基于开源 AgentChat 框架二次开发求职面试助手，接入简历解析、岗位匹配、简历改写、面试追问与 stdio MCP 工作台，实现分析结果落库和前端可视化展示。`

### 技术版

`基于 AgentChat 完成求职场景二开，新增简历匹配、简历改写、面试追问等 Tool，并设计独立 FastMCP stdio Server 暴露 save_resume_version / record_job_application / create_interview_plan / save_followup_notes 等 MCP Tool，打通 Agent 调度、结构化数据落库、执行轨迹展示与前端工作台联动。`

### 面试表达版

如果面试官追问“你这里的 MCP 具体做了什么”，可以这样回答：

- 普通 Tool 负责生成分析结果，例如匹配分析、简历改写、追问建议
- MCP 负责把这些结果转成可持续使用的工作台资产，例如简历版本、投递记录、面试计划、复盘笔记
- 我把 MCP 做成了独立 `FastMCP stdio` 服务，而不是单纯写几个本地函数
- 前端还能直接看到调用后生成的结构化结果，这样项目更像完整应用而不是聊天 Demo

## 对简历价值的判断

这一版已经比普通“聊天 + Prompt”项目更适合放进大模型应用开发实习简历，因为它能支撑下面这些关键词：

- Agent 调度
- Function Calling / Tool Calling
- MCP 集成
- 文档解析
- 结构化输出
- 前后端联动
- 大模型应用二次开发

如果后续再补一轮评测、异常处理和更强的多轮状态管理，这个项目的简历说服力还会再上一个台阶。
