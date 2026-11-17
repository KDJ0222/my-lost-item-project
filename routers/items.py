import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db

router = APIRouter(prefix="/items", tags=["items"])

UPLOAD_DIR = Path("static/uploads")
ALLOWED_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_SIZE = 5 * 1024 * 1024
KINDS = {"발견", "분실"}


@router.get("", response_model=list[schemas.ItemOut])
def list_items(
    q: str = "",
    building: str = "",
    kind: str = "",
    db: Session = Depends(get_db),
):
    query = db.query(models.Item)
    if q.strip():
        word = f"%{q.strip()}%"
        query = query.filter(
            or_(
                models.Item.title.like(word),
                models.Item.keywords.like(word),
                models.Item.place.like(word),
                models.Item.description.like(word),
            )
        )
    if building and building != "전체":
        query = query.filter(models.Item.building == building)
    if kind and kind != "전체":
        query = query.filter(models.Item.kind == kind)
    return query.order_by(models.Item.created_at.desc()).all()


@router.get("/{item_id}", response_model=schemas.ItemOut)
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(models.Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="물품을 찾을 수 없습니다")
    return item


@router.post("", response_model=schemas.ItemOut, status_code=201)
async def create_item(
    title: str = Form(...),
    kind: str = Form("발견"),
    building: str = Form(...),
    place: str = Form(...),
    date: str = Form(...),
    keywords: str = Form(""),
    description: str = Form(""),
    owner: str = Form(""),
    lat: Optional[float] = Form(None),
    lng: Optional[float] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    if kind not in KINDS:
        raise HTTPException(status_code=400, detail="kind는 발견 또는 분실이어야 합니다")
    if not title.strip() or not place.strip():
        raise HTTPException(status_code=400, detail="물품 이름과 상세 위치를 입력해 주세요")

    image_url = ""
    if file and file.filename:
        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail="JPG, PNG, WEBP 사진만 올릴 수 있습니다")
        data = await file.read()
        if len(data) > MAX_SIZE:
            raise HTTPException(status_code=400, detail="사진은 5MB 이하만 올릴 수 있습니다")
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        name = uuid.uuid4().hex + ALLOWED_TYPES[file.content_type]
        (UPLOAD_DIR / name).write_bytes(data)
        image_url = f"/static/uploads/{name}"

    item = models.Item(
        title=title.strip(),
        kind=kind,
        building=building,
        place=place.strip(),
        date=date,
        keywords=keywords.strip(),
        description=description.strip(),
        image=image_url,
        owner=owner,
        lat=lat,
        lng=lng,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(models.Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="물품을 찾을 수 없습니다")
    if item.image:
        Path(item.image.lstrip("/")).unlink(missing_ok=True)
    db.delete(item)
    db.commit()