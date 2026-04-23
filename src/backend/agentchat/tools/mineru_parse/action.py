from langchain.tools import tool
from langgraph.config import get_stream_writer
from loguru import logger

from agentchat.services.mineru import parse_file_with_mineru


@tool("mineru_parse", parse_docstring=True)
async def mineru_parse(
    file_url: str,
    output_format: str = "markdown",
    force_ocr: bool = False,
):
    """
    使用 MinerU 对上传的 PDF、DOCX、图片等文件进行高质量解析，提取可供后续工具继续使用的正文内容。

    Args:
        file_url (str): 用户上传文件的 file_url。支持公网文件链接，也支持当前系统已上传的本地/私有存储文件。
        output_format (str): 输出格式，可选 markdown、text 或 html，默认 markdown。
        force_ocr (bool): 是否强制使用 OCR 解析，适用于扫描版 PDF 或图片文档。

    Returns:
        str: 包含解析摘要和正文内容的结果，可直接继续传给 resume_match、resume_rewrite、interview_followup。
    """
    return await _mineru_parse(file_url, output_format, force_ocr)


async def _mineru_parse(file_url: str, output_format: str, force_ocr: bool) -> str:
    if not isinstance(file_url, str) or not file_url.strip():
        return "请先提供用户上传文件的 file_url，再调用 MinerU 解析。"

    normalized_output_format = output_format.strip().lower() if isinstance(output_format, str) else "markdown"
    if normalized_output_format not in {"markdown", "text", "html"}:
        normalized_output_format = "markdown"

    try:
        result = await parse_file_with_mineru(
            file_url=file_url.strip(),
            output_format=normalized_output_format,
            force_ocr=force_ocr,
        )
        _emit_mineru_parse_summary(result)
        return _format_mineru_parse_result(result)
    except Exception as err:
        logger.error(f"mineru_parse tool failed: {err}")
        return f"MinerU 文档解析失败，请检查 mineru-api 服务状态或稍后重试。错误信息：{err}"


def _emit_mineru_parse_summary(result: dict) -> None:
    try:
        writer = get_stream_writer()
    except Exception:
        writer = None

    if not writer:
        return

    writer({
        "status": "END",
        "title": "MinerU 文档解析完成",
        "message": (
            f"已完成 {result.get('file_name', '文件')} 的高质量解析，"
            f"请求方式：{_format_request_mode(result.get('request_mode'))}，"
            f"输出格式：{result.get('output_format', 'markdown')}，"
            f"内容长度：{result.get('content_length', 0)} 字符。"
        ),
        "event_type": "mineru_parse_result",
        "tool_name": "mineru_parse",
        "structured_data": {
            "file_name": result.get("file_name", ""),
            "backend": result.get("backend", "mineru-api"),
            "request_mode": result.get("request_mode", ""),
            "output_format": result.get("output_format", "markdown"),
            "content_length": result.get("content_length", 0),
            "is_truncated": result.get("is_truncated", False),
            "preview": result.get("preview", ""),
        },
    })


def _format_mineru_parse_result(result: dict) -> str:
    truncated_note = " 是" if result.get("is_truncated") else " 否"
    return (
        "MinerU 文档解析结果\n"
        f"文件名：{result.get('file_name', '未知文件')}\n"
        f"解析后端：{result.get('backend', 'mineru-api')}\n"
        f"请求方式：{_format_request_mode(result.get('request_mode'))}\n"
        f"模型版本：{result.get('model_version', '') or '未返回'}\n"
        f"输出格式：{result.get('output_format', 'markdown')}\n"
        f"是否截断：{truncated_note}\n\n"
        "以下正文可直接继续作为简历/项目内容传给 resume_match、resume_rewrite、interview_followup：\n"
        f"{result.get('content', '')}"
    )


def _format_request_mode(request_mode: str | None) -> str:
    if request_mode == "local_upload":
        return "本地文件上传"
    if request_mode == "remote_url":
        return "公网 URL 拉取"
    return "未知"
