from typing import Literal

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import get_db
from models import Item
from schemas import ItemCreate, ItemRead, ItemStatusUpdate
from services.gemini import analyze_image
from services.images import read_image, save_image, validate_image_path
from services.ownership import OwnerToken, item_response, require_owner, token_hash


router = APIRouter(prefix="/api/items", tags=["items"])


@router.get("", response_model=list[ItemRead])
def list_items(
    keyword: str | None = Query(default=None, max_length=100),
    location: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, max_length=50),
    color: str | None = Query(default=None, max_length=50),
    report_type: Literal["lost", "found"] | None = None,
    status: Literal["open", "resolved"] | None = None,
    mine: bool = False,
    owner_token: OwnerToken = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = select(Item)
    if mine:
        if not owner_token:
            raise HTTPException(401, "내 등록을 조회하려면 브라우저 식별 정보가 필요합니다.")
        query = query.where(Item.owner_token_hash == token_hash(owner_token))

    if keyword and keyword.strip():
        value = keyword.strip()
        keywords = func.json_each(Item.keywords).table_valued("key", "value")
        query = query.where(
            or_(
                Item.title.contains(value, autoescape=True),
                Item.category.contains(value, autoescape=True),
                Item.color.contains(value, autoescape=True),
                Item.material.contains(value, autoescape=True),
                Item.description.contains(value, autoescape=True),
                Item.location.contains(value, autoescape=True),
                # SQLite json_each decodes Unicode keywords before matching.
                select(1).select_from(keywords).where(
                    keywords.c.value.contains(value, autoescape=True)
                ).exists(),
            )
        )

    if location and location.strip():
        query = query.where(
            Item.location.contains(location.strip(), autoescape=True)
        )

    for column, value in ((Item.category, category), (Item.color, color)):
        if value and value.strip():
            query = query.where(column == value.strip())
    if report_type is not None:
        query = query.where(Item.report_type == report_type)
    if status is not None:
        query = query.where(Item.status == status)

    query = (
        query.order_by(Item.created_at.desc(), Item.id.desc())
        .offset(offset)
        .limit(limit)
    )

    return [item_response(item, owner_token) for item in db.scalars(query).all()]


@router.post("/report", response_model=ItemRead, status_code=201)
def report_item(
    request: Request,
    file: UploadFile = File(...),
    location: str = Form(..., min_length=1, max_length=200),
    contact: str = Form(..., min_length=1, max_length=200),
    author: str = Form(..., min_length=1, max_length=50),
    report_type: Literal["lost", "found"] = Form("found"),
    title: str | None = Form(None, min_length=1, max_length=100),
    category: str | None = Form(None, min_length=1, max_length=50),
    description: str | None = Form(None, max_length=3000),
    latitude: float | None = Form(None, ge=-90, le=90),
    longitude: float | None = Form(None, ge=-180, le=180),
    event_date: date | None = Form(None),
    owner_token: OwnerToken = None,
    db: Session = Depends(get_db),
):
    if request.app.state.production and not owner_token:
        raise HTTPException(401, "등록하려면 브라우저 식별 정보가 필요합니다.")
    # Validate whitespace and coordinate pairs before sending a paid AI request.
    try:
        fields = ItemCreate(
            title=title if title is not None else "분실물",
            category=category if category is not None else "기타",
            description=description, location=location, contact=contact,
            author=author, report_type=report_type, latitude=latitude, longitude=longitude,
            event_date=event_date,
        )
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_context=False)) from exc

    data, extension, mime_type = read_image(file)
    analysis = analyze_image(data, mime_type)
    payload = fields.model_dump()
    payload.update(analysis.model_dump())
    # Explicit user input takes precedence over AI-generated suggestions.
    for name, value in (("title", title), ("category", category), ("description", description)):
        if value is not None:
            payload[name] = value.strip()
    image_path, saved_path = save_image(data, extension, request.app.state.upload_dir)
    payload["image_path"] = image_path
    item = Item(**payload, owner_token_hash=token_hash(owner_token))
    db.add(item)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        saved_path.unlink(missing_ok=True)
        raise
    return item_response(item, owner_token)


@router.get("/{item_id}", response_model=ItemRead)
def get_item(item_id: int, owner_token: OwnerToken = None, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)

    if item is None:
        raise HTTPException(status_code=404, detail="물품을 찾을 수 없습니다.")

    return item_response(item, owner_token)


@router.post("", response_model=ItemRead, status_code=201)
def create_item(data: ItemCreate, request: Request, owner_token: OwnerToken = None, db: Session = Depends(get_db)):
    if request.app.state.production and not owner_token:
        raise HTTPException(401, "등록하려면 브라우저 식별 정보가 필요합니다.")
    validate_image_path(data.image_path, request.app.state.upload_dir)
    item = Item(**data.model_dump(), owner_token_hash=token_hash(owner_token))

    db.add(item)
    db.commit()
    db.refresh(item)

    return item_response(item, owner_token)


@router.put("/{item_id}", response_model=ItemRead)
def update_item(
    item_id: int,
    data: ItemCreate,
    request: Request,
    owner_token: OwnerToken = None,
    db: Session = Depends(get_db),
):
    item = db.get(Item, item_id)

    if item is None:
        raise HTTPException(status_code=404, detail="물품을 찾을 수 없습니다.")

    if item.owner_token_hash or request.app.state.production:
        require_owner(item, owner_token)
    validate_image_path(data.image_path, request.app.state.upload_dir)
    for name, value in data.model_dump().items():
        setattr(item, name, value)

    db.commit()
    db.refresh(item)

    return item_response(item, owner_token)


@router.patch("/{item_id}/status", response_model=ItemRead)
def update_status(
    item_id: int,
    data: ItemStatusUpdate,
    owner_token: OwnerToken = None,
    db: Session = Depends(get_db),
):
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "물품을 찾을 수 없습니다.")
    require_owner(item, owner_token)
    # Change only status so a concurrent content edit is not overwritten.
    item.status = data.status
    db.commit()
    db.refresh(item)
    return item_response(item, owner_token)


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, owner_token: OwnerToken = None, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "물품을 찾을 수 없습니다.")
    require_owner(item, owner_token)
    # Uploaded images can be shared by multiple reports; retain the original file.
    db.delete(item)
    db.commit()
    return Response(status_code=204)
