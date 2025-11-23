from pydantic import BaseModel, EmailStr, Field, field_serializer, validator
from uuid import UUID
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    about: Optional[str] = Field(None, max_length=500)

    @validator('username')
    def validate_username(cls, v):
        # Username validation rules
        if not v.replace('_', '').replace('-', '').replace('.', '').isalnum():
            raise ValueError('Username can only contain letters, numbers, hyphens, underscores, and dots')
        
        # Check for reserved usernames
        reserved = ['admin', 'api', 'www', 'mail', 'support', 'help', 'about', 'auth', 'users', 'posts', 'comments']
        if v.lower() in reserved:
            raise ValueError('Username is reserved')
            
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserProfileUpdate(BaseModel):
    """Schema for updating user profile"""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    about: Optional[str] = Field(None, max_length=500)
    
    @validator('username')
    def validate_username(cls, v):
        if v is not None:
            if not v.replace('_', '').replace('-', '').replace('.', '').isalnum():
                raise ValueError('Username can only contain letters, numbers, hyphens, underscores, and dots')
            
            reserved = ['admin', 'api', 'www', 'mail', 'support', 'help', 'about', 'auth', 'users', 'posts', 'comments']
            if v.lower() in reserved:
                raise ValueError('Username is reserved')
        return v


class UserOut(BaseModel):
    """Complete user profile (for authenticated user only)"""
    id: str
    email: EmailStr
    username: str
    about: Optional[str]
    role: str
    created_at: datetime
    is_verified: bool

    class Config:
        from_attributes = True

    @field_serializer('id')
    def serialize_id(self, value: UUID | str) -> str:
        return str(value) if isinstance(value, UUID) else value


class UserPublicProfile(BaseModel):
    """Public profile view (no sensitive info)"""
    id: str
    username: str
    about: Optional[str]
    created_at: datetime
    post_count: int = 0
    comment_count: int = 0

    class Config:
        from_attributes = True

    @field_serializer('id')
    def serialize_id(self, value: UUID | str) -> str:
        return str(value) if isinstance(value, UUID) else value


class PasswordChangeRequest(BaseModel):
    """Schema for password change"""
    current_password: str
    new_password: str = Field(..., min_length=6, max_length=128)
    confirm_password: str

    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class UserSearchResult(BaseModel):
    """User search result item"""
    id: str
    username: str
    about: Optional[str]
    
    class Config:
        from_attributes = True

    @field_serializer('id')
    def serialize_id(self, value: UUID | str) -> str:
        return str(value) if isinstance(value, UUID) else value


class UserStats(BaseModel):
    """User statistics"""
    post_count: int
    comment_count: int
    join_date: datetime
    last_active: Optional[datetime] = None


class UserAuthResponse(BaseModel):
    """Response schema for authentication"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict
