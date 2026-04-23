from lark_oapi.api.docx.v1 import *
from pydantic import Field

from .common import get_document_url
from ..utils.response import (
    build_error_response,
    build_lark_client,
    build_request_option,
    build_success_response,
)


def get_document(
        document_id: str = Field(..., description="文档ID"),
        app_id: str = Field(None, description="应用唯一标识，默认从用户配置中自动获取，无需额外传参"),
        app_secret: str = Field(None, description="应用密钥，默认从用户配置中自动获取，无需额外传参"),
        user_access_token: str = Field(None, description="飞书用户访问令牌；配置后会以用户身份读取文档内容。"),
):
    """获取文档内容，成功返回文档内容，失败返回报错信息"""
    client = build_lark_client(app_id, app_secret)
    option = build_request_option(user_access_token)

    # 构造请求对象
    request: RawContentDocumentRequest = RawContentDocumentRequest.builder() \
        .document_id(document_id) \
        .lang(0) \
        .build()

    # 发起请求
    response: RawContentDocumentResponse = client.docx.v1.document.raw_content(request, option)

    # 处理失败返回
    if not response.success():
        return build_error_response("client.docx.v1.document.raw_content", response)

    return build_success_response(
        data=response.data,
        response=response,
        user_access_token=user_access_token,
        resource_name="文档",
        extra={
            "document_url": get_document_url(client, document_id, option),
        },
    )
