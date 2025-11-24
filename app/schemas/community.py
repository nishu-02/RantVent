from pydantic import BaseModel, Field, field_serializer, validator
from uuid import UUID
from typing import Optional, List
from datetime import datetime


class CommunityCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=50)
    display_name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    category_id: Optional[UUID] = None

    @validator('name')
    def validate_name(cls, v):
        # Community name validation 
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Community name can only contain letters, numbers, hyphens, and underscores')
        
        # Check for reserved names
        reserved = ['admin', 'api', 'www', 'general', 'announcements', 'help']
        if v.lower() in reserved:
            raise ValueError('Community name is reserved')
            
        return v.lower()


class CommunityUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    rules: Optional[str] = Field(None, max_length=2000)
    category_id: Optional[UUID] = None


class CategoryOut(BaseModel):
    id: str
    name: str
    display_name: str
    description: Optional[str]
    icon: Optional[str]
    community_count: int = 0

    class Config:
        from_attributes = True
        
    @field_serializer('id')
    def serialize_id(self, value: UUID | str) -> str:
        return str(value) if isinstance(value, UUID) else value


class CommunityOut(BaseModel):
    id: str
    name: str
    display_name: str
    description: Optional[str] = None
    rules: Optional[str] = None
    category: Optional[CategoryOut] = None
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None
    type: str
    is_active: bool
    member_count: int
    post_count: int
    created_at: datetime
    is_member: bool = False # Indicates if the requesting user is a member (done by the service layer)
    user_role: Optional[str] = None  # User's role in community
    owner: Optional[dict] = None  # Owner's user ID
    pinned_posts: List[dict] = []  # List of pinned post IDs

    class Config:
        from_attributes = True

    @field_serializer('id')
    def serialize_id(self, value: UUID | str) -> str:
        return str(value) if isinstance(value, UUID) else value


class CommunityListItem(BaseModel):
    id: str
    name:str
    display_name: str
    description: Optional[str]
    category: Optional[CategoryOut]
    avatar_url: Optional[str]
    member_count: int
    post_count: int
    is_member: bool = False

    class Config:
        from_attributes = True

    @field_serializer('id')
    def serialize_id(self, value: UUID | str) -> str:
        return str(value) if isinstance(value, UUID) else value


class PinPostRequest(BaseModel):
    post_id: str = Field(..., description="ID of the post to pin")


class PinnedPostOut(BaseModel):
    id: str
    post: dict
    pinned_by: dict
    pinned_at: datetime

    class Config: 
        from_attributes = True
    
    @field_serializer('id')
    def serialize_id(self, value: UUID | str) -> str:
        return str(value) if isinstance(value, UUID) else value

class CommunityStatsOut(BaseModel):
    """Enhanced community stats"""
    member_count: int
    post_count: int
    daily_posts: int
    weekly_posts:int
    monthly_posts: int
    top_contributors: List[dict]  # List of user dicts with post counts
    growth_stats: dict
    activity_trend: List[dict]

class CommunityDiscovery(BaseModel):
    """Community discovery with trends"""
    trending: List[CommunityListItem]
    by_category: dict # category_name -> List[CommunityListItem]
    recommended: List[CommunityListItem] = []
    newest: List[CommunityListItem]


class CommunityMembershipOut(BaseModel):
    id: str
    community: CommunityListItem
    role: str
    joined_at: datetime

    class Config:
        from_attributes = True

    @field_serializer('id')
    def serialize_id(self, value: UUID | str) -> str:
        return str(value) if isinstance(value, UUID) else value