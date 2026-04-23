import asyncio
import json
import os
import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from typing import Any
from urllib.parse import urlparse

import httpx

from agentchat.services.resume_ingestion.file_loader import extract_file_name, load_file_bytes
from agentchat.settings import app_settings

DEFAULT_MINERU_TIMEOUT = 120
DEFAULT_MINERU_BASE_URL = "https://mineru.net"
MAX_MINERU_CONTENT_CHARS = 7000
HTML_FILE_SUFFIXES = {".html", ".htm", ".xhtml", ".shtml"}


@dataclass
class MineruClientConfig:
    base_url: str
    token: str | None
    timeout_seconds: int
    poll_interval_seconds: float
    max_poll_rounds: int
    model_version: str


def _build_mineru_config() -> MineruClientConfig:
    mineru_config = getattr(app_settings.tools, "mineru", {}) if app_settings.tools else {}
    if not isinstance(mineru_config, dict):
        mineru_config = {}

    timeout_seconds = int(os.getenv(
        "MINERU_API_TIMEOUT_SECONDS",
        str(mineru_config.get("timeout_seconds", DEFAULT_MINERU_TIMEOUT)),
    ))

    return MineruClientConfig(
        base_url=os.getenv(
            "MINERU_API_BASE_URL",
            str(mineru_config.get("base_url", DEFAULT_MINERU_BASE_URL)),
        ).rstrip("/"),
        token=(
            os.getenv("MINERU_API_TOKEN")
            or os.getenv("MINERU_API_KEY")
            or _normalize_optional_string(mineru_config.get("token"))
            or _normalize_optional_string(mineru_config.get("api_key"))
        ),
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=float(os.getenv(
            "MINERU_API_POLL_INTERVAL_SECONDS",
            str(mineru_config.get("poll_interval_seconds", "1.5")),
        )),
        max_poll_rounds=int(os.getenv(
            "MINERU_API_MAX_POLL_ROUNDS",
            str(mineru_config.get("max_poll_rounds", "80")),
        )),
        model_version=os.getenv(
            "MINERU_MODEL_VERSION",
            str(mineru_config.get("model_version", "vlm")),
        ).strip() or "vlm",
    )


def _build_headers(config: MineruClientConfig) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
    }
    if config.token:
        headers["Authorization"] = f"Bearer {config.token}"
    return headers


async def parse_file_with_mineru(
    file_url: str,
    output_format: str = "markdown",
    force_ocr: bool = False,
) -> dict[str, Any]:
    config = _build_mineru_config()
    _validate_mineru_config(config)

    file_name = extract_file_name(file_url)
    resolved_model_version = _resolve_model_version(config.model_version, file_name)
    request_mode = "remote_url"

    if _should_use_remote_file_url(file_url):
        payload = await _submit_file_parse(
            config=config,
            file_url=file_url,
            file_name=file_name,
            force_ocr=force_ocr,
            model_version=resolved_model_version,
        )
        payload = await _resolve_parse_payload(config, payload)
    else:
        request_mode = "local_upload"
        file_bytes = await asyncio.to_thread(load_file_bytes, file_url, file_name)
        payload = await _submit_local_file_parse(
            config=config,
            file_name=file_name,
            file_bytes=file_bytes,
            force_ocr=force_ocr,
            model_version=resolved_model_version,
        )

    return _normalize_parse_payload(
        payload,
        file_name=file_name,
        output_format=output_format,
        model_version=resolved_model_version,
        request_mode=request_mode,
    )


async def _submit_file_parse(
    *,
    config: MineruClientConfig,
    file_url: str,
    file_name: str,
    force_ocr: bool,
    model_version: str,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "url": file_url,
        "model_version": model_version,
    }
    if force_ocr:
        data["is_ocr"] = True
    data["data_id"] = _build_data_id(file_name)

    async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
        response = await client.post(
            f"{config.base_url}/api/v4/extract/task",
            headers=_build_headers(config),
            json=data,
        )
        response.raise_for_status()
        payload = response.json()
        _ensure_success_response(payload)
        return payload


async def _submit_local_file_parse(
    *,
    config: MineruClientConfig,
    file_name: str,
    file_bytes: bytes,
    force_ocr: bool,
    model_version: str,
) -> dict[str, Any]:
    if not file_bytes:
        raise RuntimeError("未能读取上传文件内容，无法调用 MinerU 解析。")

    request_file = {
        "name": file_name,
        "data_id": _build_data_id(file_name),
    }
    if force_ocr:
        request_file["is_ocr"] = True

    async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
        response = await client.post(
            f"{config.base_url}/api/v4/file-urls/batch",
            headers=_build_headers(config),
            json={
                "files": [request_file],
                "model_version": model_version,
            },
        )
        response.raise_for_status()
        payload = response.json()
        _ensure_success_response(payload)

        batch_data = payload.get("data") or {}
        batch_id = _ensure_string(batch_data.get("batch_id"))
        upload_urls = batch_data.get("file_urls") or []
        upload_url = upload_urls[0] if isinstance(upload_urls, list) and upload_urls else ""

        if not batch_id or not isinstance(upload_url, str) or not upload_url.strip():
            raise RuntimeError("MinerU 未返回本地文件上传地址，请稍后重试。")

        upload_response = await client.put(upload_url.strip(), content=file_bytes)
        upload_response.raise_for_status()

        return await _poll_batch_parse_payload(
            client=client,
            config=config,
            batch_id=batch_id,
            file_name=file_name,
            model_version=model_version,
        )


async def _resolve_parse_payload(config: MineruClientConfig, payload: dict[str, Any]) -> dict[str, Any]:
    if _has_parse_results(payload):
        return payload

    task_data = payload.get("data") or {}
    task_id = _ensure_string(task_data.get("task_id"))
    if not task_id:
        return payload

    async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
        for _ in range(config.max_poll_rounds):
            response = await client.get(
                f"{config.base_url}/api/v4/extract/task/{task_id}",
                headers=_build_headers(config),
            )
            response.raise_for_status()
            current_payload = response.json()
            _ensure_success_response(current_payload)

            current_task_data = current_payload.get("data") or {}
            state = _ensure_string(current_task_data.get("state")).lower()

            if state == "done":
                full_zip_url = _ensure_string(current_task_data.get("full_zip_url"))
                if full_zip_url:
                    zip_payload = await _fetch_result_zip_payload(client, full_zip_url)
                    zip_payload["task_data"] = current_task_data
                    return zip_payload
                raise RuntimeError("MinerU 任务已完成，但未返回 full_zip_url。")

            if state == "failed":
                raise RuntimeError(
                    _ensure_string(current_task_data.get("err_msg"))
                    or _ensure_string(current_task_data.get("message"))
                    or "MinerU 解析失败。"
                )

            await asyncio.sleep(config.poll_interval_seconds)

    raise TimeoutError("MinerU 解析超时，请稍后重试。")


async def _poll_batch_parse_payload(
    *,
    client: httpx.AsyncClient,
    config: MineruClientConfig,
    batch_id: str,
    file_name: str,
    model_version: str,
) -> dict[str, Any]:
    for _ in range(config.max_poll_rounds):
        response = await client.get(
            f"{config.base_url}/api/v4/extract-results/batch/{batch_id}",
            headers=_build_headers(config),
        )
        response.raise_for_status()
        payload = response.json()
        _ensure_success_response(payload)

        batch_data = payload.get("data") or {}
        extract_result = _get_batch_extract_result(batch_data, file_name)
        state = _ensure_string(extract_result.get("state")).lower()

        if state == "done":
            full_zip_url = _ensure_string(extract_result.get("full_zip_url"))
            if full_zip_url:
                zip_payload = await _fetch_result_zip_payload(client, full_zip_url)
                zip_payload["task_data"] = {
                    "batch_id": batch_id,
                    "state": state,
                    "model_version": model_version,
                    "file_name": file_name,
                }
                return zip_payload
            raise RuntimeError("MinerU 任务已完成，但未返回 full_zip_url。")

        if state == "failed":
            raise RuntimeError(
                _ensure_string(extract_result.get("err_msg"))
                or "MinerU 解析失败。"
            )

        await asyncio.sleep(config.poll_interval_seconds)

    raise TimeoutError("MinerU 本地文件解析超时，请稍后重试。")


async def _fetch_result_zip_payload(
    client: httpx.AsyncClient,
    full_zip_url: str,
) -> dict[str, Any]:
    response = await client.get(full_zip_url)
    response.raise_for_status()
    return _parse_result_zip(response.content)


def _parse_result_zip(zip_bytes: bytes) -> dict[str, Any]:
    with zipfile.ZipFile(BytesIO(zip_bytes)) as archive:
        payload: dict[str, Any] = {"results": {}}
        content_list_items: list[dict[str, Any]] = []

        for zipped_name in archive.namelist():
            if zipped_name.endswith(".md"):
                payload["results"][zipped_name] = {
                    "md_content": archive.read(zipped_name).decode("utf-8", errors="ignore")
                }
            elif zipped_name.endswith(".html"):
                payload["results"][zipped_name] = {
                    "html_content": archive.read(zipped_name).decode("utf-8", errors="ignore")
                }
            elif zipped_name.endswith("_content_list.json"):
                try:
                    parsed_json = json.loads(archive.read(zipped_name).decode("utf-8", errors="ignore"))
                    if isinstance(parsed_json, list):
                        content_list_items = [item for item in parsed_json if isinstance(item, dict)]
                except Exception:
                    continue

        if payload["results"]:
            first_key = next(iter(payload["results"]))
            payload["results"][first_key]["content_list"] = content_list_items

        return payload


def _has_parse_results(payload: dict[str, Any]) -> bool:
    return isinstance(payload, dict) and bool(payload.get("results"))


def _normalize_parse_payload(
    payload: dict[str, Any],
    *,
    file_name: str,
    output_format: str,
    model_version: str,
    request_mode: str,
) -> dict[str, Any]:
    primary_result = _get_primary_result(payload, file_name)
    md_content = ""
    html_content = ""
    content_list: list[dict[str, Any]] = []

    if isinstance(primary_result, dict):
        md_content = _ensure_string(primary_result.get("md_content"))
        html_content = _ensure_string(primary_result.get("html_content"))
        raw_content_list = primary_result.get("content_list")
        if isinstance(raw_content_list, list):
            content_list = [item for item in raw_content_list if isinstance(item, dict)]

    if not md_content and not html_content:
        md_content = _content_list_to_markdown(content_list)

    plain_text = (
        _markdown_to_plain_text(md_content)
        if md_content
        else _html_to_plain_text(html_content)
        if html_content
        else _content_list_to_text(content_list)
    )

    normalized_content = plain_text
    normalized_output_format = "text"
    if output_format == "markdown" and md_content:
        normalized_content = md_content
        normalized_output_format = "markdown"
    elif output_format == "html" and html_content:
        normalized_content = html_content
        normalized_output_format = "html"

    normalized_content = re.sub(r"\n{3,}", "\n\n", normalized_content).strip()
    truncated_content, is_truncated = _truncate_content(normalized_content)

    return {
        "file_name": file_name,
        "backend": "mineru-official-api",
        "request_mode": request_mode,
        "output_format": normalized_output_format,
        "content": truncated_content,
        "content_length": len(normalized_content),
        "is_truncated": is_truncated,
        "preview": truncated_content[:320],
        "task_id": _ensure_string((payload.get("task_data") or {}).get("task_id")),
        "state": _ensure_string((payload.get("task_data") or {}).get("state")) or "done",
        "model_version": (
            _ensure_string((payload.get("task_data") or {}).get("model_version"))
            or model_version
        ),
    }


def _get_primary_result(payload: dict[str, Any], file_name: str) -> dict[str, Any]:
    results = payload.get("results")
    if isinstance(results, dict):
        if file_name in results and isinstance(results[file_name], dict):
            return results[file_name]

        for key, value in results.items():
            if isinstance(key, str) and key.endswith(file_name) and isinstance(value, dict):
                return value

        for value in results.values():
            if isinstance(value, dict):
                return value
    return {}


def _content_list_to_markdown(content_list: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in content_list:
        item_type = _ensure_string(item.get("type")).lower()
        text = _extract_item_text(item)
        if not text:
            continue

        if item_type in {"title", "section_title"}:
            parts.append(f"## {text}")
        else:
            parts.append(text)

    return "\n\n".join(parts).strip()


def _content_list_to_text(content_list: list[dict[str, Any]]) -> str:
    parts = [_extract_item_text(item) for item in content_list]
    return "\n".join(part for part in parts if part).strip()


def _extract_item_text(item: dict[str, Any]) -> str:
    preferred_keys = [
        "text",
        "content",
        "md_content",
        "html_content",
        "latex",
        "html",
        "caption",
    ]
    for key in preferred_keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for key in ["blocks", "children"]:
        nested_items = item.get(key)
        if isinstance(nested_items, list):
            nested_text = _content_list_to_text([child for child in nested_items if isinstance(child, dict)])
            if nested_text:
                return nested_text

    return ""


def _markdown_to_plain_text(content: str) -> str:
    text = re.sub(r"!\[[^\]]*]\([^)]*\)", "", content)
    text = re.sub(r"\[([^\]]+)]\([^)]*\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"`{1,3}", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _html_to_plain_text(content: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", "", content, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _truncate_content(content: str) -> tuple[str, bool]:
    if len(content) <= MAX_MINERU_CONTENT_CHARS:
        return content, False

    truncated = content[:MAX_MINERU_CONTENT_CHARS].rstrip()
    if "\n" in truncated:
        truncated = truncated.rsplit("\n", 1)[0].rstrip()

    if not truncated:
        truncated = content[:MAX_MINERU_CONTENT_CHARS].rstrip()

    return f"{truncated}\n...[MinerU 解析结果过长，已截断]", True


def _ensure_string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalize_optional_string(value: Any) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return None


def _ensure_success_response(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise RuntimeError("MinerU 返回了非 JSON 对象。")
    if payload.get("code") != 0:
        raise RuntimeError(_ensure_string(payload.get("msg")) or "MinerU 接口调用失败。")


def _build_data_id(file_name: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_.-]", "_", file_name)
    return normalized[:120] or "resume_file"


def _resolve_model_version(configured_model_version: str, file_name: str) -> str:
    normalized_model_version = configured_model_version.strip() if isinstance(configured_model_version, str) else ""
    if normalized_model_version and normalized_model_version.lower() != "auto":
        return normalized_model_version

    lowered_file_name = file_name.lower()
    if any(lowered_file_name.endswith(suffix) for suffix in HTML_FILE_SUFFIXES):
        return "MinerU-HTML"

    return "vlm"


def _validate_mineru_config(config: MineruClientConfig) -> None:
    if not config.token:
        raise RuntimeError("未配置 MinerU Token，请在 config.yaml 的 tools.mineru.token 中填写。")


def _get_batch_extract_result(batch_data: dict[str, Any], file_name: str) -> dict[str, Any]:
    results = batch_data.get("extract_result")
    if not isinstance(results, list):
        return {}

    for item in results:
        if not isinstance(item, dict):
            continue
        current_name = _ensure_string(item.get("file_name"))
        if current_name == file_name or (current_name and current_name.endswith(file_name)):
            return item

    for item in results:
        if isinstance(item, dict):
            return item

    return {}


def _should_use_remote_file_url(file_url: str) -> bool:
    parsed = urlparse(file_url)
    host = (parsed.hostname or "").lower()

    if parsed.scheme not in {"http", "https"}:
        return False

    if (
        host in {"127.0.0.1", "localhost"}
        or host.startswith("10.")
        or host.startswith("192.168.")
        or re.match(r"^172\.(1[6-9]|2\d|3[0-1])\.", host)
    ):
        return False

    return True
