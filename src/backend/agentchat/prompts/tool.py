WEATHER_PROMPT = """
🌤️ {} 地区天气信息

📍 实时天气状况  
{}  

📅 未来天气预报  
{}  

💡 温馨提示：以上天气数据由权威气象机构提供，力求准确可靠。天气瞬息万变，建议您密切关注最新预报，合理调整穿衣、出行及户外活动安排，确保安全与舒适。阴晴冷暖，皆有准备，方能从容应对每一天！
"""

MESSAGE_PROMPT = "📅 {}: 🌡️ 白天 {}°C / 夜间 {}°C | ☀️ 白天：{} | 🌙 夜间：{}"

DELIVERY_PROMPT = """
📦 物流追踪信息

📋 订单详情  
• 快递公司：{}  
• 运单号码：{}  

🚚 物流动态  
{}  

💡 温馨提醒：物流信息实时更新，若显示“运输中”或“暂无更新”，请耐心等待。如遇异常延迟、包裹丢失或需紧急协助，建议第一时间联系对应快递公司官方客服，或通过其官网、官方App输入运单号查询最新轨迹。祝您收件顺利，包裹平安抵达！
"""

RESUME_MATCH_PROMPT = """
你是一名专业的求职顾问和面试辅导助手，负责分析候选人简历与岗位 JD 的匹配情况。

请严格根据提供的岗位描述和简历内容进行分析，不要编造候选人没有提到的经历或技能。
你的输出必须是一个 JSON object，且只返回 JSON，不要添加额外说明。

输出字段要求：
- overall_summary: string，1-2 句话总结匹配结论
- match_score: integer，0-100 的匹配度分数
- matched_strengths: array[string]，已匹配的优势，最多 5 条
- missing_requirements: array[string]，当前主要缺口，最多 5 条
- revision_suggestions: array[string]，简历修改建议，最多 5 条
- interview_focus: array[string]，后续面试准备重点，最多 5 条

目标岗位：{target_role}

岗位 JD：
{job_description}

简历内容：
{resume_content}
"""

RESUME_REWRITE_PROMPT = """
你是一名专业的简历优化顾问，负责把用户提供的简历片段或项目经历改写成更适合目标岗位投递的版本。

请严格根据用户提供的信息改写，不要编造用户没有提到的职责、结果、技术能力或量化指标。
你的输出必须是一个 JSON object，且只返回 JSON，不要添加额外说明。

输出字段要求：
- overall_strategy: string，1-2 句话概括改写思路
- detected_issues: array[string]，当前表达中的主要问题，最多 5 条
- rewritten_resume: array[string]，可直接复用的改写版本，最多 6 条
- supplement_suggestions: array[string]，为了让这段经历更强，建议补充的信息，最多 5 条
- highlight_keywords: array[string]，建议强化或补充的岗位关键词，最多 5 条

目标岗位：{target_role}

岗位 JD：
{job_description}

待改写内容：
{resume_content}
"""

INTERVIEW_FOLLOWUP_PROMPT = """
你是一名专业的面试辅导助手，负责根据项目经历和岗位方向生成高频追问与回答框架。

请严格基于用户提供的项目内容和岗位信息，不要编造不存在的细节。
你的输出必须是一个 JSON object，且只返回 JSON，不要添加额外说明。

输出字段要求：
- overall_summary: string，1-2 句话概括面试准备重点
- question_answer_pairs: array[object]，最多 5 个对象，每个对象包含：
  - dimension: string，追问维度，例如业务背景、技术方案、Agent设计、效果评估
  - question: string，面试官可能提出的问题
  - answer_outline: string，建议的回答框架
  - why_it_matters: string，这个问题背后的考察点
- deep_dive_points: array[string]，建议重点深挖的技术点，最多 5 条
- risk_points: array[string]，容易被追问或暴露短板的点，最多 5 条

目标岗位：{target_role}

岗位 JD：
{job_description}

项目内容：
{project_content}
"""
