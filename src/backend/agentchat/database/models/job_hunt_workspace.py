from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, JSON, Text, text
from sqlmodel import Field

from agentchat.database.models.base import SQLModelSerializable


class JobHuntWorkspaceItem(SQLModelSerializable, table=True):
    __tablename__ = "job_hunt_workspace_item"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    user_id: str = Field(index=True, description="数据所属用户 ID")
    item_type: str = Field(index=True, description="工作台条目类型")
    title: str = Field(default="", description="工作台条目标题")
    summary: str = Field(default="", description="工作台条目摘要")
    content: str = Field(default="", sa_column=Column(Text), description="详细内容")
    status: str = Field(default="", description="状态字段，主要用于投递记录")
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON), description="标签列表")
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON), description="扩展结构化数据")
    source: str = Field(default="job_hunt_mcp", description="数据来源")
    update_time: datetime | None = Field(
        sa_column=Column(
            DateTime,
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
            onupdate=text("CURRENT_TIMESTAMP"),
        ),
        description="更新时间",
    )
    create_time: datetime | None = Field(
        sa_column=Column(
            DateTime,
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
        description="创建时间",
    )
