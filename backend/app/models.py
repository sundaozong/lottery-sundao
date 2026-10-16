from datetime import datetime
from sqlalchemy import String, Integer, Float, Text, DateTime, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class Draw(Base):
    __tablename__ = "draws"
    __table_args__ = (UniqueConstraint("lottery_type", "issue", name="uq_type_issue"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lottery_type: Mapped[str] = mapped_column(String(16), index=True)
    issue: Mapped[str] = mapped_column(String(32), index=True)
    numbers: Mapped[str] = mapped_column(Text)  # JSON list or "red|blue" style
    draw_date: Mapped[str] = mapped_column(String(32), default="")
    source: Mapped[str] = mapped_column(String(32), default="seed")  # seed | crawl
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PurchaseRecord(Base):
    __tablename__ = "purchase_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lottery_type: Mapped[str] = mapped_column(String(16), index=True)
    issue: Mapped[str] = mapped_column(String(32), default="")
    numbers: Mapped[str] = mapped_column(Text)
    cost: Mapped[float] = mapped_column(Float, default=2.0)
    prize: Mapped[float] = mapped_column(Float, default=0.0)
    note: Mapped[str] = mapped_column(Text, default="")
    purchased_at: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
