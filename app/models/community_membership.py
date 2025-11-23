from sqlalchemy import Column, String, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum as PyEnum

from app.core.database import Base
from app.models.mixins import UUIDMixin, TimestampMixin

class MembershipRole(PyEnum):
    MEMBER = "member"
    MODERATOR = "moderator"
    ADMIN = "admin"


class CommuntiyMembership(Base):
    __tablename__ = "community_memberships"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    community_id: Mapped[UUID] = mapped_column(
        ForeignKey("communities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role: Mapped[MembershipRole] = mapped_column(
        Enum(MembershipRole, name="membership_role"),
        nullable=False,
        default=MembershipRole.MEMBER,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # relationships
    user = relationship("User", back_populates="community_memberships")
    community = relationship("Community", back_populates="memberships")

    def __repr__(self):
        return f"<CommunityMembership(user_id={self.user_id}, community_id={self.community_id}, role={self.role})>"