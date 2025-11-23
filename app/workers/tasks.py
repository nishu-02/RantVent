from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.post import Post
from app.models.comment import Comment
from app.services.post_service import PostService
from app.services.comment_service import CommentService
from app.services.voice_anonymizer import voice_anonymizer
from app.services.gemini_service import gemini_service

async def process_post_audio(post_id: UUID, anonymize_mode: int) -> None:
    """
    Async background processor:
    - load Post
    - anonymize voice
    - call Gemini
    - store transcript + summary + tldr
    """
    async with AsyncSessionLocal() as db: #type: AsyncSession
        service = PostService(db)

        post = await service.get_post(post_id)
        if not post or not post.audio_path:
            return

        try: 
            # 1) anonymize voice (CPU-heavy -> threadpool)
            if anonymize_mode != 0:
                anon_path = await run_in_threadpool(
                    voice_anonymizer.anonymize,
                    post.audio_path,
                    anonymize_mode,
                )
                
                post.audio_path = anon_path
                await db.commit()
                await db.refresh(post)

            else:
                anon_path = post.audio_path # use original

            # 2) Gemini transcription - use original audio for best quality
            print(f"[Gemini] Starting transcription for {post_id} with original audio...")
            # Get the original audio path (before anonymization)
            stmt = select(Post).where(Post.id == post_id)
            result_row = await db.execute(stmt)
            fresh_post = result_row.scalars().first()
            original_audio = fresh_post.audio_path if anonymize_mode == 0 else post.audio_path
            
            print(f"[Gemini] Using audio file: {original_audio}")
            result = await run_in_threadpool(
                gemini_service.transcribe_romanized_full,
                original_audio,
            )
            print(f"[Gemini] Transcription complete. Result: {result}")

            print(f"[Update] Updating post with transcript: {result.transcript[:100]}...")
            await service.update_transcription(
                post=post,
                transcript=result.transcript,
                summary=result.summary,
                tldr=result.tldr,
                language=result.language,
            )
            print(f"[Success] Post {post_id} updated successfully")

        except Exception as e:
            import traceback
            print(f"Error processing post {post_id}: {str(e)}")
            traceback.print_exc()
            await service.mark_failed(post)
            # TODO: proper logging


async def process_comment_audio(comment_id: UUID, original_audio_path: str, anonymize_mode: int = 1) -> None:
    """
    Async background processor for comments:
    - Load comment
    - Analyze sentiment using Gemini
    - Anonymize audio 
    - Update comment with results
    - Delete original audio
    """
    async with AsyncSessionLocal() as db:
        service = CommentService(db)
        
        comment = await service.get_comment(comment_id)
        if not comment:
            print(f"Comment {comment_id} not found")
            return
        
        try:
            print(f"[Comment] Starting processing for comment {comment_id}")
            
            # Process the comment audio (sentiment analysis + anonymization)
            await service.process_comment_audio(comment, original_audio_path, anonymize_mode)
            
            print(f"[Comment] Successfully processed comment {comment_id}")
            
        except Exception as e:
            import traceback
            print(f"Error processing comment {comment_id}: {str(e)}")
            traceback.print_exc()
            await service.mark_comment_failed(comment)
            # TODO: proper logging