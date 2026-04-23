import json
import asyncio
import httpx
import aiofiles
from loguru import logger
from sqlmodel import SQLModel

from agentchat.database import engine, SystemUser, ensure_mysql_database, AgentTable, ToolTable
from agentchat.api.services.agent import AgentService
from agentchat.api.services.llm import LLMService
from agentchat.api.services.tool import ToolService
from agentchat.api.services.mcp_server import MCPService
from agentchat.database.dao.agent import AgentDao
from agentchat.database.models.user import AdminUser
from agentchat.prompts.mcp import McpAsToolPrompt
from agentchat.schemas.mcp import MCPResponseFormat
from agentchat.services.mcp.manager import MCPManager
from agentchat.services.job_hunt_workspace import (
    JOB_HUNT_MCP_AS_TOOL_NAME,
    JOB_HUNT_MCP_DESCRIPTION,
    JOB_HUNT_MCP_SERVER_NAME,
    JOB_HUNT_STDIO_URL,
    build_job_hunt_stdio_config,
    get_job_hunt_mcp_server_params,
    get_job_hunt_mcp_tool_names,
)
from agentchat.services.feishu_workspace import (
    FEISHU_MCP_AS_TOOL_NAME,
    FEISHU_MCP_DESCRIPTION,
    FEISHU_MCP_SERVER_NAME,
    FEISHU_STDIO_URL,
    build_feishu_imported_config,
    build_feishu_stdio_transport_config,
    build_feishu_user_config,
)
from agentchat.services.storage import storage_client
from agentchat.settings import app_settings
from agentchat.utils.convert import convert_mcp_config
from agentchat.core.agents.structured_response_agent import StructuredResponseAgent
from agentchat.utils.helpers import get_provider_from_model
JOB_ASSISTANT_NAME = "求职面试助手"
JOB_ASSISTANT_DESCRIPTION = "围绕岗位JD、简历内容和面试准备提供匹配分析、修改建议、飞书同步与问答支持"
JOB_ASSISTANT_SYSTEM_PROMPT = (
    "你是求职面试助手。文件先mineru_parse；匹配用resume_match；"
    "改写用resume_rewrite；追问用interview_followup；"
    "保存版本/投递/计划/笔记时调job_hunt_board；"
    "同步飞书文档或安排飞书日程时调feishu_workspace；"
    "信息不足先说明；输出按结论/分析/建议；"
    "最终回复必须是自然语言，禁止输出 JSON、字段名、代码块或 overall_summary 这类结构化键名。"
)

async def init_agentchat_system():
    """
    agentchat 启动入口（推荐用于每次服务启动）

    功能：
    - 初始化数据库（幂等）
    - 检查系统是否已初始化
    - 自动选择：
        - 未初始化 → 全量初始化
        - 已初始化 → 增量更新（LLM + MCP）
    """
    await init_database()

    try:
        agents = await AgentService.get_agent()

        # 首次启动
        if not agents:
            logger.info("First-time setup: initializing agentchat system...")
            await asyncio.gather(
                _init_default_tools(),
                _init_default_llms(),
                _init_system_mcp_server(),
                upload_user_avatars_storage(),
            )
            await _sync_feishu_mcp_server()
            await _sync_job_hunt_workbench_mcp()
            await _init_default_agents()
            await _sync_job_assistant_agent()
            logger.success("Initialized agentchat successfully")
            return

        logger.info(f"Existing system detected ({len(agents)} agents), updating config...")

        await asyncio.gather(
            _update_exist_llm(),
            _sync_default_tools(),
            _update_mcp_server_into_mysql(True),
        )
        await _sync_feishu_mcp_server()
        await _sync_job_hunt_workbench_mcp()
        await _sync_job_assistant_agent()
        logger.success("agentchat runtime ready")
    except Exception as err:
        logger.error(f" agentchat init failed: {err}")

async def init_database():
    """
    初始化数据库：
    - 创建数据库（如果不存在）
    - 创建所有表结构
    """
    try:
        ensure_mysql_database()
        SQLModel.metadata.create_all(engine)
        logger.success("MySQL tables are ready")
    except Exception as err:
        logger.error(f"Create MySQL Table Error: {err}")

async def load_json(path: str):
    """
    异步读取 JSON 文件（避免阻塞事件循环）

    Args:
        path: 文件路径

    Returns:
        dict/list: JSON 数据
    """
    async with aiofiles.open(path, "r", encoding="utf-8") as f:
        return json.loads(await f.read())

async def _init_default_tools():
    """初始化默认工具"""
    tools = await load_json("./agentchat/config/tool.json")

    await asyncio.gather(*[
        ToolService.create_default_tool(
            ToolTable(
                **tool,
                user_id=SystemUser,
                is_user_defined=False
            )
        )
        for tool in tools
    ])

    logger.success("Default tools initialized")


async def _sync_default_tools():
    """增量同步新增的系统默认工具，避免已初始化系统漏掉新工具。"""
    tools = await load_json("./agentchat/config/tool.json")
    existing_tools = await ToolService.get_tools_data()
    existing_names = {tool["name"] for tool in existing_tools}
    missing_tools = [tool for tool in tools if tool["name"] not in existing_names]

    if not missing_tools:
        logger.info("Default tools already up to date")
        return

    await asyncio.gather(*[
        ToolService.create_default_tool(
            ToolTable(
                **tool,
                user_id=SystemUser,
                is_user_defined=False
            )
        )
        for tool in missing_tools
    ])

    logger.success(f"Synchronized {len(missing_tools)} default tools")


async def _update_exist_llm():
    """
    更新已存在的 LLM 配置

    逻辑：
    - 获取当前系统已有 LLM
    - 对比配置（model / base_url / api_key）
    - 若无变化 → 跳过
    - 若 API Key 是掩码（包含 **）→ 跳过（防止覆盖真实 key）
    """
    settings = app_settings.multi_models.conversation_model

    api_key = settings.api_key
    base_url = settings.base_url
    model = settings.model_name
    provider = get_provider_from_model(model)

    llm = await LLMService.select_first_llm()

    if not llm:
        # 如果数据库还没有 LLM，直接初始化
        await _init_default_llms()
        return

    # 是否需要更新
    needs_update = not (
        llm.base_url == base_url and
        llm.model == model and
        llm.api_key == api_key
    )

    if not needs_update:
        logger.info("LLM config unchanged, skip update")
        return

    # 防止用掩码覆盖真实 key
    if api_key and "**" in api_key:
        logger.warning("Masked API key detected, skip update")
        return

    await LLMService.update_first_llm(
        llm_id=llm.llm_id,
        model=model,
        provider=provider,
        base_url=base_url,
        api_key=api_key,
    )

    logger.success("LLM config updated")

async def _init_default_llms():
    """初始化默认 LLM"""
    settings = app_settings.multi_models.conversation_model

    await LLMService.create_llm(
        user_id=SystemUser,
        model=settings.model_name,
        llm_type="LLM",
        api_key=settings.api_key,
        base_url=settings.base_url,
        provider=get_provider_from_model(settings.model_name)
    )

    logger.success("Default LLM initialized")

async def _init_default_agents():
    """
    初始化默认 Agent
    - 每个 Tool 对应一个 Agent
    - 并发创建
    """
    llm = await LLMService.get_one_llm()
    tools = await ToolService.get_tools_data()

    tasks = []

    for tool in tools:
        tool["name"] = tool["display_name"] + "助手"

        agent = AgentTable(
            **ToolTable(**tool).model_dump(exclude={"user_id", "tool_id"}),
            tool_ids=[tool["tool_id"]],
            user_id=SystemUser,
            is_custom=False,
            llm_id=llm.get("llm_id")
        )

        tasks.append(AgentDao.create_agent(agent))

    await asyncio.gather(*tasks)

    logger.success("Default agents initialized")


async def _sync_job_assistant_agent():
    """为求职场景补充一个默认 Agent，减少手动配置成本。"""
    existing_agents = await AgentDao.get_agent_by_user_id(SystemUser)
    existing_agent = next((agent for agent in existing_agents if agent.name == JOB_ASSISTANT_NAME), None)

    tools = await ToolService.get_tools_data()
    preferred_tool_names = {"mineru_parse", "resume_match", "resume_rewrite", "interview_followup", "tavily_search"}
    tool_ids = [tool["tool_id"] for tool in tools if tool["name"] in preferred_tool_names]
    if len(tool_ids) < 3:
        logger.warning("Job assistant core tools not found, skip job assistant agent sync")
        return

    mcp_servers = await MCPService.get_all_servers(SystemUser)
    job_hunt_mcp_ids = [
        server["mcp_server_id"]
        for server in mcp_servers
        if server["server_name"] in {JOB_HUNT_MCP_SERVER_NAME, FEISHU_MCP_SERVER_NAME}
    ]

    llm = await LLMService.get_one_llm()
    if not llm:
        logger.warning("No available LLM found, skip job assistant agent creation")
        return

    if existing_agent:
        update_values = {}
        if set(existing_agent.tool_ids or []) != set(tool_ids):
            update_values["tool_ids"] = tool_ids
        if existing_agent.description != JOB_ASSISTANT_DESCRIPTION:
            update_values["description"] = JOB_ASSISTANT_DESCRIPTION
        if existing_agent.system_prompt != JOB_ASSISTANT_SYSTEM_PROMPT:
            update_values["system_prompt"] = JOB_ASSISTANT_SYSTEM_PROMPT
        if existing_agent.llm_id != llm.get("llm_id"):
            update_values["llm_id"] = llm.get("llm_id")
        if set(existing_agent.mcp_ids or []) != set(job_hunt_mcp_ids):
            update_values["mcp_ids"] = job_hunt_mcp_ids
        if not existing_agent.enable_memory:
            update_values["enable_memory"] = True

        if update_values:
            await AgentDao.update_agent_by_id(existing_agent.id, update_values)
            logger.success("Updated default job assistant agent")
        else:
            logger.info("Job assistant agent already up to date")
        return

    agent = AgentTable(
        name=JOB_ASSISTANT_NAME,
        description=JOB_ASSISTANT_DESCRIPTION,
        logo_url=app_settings.default_config.get("agent_logo_url"),
        tool_ids=tool_ids,
        user_id=SystemUser,
        is_custom=False,
        llm_id=llm.get("llm_id"),
        system_prompt=JOB_ASSISTANT_SYSTEM_PROMPT,
        enable_memory=True,
        mcp_ids=job_hunt_mcp_ids,
    )

    await AgentDao.create_agent(agent)
    logger.success("Created default job assistant agent")


async def _sync_feishu_mcp_server():
    all_servers = await MCPService.get_all_servers(SystemUser)
    existing_server = next(
        (server for server in all_servers if server["server_name"] == FEISHU_MCP_SERVER_NAME),
        None,
    )

    if not existing_server:
        logger.warning("Feishu MCP server not found, skip feishu MCP sync")
        return

    feishu_transport_config = build_feishu_stdio_transport_config()
    feishu_server_info = {
        "type": "stdio",
        "url": FEISHU_STDIO_URL,
        "server_name": FEISHU_MCP_SERVER_NAME,
        **feishu_transport_config,
    }

    update_data = {
        "server_name": FEISHU_MCP_SERVER_NAME,
        "url": FEISHU_STDIO_URL,
        "type": "stdio",
        "config": build_feishu_user_config(),
        "imported_config": build_feishu_imported_config(),
        "config_enabled": True,
        "logo_url": existing_server.get("logo_url") or app_settings.default_config.get("mcp_logo_url", ""),
        "mcp_as_tool_name": FEISHU_MCP_AS_TOOL_NAME,
        "description": FEISHU_MCP_DESCRIPTION,
    }

    try:
        mcp_manager = MCPManager([convert_mcp_config(feishu_server_info)])
        feishu_params = (await mcp_manager.show_mcp_tools()).get(FEISHU_MCP_SERVER_NAME, [])
        if feishu_params:
            update_data["tools"] = [tool["name"] for tool in feishu_params]
            update_data["params"] = feishu_params
    except Exception as err:
        logger.warning(f"Failed to refresh local feishu MCP tool schema, keep previous metadata: {err}")

    await MCPService.update_mcp_server(existing_server["mcp_server_id"], update_data)
    logger.info("Updated feishu MCP server")


async def _sync_job_hunt_workbench_mcp():
    all_servers = await MCPService.get_all_servers(SystemUser)
    existing_server = next(
        (server for server in all_servers if server["server_name"] == JOB_HUNT_MCP_SERVER_NAME),
        None,
    )

    update_data = {
        "server_name": JOB_HUNT_MCP_SERVER_NAME,
        "url": JOB_HUNT_STDIO_URL,
        "type": "stdio",
        "config": build_job_hunt_stdio_config(),
        "tools": get_job_hunt_mcp_tool_names(),
        "params": get_job_hunt_mcp_server_params(),
        "config_enabled": False,
        "logo_url": app_settings.default_config.get("mcp_logo_url", ""),
        "mcp_as_tool_name": JOB_HUNT_MCP_AS_TOOL_NAME,
        "description": JOB_HUNT_MCP_DESCRIPTION,
    }

    if existing_server:
        await MCPService.update_mcp_server(existing_server["mcp_server_id"], update_data)
        logger.info("Updated job hunt workbench MCP server")
        return

    await MCPService.create_mcp_server(
        user_id=SystemUser,
        user_name="Admin",
        imported_config=None,
        **update_data,
    )
    logger.success("Created job hunt workbench MCP server")

async def _init_system_mcp_server():
    """
    初始化 MCP Server（仅首次）
    """
    try:
        existing = await MCPService.get_all_servers(SystemUser)

        if not existing:
            await _update_mcp_server_into_mysql(False)

        logger.success("MCP servers initialized")

    except Exception as err:
        logger.error(f"MCP init failed: {err}")


async def _update_mcp_server_into_mysql(has_mcp_server: bool):
    """
    同步 MCP Server 到数据库（核心逻辑）

    Args:
        has_mcp_server:
            True = 更新模式
            False = 初始化模式
    """
    if has_mcp_server:
        if not await MCPService.mcp_server_need_update():
            return

        servers = await MCPService.get_all_servers(AdminUser)
        logger.info("Updating MCP servers...")
    else:
        servers = await load_json("./agentchat/config/mcp_server.json")

    servers_info = []
    for server in servers:
        servers_info.append(MCPService.resolve_server_connection_payload(server))

    mcp_manager = MCPManager(convert_mcp_config(servers_info))
    servers_params = await mcp_manager.show_mcp_tools()

    semaphore = asyncio.Semaphore(5)

    async def build_meta(server_name, params):
        """
        构建 MCP Tool 元信息（调用 LLM）
        """
        async with semaphore:
            agent = StructuredResponseAgent(MCPResponseFormat)

            result = agent.get_structured_response(
                McpAsToolPrompt.format(
                    tools_info=json.dumps(params, indent=2)
                )
            )
            return server_name, params, result

    tasks = [
        build_meta(name, params)
        for name, params in servers_params.items()
    ]

    results = await asyncio.gather(*tasks)

    for server_name, params, structured in results:
        server = next((s for s in servers if s["server_name"] == server_name), None)

        tools_name = [t["name"] for t in params]

        if has_mcp_server:
            await MCPService.update_mcp_server(
                server_id=server["mcp_server_id"],
                update_data={
                    "tools": tools_name,
                    "params": params,
                    "mcp_as_tool_name": structured.mcp_as_tool_name,
                    "description": structured.description
                }
            )
        else:
            await MCPService.create_mcp_server(
                server_name=server_name,
                user_id=SystemUser,
                user_name="Admin",
                url=server["url"],
                type=server["type"],
                config=server["config"],
                tools=tools_name,
                params=params,
                config_enabled=server["config_enabled"],
                logo_url=server["logo_url"],
                imported_config=server.get("imported_config"),
                mcp_as_tool_name=structured.mcp_as_tool_name,
                description=structured.description,
            )

async def upload_user_avatars_storage():
    """上传默认用户头像到存储"""
    if storage_client.list_files_in_folder("icons/user"):
        return

    avatars = await load_json("./agentchat/config/avatars.json")

    async with httpx.AsyncClient(timeout=10) as client:
        tasks = [
            _download_and_upload(client, url)
            for url in avatars["avatars"]
        ]
        await asyncio.gather(*tasks)

    logger.success("User avatars uploaded")


async def _download_and_upload(client, url):
    """下载图片并上传到存储"""
    resp = await client.get(url)
    file_name = url.split("/")[-1]

    storage_client.upload_file(
        f"icons/user/{file_name}",
        resp.content
    )
