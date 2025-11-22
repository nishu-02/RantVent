from __future__ import annotations

import enum
from typing import List, Optional

from sqlalchemy import String, Boolean, Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"


class User(Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    about: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    role: Mapped[UserRole] = mapped_column(
        SqlEnum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.USER,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    # reverse relationships
    posts: Mapped[List["Post"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    comments: Mapped[List["Comment"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
