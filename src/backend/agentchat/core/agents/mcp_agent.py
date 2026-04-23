from typing import List, Optional, Literal
from pydantic import BaseModel, Field

from loguru import logger
from langchain.tools import BaseTool
from langchain.agents import create_agent
from langgraph.config import get_stream_writer
from langgraph.prebuilt.tool_node import ToolCallRequest
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langchain.agents.middleware import wrap_tool_call

from agentchat.api.services.mcp_user_config import MCPUserConfigService
from agentchat.core.agents.execution_events import build_execution_event
from agentchat.core.models.manager import ModelManager
from agentchat.prompts.completion import CALL_END_PROMPT
from agentchat.services.mcp.manager import MCPManager
from agentchat.utils.convert import convert_mcp_config


class MCPConfig(BaseModel):
    type: Literal["sse", "stdio", "streamable_http", "websocket"] = "sse"
    server_name: str
    mcp_server_id: str
    tools: List[str] = Field(default_factory=list)
    url: str | None = None
    headers: dict | None = None
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict | None = None
    cwd: str | None = None


class MCPAgent:
    def __init__(self, mcp_config: MCPConfig, user_id: str):
        self.mcp_config = mcp_config
        self.mcp_manager = MCPManager([convert_mcp_config(mcp_config.model_dump())])

        self.user_id = user_id
        self.mcp_tools: List[BaseTool] = []
        self.mcp_tool_arg_names: dict[str, set[str]] = {}

        self.conversation_model = None
        self.tool_invocation_model = None

        self.react_agent = None
        self.middlewares = None
        self.event_emitter = None

    async def init_mcp_agent(self):
        if self.mcp_config:
            self.mcp_tools = await self.setup_mcp_tools()

        await self.setup_language_model()

        self.middlewares = await self.setup_agent_middlewares()

        self.react_agent = self.setup_react_agent()

    async def emit_event(self, event):
        if self.event_emitter is not None:
            self.event_emitter(event)
            return

        writer = get_stream_writer()
        writer(event)

    def set_event_emitter(self, emitter):
        self.event_emitter = emitter

    async def setup_language_model(self):
        # 普通对话模型
        self.conversation_model = ModelManager.get_conversation_model()

        # 工具调用模型
        self.tool_invocation_model = ModelManager.get_tool_invocation_model()

    async def setup_mcp_tools(self):
        mcp_tools = await self.mcp_manager.get_mcp_tools()
        self.mcp_tool_arg_names = {
            tool.name: self._extract_tool_arg_names(tool)
            for tool in mcp_tools
        }
        return mcp_tools

    async def setup_agent_middlewares(self):

        @wrap_tool_call
        async def add_tool_call_args(
            request: ToolCallRequest,
            handler
        ):
            raw_tool_name = request.tool_call["name"]
            call_id = request.tool_call.get("id")

            await self.emit_event(
                build_execution_event(
                    status="START",
                    message=f"正在调用 MCP 工具 {raw_tool_name}...",
                    call_kind="mcp_tool",
                    call_name=raw_tool_name,
                    raw_name=raw_tool_name,
                    call_scope="mcp_agent",
                    call_id=call_id,
                    parent_name=self.mcp_config.server_name,
                )
            )
            try:
                tool_arg_names = self.mcp_tool_arg_names.get(raw_tool_name, set())
                if "current_user_id" in tool_arg_names:
                    request.tool_call["args"]["current_user_id"] = self.user_id

                # 针对鉴权的MCP Server需要用户的单独配置，例如飞书、邮箱
                mcp_config = await MCPUserConfigService.get_mcp_user_config(self.user_id, self.mcp_config.mcp_server_id)
                request.tool_call["args"].update(mcp_config)
                effective_tool_args = request.tool_call.get("args", {})
                logger.info(
                    "MCP tool start | server={} | tool={} | call_id={} | args={}",
                    self.mcp_config.server_name,
                    raw_tool_name,
                    call_id,
                    effective_tool_args,
                )

                tool_result = await handler(request)
                tool_result_message = str(tool_result)
                if _looks_like_failed_tool_result(tool_result_message):
                    await self.emit_event(
                        build_execution_event(
                            status="ERROR",
                            message=tool_result_message,
                            call_kind="mcp_tool",
                            call_name=raw_tool_name,
                            raw_name=raw_tool_name,
                            call_scope="mcp_agent",
                            call_id=call_id,
                            parent_name=self.mcp_config.server_name,
                        )
                    )
                    logger.error(
                        "MCP tool returned failure text | server={} | tool={} | call_id={} | error={}",
                        self.mcp_config.server_name,
                        raw_tool_name,
                        call_id,
                        tool_result_message,
                    )
                    return tool_result

                await self.emit_event(
                    build_execution_event(
                        status="END",
                        message=tool_result_message,
                        call_kind="mcp_tool",
                        call_name=raw_tool_name,
                        raw_name=raw_tool_name,
                        call_scope="mcp_agent",
                        call_id=call_id,
                        parent_name=self.mcp_config.server_name,
                    )
                )
                logger.info(
                    "MCP tool end | server={} | tool={} | call_id={}",
                    self.mcp_config.server_name,
                    raw_tool_name,
                    call_id,
                )
                return tool_result
            except Exception as err:
                error_message = str(err)
                await self.emit_event(
                    build_execution_event(
                        status="ERROR",
                        message=error_message,
                        call_kind="mcp_tool",
                        call_name=raw_tool_name,
                        raw_name=raw_tool_name,
                        call_scope="mcp_agent",
                        call_id=call_id,
                        parent_name=self.mcp_config.server_name,
                    )
                )
                logger.error(
                    "MCP tool error | server={} | tool={} | call_id={} | error={}",
                    self.mcp_config.server_name,
                    raw_tool_name,
                    call_id,
                    error_message,
                )
                raise

        return [add_tool_call_args]

    def setup_react_agent(self):
        return create_agent(
            model=self.conversation_model,
            tools=self.mcp_tools,
            middleware=self.middlewares,
            system_prompt=CALL_END_PROMPT
        )


    async def ainvoke(self, messages: List[BaseMessage]) -> List[BaseMessage] | str:
        """非流式版本"""
        result = await self.react_agent.ainvoke({"messages": messages})
        filtered_messages = []

        for message in result["messages"][:-1]:
            if isinstance(message, (HumanMessage, SystemMessage)):
                continue

            if getattr(message, "tool_calls", None):
                continue

            content = getattr(message, "content", "")
            if not content:
                continue

            filtered_messages.append(message)
        return filtered_messages

    @staticmethod
    def _extract_tool_arg_names(tool: BaseTool) -> set[str]:
        args_schema = getattr(tool, "args_schema", None)
        if args_schema is None:
            return set()

        schema: dict | None = None
        if isinstance(args_schema, dict):
            schema = args_schema
        elif hasattr(args_schema, "model_json_schema"):
            schema = args_schema.model_json_schema()
        elif hasattr(args_schema, "schema"):
            schema = args_schema.schema()

        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        return {
            key for key in properties.keys()
            if isinstance(key, str)
        }


def _looks_like_failed_tool_result(result: str) -> bool:
    normalized = (result or "").lower()
    return (
        "failed, code:" in normalized
        or "access denied" in normalized
        or "traceback" in normalized
        or "exception" in normalized
        or "error executing tool" in normalized
        or "config_error:" in normalized
    )
