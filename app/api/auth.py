from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.user import UserCreate, UserLogin, UserOut
from app.models.user import UserRole
from app.services.user_service import UserService
from app.core.jwt import create_access_token, create_refresh_token, verify_password
from app.core.database import get_session
from app.dependencies.auth import (
    AccessTokenBearer,
    RefreshTokenBearer,
    get_current_user,
    RoleChecker,
)
from app.dependencies.redis import add_jti_to_blacklist


auth = APIRouter(prefix="/auth", tags=["auth"])

admin_or_user = RoleChecker(["admin", "user"])


@auth.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(
    data: UserCreate,
    db: AsyncSession = Depends(get_session),
):
    service = UserService(db)

    if await service.user_exist(data.email):
        raise HTTPException(400, "Email already exists")

    new_user = await service.create_user(data)

    return {"message": "User created successfully"}


@auth.post("/login")
async def login(
    data: UserLogin,
    db: AsyncSession = Depends(get_session),
):
    service = UserService(db)

    user = await service.get_user_by_email(data.email)

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")

    access = create_access_token(
        user_id=str(user.id),
        email=user.email,
        role=user.role.value,
    )

    refresh = create_refresh_token(
        user_id=str(user.id),
    )

    return {
        "access_token": access,
        "refresh_token": refresh,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "role": user.role.value
        }
    }


@auth.get("/refresh")
async def refresh_token(
    payload: dict = Depends(RefreshTokenBearer())
):
    new_access = create_access_token(
        user_id=payload["sub"],
        email=payload.get("email", ""),
        role=payload.get("role", UserRole.USER.value),
    )

    return {"access_token": new_access}


@auth.get("/logout")
async def logout(
    payload: dict = Depends(AccessTokenBearer())
):
    await add_jti_to_blacklist(payload["jti"])
    return {"message": "Logged out"}


@auth.get("/me", response_model=UserOut)
async def me(
    user=Depends(get_current_user),
):
    return user

@auth.patch("/me", response_model=UserOut)
async def update_me(
    update_data: dict,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    service = UserService(db)

    updated = await service.update_user_profile(
        user=current_user,
        data=update_data,
    )

    return updated

@auth.get("/user/{user_id}", response_model=UserOut)
async def get_user_profile(
    user_id: str,
    db: AsyncSession = Depends(get_session),
):
    service = UserService(db)
    user = await service.get_by_id(user_id)

    if not user:
        raise HTTPException(404, "User not found")

    return user
