# 求职面试助手阶段性实现记录（2026-04-21）

这份文档记录本轮已经真正落到代码里的升级点，方便后续演示、复盘和写简历时使用。

## 本轮已完成

### 1. 上传简历不再只是传链接

已经新增真实文件解析链路，支持把上传文件正文注入到对话输入中。

当前支持：

- PDF
- DOCX
- TXT / MD

本轮实现内容：

- 新增 `resume_ingestion` 服务层
- completion 接口在进入 Agent 前尝试读取上传文件正文
- 对解析后的文本做基础清洗与截断
- 如果解析失败，保留文件链接兜底

核心价值：

- 上传简历这件事从“形式支持”变成了“真实可用”
- 后续 `resume_match`、`resume_rewrite`、`interview_followup` 能基于文件正文工作

### 2. 简历改写和面试追问已经有结构化结果卡片

本轮把两个 Tool 也接成了结构化事件输出，不再只有简历匹配卡片。

已接入的结构化结果：

- `resume_match`
- `resume_rewrite`
- `interview_followup`

前端现在会按 Tool 类型分别渲染卡片，而不是只靠 Markdown 文本展示。

### 3. 上传链路补了真实可用性修复

本轮还修了两个会直接影响体验的问题：

- 聊天页上传文件时补上了 `Authorization`
- 上传接口返回可访问的下载地址，不再错误拼接 MinIO 路径

这两个修完之后，前端上传标签、后端解析、Agent 使用才算是一条完整链路。

### 4. 接入 MinerU 文档解析 Tool

在原有轻量解析基础上，本轮又新增了 `mineru_parse` Tool。

当前工作方式是：

- 默认保留轻量解析，先把文件正文注入上下文
- 如果用户上传文件或需要更高质量解析，Agent 可以继续调用 `mineru_parse`
- `mineru_parse` 会调独立的 `mineru-api`
- 解析结果再串给 `resume_match`、`resume_rewrite`、`interview_followup`

这让项目的 Agent 属性更明确，不再只是“后端先做完解析，前端再显示结果”。

## 本轮涉及的主要模块

后端：

- `src/backend/agentchat/services/resume_ingestion/parser.py`
- `src/backend/agentchat/services/mineru/client.py`
- `src/backend/agentchat/api/v1/completion.py`
- `src/backend/agentchat/api/v1/upload.py`
- `src/backend/agentchat/tools/mineru_parse/action.py`
- `src/backend/agentchat/tools/resume_rewrite/action.py`
- `src/backend/agentchat/tools/interview_followup/action.py`

前端：

- `src/frontend/src/pages/conversation/chatPage/chatPage.vue`
- `src/frontend/src/utils/toolOutput.ts`
- `src/frontend/src/components/resumeRewriteCard/ResumeRewriteCard.vue`
- `src/frontend/src/components/interviewFollowupCard/InterviewFollowupCard.vue`

## 现在怎么演示

推荐按下面顺序演示：

1. 进入 `求职面试助手`
2. 上传一份 PDF 或 DOCX 简历
3. 输入岗位 JD，先做匹配分析
4. 继续追问“把这段经历改写成适合大模型应用开发实习的版本”
5. 再追问“面试官会怎么继续问我这个项目”

演示时你能强调：

- 文件上传后后端会真实解析正文
- 复杂文档会进一步走 MinerU Tool
- Agent 会调用不同 Tool 完成匹配、改写、追问
- 页面能看到执行轨迹和结构化结果卡片

## 当前还没做完，但下一步最值得做

### 1. 文件解析状态前端提示

现在文件已经被后端使用了，但前端还没有显式提示：

- 已上传
- 已解析
- 解析失败

这是下一步最直观的体验优化点。

### 2. 卡片上的一键操作

建议继续补：

- 一键复制改写结果
- 一键继续生成面试追问
- 一键继续追问某个技术点

### 3. 多步工作流编排

当前还是“Agent 判断调哪个 Tool”。

下一步可以升级成更明确的流程：

- 识别任务
- 解析材料
- 选择 Tool
- 汇总结果

这样更适合往 LangGraph / Workflow 方向包装。

### 4. 评测样例和调用统计

下一步建议开始补：

- 固定 Demo 样例
- Tool 调用成功率
- 平均耗时
- 输出质量检查

## 本轮验证结果

已经完成：

- 后端编译检查：`./.venv/bin/python -m compileall -q agentchat`
- 前端类型检查：`npm run lint`
- 前端生产构建：`npm run build`

当前构建仍有历史遗留 warning，但不是本轮新增问题，主要包括：

- Sass legacy JS API warning
- `mars-chat.vue` 中的 `eval` warning
- 前端 chunk size warning

## 简历/面试里现在可以怎么讲

你现在可以把项目表述成：

`基于开源 AgentChat 框架做二次开发，围绕求职场景设计并实现了简历文件接入、Tool Calling、结构化结果卡片和执行轨迹展示，支持岗位匹配分析、简历改写和面试追问。`

如果要强调工程实现，可以继续说：

`我补齐了文件上传后的解析链路，支持 PDF/DOCX 简历文本抽取，并通过 SSE 结构化事件把不同 Tool 的结果渲染成前端卡片，而不是单纯输出 Markdown 文本。`
