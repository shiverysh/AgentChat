from typing import Any, Literal


ExecutionKind = Literal["tool", "mcp", "skill", "mcp_tool", "skill_tool"]
ExecutionScope = Literal["agent", "mcp_agent", "skill_agent"]


def build_execution_title(
    call_kind: ExecutionKind,
    call_name: str,
    parent_name: str | None = None,
) -> str:
    if call_kind == "tool":
        return f"工具调用: {call_name}"
    if call_kind == "mcp":
        return f"MCP 调用: {call_name}"
    if call_kind == "skill":
        return f"Skill 调用: {call_name}"
    if call_kind == "mcp_tool":
        return f"MCP 工具: {parent_name or '未知服务'} / {call_name}"
    if call_kind == "skill_tool":
        return f"Skill 工具: {parent_name or '未知技能'} / {call_name}"
    return f"执行调用: {call_name}"


def build_execution_event(
    *,
    status: str,
    message: str,
    call_kind: ExecutionKind,
    call_name: str,
    raw_name: str,
    call_scope: ExecutionScope,
    call_id: str | None = None,
    parent_name: str | None = None,
    title: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = {
        "status": status,
        "title": title or build_execution_title(call_kind, call_name, parent_name),
        "message": message,
        "event_type": "agent_execution",
        "call_kind": call_kind,
        "call_name": call_name,
        "raw_name": raw_name,
        "call_scope": call_scope,
    }

    if call_id:
        event["call_id"] = call_id

    if parent_name:
        event["parent_name"] = parent_name

    if extra:
        event.update(extra)

    return event
