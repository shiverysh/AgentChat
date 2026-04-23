import json
from typing import Any

import lark_oapi as lark
from lark_oapi.core import RequestOption


def normalize_optional_value(value: Any):
    normalized = getattr(value, "default", value)
    if normalized is ...:
        return None
    return normalized


def build_lark_client(app_id: str | None, app_secret: str | None):
    app_id = normalize_optional_value(app_id)
    app_secret = normalize_optional_value(app_secret)
    return (
        lark.Client.builder()
        .app_id(app_id)
        .app_secret(app_secret)
        .log_level(lark.LogLevel.DEBUG)
        .build()
    )


def build_request_option(user_access_token: str | None):
    user_access_token = normalize_optional_value(user_access_token)
    if not user_access_token:
        return None
    return RequestOption.builder().user_access_token(user_access_token).build()


def has_user_access_token(user_access_token: str | None) -> bool:
    return bool(normalize_optional_value(user_access_token))


def get_token_mode(user_access_token: str | None) -> str:
    user_access_token = normalize_optional_value(user_access_token)
    return "user" if user_access_token else "tenant"


def build_visibility_hint(user_access_token: str | None, resource_name: str) -> str:
    user_access_token = normalize_optional_value(user_access_token)
    if user_access_token:
        return (
            f"当前使用用户身份调用飞书 API，{resource_name}通常会出现在该用户的飞书空间；"
            "若仍不可见，请检查应用权限、可见范围和飞书客户端账号是否一致。"
        )

    return (
        f"当前使用应用身份调用飞书 API，请求可能成功，但{resource_name}不保证出现在你的个人飞书空间；"
        "如需个人空间可见，请补充 user_access_token。"
    )


def build_user_token_required_error(resource_name: str) -> str:
    message = (
        f"CONFIG_ERROR: {resource_name}需要先配置 USER_ACCESS_TOKEN。"
        "当前飞书日历相关接口必须以用户身份调用。"
        "请前往 MCP 页面给“飞书”补充 USER_ACCESS_TOKEN，"
        "并确认应用已开通 calendar:calendar、calendar:calendar:read、"
        "calendar:calendar.event:create、calendar:calendar.event:read、"
        "calendar:calendar.event:update 等权限后再重试。"
    )
    lark.logger.error(message)
    return message


def marshal_lark_data(data: Any):
    if data is None:
        return None
    if isinstance(data, (dict, list, str, int, float, bool)):
        return data

    marshaled = lark.JSON.marshal(data, indent=4)
    try:
        return json.loads(marshaled)
    except Exception:
        return marshaled


def safe_load_json_string(content: Any):
    if not isinstance(content, str):
        return content

    try:
        return json.loads(content)
    except Exception:
        return content


def build_success_response(
    *,
    data: Any,
    response: Any,
    user_access_token: str | None,
    resource_name: str,
    extra: dict[str, Any] | None = None,
) -> str:
    payload = {
        "success": True,
        "token_mode": get_token_mode(user_access_token),
        "visibility_hint": build_visibility_hint(user_access_token, resource_name),
        "log_id": response.get_log_id(),
        "data": marshal_lark_data(data),
    }
    if extra:
        payload.update(extra)

    message = json.dumps(payload, ensure_ascii=False, indent=2)
    lark.logger.info(message)
    return message


def build_error_response(action_name: str, response: Any) -> str:
    raw_content = getattr(getattr(response, "raw", None), "content", "")
    try:
        raw_body = json.dumps(json.loads(raw_content), indent=4, ensure_ascii=False)
    except Exception:
        raw_body = str(raw_content)

    fail_message = (
        f"{action_name} failed, code: {response.code}, msg: {response.msg}, "
        f"log_id: {response.get_log_id()}, resp: \n{raw_body}"
    )
    lark.logger.error(fail_message)
    return fail_message
