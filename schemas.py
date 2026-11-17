from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    kind: str
    building: str
    place: str
    date: str
    keywords: str
    description: str
    image: str
    owner: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    created_at: datetime