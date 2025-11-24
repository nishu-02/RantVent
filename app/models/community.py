from sqlalchemy import Column, String, Text, Boolean, DateTime, Integer, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from enum import Enum as PyEnum
from typing import List, Optional
from uuid import UUID

from app.core.database import Base

class CommunityType(PyEnum):
    PUBLIC = "PUBLIC"


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
    
    # Owner
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Category
    category_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("community_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Visual Customization
    avatar_url: Mapped[str] = mapped_column(
        String(500),
        nullable=True,
    )

    banner_url: Mapped[str] = mapped_column(
        String(500),
        nullable=True,
    )

    rules: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Settings
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
    
    # Statistics
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
    owner: Mapped["User"] = relationship(
        foreign_keys=[owner_id],
        back_populates="owned_communities"
    )
    
    category = relationship(
        "CommunityCategory",
        back_populates="communities"
    )

    posts: Mapped[List["Post"]] = relationship(
        back_populates="community"
    )
    
    memberships: Mapped[List["CommunityMembership"]] = relationship(
        back_populates="community"
    )

    def __repr__(self):
        return f"<Community {self.name}>"


class CommunityCategory(Base):
    __tablename__ = "community_categories"

    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True
    )

    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=True,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )
    
    icon: Mapped[str] = mapped_column(
        String(50),
        nullable=True
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True
    )

    # realtionships
    communities = relationship(
        "Community",
        back_populates="category"
    )

    def __repr__(self):
        return f"<CommunityCategory {self.name}>"


class CommunityPin(Base):
    __tablename__ = "community_pins"

    community_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("communities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    post_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    pinned_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # relationships
    community = relationship("Community")
    post = relationship("Post")
    pinner = relationship("User")

    def __repr__(self):
        return f"<CommunityPin(community_id={self.community_id}, post_id={self.post_id})>"