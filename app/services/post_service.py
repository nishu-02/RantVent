from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.post import Post, PostStatus
from app.models.user import User
from app.core.logger import logger

class PostService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_post(
        self,
        user: User,
        audio_path: str,
        audio_duration_sec: Optional[int] = None,
        community_id: Optional[UUID] = None,
    ) -> Post:

        now = datetime.utcnow()
        post = Post(
            user_id=user.id,
            community_id=community_id,
            audio_path=audio_path,
            audio_duration_sec=audio_duration_sec,
            status=PostStatus.PROCESSING,
            audio_expires_at=now + timedelta(days=settings.AUDIO_RETENTION_DAYS)
        )

        self.db.add(post)
        await self.db.commit()
        await self.db.refresh(post)
        logger.info("post_created", post_id=str(post.id), user_id=str(user.id), community_id=str(community_id) if community_id else None, duration_sec=audio_duration_sec)
        
        return post

    async def get_post(self, post_id: UUID) -> Post | None:
        stmt = select(Post).where(Post.id == post_id)
        result = await self.db.execute(stmt)

        return result.scalars().first()

    async def list_posts(self, limit: int = 20, offset: int = 0, community_id: Optional[UUID] = None) -> List[Post]:
        stmt = select(Post)
        
        if community_id:
            stmt = stmt.where(Post.community_id == community_id)
        
        stmt = (
            stmt.order_by(Post.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def list_posts_by_communities(self, community_ids: List[UUID], limit: int = 20, offset: int = 0) -> List[Post]:
        """Get posts from multiple communities (for user feed)"""
        if not community_ids:
            return []
            
        stmt = (
            select(Post)
            .where(Post.community_id.in_(community_ids))
            .order_by(Post.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def get_general_posts(self, limit: int = 20, offset: int = 0) -> List[Post]:
        """Get posts not assigned to any community (general posts)"""
        stmt = (
            select(Post)
            .where(Post.community_id.is_(None))
            .order_by(Post.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_transcription(
        self,
        post: Post,
        transcript: str,
        summary: str,
        tldr: str,
        language: str,
    ) -> Post:

        post.transcript = transcript
        post.summary = summary
        post.tldr = tldr
        post.language = language
        post.status = PostStatus.READY

        await self.db.commit()
        await self.db.refresh(post)
        logger.info("post_transcription_updated", post_id=str(post.id), language=language, status="READY")

        return post
    
    async def mark_failed(self, post: Post) -> Post:
        post.status = PostStatus.FAILED
        await self.db.commit()
        logger.error("post_marked_failed", post_id=str(post.id), status="FAILED")
        return post
        
    async def update_community_post_count(self, community_id: UUID, increment: bool = True) -> None:
        """Update post count for a community"""
        from app.models.community import Community
        
        stmt = select(Community).where(Community.id == community_id)
        result = await self.db.execute(stmt)
        community = result.scalars().first()
        
        if community:
            if increment:
                community.post_count += 1
            else:
                community.post_count = max(0, community.post_count - 1)
            await self.db.commit()