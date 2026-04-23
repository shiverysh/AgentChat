from lark_oapi.api.calendar.v4 import *
from pydantic import Field

from ..utils.response import (
    build_error_response,
    build_lark_client,
    build_request_option,
    build_success_response,
    build_user_token_required_error,
    has_user_access_token,
)

def get_calendar_info(
    calendar_id: str = Field(..., description="日历ID（必填），用于指定要获取的日历"),
    app_id: str = Field(None, description="应用唯一标识，默认从用户配置中自动获取，无需额外传参"),
    app_secret: str = Field(None, description="应用密钥，默认从用户配置中自动获取，无需额外传参"),
    user_access_token: str = Field(None, description="飞书用户访问令牌；配置后会以用户身份读取日历信息。"),
):
    """获取指定的日历信息，成功返回日历信息，失败返回报错信息"""
    if not has_user_access_token(user_access_token):
        return build_user_token_required_error("读取飞书日历信息")

    client = build_lark_client(app_id, app_secret)
    option = build_request_option(user_access_token)

    # 构造请求对象
    request: GetCalendarRequest = GetCalendarRequest.builder() \
        .calendar_id(calendar_id) \
        .build()

    # 发起请求
    response: GetCalendarResponse = client.calendar.v4.calendar.get(request, option)

    # 处理失败返回
    if not response.success():
        return build_error_response("client.calendar.v4.calendar.get", response)

    return build_success_response(
        data=response.data,
        response=response,
        user_access_token=user_access_token,
        resource_name="日历",
    )
