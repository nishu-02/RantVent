from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.post import Post
from app.schemas.post import PostOut, PostFeedItem
from app.services.post_service import PostService
from app.utils.storage import save_upload_to_disk
from app.workers.tasks import process_post_audio

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("", response_model=PostOut, status_code=status.HTTP_201_CREATED)
async def create_post(
    anonymize_mode: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
    # current_user: User = Depends(get_current_user),
):
    if not (0 <= anonymize_mode <= 6):
        raise HTTPException(400, "Invalid anonymize mode")

    raw_path = await save_upload_to_disk(file)

    # Create a temporary User object for testing (without auth)
    from sqlalchemy import select
    service = PostService(db)
    stmt = select(User).limit(1)
    result = await db.execute(stmt)
    current_user = result.scalars().first()
    
    if not current_user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No users available. Please create a user first.")
    
    post = await service.create_post(
        user=current_user,
        audio_path=raw_path,
    )

    import asyncio
    asyncio.create_task(
        process_post_audio(post.id, anonymize_mode)
    )

    return PostOut(
        id=post.id,
        user_id=post.user_id,
        status=post.status.value,
        tldr=post.tldr,
        summary=post.summary,
        transcript=post.transcript,
        language=post.language,
        created_at=post.created_at,
        audio_available=post.audio_path is not None,
    )


@router.get("/{post_id}", response_model=PostOut)
async def get_post(
    post_id: UUID,
    db: AsyncSession = Depends(get_session),
):
    service = PostService(db)
    post = await service.get_post(post_id)

    if not post:
        raise HTTPException(404, "Post not found")

    return PostOut(
        id=post.id,
        user_id=post.user_id,
        status=post.status.value,
        tldr=post.tldr,
        summary=post.summary,
        transcript=post.transcript,
        language=post.language,
        created_at=post.created_at,
        audio_available=post.audio_path is not None,
    )


@router.get("", response_model=list[PostFeedItem])
async def list_posts(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_session),
):
    service = PostService(db)
    posts = await service.list_posts(limit=limit, offset=offset)

    return [
        PostFeedItem(
            id=p.id,
            tldr=p.tldr,
            status=p.status.value,
            created_at=p.created_at,
        )
        for p in posts
    ]


@router.get("/{post_id}/audio")
async def get_post_audio(
    post_id: UUID,
    db: AsyncSession = Depends(get_session),
):
    service = PostService(db)
    post = await service.get_post(post_id)

    if not post or not post.audio_path:
        raise HTTPException(404, "Audio not found")

    # check expiry
    if post.audio_expires_at and post.audio_expires_at < datetime.now(timezone.utc):
        raise HTTPException(410, "Audio expired")

    return FileResponse(post.audio_path, media_type="audio/wav")
