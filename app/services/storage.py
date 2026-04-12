import os
import uuid
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image

from ..config import settings

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def ensure_upload_dir() -> None:
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)


def save_upload_file(file: UploadFile, user_id: int, item_id: int) -> tuple[str, str]:
    ensure_upload_dir()

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 JPG/PNG 图片")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="图片格式错误，仅支持 JPG/PNG")

    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(0)
    if size > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"单张图片不能超过 {settings.max_upload_mb}MB",
        )

    raw = file.file.read()
    compressed = compress_image(raw)
    filename = f"u{user_id}_i{item_id}_{uuid.uuid4().hex}.jpg"
    target = Path(settings.upload_dir) / filename
    with target.open("wb") as output:
        output.write(compressed)

    return filename, f"/uploads/{filename}"


def compress_image(raw: bytes) -> bytes:
    limit = 800 * 1024
    image = Image.open(BytesIO(raw))
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    if image.mode == "L":
        image = image.convert("RGB")
    for quality in [85, 75, 65, 55, 45, 35]:
        buffer = BytesIO()
        image.save(buffer, format="JPEG", optimize=True, quality=quality)
        data = buffer.getvalue()
        if len(data) <= limit:
            return data
    # Still too large, downscale progressively.
    work = image
    for _ in range(4):
        width, height = work.size
        work = work.resize((max(1, int(width * 0.8)), max(1, int(height * 0.8))))
        buffer = BytesIO()
        work.save(buffer, format="JPEG", optimize=True, quality=40)
        data = buffer.getvalue()
        if len(data) <= limit:
            return data
    return data
