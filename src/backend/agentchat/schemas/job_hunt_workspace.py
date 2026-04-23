from typing import Literal

from pydantic import BaseModel, Field


WorkspaceItemType = Literal[
    "resume_version",
    "job_application",
    "interview_plan",
    "followup_note",
]


class SaveResumeVersionReq(BaseModel):
    current_user_id: str = Field(..., description="系统自动注入的当前用户 ID")
    title: str = Field(default="", description="简历版本标题，可为空")
    target_role: str = Field(default="", description="目标岗位")
    content: str = Field(..., description="需要保存的简历正文")
    source_summary: str = Field(default="", description="该版本的简短说明")
    highlight_keywords: list[str] = Field(default_factory=list, description="建议强化的关键词")


class RecordJobApplicationReq(BaseModel):
    current_user_id: str = Field(..., description="系统自动注入的当前用户 ID")
    company: str = Field(default="待补充", description="公司名称")
    position: str = Field(..., description="岗位名称")
    status: str = Field(default="待投递", description="投递状态")
    jd_url: str = Field(default="", description="岗位 JD 链接")
    notes: str = Field(default="", description="投递备注")
    match_summary: str = Field(default="", description="匹配结论摘要")


class CreateInterviewPlanReq(BaseModel):
    current_user_id: str = Field(..., description="系统自动注入的当前用户 ID")
    title: str = Field(default="", description="面试计划标题，可为空")
    target_role: str = Field(..., description="目标岗位")
    company: str = Field(default="", description="公司名称")
    focus_points: list[str] = Field(default_factory=list, description="建议深挖的重点")
    preparation_actions: list[str] = Field(default_factory=list, description="准备动作清单")
    schedule_suggestion: str = Field(default="", description="准备节奏建议")


class SaveFollowupNotesReq(BaseModel):
    current_user_id: str = Field(..., description="系统自动注入的当前用户 ID")
    title: str = Field(default="", description="笔记标题，可为空")
    target_role: str = Field(default="", description="目标岗位")
    notes: str = Field(..., description="需要保存的追问笔记正文")
    tags: list[str] = Field(default_factory=list, description="笔记标签")
    question_count: int = Field(default=0, description="追问数量")
