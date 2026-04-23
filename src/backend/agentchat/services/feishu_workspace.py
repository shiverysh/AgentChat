import os
import sys
from pathlib import Path
from typing import Any

FEISHU_MCP_SERVER_NAME = "飞书"
FEISHU_MCP_AS_TOOL_NAME = "feishu_workspace"
FEISHU_MCP_DESCRIPTION = (
    "当用户需要把简历、匹配分析或面试准备内容同步到飞书文档，或创建飞书日历/面试日程时使用。"
    "子智能体可以调用多个自身工具，所以将用户问题整合询问一次即可。"
)
FEISHU_STDIO_URL = "stdio://feishu-workspace"


def _get_backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_feishu_stdio_transport_config() -> dict[str, Any]:
    backend_root = _get_backend_root()
    python_path = str(backend_root)
    existing_python_path = os.environ.get("PYTHONPATH", "").strip()
    merged_python_path = (
        f"{python_path}{os.pathsep}{existing_python_path}"
        if existing_python_path
        else python_path
    )

    return {
        "command": sys.executable,
        "args": ["-m", "agentchat.mcp_servers.lark_mcp.main", "--transport", "stdio"],
        "cwd": python_path,
        "env": {
            "PYTHONPATH": merged_python_path,
        },
    }


def build_feishu_imported_config() -> dict[str, Any]:
    return {
        "mcpServers": {
            FEISHU_MCP_SERVER_NAME: {
                "type": "stdio",
                **build_feishu_stdio_transport_config(),
            }
        }
    }


def build_feishu_user_config() -> list[dict[str, str]]:
    return [
        {
            "label": "APP_ID",
            "key": "app_id",
            "value": "",
        },
        {
            "label": "APP_SECRET",
            "key": "app_secret",
            "value": "",
        },
        {
            "label": "USER_ACCESS_TOKEN",
            "key": "user_access_token",
            "value": "",
        },
    ]
