from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.user import UserCreate, UserLogin, PasswordChangeRequest, UserAuthResponse
from app.services.user_service import UserService
from app.core.token import create_access_token, create_refresh_token, verify_password
from app.core.database import get_session
from app.dependencies.auth import (
    AccessTokenBearer,
    RefreshTokenBearer,
    get_current_user,
)
from app.dependencies.redis import add_jti_to_blacklist
from app.models.user import User, UserRole
from app.core.logger import logger

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(
    data: UserCreate,
    db: AsyncSession = Depends(get_session),
):
    """Register a new user"""
    service = UserService(db)

    try:
        new_user = await service.create_user(data)
        logger.info("user_signup_successful", user_id=str(new_user.id), email=new_user.email)
        return {
            "message": "User created successfully", 
            "user_id": str(new_user.id)
        }
    except ValueError as e:
        logger.warning("user_signup_failed", email=data.email, error=str(e))
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/login", response_model=UserAuthResponse)
async def login(
    data: UserLogin,
    db: AsyncSession = Depends(get_session),
):
    """Authenticate user and return tokens"""
    service = UserService(db)

    user = await service.get_user_by_email(data.email)

    if not user or not verify_password(data.password, user.password_hash):
        logger.warning("login_failed_invalid_credentials", email=data.email)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, 
            "Invalid credentials"
        )

    access_token = create_access_token(
        user_id=str(user.id),
        email=user.email,
        role=user.role.value,
    )

    refresh_token = create_refresh_token(
        user_id=str(user.id),
    )

    logger.info("user_login_successful", user_id=str(user.id), email=user.email)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "role": user.role.value
        }
    }


@router.post("/refresh")
async def refresh_token(
    payload: dict = Depends(RefreshTokenBearer())
):
    """Refresh access token using refresh token"""
    new_access_token = create_access_token(
        user_id=payload["sub"],
        email=payload.get("email", ""),
        role=payload.get("role", UserRole.USER.value),
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }


@router.post("/logout")
async def logout(
    payload: dict = Depends(AccessTokenBearer())
):
    """Logout user by blacklisting token"""
    jti = payload.get("jti")
    
    if jti:
        await add_jti_to_blacklist(jti)
    
    return {"message": "Successfully logged out"}


@router.post("/change-password")
async def change_password(
    data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Change user password"""
    service = UserService(db)
    
    try:
        await service.change_password(current_user, data)
        return {"message": "Password changed successfully"}
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current authenticated user info"""
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "username": current_user.username,
        "role": current_user.role.value,
        "is_verified": current_user.is_verified,
        "created_at": current_user.created_at
    }