from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.schemas.user import UserCreate
from app.core.token import hash_password


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_id(self, user_id: str) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def user_exist(self, email: str) -> bool:
        return (await self.get_user_by_email(email)) is not None

    async def create_user(self, data: UserCreate) -> User:
        user = User(
            username=data.username,
            email=data.email,
            about=data.about,
            role=UserRole.USER,
            password_hash=hash_password(data.password),
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def update_user_profile(self, user: User, data: dict) -> User:
        for field in ["username", "about"]:
            if field in data:
                setattr(user, field, data[field])

        await self.db.commit()
        await self.db.refresh(user)

        return user
