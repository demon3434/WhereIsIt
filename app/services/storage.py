import os
import uuid
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image

from ..config import settings

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MAX_UPLOAD_IMAGE_BYTES = 900 * 1024
SPEC_MAX_LONG_EDGE = 1600
SPEC_JPEG_QUALITY = 82
MIN_JPEG_QUALITY = 56
MIN_LONG_EDGE = 720
QUALITY_STEP = 8
SCALE_STEP = 0.85


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
    image = Image.open(BytesIO(raw))
    image.load()

    if image.mode in ("RGBA", "LA") or ("transparency" in image.info):
        rgba = image.convert("RGBA")
        white_bg = Image.new("RGB", image.size, (255, 255, 255))
        white_bg.paste(rgba, mask=rgba.split()[-1])
        image = white_bg
    elif image.mode != "RGB":
        image = image.convert("RGB")

    width, height = image.size
    long_edge = max(width, height)
    if long_edge > SPEC_MAX_LONG_EDGE:
        ratio = SPEC_MAX_LONG_EDGE / long_edge
        image = image.resize((max(1, int(width * ratio)), max(1, int(height * ratio))), Image.Resampling.LANCZOS)

    current = image
    quality = SPEC_JPEG_QUALITY
    result = b""

    # Always execute compression flow even when source dimensions are already under limits.
    while True:
        buffer = BytesIO()
        current.save(buffer, format="JPEG", optimize=True, quality=quality)
        result = buffer.getvalue()
        if len(result) <= MAX_UPLOAD_IMAGE_BYTES:
            return result

        if quality > MIN_JPEG_QUALITY:
            quality = max(MIN_JPEG_QUALITY, quality - QUALITY_STEP)
            continue

        current_long_edge = max(current.size)
        if current_long_edge <= MIN_LONG_EDGE:
            break

        next_long_edge = max(MIN_LONG_EDGE, int(current_long_edge * SCALE_STEP))
        if next_long_edge >= current_long_edge:
            break

        resize_ratio = next_long_edge / current_long_edge
        current = current.resize(
            (
                max(1, int(current.size[0] * resize_ratio)),
                max(1, int(current.size[1] * resize_ratio)),
            ),
            Image.Resampling.LANCZOS,
        )
        quality = SPEC_JPEG_QUALITY

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="图片压缩后仍超过 900KB，请更换图片")
