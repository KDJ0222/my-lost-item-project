from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from database import Base


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(80), nullable=False)
    kind = Column(String(10), nullable=False)
    building = Column(String(30), nullable=False)
    place = Column(String(120), nullable=False)
    date = Column(String(10), nullable=False)
    keywords = Column(String(160), default="")
    description = Column(Text, default="")
    image = Column(String(255), default="")
    owner = Column(String(50), default="")
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.now)