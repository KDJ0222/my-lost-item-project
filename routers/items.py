'''from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from database import get_db
from models import Item
from schemas import ItemCreate, ItemRead


router = APIRouter(prefix="/api/items", tags=["items"])


@router.get("", response_model=list[ItemRead])
def list_items(
    keyword: str | None = Query(default=None, max_length=100),
    location: str | None = Query(default=None, max_length=200),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = select(Item)

    if keyword and keyword.strip():
        value = keyword.strip()
        query = query.where(
            or_(
                Item.title.contains(value, autoescape=True),
                Item.category.contains(value, autoescape=True),
                Item.color.contains(value, autoescape=True),
                Item.material.contains(value, autoescape=True),
                Item.description.contains(value, autoescape=True),
                Item.keywords.cast(String).contains(value, autoescape=True),
            )
        )

    if location and location.strip():
        query = query.where(
            Item.location.contains(location.strip(), autoescape=True)
        )

    query = (
        query.order_by(Item.created_at.desc(), Item.id.desc())
        .offset(offset)
        .limit(limit)
    )

    return db.scalars(query).all()


@router.get("/{item_id}", response_model=ItemRead)
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)

    if item is None:
        raise HTTPException(status_code=404, detail="물품을 찾을 수 없습니다.")

    return item


@router.post("", response_model=ItemRead, status_code=201)
def create_item(data: ItemCreate, db: Session = Depends(get_db)):
    item = Item(**data.model_dump())

    db.add(item)
    db.commit()
    db.refresh(item)

    return item


@router.put("/{item_id}", response_model=ItemRead)
def update_item(
    item_id: int,
    data: ItemCreate,
    db: Session = Depends(get_db),
):
    item = db.get(Item, item_id)

    if item is None:
        raise HTTPException(status_code=404, detail="물품을 찾을 수 없습니다.")

    for name, value in data.model_dump().items():
        setattr(item, name, value)

    db.commit()
    db.refresh(item)

    return item'''