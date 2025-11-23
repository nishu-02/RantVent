# app/api/communities.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from app.schemas.community import (
    CommunityCreate, CommunityUpdate, CommunityOut, 
    CommunityListItem, CommunityMembershipOut
)
from app.services.community_service import CommunityService
from app.core.database import get_session
from app.dependencies.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/communities", tags=["communities"])


@router.post("", response_model=CommunityOut, status_code=status.HTTP_201_CREATED)
async def create_community(
    data: CommunityCreate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new community"""
    service = CommunityService(db)
    
    try:
        community = await service.create_community(data, current_user)
        
        # Add is_member flag
        community_out = CommunityOut.model_validate(community)
        community_out.is_member = True  # Creator is automatically a member
        
        return community_out
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.get("", response_model=List[CommunityListItem])
async def get_communities(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, min_length=1),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get all communities or search communities"""
    service = CommunityService(db)
    
    if search:
        communities = await service.search_communities(search, limit)
    else:
        communities = await service.get_all_communities(limit, offset)
    
    # Check membership for each community
    result = []
    for community in communities:
        is_member = await service.is_member(str(community.id), str(current_user.id))
        community_item = CommunityListItem.model_validate(community)
        community_item.is_member = is_member
        result.append(community_item)
    
    return result


@router.get("/{community_id}", response_model=CommunityOut)
async def get_community(
    community_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a specific community by ID"""
    service = CommunityService(db)
    
    community = await service.get_by_id(str(community_id))
    if not community:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Community not found"
        )
    
    # Check if current user is a member
    is_member = await service.is_member(str(community_id), str(current_user.id))
    
    community_out = CommunityOut.model_validate(community)
    community_out.is_member = is_member
    
    return community_out


@router.get("/name/{community_name}", response_model=CommunityOut)
async def get_community_by_name(
    community_name: str,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a specific community by name"""
    service = CommunityService(db)
    
    community = await service.get_by_name(community_name)
    if not community:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Community not found"
        )
    
    # Check if current user is a member
    is_member = await service.is_member(str(community.id), str(current_user.id))
    
    community_out = CommunityOut.model_validate(community)
    community_out.is_member = is_member
    
    return community_out


@router.post("/{community_id}/join")
async def join_community(
    community_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Join a community"""
    service = CommunityService(db)
    
    # Check if community exists
    community = await service.get_by_id(str(community_id))
    if not community:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Community not found"
        )
    
    try:
        await service.join_community(str(community_id), current_user)
        return {"message": f"Successfully joined {community.display_name}"}
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/{community_id}/leave")
async def leave_community(
    community_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Leave a community"""
    service = CommunityService(db)
    
    # Check if community exists
    community = await service.get_by_id(str(community_id))
    if not community:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Community not found"
        )
    
    try:
        await service.leave_community(str(community_id), current_user)
        return {"message": f"Successfully left {community.display_name}"}
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.get("/me/joined", response_model=List[CommunityMembershipOut])
async def get_my_communities(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get all communities the current user has joined"""
    service = CommunityService(db)
    
    memberships = await service.get_user_communities(str(current_user.id))
    
    result = []
    for membership in memberships:
        # Get community details
        community = await service.get_by_id(membership.community_id)
        if community:
            community_item = CommunityListItem.model_validate(community)
            community_item.is_member = True  # Obviously true since we're iterating memberships
            
            membership_out = CommunityMembershipOut(
                id=str(membership.id),
                community=community_item,
                role=membership.role,
                joined_at=membership.created_at
            )
            result.append(membership_out)
    
    return result


@router.put("/{community_id}", response_model=CommunityOut)
async def update_community(
    community_id: UUID,
    data: CommunityUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update a community"""
    service = CommunityService(db)
    
    try:
        community = await service.update_community(str(community_id), data, current_user)
        
        # Check if current user is a member
        is_member = await service.is_member(str(community_id), str(current_user.id))
        
        community_out = CommunityOut.model_validate(community)
        community_out.is_member = is_member
        
        return community_out
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))