'''from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from schemas import ImageUploadResponse


router = APIRouter(prefix="/api/images", tags=["images"])

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "static" / "uploads"
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB


def detect_extension(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"

    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"

    if (
        len(data) >= 12
        and data[:4] == b"RIFF"
        and data[8:12] == b"WEBP"
    ):
        return ".webp"

    raise HTTPException(
        status_code=415,
        detail="JPG, PNG, WEBP 이미지만 업로드할 수 있습니다.",
    )


@router.post("", response_model=ImageUploadResponse, status_code=201)
async def upload_image(file: UploadFile = File(...)):
    try:
        data = await file.read(MAX_IMAGE_SIZE + 1)
    finally:
        await file.close()

    if not data:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")

    if len(data) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="이미지는 최대 5MB까지 업로드할 수 있습니다.",
        )

    extension = detect_extension(data)
    filename = f"{uuid4().hex}{extension}"

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / filename).write_bytes(data)

    return ImageUploadResponse(
        image_path=f"/static/uploads/{filename}"
    )'''