from io import BytesIO
from pathlib import Path
import re
from uuid import uuid4
import warnings

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError


MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
IMAGE_FORMATS = {"JPEG": (".jpg", "image/jpeg"), "PNG": (".png", "image/png"),
                 "WEBP": (".webp", "image/webp")}


def inspect_image(data: bytes) -> tuple[str, str]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format not in IMAGE_FORMATS:
                    raise HTTPException(415, "JPG, PNG, WEBP 이미지만 업로드할 수 있습니다.")
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise HTTPException(413, "이미지는 최대 2천만 화소까지 업로드할 수 있습니다.")
                result = IMAGE_FORMATS[image.format]
                image.verify()
            # Reject files with a valid header but truncated pixel data as well.
            with Image.open(BytesIO(data)) as image:
                image.load()
            return result
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise HTTPException(413, "이미지 해상도가 너무 큽니다.") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise HTTPException(415, "손상되었거나 지원하지 않는 이미지입니다.") from exc


def read_image(file: UploadFile) -> tuple[bytes, str, str]:
    try:
        data = file.file.read(MAX_IMAGE_SIZE + 1)
    finally:
        file.file.close()
    if not data:
        raise HTTPException(400, "빈 파일입니다.")
    if len(data) > MAX_IMAGE_SIZE:
        raise HTTPException(413, "이미지는 최대 5MB까지 업로드할 수 있습니다.")
    extension, mime_type = inspect_image(data)
    return data, extension, mime_type


def save_image(data: bytes, extension: str, upload_dir: Path) -> tuple[str, Path]:
    upload_dir.mkdir(parents=True, exist_ok=True)
    path = upload_dir / f"{uuid4().hex}{extension}"
    try:
        path.write_bytes(data)
    except OSError:
        path.unlink(missing_ok=True)
        raise
    return f"/static/uploads/{path.name}", path


def validate_image_path(image_path: str | None, upload_dir: Path):
    if image_path is None:
        return
    if not re.fullmatch(r"/static/uploads/[0-9a-f]{32}\.(jpg|png|webp)", image_path):
        raise HTTPException(422, "이미지 업로드 API가 반환한 image_path를 사용해 주세요.")
    if not (upload_dir / image_path.rsplit("/", 1)[-1]).is_file():
        raise HTTPException(422, "업로드된 이미지를 찾을 수 없습니다.")
