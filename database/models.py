from datetime import datetime, timezone
from sqlalchemy import Integer, String, DateTime, Text, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class OutageHistory(Base):
    __tablename__ = "outage_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    recovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    incoming: Mapped[float] = mapped_column(Float, default=0)
    outgoing: Mapped[float] = mapped_column(Float, default=0)

    total_users: Mapped[int] = mapped_column(Integer, default=0)
    active_users: Mapped[int] = mapped_column(Integer, default=0)
    online_users: Mapped[int] = mapped_column(Integer, default=0)
    expired_users: Mapped[int] = mapped_column(Integer, default=0)

    cpu: Mapped[float] = mapped_column(Float, default=0)
    memory_used: Mapped[float] = mapped_column(Float, default=0)
    memory_total: Mapped[float] = mapped_column(Float, default=0)

    nodes_json: Mapped[str] = mapped_column(Text, default="[]")
