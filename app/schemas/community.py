from pydantic import BaseModel, Field, field_serializer, validator
from uuid import UUID
from typing import Optional
from datetime import datetime


class CommunityCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=50)
    display_name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

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


class CommunityOut(BaseModel):
    id: str
    name: str
    display_name: str
    description: Optional[str]
    rules: Optional[str]
    type: str
    is_active: bool
    member_count: int  # Fixed typo
    post_count: int
    created_at: datetime
    is_member: bool = False # Indicates if the requesting user is a member (done by the service layer)
    user_role: Optional[str] = None  # User's role in community

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
    member_count: int
    post_count: int
    is_member: bool = False

    class Config:
        from_attributes = True

    @field_serializer('id')
    def serialize_id(self, value: UUID | str) -> str:
        return str(value) if isinstance(value, UUID) else value


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