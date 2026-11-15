'''from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)

    title: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(50))
    color: Mapped[str | None] = mapped_column(String(50))
    material: Mapped[str | None] = mapped_column(String(100))

    description: Mapped[str | None] = mapped_column(Text)
    image_path: Mapped[str | None] = mapped_column(String(255))
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)

    location: Mapped[str] = mapped_column(String(200))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    author: Mapped[str] = mapped_column(String(50))

    # lost: 분실 신고 / found: 습득 신고
    report_type: Mapped[str] = mapped_column(String(10), default="found")

    # open: 처리 중 / resolved: 반환 또는 해결 완료
    status: Mapped[str] = mapped_column(String(10), default="open")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )'''