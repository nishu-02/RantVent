import os
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment import Comment, CommentStatusEnum, CommentSentimentEnum
from app.models.post import Post
from app.models.user import User
from app.core.config import settings
from app.services.voice_anonymizer import voice_anonymizer
from app.services.gemini_service import gemini_service


class CommentGeminiService:
    """Separate Gemini service for comment sentiment analysis"""
    
    def __init__(self):
        self.gemini = gemini_service
        
    def analyze_comment_sentiment(self, audio_filepath: str, post_summary: str) -> dict:
        """
        Analyze comment sentiment relative to the post
        Returns sentiment analysis result
        """
        if not self.gemini.available:
            raise RuntimeError("GEMINI_API_KEY is not configured. Gemini service is unavailable.")
        
        # Resolve to absolute path
        if not os.path.isabs(audio_filepath):
            audio_filepath = os.path.abspath(audio_filepath)
        
        if not os.path.exists(audio_filepath):
            raise FileNotFoundError(f"Audio file not found: {audio_filepath}")
        
        # Upload file
        uploaded = None
        try:
            uploaded = self.gemini.client.files.upload(file=audio_filepath)
            
            # Generate sentiment analysis
            response = self.gemini.client.models.generate_content(
                model=self.gemini.model,
                contents=[
                    f"""Analyze this audio comment in relation to the following post summary:

POST SUMMARY: "{post_summary}"

Listen to the audio comment and determine if the speaker's sentiment is:
- IN_FAVOR: Supporting, agreeing with, or positive about the post
- AGAINST: Opposing, disagreeing with, or negative about the post

Provide the output in JSON format with this exact structure:
{{"SENTIMENT": "IN_FAVOR or AGAINST"}}

Return ONLY the JSON, no markdown code blocks or extra text.""",
                    uploaded
                ]
            )
            
        finally:
            # Clean up uploaded file
            if uploaded:
                try:
                    self.gemini.client.files.delete(name=uploaded.name)
                except Exception as e:
                    print(f"Error deleting uploaded file: {e}")
        
        if not response or not response.text:
            raise RuntimeError("No response from Gemini for sentiment analysis")
        
        return self._parse_sentiment_output(response.text)
    
    def _parse_sentiment_output(self, raw: str) -> dict:
        """Parse Gemini sentiment analysis output"""
        import json
        import re
        
        # Clean up response
        cleaned = raw.strip()
        
        # Remove markdown code blocks if present
        if cleaned.startswith('```'):
            cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
            cleaned = re.sub(r'\n?```\s*$', '', cleaned)
        
        try:
            data = json.loads(cleaned)
            sentiment = data.get("SENTIMENT", "").upper()
            
            if sentiment not in ["IN_FAVOR", "AGAINST"]:
                raise ValueError(f"Invalid sentiment: {sentiment}")
                
            return {"sentiment": sentiment}
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing sentiment response: {e}")
            print(f"Raw response: {raw}")
            # Default fallback
            return {"sentiment": "AGAINST"}


class CommentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.comment_gemini = CommentGeminiService()
    
    async def create_comment(
        self,
        user: User,
        post_id: UUID,
        original_audio_path: str,
    ) -> Comment:
        """
        Create a new comment on a post
        - Verifies post exists
        - Creates comment in PROCESSING status
        - Returns comment for background processing
        """
        # Verify post exists
        result = await self.db.execute(
            select(Post).where(Post.id == post_id)
        )
        post = result.scalars().first()
        
        if not post:
            raise ValueError("Post does not exist")
        
        # Create comment in PROCESSING status
        comment = Comment(
            post_id=post_id,
            user_id=user.id,
            status=CommentStatusEnum.PROCESSING,
            # anonymized_audio_path will be set after processing
        )
        
        self.db.add(comment)
        await self.db.commit()
        await self.db.refresh(comment)
        
        return comment
    
    async def process_comment_audio(
        self,
        comment: Comment,
        original_audio_path: str,
    ) -> Comment:
        """
        Process comment audio:
        1. Get post summary for sentiment analysis
        2. Use Gemini to analyze sentiment relative to post
        3. Anonymize audio
        4. Update comment with results
        5. Delete original audio
        """
        try:
            # Get the post for sentiment analysis
            result = await self.db.execute(
                select(Post).where(Post.id == comment.post_id)
            )
            post = result.scalars().first()
            
            if not post or not post.summary:
                raise ValueError("Post or post summary not found")
            
            # Analyze sentiment using Gemini
            sentiment_result = self.comment_gemini.analyze_comment_sentiment(
                original_audio_path, 
                post.summary
            )
            
            # Anonymize the audio (using preset 1 as default, can be made configurable)
            anonymized_path = voice_anonymizer.anonymize(
                original_audio_path, 
                preset_index=1  # You can make this configurable
            )
            
            # Update comment with results
            comment.sentiment = CommentSentimentEnum(sentiment_result["sentiment"])
            comment.anonymized_audio_path = anonymized_path
            comment.status = CommentStatusEnum.READY
            
            await self.db.commit()
            await self.db.refresh(comment)
            
            # Delete original audio file
            try:
                if os.path.exists(original_audio_path):
                    os.remove(original_audio_path)
            except Exception as e:
                print(f"Warning: Could not delete original audio file {original_audio_path}: {e}")
            
            return comment
            
        except Exception as e:
            print(f"Error processing comment audio: {e}")
            comment.status = CommentStatusEnum.FAILED
            await self.db.commit()
            
            # Still try to delete original audio on failure
            try:
                if os.path.exists(original_audio_path):
                    os.remove(original_audio_path)
            except Exception:
                pass
            
            raise
    
    async def get_comment(self, comment_id: UUID) -> Optional[Comment]:
        """Get a comment by ID"""
        stmt = select(Comment).where(Comment.id == comment_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()
    
    async def get_comments_for_post(
        self, 
        post_id: UUID, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[Comment]:
        """Get comments for a specific post"""
        stmt = (
            select(Comment)
            .where(Comment.post_id == post_id)
            .where(Comment.status == CommentStatusEnum.READY)
            .order_by(Comment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def get_comments_by_sentiment(
        self,
        post_id: UUID,
        sentiment: CommentSentimentEnum,
        limit: int = 50,
        offset: int = 0
    ) -> List[Comment]:
        """Get comments filtered by sentiment"""
        stmt = (
            select(Comment)
            .where(Comment.post_id == post_id)
            .where(Comment.sentiment == sentiment)
            .where(Comment.status == CommentStatusEnum.READY)
            .order_by(Comment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def mark_comment_failed(self, comment: Comment) -> Comment:
        """Mark a comment as failed"""
        comment.status = CommentStatusEnum.FAILED
        await self.db.commit()
        await self.db.refresh(comment)
        return comment
        