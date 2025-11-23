# app/api/comments.py
import asyncio
from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.comment import CommentSentimentEnum
from app.schemas.comment import CommentOut, CommentCreate, CommentFeedItem
from app.services.comment_service import CommentService
from app.utils.storage import save_upload_to_disk
from app.workers.tasks import process_comment_audio

router = APIRouter(prefix="/comments", tags=["comments"])


@router.post("", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
async def create_comment(
    post_id: UUID = Query(..., description="ID of the post to comment on"),
    anonymize_mode: int = Query(1, ge=0, le=6, description="Anonymization preset (0-6)"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new comment on a post"""
    
    if not (0 <= anonymize_mode <= 6):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid anonymize mode")
    
    # Save uploaded audio file
    original_audio_path = await save_upload_to_disk(file)
    
    # Create comment service and create comment
    service = CommentService(db)
    
    try:
        comment = await service.create_comment(
            user=current_user,
            post_id=post_id,
        )
        
        # Start background processing
        asyncio.create_task(
            process_comment_audio(comment.id, original_audio_path, anonymize_mode)
        )
        
        # Convert to response format
        comment_out = CommentOut(
            id=comment.id,
            post_id=comment.post_id,
            user_id=comment.user_id,
            status=comment.status,
            sentiment=comment.sentiment,
            audio_available=bool(comment.anonymized_audio_path),
            created_at=comment.created_at,
        )
        
        return comment_out
        
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.get("/post/{post_id}", response_model=List[CommentOut])
async def get_comments_for_post(
    post_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sentiment: Optional[CommentSentimentEnum] = Query(None),
    db: AsyncSession = Depends(get_session),
):
    """Get comments for a specific post, optionally filtered by sentiment"""
    
    service = CommentService(db)
    
    if sentiment:
        comments = await service.get_comments_by_sentiment(
            post_id=post_id,
            sentiment=sentiment,
            limit=limit,
            offset=offset
        )
    else:
        comments = await service.get_comments_for_post(
            post_id=post_id,
            limit=limit,
            offset=offset
        )
    
    # Convert to response format
    comment_outs = []
    for comment in comments:
        comment_out = CommentOut(
            id=comment.id,
            post_id=comment.post_id,
            user_id=comment.user_id,
            status=comment.status,
            sentiment=comment.sentiment,
            audio_available=bool(comment.anonymized_audio_path),
            created_at=comment.created_at,
        )
        comment_outs.append(comment_out)
    
    return comment_outs


@router.get("/{comment_id}", response_model=CommentOut)
async def get_comment(
    comment_id: UUID,
    db: AsyncSession = Depends(get_session),
):
    """Get a specific comment by ID"""
    
    service = CommentService(db)
    comment = await service.get_comment(comment_id)
    
    if not comment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")
    
    comment_out = CommentOut(
        id=comment.id,
        post_id=comment.post_id,
        user_id=comment.user_id,
        status=comment.status,
        sentiment=comment.sentiment,
        audio_available=bool(comment.anonymized_audio_path),
        created_at=comment.created_at,
    )
    
    return comment_out


@router.get("/{comment_id}/audio")
async def get_comment_audio(
    comment_id: UUID,
    db: AsyncSession = Depends(get_session),
):
    """Get the anonymized audio file for a comment"""
    
    service = CommentService(db)
    comment = await service.get_comment(comment_id)
    
    if not comment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")
    
    if not comment.anonymized_audio_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audio not available")
    
    return FileResponse(
        comment.anonymized_audio_path,
        media_type="audio/wav",
        filename=f"comment_{comment_id}_audio.wav"
    )