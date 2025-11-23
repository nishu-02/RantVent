from sqlalchemy import Column, String, Text, Boolean, DateTime, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum as PyEnum

from app.core.database import Base
from app.models.mixins import UUIDMixin, TimestampMixin

class CommunityType(PyEnum):
    PUBLIC = "public"


class Community(Base):
    __tablename__ = "communities"

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    type: Mapped[CommunityType] = mapped_column(
        Enum(CommunityType, name="community_type"),
        nullable=False,
        default=CommunityType.PUBLIC,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    members_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    post_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # relationships
    posts = relationship("Post", back_populates="community")
    memberships = relationship("CommunityMembership", back_populates="community")

    def __repr__(self):
        return f"<Community(id={self.id}, name={self.name}, display_name={self.display_name})>"