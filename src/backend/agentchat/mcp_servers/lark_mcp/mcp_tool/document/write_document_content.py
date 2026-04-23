import json

from pydantic import Field

from .common import append_document_blocks, get_document_revision, get_document_url, parse_content_to_blocks
from ..utils.response import (
    build_lark_client,
    build_request_option,
    build_visibility_hint,
    get_token_mode,
)


def write_document_content(
        document_id: str = Field(..., description="文档 ID"),
        content: str = Field(..., description="需要写入飞书文档的正文内容，支持按行解析为标题、段落和列表"),
        app_id: str = Field(None, description="应用唯一标识，默认从用户配置中自动获取，无需额外传参"),
        app_secret: str = Field(None, description="应用密钥，默认从用户配置中自动获取，无需额外传参"),
        user_access_token: str = Field(None, description="飞书用户访问令牌；配置后会以用户身份写入文档内容。"),
):
    """向飞书文档写入正文内容，支持标题、段落和列表。"""
    client = build_lark_client(app_id, app_secret)
    option = build_request_option(user_access_token)

    document_response, error_message = get_document_revision(client, document_id, option)
    if error_message:
        return error_message

    document = getattr(getattr(document_response, "data", None), "document", None)
    document_revision_id = getattr(document, "revision_id", 0)
    title = getattr(document, "title", "")

    blocks = parse_content_to_blocks(content)
    if not blocks:
        payload = {
            "success": True,
            "token_mode": get_token_mode(user_access_token),
            "visibility_hint": build_visibility_hint(user_access_token, "文档"),
            "document_id": document_id,
            "document_title": title,
            "document_url": get_document_url(client, document_id, option),
            "written_block_count": 0,
            "message": "未检测到可写入的正文内容，跳过正文灌入。",
            "read_log_id": document_response.get_log_id(),
        }
        message = json.dumps(payload, ensure_ascii=False, indent=2)
        return message

    append_result, error_message = append_document_blocks(
        client=client,
        document_id=document_id,
        document_revision_id=document_revision_id,
        blocks=blocks,
        option=option,
    )
    if error_message:
        return error_message

    payload = {
        "success": True,
        "token_mode": get_token_mode(user_access_token),
        "visibility_hint": build_visibility_hint(user_access_token, "文档"),
        "document_id": document_id,
        "document_title": title,
        "document_url": get_document_url(client, document_id, option),
        "written_block_count": append_result["written_block_count"],
        "document_revision_id": append_result["document_revision_id"],
        "read_log_id": document_response.get_log_id(),
        "write_log_ids": append_result["write_log_ids"],
    }
    message = json.dumps(payload, ensure_ascii=False, indent=2)
    return message
