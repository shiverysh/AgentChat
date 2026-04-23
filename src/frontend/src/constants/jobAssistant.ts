export const JOB_ASSISTANT_NAME = '求职面试助手'

export const JOB_ASSISTANT_DESCRIPTION =
  '围绕岗位 JD、简历内容和项目经历，结合 MinerU 文档解析、MCP 工作台、飞书文档与飞书日历完成匹配分析、改写建议和面试准备。'

export const JOB_ASSISTANT_HIGHLIGHTS = [
  '上传 PDF / DOCX 后可先走 MinerU 高质量文档解析',
  '岗位 JD 与简历一键匹配分析',
  '项目经历改写为更适合实习简历的版本',
  '围绕项目亮点生成面试追问与回答框架',
  '支持通过 MCP 工作台保存简历版本、投递记录和面试计划',
  '支持将改写结果同步到飞书文档，并把面试准备安排到飞书日历'
]

export const JOB_ASSISTANT_QUICK_PROMPTS = [
  {
    label: '岗位匹配分析',
    shortLabel: 'JD 匹配',
    description: '输入岗位要求和简历内容，输出匹配度、缺口与修改建议。',
    prompt:
      '我在面试大模型应用开发实习生岗位。请调用简历匹配工具分析下面的岗位 JD 和我的简历内容，输出匹配度、优势、缺口和修改建议。\n\n岗位 JD：\n【请粘贴岗位描述】\n\n我的简历内容：\n【请粘贴简历或项目经历】'
  },
  {
    label: '上传简历解析',
    shortLabel: 'MinerU解析',
    description: '上传 PDF 或 DOCX 简历后，优先触发 MinerU 解析再继续后续分析。',
    prompt:
      '我已经上传了一份简历文件。请先调用 mineru_parse 对文件做高质量解析，再基于解析结果总结我的核心经历、技能关键词和适合继续做岗位匹配的重点信息。'
  },
  {
    label: '项目经历改写',
    shortLabel: '改写项目',
    description: '把通用项目描述改写成更贴近大模型应用岗位的简历表达。',
    prompt:
      '我在准备大模型应用开发实习生岗位的简历。请调用简历改写工具，把下面这段项目经历改写成适合投递简历的版本，要求突出业务场景、Agent 能力、工具调用链路、RAG 或工作流设计，以及我个人的具体贡献。\n\n项目经历：\n【请粘贴项目原文】'
  },
  {
    label: '面试追问准备',
    shortLabel: '面试追问',
    description: '围绕项目经历生成面试官追问点和回答框架。',
    prompt:
      '我在准备大模型应用开发实习生岗位的面试。请调用面试追问工具，围绕下面这个项目从业务背景、技术方案、Agent 设计、工具调用、效果评估和个人贡献几个维度，给我列出高频追问和作答建议。\n\n项目内容：\n【请粘贴项目经历】'
  },
  {
    label: '记录岗位投递',
    shortLabel: '记录投递',
    description: '通过 MCP 工作台沉淀岗位、公司、状态和备注。',
    prompt:
      '请调用求职工作台 MCP，帮我记录一条岗位投递信息。岗位名称是【请填写岗位】；公司名称是【请填写公司】；当前状态先记为待投递；如果我补充了岗位链接或备注，也一起保存。'
  },
  {
    label: '同步飞书文档',
    shortLabel: '飞书文档',
    description: '把简历改写或项目总结同步为一篇飞书文档，方便继续编辑和投递。',
    requiresFeishu: true,
    prompt:
      '请调用 feishu_workspace（飞书 MCP），把下面内容整理并同步为一篇飞书文档。标题控制在20字内，优先保留目标岗位、版本说明和正文内容；如果需要可先创建文档再写入。\n\n目标岗位：\n【请填写岗位】\n\n版本说明：\n【请填写说明】\n\n正文内容：\n【请粘贴简历改写或项目总结】'
  },
  {
    label: '安排飞书日程',
    shortLabel: '飞书日历',
    description: '把面试准备事项安排到飞书日历，形成可执行的提醒。',
    requiresFeishu: true,
    requiresFeishuUserToken: true,
    prompt:
      '请调用 feishu_workspace（飞书 MCP），帮我创建一个飞书面试准备日程。如果没有合适的日历，可先创建“求职面试”日历。请根据下面内容生成标题、描述和时间安排。\n\n目标岗位：\n【请填写岗位】\n\n公司名称：\n【请填写公司】\n\n准备重点：\n【请填写准备重点】\n\n期望时间：\n【请填写具体时间，例如 2026-04-22 19:00 到 2026-04-22 20:00】'
  }
]

export function isJobAssistantAgentName(name = ''): boolean {
  return name.includes(JOB_ASSISTANT_NAME)
}
