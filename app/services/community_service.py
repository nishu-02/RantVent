from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from typing import Optional, List

from app.models.community import Community, CommunityType
from app.models.community_membership import CommunityMembership, MembershipRole
from app.models.user import User
from app.schemas.community import CommunityCreate, CommunityUpdate


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
                role=MembershipRole.OWNER.value,
            )
            self.db.add(membership)
            await self.db.commit()

        except IntegrityError:
            await self.db.rollback()
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
    