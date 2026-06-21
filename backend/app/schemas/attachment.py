"""附件 DTO — 不含 uploaded_by_user_id 等内部标识。"""
from __future__ import annotations

from pydantic import BaseModel


class AttachmentPublic(BaseModel):
    """对外附件信息(不含上传者等内部字段)。"""
    id: int
    original_filename: str
    content_type: str
    size_bytes: int
    download_url: str
    thumbnail_url: str | None = None
