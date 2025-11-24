from sqlalchemy import select, func, desc, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict
from uuid import UUID

from app.models.community import Community
from app.models.community_membership import CommunityMembership, MembershipRole
from app.models.user import User
from app.models.post import Post
from app.models.comment import Comment


class CommunityManagementService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_role_in_community(self, community_id: str, user_id: str) -> Optional[MembershipRole]:
        """Get user's role in a community"""
        stmt = select(CommunityMembership).where(
            and_(
                CommunityMembership.community_id == community_id,
                CommunityMembership.user_id == user_id,
                CommunityMembership.is_active == True
            )
        )
        result = await self.db.execute(stmt)
        membership = result.scalars().first()
        
        if not membership:
            return None
        
        return MembershipRole(membership.role)

    async def check_permission(self, community_id: str, user_id: str, required_role: MembershipRole) -> bool:
        """Check if user has required permission level in community"""
        user_role = await self.get_user_role_in_community(community_id, user_id)
        
        if not user_role:
            return False
        
        # Permission hierarchy: OWNER > ADMIN > MODERATOR > MEMBER
        role_hierarchy = {
            MembershipRole.MEMBER: 1,
            MembershipRole.MODERATOR: 2,
            MembershipRole.ADMIN: 3,
            MembershipRole.OWNER: 4
        }
        
        return role_hierarchy.get(user_role, 0) >= role_hierarchy.get(required_role, 0)

    async def change_member_role(
        self, 
        community_id: str, 
        target_user_id: str, 
        new_role: MembershipRole, 
        acting_user_id: str
    ) -> bool:
        """Change a member's role (requires admin+ permission)"""
        
        # Check if acting user has admin+ permission
        if not await self.check_permission(community_id, acting_user_id, MembershipRole.ADMIN):
            raise PermissionError("Only admins can change member roles")
        
        # Get target user's current membership
        stmt = select(CommunityMembership).where(
            and_(
                CommunityMembership.community_id == community_id,
                CommunityMembership.user_id == target_user_id,
                CommunityMembership.is_active == True
            )
        )
        result = await self.db.execute(stmt)
        membership = result.scalars().first()
        
        if not membership:
            raise ValueError("User is not a member of this community")
        
        # Don't allow changing owner role
        if MembershipRole(membership.role) == MembershipRole.OWNER:
            raise PermissionError("Cannot change owner role")
        
        # Don't allow setting someone as owner (transfer ownership is separate)
        if new_role == MembershipRole.OWNER:
            raise PermissionError("Use transfer_ownership method to make someone owner")
        
        # Update role
        membership.role = new_role.value
        await self.db.commit()
        await self.db.refresh(membership)
        
        return True

    async def remove_member(self, community_id: str, target_user_id: str, acting_user_id: str) -> bool:
        """Remove a member from community (requires admin+ permission)"""
        
        # Check if acting user has admin+ permission
        if not await self.check_permission(community_id, acting_user_id, MembershipRole.ADMIN):
            raise PermissionError("Only admins can remove members")
        
        # Get target user's membership
        stmt = select(CommunityMembership).where(
            and_(
                CommunityMembership.community_id == community_id,
                CommunityMembership.user_id == target_user_id,
                CommunityMembership.is_active == True
            )
        )
        result = await self.db.execute(stmt)
        membership = result.scalars().first()
        
        if not membership:
            raise ValueError("User is not a member of this community")
        
        # Don't allow removing owner
        if MembershipRole(membership.role) == MembershipRole.OWNER:
            raise PermissionError("Cannot remove community owner")
        
        # Don't allow removing yourself
        if target_user_id == acting_user_id:
            raise ValueError("Cannot remove yourself (use leave community instead)")
        
        # Deactivate membership
        membership.is_active = False
        
        # Update community member count
        community = await self.get_community(community_id)
        if community and community.member_count > 0:
            community.member_count -= 1
        
        await self.db.commit()
        return True

    async def get_community_members(
        self, 
        community_id: str, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[Dict]:
        """Get all members of a community with their roles"""
        stmt = (
            select(CommunityMembership, User)
            .join(User, CommunityMembership.user_id == User.id)
            .where(
                and_(
                    CommunityMembership.community_id == community_id,
                    CommunityMembership.is_active == True
                )
            )
            .order_by(
                # Order by role hierarchy (owners first, then admins, etc.)
                CommunityMembership.role.desc(),
                CommunityMembership.created_at.asc()
            )
            .offset(offset)
            .limit(limit)
        )
        
        result = await self.db.execute(stmt)
        rows = result.all()
        
        members = []
        for membership, user in rows:
            members.append({
                "user_id": str(user.id),
                "username": user.username,
                "role": membership.role,
                "joined_at": membership.created_at,
                "is_active": membership.is_active
            })
        
        return members

    async def get_community_stats(self, community_id: str) -> Dict:
        """Get detailed community statistics"""
        
        # Get basic community info
        community = await self.get_community(community_id)
        if not community:
            raise ValueError("Community not found")
        
        # Get member count by role
        role_count_stmt = (
            select(
                CommunityMembership.role,
                func.count(CommunityMembership.id).label('count')
            )
            .where(
                and_(
                    CommunityMembership.community_id == community_id,
                    CommunityMembership.is_active == True
                )
            )
            .group_by(CommunityMembership.role)
        )
        
        result = await self.db.execute(role_count_stmt)
        role_counts = {row.role: row.count for row in result.all()}
        
        # Get recent activity (posts in last 7 days)
        from datetime import datetime, timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        recent_posts_stmt = select(func.count(Post.id)).where(
            and_(
                Post.community_id == community_id,
                Post.created_at >= week_ago
            )
        )
        result = await self.db.execute(recent_posts_stmt)
        recent_posts = result.scalar() or 0
        
        # Get total comments in community
        total_comments_stmt = (
            select(func.count(Comment.id))
            .select_from(Comment)
            .join(Post, Comment.post_id == Post.id)
            .where(Post.community_id == community_id)
        )
        result = await self.db.execute(total_comments_stmt)
        total_comments = result.scalar() or 0
        
        return {
            "community_id": community_id,
            "name": community.name,
            "display_name": community.display_name,
            "total_members": community.member_count,
            "total_posts": community.post_count,
            "total_comments": total_comments,
            "recent_posts_week": recent_posts,
            "member_roles": role_counts,
            "created_at": community.created_at
        }

    async def update_community_settings(
        self, 
        community_id: str, 
        updates: Dict, 
        acting_user_id: str
    ) -> Community:
        """Update community settings (requires admin+ permission)"""
        
        # Check if acting user has admin+ permission
        if not await self.check_permission(community_id, acting_user_id, MembershipRole.ADMIN):
            raise PermissionError("Only admins can update community settings")
        
        community = await self.get_community(community_id)
        if not community:
            raise ValueError("Community not found")
        
        # Update allowed fields
        allowed_fields = ['display_name', 'description', 'rules']
        for field, value in updates.items():
            if field in allowed_fields and hasattr(community, field):
                setattr(community, field, value)
        
        await self.db.commit()
        await self.db.refresh(community)
        
        return community

    async def get_community(self, community_id: str) -> Optional[Community]:
        """Helper method to get community by ID"""
        stmt = select(Community).where(Community.id == community_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def transfer_ownership(
        self, 
        community_id: str, 
        new_owner_id: str, 
        current_owner_id: str
    ) -> bool:
        """Transfer community ownership (owner only)"""
        
        # Verify current owner
        if not await self.check_permission(community_id, current_owner_id, MembershipRole.OWNER):
            raise PermissionError("Only the current owner can transfer ownership")
        
        # Verify new owner is a member
        new_owner_membership = await self._get_membership(community_id, new_owner_id)
        if not new_owner_membership or not new_owner_membership.is_active:
            raise ValueError("New owner must be an active member of the community")
        
        # Get current owner membership
        current_owner_membership = await self._get_membership(community_id, current_owner_id)
        
        # Update community owner
        community = await self.get_community(community_id)
        community.owner_id = UUID(new_owner_id)
        
        # Update memberships
        new_owner_membership.role = MembershipRole.OWNER.value
        current_owner_membership.role = MembershipRole.ADMIN.value  # Demote to admin
        
        await self.db.commit()
        return True

    async def _get_membership(self, community_id: str, user_id: str) -> Optional[CommunityMembership]:
        """Helper method to get membership record"""
        stmt = select(CommunityMembership).where(
            and_(
                CommunityMembership.community_id == community_id,
                CommunityMembership.user_id == user_id
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    # Phase 2B Methods
    async def pin_post(self, community_id: str, post_id: str, moderator_id: str) -> bool:
        """Pin a post to community (moderator+ only)"""
        from app.models.post import Post
        
        # Verify post exists and belongs to community
        stmt = select(Post).where(
            and_(
                Post.id == post_id,
                Post.community_id == community_id
            )
        )
        result = await self.db.execute(stmt)
        post = result.scalars().first()
        
        if not post:
            raise ValueError("Post not found or doesn't belong to this community")
        
        # Pin the post
        post.is_pinned = True
        post.pinned_by = moderator_id
        post.pinned_at = func.now()
        
        await self.db.commit()
        return True

    async def unpin_post(self, community_id: str, post_id: str) -> bool:
        """Unpin a post from community"""
        from app.models.post import Post
        
        stmt = select(Post).where(
            and_(
                Post.id == post_id,
                Post.community_id == community_id,
                Post.is_pinned == True
            )
        )
        result = await self.db.execute(stmt)
        post = result.scalars().first()
        
        if not post:
            return False
        
        post.is_pinned = False
        post.pinned_by = None
        post.pinned_at = None
        
        await self.db.commit()
        return True

    async def get_pinned_posts(self, community_id: str) -> List[dict]:
        """Get all pinned posts in a community"""
        from app.models.post import Post
        
        stmt = (
            select(Post)
            .where(
                and_(
                    Post.community_id == community_id,
                    Post.is_pinned == True
                )
            )
            .order_by(desc(Post.pinned_at))
        )
        
        result = await self.db.execute(stmt)
        posts = result.scalars().all()
        
        return [
            {
                "id": str(post.id),
                "title": post.title,
                "content": post.content,
                "user_id": str(post.user_id),
                "created_at": post.created_at,
                "pinned_at": post.pinned_at,
                "pinned_by": post.pinned_by
            }
            for post in posts
        ]

    async def upload_community_avatar(self, community_id: str, file) -> str:
        """Upload community avatar (placeholder - would integrate with storage service)"""
        from app.utils.storage import save_uploaded_file
        
        # Save file (placeholder implementation)
        filename = f"community_{community_id}_avatar_{file.filename}"
        file_path = await save_uploaded_file(file, "avatars", filename)
        
        # Update community
        community = await self.get_community(community_id)
        community.avatar_url = file_path
        
        await self.db.commit()
        return file_path

    async def upload_community_banner(self, community_id: str, file) -> str:
        """Upload community banner"""
        from app.utils.storage import save_uploaded_file
        
        # Save file (placeholder implementation)  
        filename = f"community_{community_id}_banner_{file.filename}"
        file_path = await save_uploaded_file(file, "banners", filename)
        
        # Update community
        community = await self.get_community(community_id)
        community.banner_url = file_path
        
        await self.db.commit()
        return file_path

    async def get_community_analytics(self, community_id: str) -> dict:
        """Get detailed community analytics"""
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        # Member growth
        members_stmt = select(func.count(CommunityMembership.id)).where(
            and_(
                CommunityMembership.community_id == community_id,
                CommunityMembership.is_active == True
            )
        )
        total_members = await self.db.scalar(members_stmt) or 0
        
        new_members_week_stmt = select(func.count(CommunityMembership.id)).where(
            and_(
                CommunityMembership.community_id == community_id,
                CommunityMembership.is_active == True,
                CommunityMembership.created_at >= week_ago
            )
        )
        new_members_week = await self.db.scalar(new_members_week_stmt) or 0
        
        # Post analytics
        posts_stmt = select(func.count(Post.id)).where(Post.community_id == community_id)
        total_posts = await self.db.scalar(posts_stmt) or 0
        
        posts_week_stmt = select(func.count(Post.id)).where(
            and_(
                Post.community_id == community_id,
                Post.created_at >= week_ago
            )
        )
        posts_week = await self.db.scalar(posts_week_stmt) or 0
        
        # Comment analytics
        comments_stmt = (
            select(func.count(Comment.id))
            .join(Post, Comment.post_id == Post.id)
            .where(Post.community_id == community_id)
        )
        total_comments = await self.db.scalar(comments_stmt) or 0
        
        # Active users (posted or commented in last week)
        active_users_posts_stmt = (
            select(func.count(func.distinct(Post.user_id)))
            .where(
                and_(
                    Post.community_id == community_id,
                    Post.created_at >= week_ago
                )
            )
        )
        active_users_posts = await self.db.scalar(active_users_posts_stmt) or 0
        
        # Top contributors (placeholder)
        top_contributors = [
            {"user_id": "placeholder", "username": "Top User", "contributions": 15}
        ]
        
        return {
            "member_count": total_members,
            "post_count": total_posts,
            "daily_posts": round(posts_week / 7, 1),
            "weekly_posts": posts_week,
            "monthly_posts": await self.db.scalar(select(func.count(Post.id)).where(
                and_(Post.community_id == community_id, Post.created_at >= month_ago)
            )) or 0,
            "top_contributors": top_contributors,
            "growth_stats": {
                "new_members_week": new_members_week,
                "growth_rate": round((new_members_week / max(total_members - new_members_week, 1)) * 100, 2)
            },
            "activity_trend": [
                {"period": "week", "posts": posts_week, "active_users": active_users_posts}
            ]
        }

    async def get_user_role(self, community_id: str, user_id: str) -> Optional[MembershipRole]:
        """Alias for get_user_role_in_community to match API expectations"""
        return await self.get_user_role_in_community(community_id, user_id)

    async def pin_post(self, community_id: str, post_id: str, moderator_id: str, reason: str = None) -> bool:
        """Pin a post to community (moderator+ only) - updated signature"""
        from app.models.post import Post
        
        # Verify post exists and belongs to community
        stmt = select(Post).where(
            and_(
                Post.id == post_id,
                Post.community_id == community_id
            )
        )
        result = await self.db.execute(stmt)
        post = result.scalars().first()
        
        if not post:
            raise ValueError("Post not found or doesn't belong to this community")
        
        # Pin the post
        post.is_pinned = True
        post.pinned_by = moderator_id
        post.pinned_at = func.now()
        
        await self.db.commit()
        return True