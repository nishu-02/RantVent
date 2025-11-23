from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from app.schemas.user import (
    UserOut, UserPublicProfile, UserProfileUpdate, 
    UserSearchResult, UserStats
)
from app.services.user_service import UserService
from app.core.database import get_session
from app.dependencies.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def get_my_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current user's full profile"""
    return UserOut.model_validate(current_user)


@router.put("/me", response_model=UserOut)
async def update_my_profile(
    data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Update current user's profile"""
    service = UserService(db)
    
    try:
        updated_user = await service.update_user_profile(current_user, data)
        return UserOut.model_validate(updated_user)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.get("/{user_id}", response_model=UserPublicProfile)
async def get_user_profile(
    user_id: UUID,
    db: AsyncSession = Depends(get_session),
):
    """Get public profile of any user"""
    service = UserService(db)
    
    profile = await service.get_public_profile(str(user_id))
    
    if not profile:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, 
            "User not found"
        )
    
    return UserPublicProfile.model_validate(profile)


@router.get("/{username}/by-username", response_model=UserPublicProfile)
async def get_user_by_username(
    username: str,
    db: AsyncSession = Depends(get_session),
):
    """Get public profile by username"""
    service = UserService(db)
    
    user = await service.get_by_username(username)
    
    if not user:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, 
            "User not found"
        )
    
    profile = await service.get_public_profile(str(user.id))
    return UserPublicProfile.model_validate(profile)


@router.get("", response_model=List[UserSearchResult])
async def search_users(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
):
    """Search users by username"""
    service = UserService(db)
    
    users = await service.search_users(q, limit)
    
    return [
        UserSearchResult(
            id=str(user.id),
            username=user.username,
            about=user.about
        ) for user in users
    ]


@router.get("/me/stats", response_model=UserStats)
async def get_my_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get current user's statistics"""
    service = UserService(db)
    
    stats = await service.get_user_stats(str(current_user.id))
    return UserStats(**stats)


@router.get("/{user_id}/stats", response_model=UserStats)
async def get_user_stats(
    user_id: UUID,
    db: AsyncSession = Depends(get_session),
):
    """Get any user's public statistics"""
    service = UserService(db)
    
    user = await service.get_by_id(str(user_id))
    if not user:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, 
            "User not found"
        )
    
    stats = await service.get_user_stats(str(user_id))
    return UserStats(**stats)


@router.get("/recent", response_model=List[UserSearchResult])
async def get_recent_users(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_session),
):
    """Get recently joined users"""
    service = UserService(db)
    users = await service.get_recent_users(limit)
    
    return [
        UserSearchResult(
            id=str(user.id),
            username=user.username,
            about=user.about
        ) for user in users
    ]


@router.get("/active", response_model=List[UserSearchResult])
async def get_active_users(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_session),
):
    """Get most active users"""
    service = UserService(db)
    users = await service.get_active_users(limit)
    
    return [
        UserSearchResult(
            id=str(user.id),
            username=user.username,
            about=user.about
        ) for user in users
    ]


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Delete current user's account"""
    service = UserService(db)
    
    success = await service.delete_user(str(current_user.id))
    if not success:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Failed to delete account"
        )
    
    return None