from lark_oapi.api.docx.v1 import *
from pydantic import Field

from .common import create_document_record, get_document_url
from ..utils.response import (
    build_lark_client,
    build_request_option,
    build_success_response,
)


def create_document(
        folder_token: str = Field(None, description="文件夹token, 没有传入的话在根目录中创建"),
        title: str = Field(..., description="文档标题"),
        app_id: str = Field(None, description="应用唯一标识，默认从用户配置中自动获取，无需额外传参"),
        app_secret: str = Field(None, description="应用密钥，默认从用户配置中自动获取，无需额外传参"),
        user_access_token: str = Field(None, description="飞书用户访问令牌；配置后会以用户身份调用，结果更容易出现在个人云文档。"),
):
    """创建文档，成功返回文档信息，失败返回报错信息"""
    client = build_lark_client(app_id, app_secret)
    option = build_request_option(user_access_token)
    response, error_message = create_document_record(client, title, folder_token, option)

    # 处理失败返回
    if error_message:
        return error_message

    return build_success_response(
        data=response.data,
        response=response,
        user_access_token=user_access_token,
        resource_name="文档",
        extra={
            "document_url": get_document_url(
                client,
                response.data.document.document_id,
                option,
            ),
        },
    )
