from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

class PostOut(BaseModel):
    id: UUID
    user_id: UUID
    status: str
    tldr: str | None
    summary: str | None
    transcript: str | None
    language: str | None
    created_at: datetime
    audio_available: bool

    class Config: 
        from_attributes = True  # enables ORM → schema conversion
    
class PostFeedItem(BaseModel):
    id: UUID
    tldr: str | None
    status: str
    created_at: datetime

    class Config: 
        from_attributes = True  # enables ORM → schema conversion