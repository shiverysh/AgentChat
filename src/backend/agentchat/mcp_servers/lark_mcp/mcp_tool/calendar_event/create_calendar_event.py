import uuid

from lark_oapi.api.calendar.v4 import *
from pydantic import Field

from .append_calendar_event_attendees import append_calendar_event_attendee
from ..utils.response import (
    build_error_response,
    build_lark_client,
    build_request_option,
    build_success_response,
    build_user_token_required_error,
    has_user_access_token,
    safe_load_json_string,
)
from ..utils.time import convert_timestamp


def create_calendar_event(
        user_id_type: str = Field(default="open_id",
                                            description="用户ID类型，默认值为open_id"),
        calendar_id: str = Field(..., description="日历ID"),
        summary: str = Field(..., description="日程标题"),
        description: str = Field(..., description="日程描述"),
        need_notification: bool = Field(True, description="更新日程时，是否给日程参与人发送通知"),
        start_time: str = Field(..., description="开始时间，格式YYYY-MM-DD HH:MM"),
        end_time: str = Field(..., description="结束时间，格式YYYY-MM-DD HH:MM"),
        location_name: str = Field(None, description="日程的会议位置"),
        location_address: str = Field(None, description="日程的会议具体地点，如301会议室"),
        attendees: List[str] = Field(None, description="参会者列表，每个元素需包含用户的open_id"),
        timezone: str = Field("Asia/Shanghai", description="时区"),
        visibility: str = Field("default", description="日程公开范围"),
        attendee_ability: str = Field("can_see_others", description="参与者权限"),
        free_busy_status: str = Field("busy", description="日程占用的忙闲状态，新建日程默认为 busy"),
        recurrence: str = Field("FREQ=DAILY;INTERVAL=1", description="遵循日历RRule重复规则，如FREQ=DAILY;INTERVAL=1"),
        app_id: str = Field(None, description="应用唯一标识，默认从用户配置中自动获取，无需额外传参"),
        app_secret: str = Field(None, description="应用密钥，默认从用户配置中自动获取，无需额外传参"),
        user_access_token: str = Field(None, description="飞书用户访问令牌；配置后会以用户身份创建日程。"),
):
    """创建飞书日程事件，日程创建成功返回日程信息，失败返回错误信息"""
    if not has_user_access_token(user_access_token):
        return build_user_token_required_error("创建飞书日程")

    client = build_lark_client(app_id, app_secret)
    option = build_request_option(user_access_token)

    # 将给的字符串时间转成时间戳
    start_timestamp = convert_timestamp(start_time)
    end_timestamp = convert_timestamp(end_time)


    # 构造请求对象
    request: CreateCalendarEventRequest = CreateCalendarEventRequest.builder() \
        .calendar_id(calendar_id) \
        .idempotency_key(uuid.uuid4().hex) \
        .user_id_type(user_id_type) \
        .request_body(CalendarEvent.builder()
                      .summary(summary)
                      .description(description)
                      .need_notification(need_notification)
                      .start_time(TimeInfo.builder()
                                  #.date(start_date) # 使用更精准的时间戳代表时间
                                  .timestamp(start_timestamp)
                                  .timezone(timezone)
                                  .build())
                      .end_time(TimeInfo.builder()
                                #.date(end_date)  # 使用更精准的时间戳代表时间
                                .timestamp(end_timestamp)
                                .timezone(timezone)
                                .build())
                      .visibility(visibility)
                      .location(EventLocation.builder().name(location_name).address(location_address).build())
                      .attendee_ability(attendee_ability)
                      .free_busy_status(free_busy_status)
                      .recurrence(recurrence)
                      .build()) \
        .build()

    # 发起请求
    response: CreateCalendarEventResponse = client.calendar.v4.calendar_event.create(request, option)

    # 处理失败返回
    if not response.success():
        return build_error_response("client.calendar.v4.calendar_event.create", response)

    # 参会人处理（如果有参会人）
    attendee_result = None
    if attendees:
        try:
            event_id = response.data.event.event_id
            attendee_result = append_calendar_event_attendee(
                app_id=app_id,
                app_secret=app_secret,
                user_access_token=user_access_token,
                event_id=event_id,
                calendar_id=calendar_id,
                user_id_type=user_id_type,
                attendees=attendees,
                need_notification=need_notification
            )
        except Exception as err:
            attendee_result = {
                "success": False,
                "error": f"添加参会人失败: {err}",
            }

    return build_success_response(
        data=response.data,
        response=response,
        user_access_token=user_access_token,
        resource_name="日程",
        extra={
            "attendee_result": safe_load_json_string(attendee_result),
        } if attendee_result is not None else None,
    )
