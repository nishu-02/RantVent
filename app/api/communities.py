from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from app.schemas.community import (
    CommunityCreate, CommunityUpdate, CommunityOut, 
    CommunityListItem, CommunityMembershipOut, CategoryOut, 
    PinPostRequest, CommunityDiscovery, CommunityStatsOut
)
from app.services.community_service import CommunityService
from app.services.community_management_service import CommunityManagementService
from app.services.category_service import CategoryService
from app.core.database import get_session
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.community_membership import MembershipRole

router = APIRouter(prefix="/communities", tags=["communities"])


@router.get("/categories", response_model=List[CategoryOut])
async def get_categories(
    db: AsyncSession = Depends(get_session),
):
    """Get all community categories with counts"""
    service = CategoryService(db)
    categories = await service.get_categories_with_counts()
    return [CategoryOut.model_validate(cat) for cat in categories]


@router.get("/category/{category_id}", response_model=List[CommunityListItem])
async def get_communities_by_category(
    category_id: str,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get communities in a specific category"""
    service = CommunityService(db)
    communities = await service.get_communities_by_category(category_id, limit, offset)
    
    result = []
    for community in communities:
        is_member = await service.is_member(str(community.id), str(current_user.id))
        item = CommunityListItem.model_validate(community)
        item.is_member = is_member
        result.append(item)
    
    return result


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
        
        # Create response with proper field conversion
        return CommunityOut(
            id=str(community.id),
            name=community.name,
            display_name=community.display_name,
            description=community.description,
            rules=community.rules,
            type=community.type.value,  # Convert enum to string
            is_active=community.is_active,
            member_count=community.member_count,
            post_count=community.post_count,
            created_at=community.created_at,
            is_member=True,  # Creator is automatically a member
            user_role='OWNER'  # Creator is the owner
        )
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


@router.get("/discover", response_model=CommunityDiscovery)
async def discover_communities(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get community discovery feed with trending, categories, etc."""
    service = CommunityService(db)
    
    # Get trending communities (most active in last week)
    trending = await service.get_trending_communities(limit=10)
    
    # Get newest communities
    newest = await service.get_newest_communities(limit=5)
    
    # Get recommended communities (placeholder - can enhance later)
    recommended = await service.get_recommended_communities(
        str(current_user.id), limit=5
    )
    
    # Get communities by popular categories (simplified)
    by_category = {
        "Tech & Programming": await service.get_communities_by_tag("tech", limit=5),
        "Health & Wellness": await service.get_communities_by_tag("health", limit=5),
        "Work & Career": await service.get_communities_by_tag("work", limit=5)
    }
    
    # Convert to response format
    trending_items = []
    for community in trending:
        is_member = await service.is_member(str(community.id), str(current_user.id))
        item = CommunityListItem(
            id=str(community.id),
            name=community.name,
            display_name=community.display_name,
            description=community.description,
            member_count=community.member_count,
            post_count=community.post_count,
            is_member=is_member
        )
        trending_items.append(item)
    
    newest_items = []
    for community in newest:
        is_member = await service.is_member(str(community.id), str(current_user.id))
        item = CommunityListItem(
            id=str(community.id),
            name=community.name,
            display_name=community.display_name,
            description=community.description,
            member_count=community.member_count,
            post_count=community.post_count,
            is_member=is_member
        )
        newest_items.append(item)
    
    return CommunityDiscovery(
        trending=trending_items,
        newest=newest_items,
        by_category=by_category,
        recommended=recommended
    )


@router.get("/trending", response_model=List[CommunityListItem])
async def get_trending_communities(
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get trending communities"""
    service = CommunityService(db)
    communities = await service.get_trending_communities(limit)
    
    result = []
    for community in communities:
        is_member = await service.is_member(str(community.id), str(current_user.id))
        item = CommunityListItem(
            id=str(community.id),
            name=community.name,
            display_name=community.display_name,
            description=community.description,
            member_count=community.member_count,
            post_count=community.post_count,
            is_member=is_member
        )
        result.append(item)
    
    return result


@router.post("/{community_id}/pin")
async def pin_post(
    community_id: UUID,
    pin_request: PinPostRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Pin a post to community (moderator+ only)"""
    mgmt_service = CommunityManagementService(db)
    
    # Check permissions
    user_role = await mgmt_service.get_user_role(str(community_id), str(current_user.id))
    if user_role not in [MembershipRole.MODERATOR, MembershipRole.ADMIN, MembershipRole.OWNER]:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only moderators and admins can pin posts"
        )
    
    try:
        success = await mgmt_service.pin_post(
            str(community_id), 
            pin_request.post_id, 
            str(current_user.id)
        )
        
        if not success:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Failed to pin post"
            )
        
        return {"message": "Post pinned successfully"}
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.delete("/{community_id}/pin/{post_id}")
async def unpin_post(
    community_id: UUID,
    post_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Unpin a post from community"""
    mgmt_service = CommunityManagementService(db)
    
    # Check permissions
    user_role = await mgmt_service.get_user_role(str(community_id), str(current_user.id))
    if user_role not in [MembershipRole.MODERATOR, MembershipRole.ADMIN, MembershipRole.OWNER]:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only moderators and admins can unpin posts"
        )
    
    try:
        success = await mgmt_service.unpin_post(str(community_id), str(post_id))
        
        if not success:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Failed to unpin post or post not pinned"
            )
        
        return {"message": "Post unpinned successfully"}
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.get("/{community_id}/pins")
async def get_pinned_posts(
    community_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get all pinned posts in a community"""
    mgmt_service = CommunityManagementService(db)
    
    # Check if user is a member
    user_role = await mgmt_service.get_user_role(str(community_id), str(current_user.id))
    if not user_role:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Must be a member to view pinned posts"
        )
    
    pinned_posts = await mgmt_service.get_pinned_posts(str(community_id))
    return {"pinned_posts": pinned_posts}


@router.post("/{community_id}/avatar")
async def upload_community_avatar(
    community_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Upload community avatar (admin+ only)"""
    mgmt_service = CommunityManagementService(db)
    
    # Check permissions
    user_role = await mgmt_service.get_user_role(str(community_id), str(current_user.id))
    if user_role not in [MembershipRole.ADMIN, MembershipRole.OWNER]:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only admins can update community avatar"
        )
    
    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "File must be an image"
        )
    
    # Save file and update community
    try:
        avatar_url = await mgmt_service.upload_community_avatar(str(community_id), file)
        return {"avatar_url": avatar_url, "message": "Avatar updated successfully"}
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/{community_id}/banner")
async def upload_community_banner(
    community_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Upload community banner (admin+ only)"""
    mgmt_service = CommunityManagementService(db)
    
    # Check permissions
    user_role = await mgmt_service.get_user_role(str(community_id), str(current_user.id))
    if user_role not in [MembershipRole.ADMIN, MembershipRole.OWNER]:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only admins can update community banner"
        )
    
    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "File must be an image"
        )
    
    # Save file and update community
    try:
        banner_url = await mgmt_service.upload_community_banner(str(community_id), file)
        return {"banner_url": banner_url, "message": "Banner updated successfully"}
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.get("/{community_id}/analytics", response_model=CommunityStatsOut)
async def get_community_analytics(
    community_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get detailed community analytics (moderator+ only)"""
    mgmt_service = CommunityManagementService(db)
    
    # Check permissions
    user_role = await mgmt_service.get_user_role(str(community_id), str(current_user.id))
    if user_role not in [MembershipRole.MODERATOR, MembershipRole.ADMIN, MembershipRole.OWNER]:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only moderators and admins can view analytics"
        )
    
    try:
        analytics = await mgmt_service.get_community_analytics(str(community_id))
        return CommunityStatsOut.model_validate(analytics)
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


# Community Leaderboards
@router.get("/{community_id}/leaderboard")
async def get_community_leaderboard(
    community_id: UUID,
    period: str = Query("month", regex="^(week|month|all)$"),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get community leaderboard (top contributors)"""
    service = CommunityService(db)
    
    # Check if user is a member
    is_member = await service.is_member(str(community_id), str(current_user.id))
    if not is_member:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Must be a member to view leaderboard"
        )
    
    try:
        leaderboard = await service.get_community_leaderboard(
            str(community_id), period, limit
        )
        return {"leaderboard": leaderboard, "period": period}
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


# Enhanced Post Sorting
@router.get("/{community_id}/posts")
async def get_community_posts(
    community_id: UUID,
    sort_by: str = Query("new", regex="^(hot|new|top)$"),
    time_period: str = Query("week", regex="^(day|week|month|all)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_pinned: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get posts in community with enhanced sorting"""
    service = CommunityService(db)
    mgmt_service = CommunityManagementService(db)
    
    # Check if user is a member
    is_member = await service.is_member(str(community_id), str(current_user.id))
    if not is_member:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Must be a member to view community posts"
        )
    
    try:
        # Get regular posts
        posts = await service.get_community_posts_sorted(
            str(community_id), sort_by, time_period, limit, offset
        )
        
        result = {"posts": posts}
        
        # Include pinned posts if requested and on first page
        if include_pinned and offset == 0:
            pinned_posts = await mgmt_service.get_pinned_posts(str(community_id))
            result["pinned_posts"] = pinned_posts
        
        return result
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


# Activity Summary
@router.get("/{community_id}/activity")
async def get_community_activity(
    community_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get community activity summary"""
    service = CommunityService(db)
    
    # Check if user is a member
    is_member = await service.is_member(str(community_id), str(current_user.id))
    if not is_member:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Must be a member to view activity"
        )
    
    try:
        activity = await service.get_community_activity_summary(str(community_id))
        return activity
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


# Enhanced Search
@router.get("/search/advanced")
async def advanced_community_search(
    q: str = Query(..., min_length=1),
    min_members: Optional[int] = Query(None, ge=0),
    max_members: Optional[int] = Query(None, ge=0),
    min_posts: Optional[int] = Query(None, ge=0),
    active_since: Optional[str] = Query(None, regex="^(day|week|month)$"),
    sort_by: str = Query("relevance", regex="^(relevance|members|posts|activity|newest)$"),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Advanced community search with filters"""
    service = CommunityService(db)
    
    filters = {
        "min_members": min_members,
        "max_members": max_members,
        "min_posts": min_posts,
        "active_since": active_since,
        "sort_by": sort_by
    }
    
    try:
        results = await service.advanced_search_communities(
            q, filters, limit, offset, str(current_user.id)
        )
        return results
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


# Community Suggestions
@router.get("/suggestions")
async def get_community_suggestions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get personalized community suggestions"""
    service = CommunityService(db)
    
    try:
        suggestions = await service.get_personalized_suggestions(str(current_user.id))
        return {"suggestions": suggestions}
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


# Related Communities
@router.get("/{community_id}/related")
async def get_related_communities(
    community_id: UUID,
    limit: int = Query(10, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get communities related to this one"""
    service = CommunityService(db)
    
    try:
        related = await service.get_related_communities(
            str(community_id), limit, str(current_user.id)
        )
        return {"related_communities": related}
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))