from typing import Optional

from langchain.tools import tool
from langchain_community.utilities import SerpAPIWrapper

from agentchat.settings import app_settings


search: Optional[SerpAPIWrapper] = None


def _get_google_search_client() -> SerpAPIWrapper:
    global search

    if search is not None:
        return search

    if not app_settings.tools:
        raise ValueError("Google 搜索工具尚未初始化配置。")

    api_key = app_settings.tools.google.get("api_key")
    if not api_key:
        raise ValueError("Google 搜索工具缺少 api_key 配置。")

    search = SerpAPIWrapper(serpapi_api_key=api_key)
    return search

@tool("web_search", parse_docstring=True)
def google_search(query: str):
    """
    根据用户的问题进行网上搜索信息。

    Args:
        query (str): 用户的问题。

    Returns:
        str: 搜索到的信息。
    """
    return _google_search(query)

def _google_search(query: str):
    """使用搜索工具给用户进行搜索"""
    result = _get_google_search_client().run(query)
    return result
