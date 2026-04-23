# MinerU Tool 集成说明

这份文档记录本轮接入 `MinerU` 的实现方式、运行要求，以及后续写简历时可以如何包装这部分工作。

## 本轮实现了什么

### 1. 新增独立的 MinerU Tool

后端新增了 `mineru_parse` Tool，定位是：

- 接收用户上传文件的 `file_url`
- 调用 MinerU 官方远程 API
- 返回可供后续 Agent Tool 继续使用的正文内容

当前 Tool 能力：

- 解析 PDF
- 解析 DOCX
- 解析图片类文档
- 支持 HTML 文件走 `MinerU-HTML` 模型
- 支持根据上传文件后缀自动选择 `vlm` 或 `MinerU-HTML`
- 支持强制 OCR
- 支持 `markdown` / `text` / `html` 三种输出
- 支持公网 URL 拉取解析
- 支持本地上传文件自动走 MinerU 官方签名上传解析

核心代码：

- `src/backend/agentchat/tools/mineru_parse/action.py`
- `src/backend/agentchat/services/mineru/client.py`

### 2. 新增 MinerU 官方 API 适配层

本轮没有把 MinerU 模型直接塞进 AgentChat 主进程，而是对接官方远程 API。

这样做的好处：

- 避免把重依赖直接耦合进主服务
- 更适合单独部署 MinerU
- 更方便后续替换成本地 Docker 服务或远端解析服务

适配层当前负责：

- 调用 `POST /api/v4/extract/task`
- 调用 `POST /api/v4/file-urls/batch`
- 将本地上传文件 PUT 到 MinerU 返回的签名地址
- 轮询 `GET /api/v4/extract-results/batch/{batch_id}`
- 轮询任务状态
- 下载 `full_zip_url` 结果包
- 统一解析输出为标准结构

### 3. 接进 Agent Tool Calling

本轮已经把 `mineru_parse` 注册进系统默认工具集合，前端执行轨迹会直接显示它的调用记录。

集成位置：

- `src/backend/agentchat/tools/__init__.py`
- `src/backend/agentchat/config/tool.json`
- `src/backend/agentchat/database/init_data.py`

### 4. 接进求职助手工作流

默认 `求职面试助手` 的系统提示已经更新：

- 如果用户上传文件或提供文件链接
- 先优先调用 `mineru_parse`
- 再继续调用：
  - `resume_match`
  - `resume_rewrite`
  - `interview_followup`

这意味着当前项目已经具备更明确的多步链路：

`文件上传 -> MinerU 解析 -> 简历匹配/改写/面试追问`

### 5. 保留轻量解析兜底

当前项目没有废掉之前的本地轻量解析。

仍然保留：

- PyMuPDF / fitz 的快速 PDF 文本抽取
- DOCX XML 直读

这样做的目的：

- 简单文档先快速进上下文
- 复杂文档再由 Agent 决定是否调用 MinerU

这比“一刀切全量走 MinerU”更实用，也更像真实工程。

## 当前目录结构

### 新增模块

- `src/backend/agentchat/services/mineru/`
- `src/backend/agentchat/tools/mineru_parse/`
- `src/backend/agentchat/services/resume_ingestion/file_loader.py`

### 相关改动模块

- `src/backend/agentchat/database/init_data.py`
- `src/backend/agentchat/utils/helpers.py`
- `src/backend/agentchat/core/agents/general_agent.py`

## 运行要求

本轮接入默认优先通过 `config.yaml` 读取 MinerU 服务地址，同时保留环境变量兜底覆盖。

### 关键环境变量

- `MINERU_API_BASE_URL`
- `MINERU_API_TOKEN`
- `MINERU_API_TIMEOUT_SECONDS`
- `MINERU_MODEL_VERSION`

### config.yaml 示例

```yaml
tools:
  mineru:
    base_url: "https://mineru.net"
    token: "官网申请的api token"
    model_version: "auto" # html/htm/xhtml 自动走 MinerU-HTML，其余默认 vlm
    timeout_seconds: 120
    poll_interval_seconds: 1.5
    max_poll_rounds: 80
```

### 自动模型选择规则

当前实现支持自动识别上传文件格式：

- `html` / `htm` / `xhtml` / `shtml` -> `MinerU-HTML`
- 其他文档类型 -> `vlm`

如果你不想自动选择，也可以把 `model_version` 显式写死成：

- `vlm`
- `MinerU-HTML`

### 环境变量覆盖示例

```bash
export MINERU_API_BASE_URL=https://mineru.net
export MINERU_API_TOKEN=your_token
export MINERU_API_TIMEOUT_SECONDS=120
export MINERU_MODEL_VERSION=auto
```

如果同时配置了 `config.yaml` 和环境变量，当前实现会优先使用环境变量。

### 重要限制

当前实现已经支持两种解析模式：

- 公网文件 URL：直接走 `POST /api/v4/extract/task`
- 本地上传或私有存储文件：自动走 `POST /api/v4/file-urls/batch`

这意味着即使当前系统的 `storage.mode` 还是本地 `minio`，上传后的 `file_url` 是：

- `127.0.0.1`
- `localhost`
- 局域网地址

也可以继续调用 `mineru_parse`，后端会自动下载该文件，再通过 MinerU 官方上传接口提交解析。

仍然建议在生产环境中优先使用公网 OSS/CDN，因为这样可以减少一次“本地下载 -> 再上传到 MinerU”的中转开销。

## 当前可演示的链路

推荐演示方式：

1. 上传 PDF 简历
2. 输入岗位 JD
3. 观察执行轨迹里先调用 `MinerU解析`
4. 然后继续调用 `简历匹配`
5. 再继续追问改写和面试问题

这样演示时，Agent 属性会比“只写几个 Prompt Tool”明显很多。

## 这部分怎么写进简历

### 技术实现版

可以写成：

`封装 MinerU 官方文档解析 API 为 Agent Tool，通过 function calling 接入求职助手工作流，支持对 PDF/DOCX/HTML 文件进行高质量解析，并将解析结果串联到简历匹配、简历改写、面试追问等后续工具中。`

### 工程化版

也可以写成：

`设计独立的文档解析适配层，基于 MinerU 官方远程 API 实现任务创建、状态轮询、结果包下载与标准化输出，构建“文件上传 -> 文档解析 -> 下游工具消费”的多步 Agent 链路。`

### 面试回答版

如果面试官追问“为什么不是直接自己写 PDF 解析”，你可以答：

- 轻量场景保留本地解析，保证低成本和响应速度
- 复杂场景接入 MinerU，解决扫描件、双栏排版、表格和 OCR 问题
- 通过 Tool Calling 让 Agent 按需选择高质量解析，而不是每次都走重解析链路

## 下一步最值得继续做的点

### 1. MinerU 结果卡片

现在前端主要通过执行轨迹看到了 `mineru_parse` 的调用。

下一步可以补一张解析结果卡片，展示：

- 文件名
- 解析状态
- 内容预览
- 是否触发 OCR

### 2. 解析结果缓存

现在同一个文件重复调用 MinerU 时，仍然会重复解析。

下一步建议加：

- `file_url -> parse_result` 缓存
- 避免多轮对话反复触发重解析

### 3. 结构化简历抽取

当前 `mineru_parse` 主要返回正文。

下一步可以继续抽取：

- 教育经历
- 项目经历
- 技能栈
- 实习经历

这样可以把 `resume_match` 等工具进一步升级成更强的结构化工作流。
