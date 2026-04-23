from lark_oapi.api.calendar.v4 import *
from pydantic import Field
from typing import List

from ..calendar.primary_calendar import get_primary_calendar
from ..utils.response import (
    build_error_response,
    build_lark_client,
    build_request_option,
    build_success_response,
    build_user_token_required_error,
    has_user_access_token,
)


# 针对MCP的工具
# def append_calendar_event_attendee(
#         calendar_id: str = Field(..., description="日历ID"),
#         event_id: str = Field(..., description="日程事件ID"),
#         attendees: List[str] = Field(..., description="参会者列表，每个元素需包含open_id，"),
#         user_id_type: Literal["open_id", "user_id", "union_id"] = Field("open_id", description="用户ID类型"),
#         need_notification: bool = Field(False, description="是否需要发送通知给参会者"),
#         app_id: str = Field(None, description="应用唯一标识，默认从用户配置中自动获取，无需额外传参"),
#         app_secret: str = Field(None, description="应用密钥，默认从用户配置中自动获取，无需额外传参")
# ):


# 只针对MCP 的工具调用该函数，不给用户使用该函数
def append_calendar_event_attendee(
        calendar_id: str = Field(..., description="日历ID"),
        event_id: str = Field(..., description="日程事件ID"),
        user_id_type: str = Field(default="open_id", description="用户ID类型，可选值：open_id、union_id、user_id。"),
        need_notification: bool = Field(True, description="更新日程时，是否给日程参与人发送通知。"),
        attendees: List[str] = Field(..., description="参会者列表，每个元素需包含用户的open_id，"),
        app_id: str = Field(None, description="应用唯一标识，默认从用户配置中自动获取，无需额外传参"),
        app_secret: str = Field(None, description="应用密钥，默认从用户配置中自动获取，无需额外传参"),
        user_access_token: str = Field(None, description="飞书用户访问令牌；配置后会以用户身份追加参会人。"),
):
    """为日程事件添加参会者，成功返回日程信息，失败返回报错信息"""
    if not has_user_access_token(user_access_token):
        return build_user_token_required_error("为飞书日程追加参会人")

    client = build_lark_client(app_id, app_secret)
    option = build_request_option(user_access_token)

    # 如果用户不指定日历ID，默认使用共享日历
    if not calendar_id:
        calendar_id = get_primary_calendar(app_id, app_secret, user_access_token=user_access_token)

    # 构造参会者列表请求体
    attendee_list = [
        CalendarEventAttendee.builder()
        .type("user")
        .is_optional(True)  # 默认设为可选参会者
        .user_id(attendee)
        .build()
        for attendee in attendees
    ]

    # 构造请求对象
    request: CreateCalendarEventAttendeeRequest = CreateCalendarEventAttendeeRequest.builder() \
        .calendar_id(calendar_id) \
        .event_id(event_id) \
        .user_id_type(user_id_type) \
        .request_body(CreateCalendarEventAttendeeRequestBody.builder()
                      .attendees(attendee_list)
                      .need_notification(need_notification)
                      .build()) \
        .build()

    # 发起请求
    response: CreateCalendarEventAttendeeResponse = client.calendar.v4.calendar_event_attendee.create(request, option)

    # 处理失败返回
    if not response.success():
        raise ValueError(build_error_response("client.calendar.v4.calendar_event_attendee.create", response))

    return build_success_response(
        data=response.data,
        response=response,
        user_access_token=user_access_token,
        resource_name="日程参会人",
    )
