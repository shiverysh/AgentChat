import copy
import time
import asyncio
import json
from loguru import logger
from pydantic import BaseModel
from typing import List, Dict, Any, AsyncGenerator, Callable, NotRequired
from langgraph.runtime import Runtime
from langgraph.types import Command
from langchain_core.tools import BaseTool, tool, StructuredTool
from langchain.tools.tool_node import ToolCallRequest
from langchain.agents import create_agent, AgentState
from langgraph.config import get_stream_writer
from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage, AIMessageChunk
from langchain.agents.middleware import LLMToolSelectorMiddleware, ModelRequest, ModelResponse, AgentMiddleware

from agentchat.api.services.agent_skill import AgentSkillService
from agentchat.core.agents.execution_events import build_execution_event
from agentchat.core.agents.skill_agent import SkillAgent
from agentchat.core.callbacks import usage_metadata_callback
from agentchat.database import AgentSkill
from agentchat.tools import AgentToolsWithName
from agentchat.api.services.llm import LLMService
from agentchat.core.models.manager import ModelManager
from agentchat.api.services.tool import ToolService
from agentchat.services.rag.handler import RagHandler
from agentchat.core.agents.mcp_agent import MCPAgent, MCPConfig
from agentchat.api.services.mcp_server import MCPService
from agentchat.tools.openapi_tool.adapter import OpenAPIToolAdapter


class StreamAgentState(AgentState):
    tool_call_count: NotRequired[int]
    model_call_count: NotRequired[int]
    user_id: NotRequired[str]
    available_tools: NotRequired[List[BaseTool]]
    tool_call_cache: NotRequired[Dict[str, str]]


MAX_TOOLS_SIZE = 10
MAX_EVENT_MESSAGE_LENGTH = 480

class AgentConfig(BaseModel):
    user_id: str
    llm_id: str
    mcp_ids: List[str]
    knowledge_ids: List[str]
    tool_ids: List[str]
    agent_skill_ids: List[str]
    system_prompt: str
    enable_memory: bool = False
    name: str = None



class EmitEventAgentMiddleware(AgentMiddleware):
    def __init__(self, name_resolver_func):
        super().__init__()

        self.name_resolver_func = name_resolver_func

    async def aafter_model(
        self, state: StreamAgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return {
                "model_call_count": state["model_call_count"] + 1
            }

        return {
            "jump_to": "end"
        }

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        try:
            if available_tools := request.state.get("available_tools", []):
                request.tools = available_tools
            response = await handler(request)
            return response
        except Exception as err:
            logger.error(f"Model call error: {err}")
            raise ValueError(err)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        writer = get_stream_writer()
        tool_call_count = request.state.get("tool_call_count", 0)
        raw_tool_name = request.tool_call["name"]
        tool_type, display_tool_name = self.name_resolver_func(raw_tool_name)
        tool_kind_map = {
            "工具": "tool",
            "MCP": "mcp",
            "Skill": "skill",
        }
        call_kind = tool_kind_map.get(tool_type, "tool")
        call_id = request.tool_call.get("id")
        tool_args = request.tool_call.get("args", {})
        tool_call_cache = request.state.setdefault("tool_call_cache", {})
        call_signature = _build_tool_call_signature(raw_tool_name, tool_args)

        if call_signature in tool_call_cache:
            cached_result = tool_call_cache[call_signature]
            logger.warning(
                "Agent call deduplicated | kind={} | display_name={} | raw_name={} | call_id={}",
                call_kind,
                display_tool_name,
                raw_tool_name,
                call_id,
            )
            return ToolMessage(
                content=cached_result,
                name=raw_tool_name,
                tool_call_id=request.tool_call["id"],
            )

        writer(build_execution_event(
            status="START",
            message=f"正在调用{tool_type} {display_tool_name}...",
            call_kind=call_kind,
            call_name=display_tool_name,
            raw_name=raw_tool_name,
            call_scope="agent",
            call_id=call_id,
        ))
        request.state["tool_call_count"] = tool_call_count + 1
        logger.info(
            "Agent call start | kind={} | display_name={} | raw_name={} | call_id={} | args={}",
            call_kind,
            display_tool_name,
            raw_tool_name,
            call_id,
            tool_args,
        )
        try:
            tool_result = await handler(request)
            tool_result_message = getattr(tool_result, "content", str(tool_result))
            tool_call_cache[call_signature] = str(tool_result_message)
            event_message = _truncate_event_message(tool_result_message)
            writer(build_execution_event(
                status="END",
                message=event_message,
                call_kind=call_kind,
                call_name=display_tool_name,
                raw_name=raw_tool_name,
                call_scope="agent",
                call_id=call_id,
            ))
            logger.info(
                "Agent call end | kind={} | display_name={} | raw_name={} | call_id={}",
                call_kind,
                display_tool_name,
                raw_tool_name,
                call_id,
            )
            return tool_result
        except Exception as err:
            error_message = str(err)
            tool_call_cache[call_signature] = error_message
            writer(build_execution_event(
                status="ERROR",
                message=_truncate_event_message(error_message),
                call_kind=call_kind,
                call_name=display_tool_name,
                raw_name=raw_tool_name,
                call_scope="agent",
                call_id=call_id,
            ))
            logger.error(
                "Agent call error | kind={} | display_name={} | raw_name={} | call_id={} | error={}",
                call_kind,
                display_tool_name,
                raw_tool_name,
                call_id,
                error_message,
            )
            return ToolMessage(content=error_message, name=raw_tool_name, tool_call_id=request.tool_call["id"])


def _truncate_event_message(message: Any) -> str:
    if isinstance(message, list):
        normalized = "\n".join(str(item) for item in message)
    else:
        normalized = str(message)

    if len(normalized) <= MAX_EVENT_MESSAGE_LENGTH:
        return normalized

    truncated = normalized[:MAX_EVENT_MESSAGE_LENGTH].rstrip()
    if "\n" in truncated:
        truncated = truncated.rsplit("\n", 1)[0].rstrip()

    if not truncated:
        truncated = normalized[:MAX_EVENT_MESSAGE_LENGTH].rstrip()

    return f"{truncated}\n...[工具结果过长，执行轨迹仅展示摘要]"


def _build_tool_call_signature(tool_name: str, tool_args: Dict[str, Any]) -> str:
    try:
        normalized_args = json.dumps(tool_args or {}, ensure_ascii=False, sort_keys=True, default=str)
    except TypeError:
        normalized_args = str(tool_args)
    return f"{tool_name}:{normalized_args}"


def _detect_feishu_token_mode(content: str) -> str | None:
    normalized = content or ""
    if '"token_mode": "user"' in normalized or "'token_mode': 'user'" in normalized:
        return "user"
    if '"token_mode": "tenant"' in normalized or "'token_mode': 'tenant'" in normalized:
        return "tenant"
    return None


def _normalize_mcp_query(server_name: str, query: str) -> str:
    if server_name != "飞书":
        return query

    return (
        "你正在调用飞书 MCP，请严格遵守以下约束：\n"
        "1. 当目标是同步飞书文档时，优先使用 create_document 和 write_document_content 组合完成“创建文档 + 写入正文”；如果已有 document_id，可直接用 write_document_content；\n"
        "2. 禁止使用 create_message 代替文档内容写入；只有用户明确要求发送飞书消息时，才允许调用 create_message；\n"
        "3. create_document 成功后，继续调用 write_document_content 写入用户给出的正文、版本说明、要点或追问摘要；\n"
        "4. 当目标是创建飞书日历或面试日程时，只允许使用 create_calendar、get_calendars_list、create_calendar_event、get_calendar_event、update_calendar_event 这类日历工具，禁止改用 create_message 等机器人消息工具；\n"
        "5. 飞书日历相关能力必须依赖 USER_ACCESS_TOKEN。如果工具返回缺少 USER_ACCESS_TOKEN 的配置错误，直接结束并明确提示用户去 MCP 页面补充 USER_ACCESS_TOKEN，不要编造“机器人身份”之类的模糊原因；\n"
        "6. 返回结果时优先给出文档标题、document_id、document_url，或者 calendar_id、event_id、开始/结束时间，以及是否真正写入正文或真正创建了日程；\n"
        "7. 如果当前工具集中没有文档正文写入能力，创建文档并获取文档信息后立即结束，不要再尝试消息类工具。\n\n"
        f"用户请求：\n{query}"
    )


def _format_mcp_agent_result(server_name: str, original_query: str, messages: List[BaseMessage]) -> str:
    content = "\n".join(
        getattr(message, "content", "")
        for message in messages
        if getattr(message, "content", "")
    )

    if server_name != "飞书":
        return content

    tool_names = [
        getattr(message, "name", "")
        for message in messages
        if getattr(message, "name", "")
    ]
    token_mode = _detect_feishu_token_mode(content)
    only_document_meta = tool_names and set(tool_names).issubset({"create_document", "get_document"})
    wants_document_sync = "文档" in original_query or "简历" in original_query or "同步" in original_query

    if "config_error:" in content.lower():
        if "user_access_token" in content.lower():
            return (
                "当前飞书能力调用失败，原因是没有拿到可用的 USER_ACCESS_TOKEN。"
                "文档同步有时还能以应用身份勉强执行，但飞书日历/日程创建必须走用户身份。"
                "请到 MCP 页面给“飞书”补充 USER_ACCESS_TOKEN，并确认已开通日历相关权限后再重试。\n\n"
                f"{content}"
            )
        return content

    if "app bot_id not found" in content.lower():
        return (
            "当前飞书调用失败。就这个求职助手场景看，更可能是飞书日历请求退回到了错误的应用/机器人身份，"
            "而不是前端页面本身的问题。优先检查 MCP 页面中的 USER_ACCESS_TOKEN 是否已配置、"
            "飞书开放平台是否开通日历相关权限，以及当前登录飞书账号是否与该 USER_ACCESS_TOKEN 对应。\n\n"
            f"{content}"
        )

    if only_document_meta and wants_document_sync:
        visibility_hint = (
            "当前使用的是应用身份创建，飞书 API 可以成功，但不保证出现在你的个人云文档；"
            "如需个人空间可见，请补充 USER_ACCESS_TOKEN。"
            if token_mode != "user"
            else "当前使用的是用户身份创建，理论上应可在对应用户的飞书空间中查看；若仍不可见，请检查应用权限和飞书侧可见范围。"
        )
        return (
            "当前飞书 MCP 已成功创建文档并返回文档信息，但还没有真正写入正文内容。"
            "原因是本次调用只执行了 create_document/get_document，没有继续调用 write_document_content。"
            f"{visibility_hint}"
            "你可以先使用下面的文档信息继续记录，或重新触发一次同步，让 Agent 补写正文。\n\n"
            f"{content}"
        )

    return content

class GeneralAgent:
    def __init__(self, agent_config: AgentConfig):
        self.agent_config = agent_config

        self.conversation_model = None
        self.tool_invocation_model = None
        self.react_agent = None

        self.tools = []
        self.mcp_agent_as_tools = []
        self.middlewares = []
        self.skill_agent_as_tools = []
        self.tool_metadata_map: Dict[str, Dict[str, str]] = {}

        # 流式事件队列
        self.event_queue = asyncio.Queue()
        self.stop_streaming = False

    def wrap_event(self, data: Dict[Any, Any]):
        """发送流式事件"""
        event = {
            "type": "event",
            "timestamp": time.time(),
            "data": data
        }
        return event

    async def init_agent(self):
        self.mcp_agent_as_tools = await self.setup_mcp_agent_as_tools()

        self.tools = await self.setup_tools()

        self.skill_agent_as_tools = await self.setup_agent_skill_as_tools()

        await self.setup_knowledge_tool()
        await self.setup_language_model()

        self.search_tool = self.setup_search_tool()
        self.middlewares = await self.setup_agent_middleware()
        self.react_agent = self.setup_react_agent()

    async def setup_agent_middleware(self):
        # 仅支持传入response_format为json object的模型
        tool_selector_middleware = LLMToolSelectorMiddleware(
            model=self.tool_invocation_model,
            max_tools=3 # 限制每次选择最多 3个工具
        )

        emit_event_middleware = EmitEventAgentMiddleware(self.get_tool_display_name)

        return [emit_event_middleware]


    async def setup_language_model(self):
        # 普通对话模型
        if self.agent_config.llm_id:
            model_config = await LLMService.get_llm_by_id(self.agent_config.llm_id)
            self.conversation_model = ModelManager.get_user_model(**model_config)
        else:
            self.conversation_model = ModelManager.get_conversation_model()

        # 意图识别模型
        self.tool_invocation_model = ModelManager.get_tool_invocation_model()

    def setup_react_agent(self):
        return create_agent(
            model=self.conversation_model,
            tools=self.tools + self.mcp_agent_as_tools + self.skill_agent_as_tools,
            #tools=[self.search_tool] if len(self.tools + self.mcp_agent_as_tools) >= MAX_TOOLS_SIZE else self.tools + self.mcp_agent_as_tools,
            middleware=self.middlewares,
            state_schema=StreamAgentState
        )

    def setup_search_tool(self):
        """这里相当于也是一个探索阶段，当绑定的工具数量很多时，会极大的占用上下文的Token数量以及影响命中效果
        所以在工具数量超过MaxToolsSize阈值后，会先只绑定一个搜索工具去搜索可用的工具，之后再拿着可用的工具进行对应的调用

        不适用：
            1.工具数量较少
            2.一些工具在每次对话都能用到
        """
        @tool(parse_docstring=True)
        def search_available_tools(query: str, tool_call_id):
            """
            搜索可用的工具，使用此工具查找是否包含相关的能力

            Args:
                query (str): 执行任务的关键词，例如 'github'、'search'、'天气'

            Returns:
                str: 返回本次任务可能能用到的接口
            """
            found_tools = []
            available_tools = self.tools + self.mcp_agent_as_tools
            for tool in available_tools:
                if tool.name == "search_available_tools":
                    continue
                if query.lower() in tool.name or query.lower() in tool.description:
                    found_tools.append(tool)

            if not found_tools:
                content_str = "未找到相关工具。请尝试其他关键词。"
            else:
                content_str = f"已找到并激活以下工具:\n" + "\n".join([tool.name for tool in found_tools]) + "\n\n现在你可以调用这些工具了。"

            tool_msg = ToolMessage(
                content=content_str,
                tool_call_id=tool_call_id,
                name="search_available_tools"
            )

            return Command(update={"available_tools": found_tools, "messages": [tool_msg]})
        return search_available_tools


    async def setup_tools(self) -> List[BaseTool]:
        def create_openapi_tool_executor(tool_adapter, tool_name):
            """闭包创建一个执行OpenAPI Tool的方法"""
            async def _execute_wrapper(**kwargs):
                return await tool_adapter.execute(
                    _tool_name=tool_name,
                    **kwargs
                )

            return _execute_wrapper

        tools = []
        db_tools = await ToolService.get_tools_from_id(self.agent_config.tool_ids)
        for db_tool in db_tools:
            if db_tool.is_user_defined:
                tool_adapter = OpenAPIToolAdapter(
                    auth_config=db_tool.auth_config,
                    openapi_schema=db_tool.openapi_schema
                )

                for openapi_tool in tool_adapter.tools:
                    tools.append(
                        StructuredTool(
                            name=openapi_tool["function"].get("name", ""),
                            description=openapi_tool["function"].get("description", ""),
                            coroutine=create_openapi_tool_executor(tool_adapter, openapi_tool["function"].get("name")),
                            args_schema=openapi_tool
                        )
                    )

                    self.tool_metadata_map[openapi_tool["function"].get("name", "")] = {
                        "name": db_tool.display_name,
                        "type": "工具"
                    }
            else:
                agent_tool = AgentToolsWithName.get(db_tool.name)
                if agent_tool:
                    tools.append(agent_tool)
                self.tool_metadata_map[db_tool.name] = {
                    "name": db_tool.display_name,
                    "type": "工具"
                }

        return tools

    async def setup_agent_skill_as_tools(self) -> List[BaseTool]:
        agent_skill_as_tools = []
        agent_skills = await AgentSkillService.get_agent_skills_by_ids(self.agent_config.agent_skill_ids)

        def create_skill_agent_as_tool(agent_skill: AgentSkill):

            @tool(agent_skill.as_tool_name, description=agent_skill.description)
            async def call_skill_agent(query: str):
                """调用技能Agent"""
                skill_agent = SkillAgent(agent_skill, self.agent_config.user_id)
                await skill_agent.init_skill_agent()
                messages = await skill_agent.ainvoke([HumanMessage(content=query)])
                return "\n".join([message.content for message in messages])

            return call_skill_agent

        for agent_skill in agent_skills:
            self.tool_metadata_map[agent_skill.as_tool_name] = {
                "name": agent_skill.name,  # 技能的中文/友好名称
                "type": "Skill"
            }
            agent_skill_as_tools.append(create_skill_agent_as_tool(agent_skill))

        return agent_skill_as_tools


    async def setup_mcp_agent_as_tools(self):
        mcp_agent_as_tools = []

        def create_mcp_agent_as_tool(mcp_agent, mcp_as_tool_name, description):
            @tool(mcp_as_tool_name, description=description)
            async def call_mcp_agent(query: str):
                """
                用户想要根据这些mcp工具来完成的一些任务
                Args:
                    query: 用户询问的问题
                Returns:
                    根据该MCP Agent来完成的一些任务
                """
                mcp_agent.set_event_emitter(get_stream_writer())
                try:
                    normalized_query = _normalize_mcp_query(mcp_agent.mcp_config.server_name, query)
                    messages = await mcp_agent.ainvoke([HumanMessage(content=normalized_query)])
                finally:
                    mcp_agent.set_event_emitter(None)
                return _format_mcp_agent_result(mcp_agent.mcp_config.server_name, query, messages)
            return call_mcp_agent

        for mcp_id in self.agent_config.mcp_ids:
            mcp_server = await MCPService.get_mcp_server_from_id(mcp_id)
            mcp_config = self._build_mcp_config(mcp_server)

            mcp_agent = MCPAgent(mcp_config, self.agent_config.user_id)
            await mcp_agent.init_mcp_agent()

            tool_name = mcp_server.get("mcp_as_tool_name")
            description = mcp_server.get("description")

            # 更新元数据映射
            self.tool_metadata_map[tool_name] = {
                "name": mcp_config.server_name,
                "type": "MCP"
            }

            # 创建并添加工具
            mcp_agent_as_tools.append(
                create_mcp_agent_as_tool(mcp_agent, tool_name, description)
            )
        return mcp_agent_as_tools

    @staticmethod
    def _build_mcp_config(mcp_server: dict) -> MCPConfig:
        config_payload = {
            "tools": mcp_server.get("tools", []),
            "mcp_server_id": mcp_server.get("mcp_server_id", ""),
        }
        config_payload.update(MCPService.resolve_server_connection_payload(mcp_server))
        return MCPConfig(**config_payload)

    async def setup_knowledge_tool(self):
        @tool(parse_docstring=True)
        async def retrival_knowledge(query: str) -> str:
            """
            通过检索知识库来获取信息

            Args:
                query (str): 用户问题

            Returns:
                str: 返回从知识库检索来的信息
            """
            knowledge_message = await RagHandler.retrieve_ranked_documents(
                query, self.agent_config.knowledge_ids
            )
            return knowledge_message

        if self.agent_config.knowledge_ids: # 当绑定知识库ID后才 As Tool
            self.tools.append(retrival_knowledge)
            self.tool_metadata_map[retrival_knowledge.name] = {
                "name": "检索知识库",
                "type": "工具"
            }


    async def astream(self, messages: List[BaseMessage]) -> AsyncGenerator[Dict[str, Any], None]:
        """流式调用主方法"""
        response_content = ""
        try:
            async for token, metadata in self.react_agent.astream(
                    input={"messages": copy.deepcopy(messages), "model_call_count": 0, "user_id": self.agent_config.user_id},
                    config={"callbacks": [usage_metadata_callback]},
                    stream_mode=["messages", "custom"],
            ):
                if token == "custom":
                    yield self.wrap_event(metadata)
                elif isinstance(metadata[0], AIMessageChunk) and metadata[0].content:
                    response_content += metadata[0].content
                    yield {
                        "type": "response_chunk",
                        "timestamp": time.time(),
                        "data": {
                            "chunk": metadata[0].content,
                            "accumulated": response_content
                        }
                    }

        # 针对模型回复进行兜底操作，错误类型包括：敏感词，模型问题
        except Exception as err:
            logger.error(f"LLM Model Error: {err}")
            yield {
                "type": "response_chunk",
                "timestamp": time.time(),
                "data": {
                    "chunk": "您的问题触及到我的知识盲区，请换个问题吧✨",
                    "accumulated": response_content
                }
            }

    def stop_streaming_callback(self):
        self.stop_streaming = True

    def get_tool_display_name(self, tool_name: str):
        """
        根据工具的原始名称，解析出带有类型后缀的展示名称
        例如:
        - "gaode_weather" -> "执行Skill：高德天气"
        - "mcp_filesystem" -> "执行MCP：文件系统"
        - "search" -> "执行工具：search"
        """
        metadata = self.tool_metadata_map.get(tool_name)

        if not metadata:
            # 如果没有记录元数据，直接返回原始名称
            return "工具", tool_name

        friendly_name = metadata.get("name", tool_name)
        tool_type = metadata.get("type", "工具")

        return tool_type, friendly_name
