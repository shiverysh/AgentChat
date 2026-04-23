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


def get_calendars_list(
        app_id: str = Field(None, description="应用唯一标识，默认从用户配置中自动获取，无需额外传参"),
        app_secret: str = Field(None, description="应用密钥，默认从用户配置中自动获取，无需额外传参"),
        user_access_token: str = Field(None, description="飞书用户访问令牌；配置后会以用户身份读取日历列表。"),
):
    """获取日历列表，成功返回日历列表，失败返回报错信息"""
    if not has_user_access_token(user_access_token):
        return build_user_token_required_error("读取飞书日历列表")

    page_size = 100
    client = build_lark_client(app_id, app_secret)
    option = build_request_option(user_access_token)

    # 构造请求对象
    request_builder = ListCalendarRequest.builder().page_size(page_size)

    request: ListCalendarRequest = request_builder.build()

    # 发起请求
    response: ListCalendarResponse = client.calendar.v4.calendar.list(request, option)

    # 处理失败返回
    if not response.success():
        return build_error_response("client.calendar.v4.calendar.list", response)

    return build_success_response(
        data=response.data,
        response=response,
        user_access_token=user_access_token,
        resource_name="日历列表",
    )

    # # 对超过2000字符的工具进行特殊处理
    # max_return_char = 2000
    #
    # current_calendar = []
    # for calendar_info in response.data.calendar_list:
    #     if len(current_calendar) + len(str(calendar_info)) > max_return_char:
    #         current_calendar.append("上下文长度超出限制，仅展示部分日历信息")
    #         break
    #     else:
    #         current_calendar.append(calendar_info)
    # return str(current_calendar)
