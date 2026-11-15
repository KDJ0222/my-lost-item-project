'''from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ItemCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=50)
    color: str | None = Field(default=None, max_length=50)
    material: str | None = Field(default=None, max_length=100)

    description: str | None = Field(default=None, max_length=3000)
    image_path: str | None = Field(default=None, max_length=255)
    keywords: list[str] = Field(default_factory=list, max_length=20)

    location: str = Field(min_length=1, max_length=200)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    author: str = Field(min_length=1, max_length=50)
    report_type: Literal["lost", "found"] = "found"
    status: Literal["open", "resolved"] = "open"


class ItemRead(ItemCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class ImageUploadResponse(BaseModel):
    image_path: str'''