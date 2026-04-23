from typing import Literal

from pydantic import BaseModel, Field


class EvalRunRequest(BaseModel):
    run_label: str = Field(default="manual_eval", max_length=64)
    tool: Literal["all", "resume_match", "resume_rewrite", "interview_followup"] = Field(default="all")
    enable_judge: bool = Field(default=True)
    judge_weight: float = Field(default=0.35, ge=0.0, le=1.0)
    compare_latest: bool = Field(default=True)
