from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.models.post import Post
from app.services.post_service import PostService
from app.services.voice_anonymizer import anonymize_single
from app.services.gemini_service import gemini_service

async def process_post_audio(post_id: UUID) -> None:
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
        if not post or not post.audio.path:
            return

        try: 
            # 1) anonymize voice (CPU-heavy -> threadpool)
            anon_path = await run_in_threadpool(
                anonymize_single,
                post.audio_path
                0, # preset index
                None,
            )

            post.audio_path = anon_path
            await db.commit()
            await db.refresh(post)

            # 2) Gemini transcription (also threadpool)
            result = await run_in_threadpool(
                gemini_service.transcribe_romanized_with_summary,
                anon_path,
            )

            await service.update_transcription(
                post=post,
                transcript=result.transcript,
                summary=result.summary,
                tldr=result.tldr,
                language=result.language,
            )

        except Exception as e:
            await service.update.mark_failed(post)
            # TODO: proper logging