# 飞书 MCP 集成说明

这份文档记录“求职面试助手”当前飞书集成的真实实现状态、问题根因和后续测试方法，方便你复盘、演示和写简历。

## 当前实现状态

当前求职助手已经把飞书能力接到求职场景里，主要包含两类操作：

- 飞书文档：把简历改写结果整理后同步成飞书文档
- 飞书日历：把面试准备内容创建成飞书日程

这两类能力都不是普通本地 Tool，而是通过 `feishu_workspace` 这个 MCP 子智能体来完成。

## 这次修复了什么

本轮不是简单改提示词，而是把飞书链路的几个关键问题真正落到了代码里：

### 1. 飞书 MCP 从远程黑盒切到本地 stdio

现在后端会把系统里的 `飞书` MCP Server 同步成本地 `stdio` 服务，而不是继续依赖远程 SSE 黑盒。

这意味着：

- 飞书工具代码就是你仓库里的代码
- 后续新增参数、加日志、补能力可以直接二开
- 可以明确追踪当前到底调用了哪个飞书工具

相关核心文件：

- `src/backend/agentchat/services/feishu_workspace.py`
- `src/backend/agentchat/database/init_data.py`
- `src/backend/agentchat/mcp_servers/lark_mcp/`

### 2. 本地飞书 MCP 已支持 `user_access_token`

这次给关键飞书工具补了 `user_access_token` 透传：

- `create_document`
- `get_document`
- `write_document_content`
- `create_calendar`
- `get_calendars_list`
- `get_calendar_info`
- `create_calendar_event`
- `append_calendar_event_attendee`

调用时如果配置了 `user_access_token`，工具会走用户身份；否则仍然走应用身份。

### 3. 工具返回结果会明确告诉你当前身份模式

现在飞书工具的返回结果里会带这些信息：

- `token_mode`: `user` 或 `tenant`
- `visibility_hint`: 解释当前结果是否保证出现在个人空间
- `log_id`: 便于去飞书开放平台排查

这样前端和 Agent 不会再把“API 成功”误判成“个人飞书空间一定可见”。

### 4. 前端状态提示不再误导

以前页面只要检测到 `APP_ID / APP_SECRET`，就会显示“飞书能力已就绪”。

现在已经拆成两层状态：

- 只配置 `APP_ID / APP_SECRET`：表示应用身份已连接
- 同时配置 `USER_ACCESS_TOKEN`：才表示个人空间同步能力更完整

聊天页会明确提示：

- 当前只是应用身份，API 可能成功，但结果不一定在个人云文档/个人日历可见
- 如果要个人空间可见，需要补充 `USER_ACCESS_TOKEN`

## 为什么之前飞书 API 200，但你看不到文档

根因不是“没有调用到飞书”，而是“调用身份不对”。

你之前给出的飞书开放平台记录已经证明：

- `POST /open-apis/docx/v1/documents`
- `httpCode = 200`
- `errCode = 0`
- `Authorization = Bearer t-...`

这里的 `t-...` 是 `tenant_access_token`，说明当前请求是应用身份调用，不是用户身份调用。

这会导致一个很容易误判的问题：

- 飞书 API 可以成功
- 文档也确实被创建
- 但它不一定出现在你当前登录账号的个人云文档里

所以“飞书平台有调用记录”和“我个人空间能看到文档”并不是同一件事。

## 现在需要配置什么

你需要在 `MCP Server` 页面找到 `飞书`，填写：

1. `APP_ID`
2. `APP_SECRET`
3. `USER_ACCESS_TOKEN`

含义分别是：

- `APP_ID / APP_SECRET`：让系统具备飞书应用身份调用能力
- `USER_ACCESS_TOKEN`：让文档/日程更可能出现在当前用户个人空间

如果只填前两个：

- 可以发起飞书 API
- 但不能保证个人空间可见

## 推荐测试路径

### 测试飞书文档

1. 进入 `求职面试助手`
2. 先完成一次简历改写
3. 点击 `同步到飞书文档`
4. 查看执行轨迹，确认出现：
   - `MCP 调用: 飞书`
   - `MCP 工具: create_document`
5. 查看返回结果中的：
   - `token_mode`
   - `visibility_hint`
   - `log_id`
6. 再去飞书开放平台核对该 `log_id`

### 测试飞书日历

1. 进入 `求职面试助手`
2. 完成一次面试追问
3. 点击 `安排飞书日程`
4. 查看执行轨迹中是否依次出现：
   - `get_calendars_list` 或 `create_calendar`
   - `create_calendar_event`
5. 检查返回结果中的：
   - `calendar_id`
   - `event_id`
   - `token_mode`

## 当前仍然存在的边界

这次主要解决的是“身份模式、MCP 可控性、状态提示和可追踪性”。

还需要注意的一点是：

- 当前正文写入已经支持标题、段落、无序列表和有序列表
- 更复杂的富文本样式、图片、表格、附件内嵌还没有继续下钻

所以现在更准确的描述应该是：

- 已完成飞书文档创建链路
- 已完成飞书文档正文自动写入链路
- 已完成飞书日历创建链路
- 已支持用户身份和应用身份区分
- 复杂富文本块仍可作为下一步优化点

## 这部分怎么包装到简历

建议写法强调“基于开源平台二开 + MCP 接入 + 身份模式修复 + 可观测性增强”，不要包装成“从零自研飞书系统”。

可用表达：

`基于开源 AgentChat 框架完成求职场景二次开发，将飞书 MCP 接入求职面试助手，支持将简历改写结果同步为飞书文档、将面试准备内容创建为飞书日历，并补齐用户身份鉴权、MCP 本地化接入和执行轨迹展示。`

如果面试官继续追问，可以补充：

- 主 Agent 负责意图识别和任务路由
- 求职分析类能力走普通 Tool
- 外部协同类能力走 MCP
- 飞书能力区分应用身份与用户身份，避免把 API 成功误判为个人空间同步成功
- 前端会展示执行轨迹，后端返回 `token_mode / log_id / visibility_hint` 便于排查
