from pydantic import BaseModel, EmailStr, Field, field_serializer
from uuid import UUID


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    about: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str | UUID
    email: EmailStr
    username: str
    about: str | None
    role: str

    class Config:
        from_attributes = True  # enables ORM → schema conversion

    @field_serializer('id')
    def serialize_id(self, value: UUID | str) -> str:
        """Convert UUID to string for JSON response"""
        return str(value) if isinstance(value, UUID) else value
