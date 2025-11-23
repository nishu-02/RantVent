from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, Field

from app.services.community_management_service import CommunityManagementService
from app.models.community_membership import MembershipRole
from app.core.database import get_session
from app.dependencies.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/communities", tags=["community-management"])


# Schemas
class RoleChangeRequest(BaseModel):
    target_user_id: UUID
    new_role: MembershipRole
    
    class Config:
        use_enum_values = True


class CommunitySettingsUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    rules: Optional[str] = Field(None, max_length=2000)


class MemberInfo(BaseModel):
    user_id: str
    username: str
    role: str
    joined_at: str
    is_active: bool


class OwnerTransferRequest(BaseModel):
    new_owner_id: UUID


# Endpoints
@router.get("/{community_id}/members", response_model=List[MemberInfo])
async def get_community_members(
    community_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get all members of a community (requires membership)"""
    service = CommunityManagementService(db)
    
    # Check if user is a member of the community
    user_role = await service.get_user_role_in_community(str(community_id), str(current_user.id))
    if not user_role:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Must be a member to view community members"
        )
    
    members = await service.get_community_members(str(community_id), limit, offset)
    return [MemberInfo(**member) for member in members]


@router.post("/{community_id}/members/role")
async def change_member_role(
    community_id: UUID,
    role_request: RoleChangeRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Change a member's role (requires admin+ permission)"""
    service = CommunityManagementService(db)
    
    try:
        await service.change_member_role(
            str(community_id),
            str(role_request.target_user_id),
            role_request.new_role,
            str(current_user.id)
        )
        return {"message": f"Successfully changed user role to {role_request.new_role.value}"}
    except PermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e))
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.delete("/{community_id}/members/{user_id}")
async def remove_member(
    community_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Remove a member from the community (requires admin+ permission)"""
    service = CommunityManagementService(db)
    
    try:
        await service.remove_member(
            str(community_id),
            str(user_id),
            str(current_user.id)
        )
        return {"message": "Member removed successfully"}
    except PermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e))
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.get("/{community_id}/stats")
async def get_community_stats(
    community_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get detailed community statistics (requires moderator+ permission)"""
    service = CommunityManagementService(db)
    
    # Check if user has moderator+ permission
    if not await service.check_permission(str(community_id), str(current_user.id), MembershipRole.MODERATOR):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only moderators and above can view detailed stats"
        )
    
    try:
        stats = await service.get_community_stats(str(community_id))
        return stats
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.put("/{community_id}/settings")
async def update_community_settings(
    community_id: UUID,
    settings_update: CommunitySettingsUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update community settings (requires admin+ permission)"""
    service = CommunityManagementService(db)
    
    try:
        updates = settings_update.dict(exclude_unset=True)
        community = await service.update_community_settings(
            str(community_id),
            updates,
            str(current_user.id)
        )
        
        return {
            "message": "Community settings updated successfully",
            "community": {
                "id": str(community.id),
                "name": community.name,
                "display_name": community.display_name,
                "description": community.description,
                "rules": community.rules
            }
        }
    except PermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e))
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.post("/{community_id}/transfer-ownership")
async def transfer_ownership(
    community_id: UUID,
    transfer_request: OwnerTransferRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Transfer community ownership (owner only)"""
    service = CommunityManagementService(db)
    
    try:
        await service.transfer_ownership(
            str(community_id),
            str(transfer_request.new_owner_id),
            str(current_user.id)
        )
        return {"message": "Ownership transferred successfully"}
    except PermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e))
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.get("/{community_id}/my-role")
async def get_my_role(
    community_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get current user's role in the community"""
    service = CommunityManagementService(db)
    
    role = await service.get_user_role_in_community(str(community_id), str(current_user.id))
    
    if not role:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "User is not a member of this community"
        )
    
    return {
        "community_id": str(community_id),
        "user_id": str(current_user.id),
        "role": role.value,
        "permissions": {
            "can_moderate": role in [MembershipRole.MODERATOR, MembershipRole.ADMIN, MembershipRole.OWNER],
            "can_manage": role in [MembershipRole.ADMIN, MembershipRole.OWNER],
            "is_owner": role == MembershipRole.OWNER
        }
    }