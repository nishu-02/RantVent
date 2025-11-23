import redis.asyncio as redis
from app.core.config import settings

JTI_EXPIRY_SECONDS = 3600

token_blocklist = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=0,
    decode_responses=True
)

async def add_jti_to_blacklist(jti: str) -> None:
    await token_blocklist.set(
        name=jti,
        value="",  
        ex=JTI_EXPIRY_SECONDS
    )

async def token_in_blacklist(jti: str) -> bool:
    exists = await token_blocklist.get(jti)
    return exists is not None
