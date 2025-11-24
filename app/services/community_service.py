from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from typing import Optional, List

from app.models.community import Community, CommunityType
from app.models.community_membership import CommunityMembership, MembershipRole
from app.models.user import User
from app.schemas.community import CommunityCreate, CommunityUpdate
from app.core.logger import logger


class CommunityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_community(self,
        data: CommunityCreate,
        creator: User
    ) -> Community:
        """Create a new community and make the creator a member"""
        # Check if community with same name exists
        existing = await self.get_by_name(data.name)
        if existing:
            logger.warning("community_creation_failed_name_exists", name=data.name, creator_id=str(creator.id))
            raise ValueError("Community with this name already exists")

        community = Community(
            name=data.name,
            display_name=data.display_name,
            description=data.description,
            type=CommunityType.PUBLIC.value,
            owner_id=creator.id,
            member_count=1,
        )

        self.db.add(community)

        try:
            await self.db.commit()
            await self.db.refresh(community)

            # Add creator as owner
            membership = CommunityMembership(
                user_id=str(creator.id),
                community_id=str(community.id),
                role=MembershipRole.OWNER,
            )
            self.db.add(membership)
            await self.db.commit()
            logger.info("community_created", community_id=str(community.id), name=community.name, creator_id=str(creator.id))

        except IntegrityError:
            await self.db.rollback()
            logger.error("community_creation_failed_integrity", name=data.name, creator_id=str(creator.id), exc_info=True)
            raise ValueError("Failed to create community")
        
        return community
    
    async def get_by_name(self,
        name: str
    ) -> Optional[Community]:
        stmt = select(Community).where(Community.name == name.lower())
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_id(self,
        community_id: str
    ) -> Optional[Community]:
        stmt = select(Community).where(Community.id == community_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_all_communities(self,
        limit: int = 20,
        offset: int = 0
    ) -> List[Community]:
        """Get all active communities"""
        stmt = (
            select(Community)
            .where(Community.is_active == True)
            .order_by(desc(Community.memeber_count))
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def search_communities(
        self,
        query: str,
        limit: int = 20,
    ) -> List[Community]:
        """Search communities by name or description"""
        stmt = (
            select(Community)
            .where(
                Community.is_active == True,
                or_(
                    Community.display_name.ilike(f"%{query}%"),
                    Community.description.ilike(f"%{query}%"),
                    Community.name.ilike(f"%{query}%")
                )
            )
            .order_by(desc(Community.member_count))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def join_community(
        self,
        community_id: str,
        user: User,
    ) -> bool:
        """Join a community"""
        # Check if already a member
        existing_membership = await self._get_membership(community_id, str(user.id))
        if existing_membership and existing_membership.is_active:
            logger.warning("user_already_member", community_id=community_id, user_id=str(user.id))
            raise ValueError("Already a member of this community")

        if existing_membership:
            # Reactive membership
            existing_membership.is_active = True
        else:
            # Create new membership
            membership = CommunityMembership(
                user_id=str(user.id),
                community_id=community_id,
                role=MembershipRole.MEMBER.value,
            )
            self.db.add(membership)

        # Update community member count
        community = await self.get_by_id(community_id)
        if community:
            community.member_count += 1

        await self.db.commit()
        logger.info("user_joined_community", community_id=community_id, user_id=str(user.id))
        return True

    async def leave_community(
        self,
        community_id: str,
        user: User,
    ) -> bool:
        """Leave a community"""
        membership = await self._get_membership(community_id, str(user.id))
        if not membership or not membership.is_active:
            raise ValueError("Not a member of this community")

        membership.is_active = False
        
        # Update community member count
        community = await self.get_by_id(community_id)
        if community and community.member_count > 0:
            community.member_count -= 1

        await self.db.commit()
        return True

    async def is_member(self,
        community_id: str,
        user_id: str
    ) -> bool:
        """Check if user is a member of community"""
        membership = await self._get_membership(community_id, user_id)
        return membership is not None and membership.is_active

    async def get_user_communities(self,
        user_id: str
    ) -> List[CommunityMembership]:
        """Get all communities a user is a member of"""
        stmt = (
            select(CommunityMembership)
            .where(
                CommunityMembership.user_id == user_id,
                CommunityMembership.is_active == True
            )
            .order_by(desc(CommunityMembership.created_at))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _get_membership(self,
        community_id: str,
        user_id: str
    ) -> Optional[CommunityMembership]:
        """Get membership record"""
        stmt = select(CommunityMembership).where(
            CommunityMembership.community_id == community_id,
            CommunityMembership.user_id == user_id
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def update_community(self,
        community_id: str,
        data: CommunityUpdate,
        user: User
    ) -> Community:
        """Update community (admin only for Phase 2)"""
        community = await self.get_by_id(community_id)
        if not community:
            raise ValueError("Community not found")

        # For Phase 1, allow any member to update (Phase 2 will add admin checks)
        
        update_data = data.dict(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(community, field):
                setattr(community, field, value)

        await self.db.commit()
        await self.db.refresh(community)
        return community

    # Phase 2B Methods
    async def get_trending_communities(self, limit: int = 10) -> List[Community]:
        """Get trending communities based on recent activity"""
        from datetime import datetime, timedelta
        from app.models.post import Post
        
        # Communities with most posts in last week
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        stmt = (
            select(Community)
            .join(Post, Community.id == Post.community_id, isouter=True)
            .where(
                Community.is_active == True,
                or_(Post.created_at >= week_ago, Post.created_at.is_(None))
            )
            .group_by(Community.id)
            .order_by(desc(func.count(Post.id)), desc(Community.member_count))
            .limit(limit)
        )
        
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_newest_communities(self, limit: int = 5) -> List[Community]:
        """Get newest communities"""
        stmt = (
            select(Community)
            .where(Community.is_active == True)
            .order_by(desc(Community.created_at))
            .limit(limit)
        )
        
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_recommended_communities(self, user_id: str, limit: int = 5) -> List[Community]:
        """Get recommended communities for a user (placeholder implementation)"""
        # Placeholder: get popular communities user hasn't joined
        from app.models.community_membership import CommunityMembership
        
        # Get communities user is not a member of
        user_communities_subquery = (
            select(CommunityMembership.community_id)
            .where(CommunityMembership.user_id == user_id)
        )
        
        stmt = (
            select(Community)
            .where(
                Community.is_active == True,
                ~Community.id.in_(user_communities_subquery)
            )
            .order_by(desc(Community.member_count))
            .limit(limit)
        )
        
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_communities_by_tag(self, tag: str, limit: int = 5) -> List[Community]:
        """Get communities by tag/category (simple text search for now)"""
        stmt = (
            select(Community)
            .where(
                Community.is_active == True,
                or_(
                    Community.description.ilike(f'%{tag}%'),
                    Community.display_name.ilike(f'%{tag}%')
                )
            )
            .order_by(desc(Community.member_count))
            .limit(limit)
        )
        
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_community_leaderboard(self, community_id: str, period: str, limit: int) -> List[dict]:
        """Get community leaderboard of top contributors"""
        from datetime import datetime, timedelta
        from app.models.post import Post
        from app.models.comment import Comment
        
        # Calculate time filter
        now = datetime.utcnow()
        if period == "week":
            time_filter = now - timedelta(days=7)
        elif period == "month":
            time_filter = now - timedelta(days=30)
        else:  # all
            time_filter = datetime.min
        
        # Get post counts per user
        post_counts_stmt = (
            select(Post.user_id, func.count(Post.id).label('post_count'))
            .where(
                Post.community_id == community_id,
                Post.created_at >= time_filter
            )
            .group_by(Post.user_id)
        )
        
        # Get comment counts per user
        comment_counts_stmt = (
            select(Comment.user_id, func.count(Comment.id).label('comment_count'))
            .join(Post, Comment.post_id == Post.id)
            .where(
                Post.community_id == community_id,
                Comment.created_at >= time_filter
            )
            .group_by(Comment.user_id)
        )
        
        # For now, return placeholder data - would need more complex query
        return [
            {
                "user_id": "placeholder",
                "username": "Top User",
                "post_count": 10,
                "comment_count": 25,
                "total_score": 35
            }
        ]

    async def get_community_posts_sorted(
        self, 
        community_id: str, 
        sort_by: str, 
        time_period: str, 
        limit: int, 
        offset: int
    ) -> List[dict]:
        """Get community posts with enhanced sorting"""
        from datetime import datetime, timedelta
        from app.models.post import Post
        
        # Calculate time filter
        now = datetime.utcnow()
        if time_period == "day":
            time_filter = now - timedelta(days=1)
        elif time_period == "week":
            time_filter = now - timedelta(days=7)
        elif time_period == "month":
            time_filter = now - timedelta(days=30)
        else:  # all
            time_filter = datetime.min
        
        # Base query
        stmt = select(Post).where(
            Post.community_id == community_id,
            Post.created_at >= time_filter
        )
        
        # Apply sorting
        if sort_by == "hot":
            # Hot = recent + engagement (simplified)
            stmt = stmt.order_by(desc(Post.created_at))
        elif sort_by == "top":
            # Top by engagement (placeholder - would need voting system)
            stmt = stmt.order_by(desc(Post.created_at))
        else:  # new
            stmt = stmt.order_by(desc(Post.created_at))
        
        stmt = stmt.offset(offset).limit(limit)
        
        result = await self.db.execute(stmt)
        posts = result.scalars().all()
        
        # Convert to dict format (would normally use schemas)
        return [
            {
                "id": str(post.id),
                "title": post.title,
                "content": post.content,
                "created_at": post.created_at,
                "user_id": str(post.user_id)
            }
            for post in posts
        ]

    async def get_community_activity_summary(self, community_id: str) -> dict:
        """Get community activity summary"""
        from datetime import datetime, timedelta
        from app.models.post import Post
        from app.models.comment import Comment
        
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        # Posts this week/month
        posts_week_stmt = select(func.count(Post.id)).where(
            Post.community_id == community_id,
            Post.created_at >= week_ago
        )
        posts_month_stmt = select(func.count(Post.id)).where(
            Post.community_id == community_id,
            Post.created_at >= month_ago
        )
        
        posts_week = await self.db.scalar(posts_week_stmt) or 0
        posts_month = await self.db.scalar(posts_month_stmt) or 0
        
        # Active members (posted/commented recently)
        active_users_stmt = (
            select(func.count(func.distinct(Post.user_id)))
            .where(
                Post.community_id == community_id,
                Post.created_at >= week_ago
            )
        )
        active_users = await self.db.scalar(active_users_stmt) or 0
        
        return {
            "posts_this_week": posts_week,
            "posts_this_month": posts_month,
            "active_users_this_week": active_users,
            "growth_trend": "stable"  # Placeholder
        }

    async def advanced_search_communities(
        self, 
        query: str, 
        filters: dict, 
        limit: int, 
        offset: int, 
        user_id: str
    ) -> dict:
        """Advanced community search with filters"""
        stmt = select(Community).where(Community.is_active == True)
        
        # Text search
        stmt = stmt.where(
            or_(
                Community.display_name.ilike(f'%{query}%'),
                Community.description.ilike(f'%{query}%')
            )
        )
        
        # Apply filters
        if filters.get("min_members"):
            stmt = stmt.where(Community.member_count >= filters["min_members"])
        if filters.get("max_members"):
            stmt = stmt.where(Community.member_count <= filters["max_members"])
        if filters.get("min_posts"):
            stmt = stmt.where(Community.post_count >= filters["min_posts"])
        
        # Sorting
        sort_by = filters.get("sort_by", "relevance")
        if sort_by == "members":
            stmt = stmt.order_by(desc(Community.member_count))
        elif sort_by == "posts":
            stmt = stmt.order_by(desc(Community.post_count))
        elif sort_by == "newest":
            stmt = stmt.order_by(desc(Community.created_at))
        else:  # relevance or activity
            stmt = stmt.order_by(desc(Community.member_count))
        
        # Pagination
        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.db.scalar(total_stmt) or 0
        
        stmt = stmt.offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        communities = result.scalars().all()
        
        # Convert to response format
        items = []
        for community in communities:
            is_member = await self.is_member(str(community.id), user_id)
            items.append({
                "id": str(community.id),
                "name": community.name,
                "display_name": community.display_name,
                "description": community.description,
                "member_count": community.member_count,
                "post_count": community.post_count,
                "is_member": is_member
            })
        
        return {
            "communities": items,
            "total": total,
            "has_more": offset + limit < total
        }

    async def get_personalized_suggestions(self, user_id: str) -> List[dict]:
        """Get personalized community suggestions (placeholder)"""
        # For now, return popular communities user hasn't joined
        communities = await self.get_recommended_communities(user_id, 5)
        
        suggestions = []
        for community in communities:
            suggestions.append({
                "id": str(community.id),
                "name": community.name,
                "display_name": community.display_name,
                "description": community.description,
                "member_count": community.member_count,
                "reason": "Popular in your interests"  # Placeholder
            })
        
        return suggestions

    async def get_related_communities(
        self, 
        community_id: str, 
        limit: int, 
        user_id: str
    ) -> List[dict]:
        """Get communities related to the given one"""
        # Simple implementation: communities with similar descriptions
        current_community = await self.get_by_id(community_id)
        if not current_community:
            return []
        
        # Get communities with similar keywords in description
        keywords = current_community.description.split()[:5] if current_community.description else []
        
        if not keywords:
            return []
        
        # Build search for similar communities
        conditions = [Community.description.ilike(f'%{word}%') for word in keywords]
        
        stmt = (
            select(Community)
            .where(
                Community.is_active == True,
                Community.id != community_id,
                or_(*conditions)
            )
            .order_by(desc(Community.member_count))
            .limit(limit)
        )
        
        result = await self.db.execute(stmt)
        communities = result.scalars().all()
        
        related = []
        for community in communities:
            is_member = await self.is_member(str(community.id), user_id)
            related.append({
                "id": str(community.id),
                "name": community.name,
                "display_name": community.display_name,
                "description": community.description,
                "member_count": community.member_count,
                "is_member": is_member,
                "similarity_reason": "Similar topics"
            })
        
        return related

    async def get_communities_by_category(self, category_id: str, limit: int = 20, offset: int = 0) -> List[Community]:
        """Get communities in a specific category"""
        stmt = (
            select(Community)
            .where(
                Community.category_id == category_id,
                Community.is_active == True
            )
            .order_by(desc(Community.member_count))
            .offset(offset)
            .limit(limit)
        )
        
        result = await self.db.execute(stmt)
        return result.scalars().all()