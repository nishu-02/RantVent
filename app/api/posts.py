from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Query
from fastapi.responses import FileResponse
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

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
    anonymize_mode: int = Query(..., ge=0, le=6, description="Anonymization preset (0-6)"),
    community_id: Optional[UUID] = Query(None, description="Community to post in (optional)"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if not (0 <= anonymize_mode <= 6):
        raise HTTPException(400, "Invalid anonymize mode")

    # If community_id is provided, verify it exists and user is a member
    if community_id:
        from app.services.community_service import CommunityService
        community_service = CommunityService(db)
        
        community = await community_service.get_by_id(str(community_id))
        if not community:
            raise HTTPException(404, "Community not found")
        
        is_member = await community_service.is_member(str(community_id), str(current_user.id))
        if not is_member:
            raise HTTPException(403, "Must be a member of the community to post")

    raw_path = await save_upload_to_disk(file)

    service = PostService(db)
    post = await service.create_post(
        user=current_user,
        audio_path=raw_path,
        community_id=community_id,
    )

    import asyncio
    asyncio.create_task(
        process_post_audio(post.id, anonymize_mode)
    )
    
    # Update community post count if post is in a community
    if community_id:
        await service.update_community_post_count(community_id, increment=True)

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


@router.get("", response_model=List[PostFeedItem])
async def list_posts(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    community_id: Optional[UUID] = Query(None, description="Filter by community"),
    feed_type: str = Query("general", description="Feed type: general, communities, or all"),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    service = PostService(db)
    
    if community_id:
        # Get posts from specific community
        posts = await service.list_posts(limit, offset, community_id)
    elif feed_type == "communities":
        # Get posts from user's joined communities
        from app.services.community_service import CommunityService
        community_service = CommunityService(db)
        
        memberships = await community_service.get_user_communities(str(current_user.id))
        community_ids = [UUID(m.community_id) for m in memberships]
        
        posts = await service.list_posts_by_communities(community_ids, limit, offset)
    elif feed_type == "general":
        # Get posts not in any community (general feed)
        posts = await service.get_general_posts(limit, offset)
    else:
        # Get all posts (mixed feed)
        posts = await service.list_posts(limit, offset)

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
