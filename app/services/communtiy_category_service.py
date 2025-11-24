from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from typing import List, Optional

from app.models.community_category import CommunityCategory
from app.models.community import Community

class CommunityCategoryService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_all_categories(self) -> List[CommunityCategory]:
        """Get all active categories with community counts"""
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
            .outerjoin(Community)
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

    async def create_default_categories(self):
        """Create default categories if none exist"""
        existing = await self.get_all_categories()
        if existing:
            return
        
        default_categories = [
            {
                "name": "general",
                "display_name": "General Discussion",
                "description": "General topics and discussions",
                "icon": "💬",
                "sort_order": 1
            },
            {
                "name": "tech",
                "display_name": "Technology",
                "description": "Tech rants, programming, and digital life",
                "icon": "💻",
                "sort_order": 2
            },
            {
                "name": "health",
                "display_name": "Health & Wellness",
                "description": "Mental health, fitness, and wellbeing",
                "icon": "🏥",
                "sort_order": 3
            },
            {
                "name": "work",
                "display_name": "Work & Career",
                "description": "Job frustrations, career advice, workplace issues",
                "icon": "💼",
                "sort_order": 4
            },
            {
                "name": "relationships",
                "display_name": "Relationships",
                "description": "Family, friends, dating, and social connections",
                "icon": "❤️",
                "sort_order": 5
            },
            {
                "name": "lifestyle",
                "display_name": "Lifestyle",
                "description": "Daily life, hobbies, and personal experiences",
                "icon": "🎨",
                "sort_order": 6
            }
        ]

        for cat_data in default_categories:
            category = CommunityCategory(**cat_data)
            self.db.add(category)

        await self.db.commit()
