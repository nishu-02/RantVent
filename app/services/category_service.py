from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.models.community import CommunityCategory
from app.models.community import Community


class CategoryService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_all_categories(self) -> List[CommunityCategory]:
        """Get all active categories"""
        stmt = (
            select(CommunityCategory)
            .where(CommunityCategory.is_active == True)
            .order_by(CommunityCategory.sort_order, CommunityCategory.name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_category_by_id(self, category_id: str) -> Optional[CommunityCategory]:
        """Get category by ID"""
        stmt = select(CommunityCategory).where(CommunityCategory.id == category_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_categories_with_counts(self) -> List[dict]:
        """Get categories with their community counts"""
        stmt = (
            select(
                CommunityCategory,
                func.count(Community.id).label('community_count')
            )
            .outerjoin(Community, Community.category_id == CommunityCategory.id)
            .where(CommunityCategory.is_active == True)
            .group_by(CommunityCategory.id)
            .order_by(CommunityCategory.sort_order, CommunityCategory.name)
        )
        result = await self.db.execute(stmt)
        
        categories = []
        for category, count in result.all():
            category_dict = {
                "id": str(category.id),
                "name": category.name,
                "display_name": category.display_name,
                "description": category.description,
                "icon": category.icon,
                "community_count": count or 0
            }
            categories.append(category_dict)
        
        return categories