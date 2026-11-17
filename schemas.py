from datetime import date, datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Keyword = Annotated[str, Field(min_length=1, max_length=50)]


class ImageAnalysis(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=50)
    color: str | None = Field(default=None, max_length=50)
    material: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=3000)
    keywords: list[Keyword] = Field(min_length=1, max_length=20)

    @field_validator("keywords")
    @classmethod
    def unique_keywords(cls, value):
        return list(dict.fromkeys(value))


class ItemCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False)

    title: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=50)
    color: str | None = Field(default=None, max_length=50)
    material: str | None = Field(default=None, max_length=100)

    description: str | None = Field(default=None, max_length=3000)
    image_path: str | None = Field(default=None, max_length=255)
    keywords: list[Keyword] = Field(default_factory=list, max_length=20)

    location: str = Field(min_length=1, max_length=200)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    author: str = Field(min_length=1, max_length=50)
    contact: str | None = Field(default=None, min_length=1, max_length=200)
    event_date: date | None = None
    report_type: Literal["lost", "found"] = "found"
    status: Literal["open", "resolved"] = "open"

    @field_validator("keywords")
    @classmethod
    def unique_keywords(cls, value):
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def paired_coordinates(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("위도와 경도는 함께 입력해야 합니다.")
        return self


class ItemRead(ItemCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    is_mine: bool = False

    @field_validator("created_at")
    @classmethod
    def utc_created_at(cls, value):
        # SQLite drops timezone metadata even with DateTime(timezone=True).
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class ImageUploadResponse(BaseModel):
    image_path: str


class ImageAnalysisResponse(ImageAnalysis):
    image_path: str
