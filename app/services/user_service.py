from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from typing import Optional, List
from datetime import datetime

from app.models.user import User, UserRole
from app.models.post import Post
from app.models.comment import Comment
from app.schemas.user import UserCreate, UserProfileUpdate, PasswordChangeRequest
from app.core.token import hash_password, verify_password
from app.core.logger import logger


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_id(self, user_id: str) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username (case insensitive)"""
        stmt = select(User).where(User.username.ilike(username))
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def user_exists(self, email: str) -> bool:
        """Check if user exists by email"""
        return (await self.get_user_by_email(email)) is not None

    async def username_exists(self, username: str, exclude_user_id: str = None) -> bool:
        """Check if username exists, optionally excluding a specific user"""
        stmt = select(User).where(User.username.ilike(username))
        if exclude_user_id:
            stmt = stmt.where(User.id != exclude_user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first() is not None

    async def create_user(self, data: UserCreate) -> User:
        """Create a new user"""
        # Check if username already exists
        if await self.username_exists(data.username):
            logger.warning("user_registration_failed_username_exists", username=data.username)
            raise ValueError("Username already exists")
            
        # Check if email already exists
        if await self.user_exists(data.email):
            logger.warning("user_registration_failed_email_exists", email=data.email)
            raise ValueError("Email already exists")
            
        user = User(
            username=data.username,
            email=data.email,
            about=data.about,
            role=UserRole.USER,
            password_hash=hash_password(data.password),
        )

        self.db.add(user)
        try:
            await self.db.commit()
            await self.db.refresh(user)
            logger.info("user_created", user_id=str(user.id), username=user.username, email=user.email)
        except IntegrityError:
            await self.db.rollback()
            logger.error("user_creation_failed_integrity", email=data.email, username=data.username)
            raise ValueError("Email or username already exists")

        return user

    async def update_user_profile(self, user: User, data: UserProfileUpdate) -> User:
        """Update user profile with validation"""
        update_data = data.dict(exclude_unset=True)
        
        # Check username uniqueness if being updated
        if 'username' in update_data:
            if await self.username_exists(update_data['username'], str(user.id)):
                raise ValueError("Username already exists")

        # Update fields
        for field, value in update_data.items():
            if hasattr(user, field):
                setattr(user, field, value)

        try:
            await self.db.commit()
            await self.db.refresh(user)
        except IntegrityError:
            await self.db.rollback()
            raise ValueError("Username already exists")

        return user

    async def change_password(self, user: User, data: PasswordChangeRequest) -> bool:
        """Change user password with current password verification"""
        if not verify_password(data.current_password, user.password_hash):
            logger.warning("password_change_failed_incorrect_current", user_id=str(user.id))
            raise ValueError("Current password is incorrect")
        
        user.password_hash = hash_password(data.new_password)
        
        try:
            await self.db.commit()
            await self.db.refresh(user)
            logger.info("password_changed", user_id=str(user.id))
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error("password_change_failed", user_id=str(user.id), error=str(e), exc_info=True)
            raise ValueError("Failed to update password")

    async def get_user_stats(self, user_id: str) -> dict:
        """Get comprehensive user statistics"""
        # Get post count
        post_count_stmt = select(func.count(Post.id)).where(Post.user_id == user_id)
        post_count_result = await self.db.execute(post_count_stmt)
        post_count = post_count_result.scalar() or 0

        # Get comment count  
        comment_count_stmt = select(func.count(Comment.id)).where(Comment.user_id == user_id)
        comment_count_result = await self.db.execute(comment_count_stmt)
        comment_count = comment_count_result.scalar() or 0

        # Get user join date
        user = await self.get_by_id(user_id)
        join_date = user.created_at if user else None

        # Get last post date as last_active (you can enhance this with actual activity tracking)
        last_post_stmt = (
            select(Post.created_at)
            .where(Post.user_id == user_id)
            .order_by(desc(Post.created_at))
            .limit(1)
        )
        last_post_result = await self.db.execute(last_post_stmt)
        last_active = last_post_result.scalar()

        return {
            "post_count": post_count,
            "comment_count": comment_count,
            "join_date": join_date,
            "last_active": last_active
        }

    async def get_public_profile(self, user_id: str) -> Optional[dict]:
        """Get public profile with stats"""
        user = await self.get_by_id(user_id)
        if not user:
            return None
            
        stats = await self.get_user_stats(user_id)
        
        return {
            "id": str(user.id),
            "username": user.username,
            "about": user.about,
            "created_at": user.created_at,
            "post_count": stats["post_count"],
            "comment_count": stats["comment_count"]
        }

    async def search_users(self, query: str, limit: int = 20) -> List[User]:
        """Search users by username or partial match"""
        stmt = (
            select(User)
            .where(
                or_(
                    User.username.ilike(f"%{query}%"),
                    User.username.ilike(f"{query}%")  # Prioritize starts-with matches
                )
            )
            .order_by(
                # Order by exact match first, then starts-with, then contains
                User.username.ilike(f"{query}").desc(),
                User.username.ilike(f"{query}%").desc(),
                User.username
            )
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_users(self, limit: int = 10) -> List[User]:
        """Get recently joined users"""
        stmt = (
            select(User)
            .order_by(desc(User.created_at))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_active_users(self, limit: int = 10) -> List[User]:
        """Get most active users (by post count)"""
        stmt = (
            select(User, func.count(Post.id).label('post_count'))
            .outerjoin(Post)
            .group_by(User.id)
            .order_by(desc('post_count'))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]

    async def delete_user(self, user_id: str) -> bool:
        """Soft delete user (you might want to implement proper soft delete)"""
        user = await self.get_by_id(user_id)
        if not user:
            return False
            
        # For now, we'll actually delete. In production, you might want soft delete
        await self.db.delete(user)
        await self.db.commit()
        return True

    async def verify_user_email(self, user_id: str) -> bool:
        """Mark user email as verified"""
        user = await self.get_by_id(user_id)
        if not user:
            return False
            
        user.is_verified = True
        await self.db.commit()
        await self.db.refresh(user)
        return True