from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    Enum as SqlEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

class PostStatus(str, enum.Enum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"

class Post(Base):
    __tablename__ = "posts"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    audio_path: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    audio_duration_sec: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    status: Mapped[PostStatus] = mapped_column(
        SqlEnum(PostStatus, name="post_status"),
        nullable=False,
        default=PostStatus.PROCESSING,
    )

    transcript: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    tldr: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    language: Mapped[Optional[str]] = mapped_column(
        String(16),
        nullable=True,
    )

    audio_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # relationships
    user: Mapped["User"] = relationship(back_populates="posts")