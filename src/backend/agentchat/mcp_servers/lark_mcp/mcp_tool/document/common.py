import re
import uuid
from typing import Any

from lark_oapi.api.docx.v1 import (
    Block,
    CreateDocumentBlockChildrenRequest,
    CreateDocumentBlockChildrenRequestBody,
    CreateDocumentRequest,
    CreateDocumentRequestBody,
    GetDocumentRequest,
    Text,
    TextElement,
    TextRun,
)
from lark_oapi.api.drive.v1 import BatchQueryMetaRequest, MetaRequest, RequestDoc

from ..utils.response import build_error_response, normalize_optional_value

DOCX_BATCH_SIZE = 20
DOCX_TYPE = "docx"

BLOCK_TYPE_TEXT = 2
BLOCK_TYPE_HEADING_1 = 3
BLOCK_TYPE_HEADING_2 = 4
BLOCK_TYPE_HEADING_3 = 5
BLOCK_TYPE_BULLET = 12
BLOCK_TYPE_ORDERED = 13


def create_document_record(client, title: str, folder_token: str | None, option):
    folder_token = normalize_optional_value(folder_token)
    request = (
        CreateDocumentRequest.builder()
        .request_body(
            CreateDocumentRequestBody.builder()
            .folder_token(folder_token)
            .title(title)
            .build()
        )
        .build()
    )
    response = client.docx.v1.document.create(request, option)
    if not response.success():
        return None, build_error_response("client.docx.v1.document.create", response)
    return response, None


def get_document_revision(client, document_id: str, option):
    request = GetDocumentRequest.builder().document_id(document_id).build()
    response = client.docx.v1.document.get(request, option)
    if not response.success():
        return None, build_error_response("client.docx.v1.document.get", response)
    return response, None


def get_document_url(client, document_id: str, option):
    request = (
        BatchQueryMetaRequest.builder()
        .request_body(
            MetaRequest.builder()
            .with_url(True)
            .request_docs([
                RequestDoc.builder().doc_token(document_id).doc_type(DOCX_TYPE).build()
            ])
            .build()
        )
        .build()
    )
    response = client.drive.v1.meta.batch_query(request, option)
    if not response.success():
        return None
    metas = getattr(getattr(response, "data", None), "metas", None) or []
    if not metas:
        return None
    return getattr(metas[0], "url", None)


def append_document_blocks(client, document_id: str, document_revision_id: int, blocks: list[Block], option):
    current_revision_id = document_revision_id
    log_ids: list[str] = []
    written_block_count = 0

    for batch in _chunk_blocks(blocks, DOCX_BATCH_SIZE):
        request = (
            CreateDocumentBlockChildrenRequest.builder()
            .document_id(document_id)
            .block_id(document_id)
            .document_revision_id(current_revision_id)
            .client_token(uuid.uuid4().hex)
            .request_body(
                CreateDocumentBlockChildrenRequestBody.builder()
                .children(batch)
                .build()
            )
            .build()
        )
        response = client.docx.v1.document_block_children.create(request, option)
        if not response.success():
            return None, build_error_response("client.docx.v1.document_block_children.create", response)

        current_revision_id = getattr(getattr(response, "data", None), "document_revision_id", current_revision_id)
        written_block_count += len(getattr(getattr(response, "data", None), "children", []) or batch)
        log_ids.append(response.get_log_id())

    return {
        "document_revision_id": current_revision_id,
        "written_block_count": written_block_count,
        "write_log_ids": log_ids,
    }, None


def parse_content_to_blocks(content: str) -> list[Block]:
    blocks: list[Block] = []
    for raw_line in (content or "").splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        parsed_line = _parse_line_kind(stripped)
        if parsed_line is None:
            continue
        blocks.append(_build_text_block(parsed_line["kind"], parsed_line["text"]))

    if not blocks and (content or "").strip():
        blocks.append(_build_text_block("text", content.strip()))

    return blocks


def _chunk_blocks(blocks: list[Block], size: int):
    for index in range(0, len(blocks), size):
        yield blocks[index:index + size]


def _parse_line_kind(line: str):
    if line.startswith("### "):
        return {"kind": "heading3", "text": line[4:].strip()}
    if line.startswith("## "):
        return {"kind": "heading2", "text": line[3:].strip()}
    if line.startswith("# "):
        return {"kind": "heading1", "text": line[2:].strip()}
    if re.match(r"^[-*•]\s+", line):
        return {"kind": "bullet", "text": re.sub(r"^[-*•]\s+", "", line, count=1).strip()}
    if re.match(r"^\d+[.)]\s+", line):
        return {"kind": "ordered", "text": re.sub(r"^\d+[.)]\s+", "", line, count=1).strip()}
    if (line.endswith("：") or line.endswith(":")) and len(line) <= 24:
        return {"kind": "heading2", "text": line[:-1].strip()}
    return {"kind": "text", "text": line}


def _build_text_block(kind: str, content: str) -> Block:
    text = (
        Text.builder()
        .elements([
            TextElement.builder()
            .text_run(TextRun.builder().content(content).build())
            .build()
        ])
        .build()
    )

    builder = Block.builder()
    if kind == "heading1":
        return builder.block_type(BLOCK_TYPE_HEADING_1).heading1(text).build()
    if kind == "heading2":
        return builder.block_type(BLOCK_TYPE_HEADING_2).heading2(text).build()
    if kind == "heading3":
        return builder.block_type(BLOCK_TYPE_HEADING_3).heading3(text).build()
    if kind == "bullet":
        return builder.block_type(BLOCK_TYPE_BULLET).bullet(text).build()
    if kind == "ordered":
        return builder.block_type(BLOCK_TYPE_ORDERED).ordered(text).build()
    return builder.block_type(BLOCK_TYPE_TEXT).text(text).build()
