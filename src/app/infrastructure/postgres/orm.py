from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.app.domain.models.task_state import TaskState
from src.app.domain.models.task_type import TaskType


class Base(DeclarativeBase):
    pass


class TaskRow(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    task_type: Mapped[TaskType] = mapped_column(
        Enum(TaskType, name="task_type"), nullable=False
    )

    payload: Mapped["TaskPayloadRow"] = relationship(
        back_populates="task", uselist=False, cascade="all, delete-orphan"
    )
    task_metadata: Mapped["TaskMetadataRow"] = relationship(
        back_populates="task", uselist=False, cascade="all, delete-orphan"
    )
    status: Mapped["TaskStatusRow"] = relationship(
        back_populates="task", uselist=False, cascade="all, delete-orphan"
    )
    result: Mapped["TaskResultRow"] = relationship(
        back_populates="task", uselist=False, cascade="all, delete-orphan"
    )


class TaskPayloadRow(Base):
    __tablename__ = "task_payloads"

    task_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    task: Mapped[TaskRow] = relationship(back_populates="payload")


class TaskMetadataRow(Base):
    __tablename__ = "task_metadata"

    task_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    custom: Mapped[dict | None] = mapped_column(JSON)

    task: Mapped[TaskRow] = relationship(back_populates="task_metadata")


class TaskStatusRow(Base):
    __tablename__ = "task_statuses"

    task_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    state: Mapped[TaskState] = mapped_column(
        Enum(TaskState, name="task_state"), nullable=False
    )
    progress_current: Mapped[int | None] = mapped_column(Integer)
    progress_total: Mapped[int | None] = mapped_column(Integer)
    progress_percentage: Mapped[float | None] = mapped_column(Float)
    progress_phase: Mapped[str | None] = mapped_column(String(128))
    message: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[dict | None] = mapped_column(JSON)

    task: Mapped[TaskRow] = relationship(back_populates="status")


class TaskResultRow(Base):
    __tablename__ = "task_results"

    task_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    data: Mapped[dict | None] = mapped_column(JSON)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ttl_seconds: Mapped[int | None] = mapped_column(Integer)

    task: Mapped[TaskRow] = relationship(back_populates="result")


class PostgresOrm:
    """
    SQLAlchemy async ORM holder. Create once and inject where needed.
    """

    def __init__(self, database_url: str, *, echo: bool = False) -> None:
        self._engine: AsyncEngine = create_async_engine(database_url, echo=echo)
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self._engine, expire_on_commit=False
        )

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory
