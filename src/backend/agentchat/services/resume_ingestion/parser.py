import asyncio
import io
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import fitz
from loguru import logger

from agentchat.services.resume_ingestion.file_loader import extract_file_name, load_file_bytes

MAX_RESUME_TEXT_CHARS = 6000
WORD_NAMESPACE = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
TEXT_FILE_SUFFIXES = {".txt", ".md", ".markdown"}


async def parse_uploaded_file(file_url: str | None) -> dict | None:
    if not file_url:
        return None

    return await asyncio.to_thread(_parse_uploaded_file_sync, file_url)


def _parse_uploaded_file_sync(file_url: str) -> dict | None:
    file_name = extract_file_name(file_url)
    file_suffix = Path(file_name).suffix.lower()

    try:
        file_bytes = load_file_bytes(file_url, file_name)
        extracted_text = _extract_text(file_bytes, file_suffix)
        cleaned_text = _normalize_text(extracted_text)

        if not cleaned_text:
            return {
                "file_name": file_name,
                "file_type": file_suffix.lstrip(".") or "unknown",
                "content": "",
                "parse_status": "empty",
                "is_truncated": False,
            }

        truncated_text, is_truncated = _truncate_text(cleaned_text, MAX_RESUME_TEXT_CHARS)
        return {
            "file_name": file_name,
            "file_type": file_suffix.lstrip(".") or "unknown",
            "content": truncated_text,
            "parse_status": "success",
            "is_truncated": is_truncated,
        }
    except Exception as err:
        logger.error(f"parse uploaded file failed | file_url={file_url} | error={err}")
        return {
            "file_name": file_name,
            "file_type": file_suffix.lstrip(".") or "unknown",
            "content": "",
            "parse_status": "failed",
            "is_truncated": False,
            "error_message": str(err),
        }


def _extract_text(file_bytes: bytes, file_suffix: str) -> str:
    if file_suffix == ".pdf":
        return _extract_pdf_text(file_bytes)

    if file_suffix == ".docx":
        return _extract_docx_text(file_bytes)

    if file_suffix in TEXT_FILE_SUFFIXES:
        return _extract_plain_text(file_bytes)

    # 没有识别到后缀时，退化为纯文本尝试，避免把可读文本文件直接判死。
    return _extract_plain_text(file_bytes)


def _extract_pdf_text(file_bytes: bytes) -> str:
    with fitz.open(stream=file_bytes, filetype="pdf") as document:
        pages = [page.get_text("text") for page in document]
    return "\n".join(pages)


def _extract_docx_text(file_bytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
        document_xml = archive.read("word/document.xml")

    root = ElementTree.fromstring(document_xml)
    paragraphs: list[str] = []

    for paragraph in root.findall(".//w:p", WORD_NAMESPACE):
        texts = []
        for node in paragraph.findall(".//w:t", WORD_NAMESPACE):
            if node.text:
                texts.append(node.text)

        paragraph_text = "".join(texts).strip()
        if paragraph_text:
            paragraphs.append(paragraph_text)

    return "\n".join(paragraphs)


def _extract_plain_text(file_bytes: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue

    return file_bytes.decode("utf-8", errors="ignore")


def _normalize_text(content: str) -> str:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    normalized = re.sub(r"[ \t]+", " ", normalized)

    lines: list[str] = []
    previous_blank = False

    for raw_line in normalized.split("\n"):
        line = raw_line.strip()
        if not line:
            if previous_blank:
                continue
            previous_blank = True
            lines.append("")
            continue

        previous_blank = False
        lines.append(line)

    return "\n".join(lines).strip()


def _truncate_text(content: str, limit: int) -> tuple[str, bool]:
    if len(content) <= limit:
        return content, False

    truncated = content[:limit].rstrip()
    if "\n" in truncated:
        truncated = truncated.rsplit("\n", 1)[0].rstrip()

    if not truncated:
        truncated = content[:limit].rstrip()

    return f"{truncated}\n...[文件内容过长，已截断]", True
