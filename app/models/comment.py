import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Text, func, Enum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.user import User
from app.models.post import Post

from enum import Enum as PyEnum

class CommentStatusEnum(PyEnum):
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"

class CommentSentimentEnum(PyEnum):
    IN_FAVOR = "IN_FAVOR"
    AGAINST = "AGAINST"

class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    post_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    anonymized_audio_path: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[CommentStatusEnum] = mapped_column(
        Enum(CommentStatusEnum, name="comment_status"),
        nullable=False,
        default=CommentStatusEnum.PROCESSING,
    )

    # sentiment relative to post: IN_FAVOR / AGAINST / NEUTRAL
    sentiment: Mapped[Optional[CommentSentimentEnum]] = mapped_column(
        Enum(CommentSentimentEnum, name="comment_sentiment"),
        nullable=True,
    )

    post = relationship("Post", back_populates="comments")
    user = relationship("User", back_populates="comments")