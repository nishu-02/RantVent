from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.post import Post, PostStatus
from app.models.user import User

class PostService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_post(
        self,
        user: User,
        audio_path: str,
        audio_duration_sec" Optional[int] = None,
    ) -> Post:

        now = datetime.utcnow()
        post = Post(
            user_id=user.id,
            audio_path=audio_path,
            audio_duration_sec=audio_duration_sec,
            status=PostStatus.PROCESSING,
            audio_expires_at=now + timedelta(days=settings.AUDIO_RETENTION_DAYS)
        )

        self.db.add(post)
        await self.db.commit()
        await self.db.refresh(post)
        
        return post

    async def get_post(self, post_id: UUID) -> Post | None:
        stmt = select(Post).where(Post.id== post.id)
        result = await self.db.execute(stmt)

        return results.scalars().first()

    async def list_post(self, limit: int = 20, offset: int = 0) -> List[Post]:
        stmt = (
            select(Post)
            .order_by(Post.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        resutl = await self.db.execute(stmt)
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
        post.status = PostStatus.COMPLETED

        await self.db.commit()
        await self.db.refresh(post)

        return post
    
    async def mark_failed(self, post: Post) -> Post:
        post.status = PostStatus.FAILED
        await self.db.commit()