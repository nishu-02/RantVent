# app/schemas/comment.py
from datetime import datetime
from uuid import UUID
from typing import Optional

from pydantic import BaseModel
from app.models.comment import CommentStatusEnum, CommentSentimentEnum


class CommentCreate(BaseModel):
    """Schema for creating a comment"""
    post_id: UUID


class CommentOut(BaseModel):
    """Schema for comment output"""
    id: UUID
    post_id: UUID
    user_id: UUID
    status: CommentStatusEnum
    sentiment: Optional[CommentSentimentEnum] = None
    audio_available: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CommentFeedItem(BaseModel):
    """Schema for comment in feed/list views"""
    id: UUID
    sentiment: Optional[CommentSentimentEnum] = None
    status: CommentStatusEnum
    created_at: datetime
    
    class Config:
        from_attributes = True
