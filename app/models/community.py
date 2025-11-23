from sqlalchemy import Column, String, Text, Boolean, DateTime, Integer, Enum
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from enum import Enum as PyEnum
from typing import List, Optional

from app.core.database import Base

class CommunityType(PyEnum):
    PUBLIC = "public"


class Community(Base):
    __tablename__ = "communities"

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    type: Mapped[CommunityType] = mapped_column(
        Enum(CommunityType, name="community_type"),
        default=CommunityType.PUBLIC,
        nullable=False,
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    
    member_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    post_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    # Relationships
    posts: Mapped[List["Post"]] = relationship(
        back_populates="community"
    )
    
    memberships: Mapped[List["CommunityMembership"]] = relationship(
        back_populates="community"
    )

    def __repr__(self):
        return f"<Community {self.name}>"