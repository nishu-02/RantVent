from typing import Any, List

from fastapi import Request, status, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.token import decode_token
from app.dependencies.redis import token_in_blacklist
from app.core.database import get_session
from app.services.user_service import UserService
from app.models.user import User


class TokenBearer(HTTPBearer):
    """ Base class — extracts token, decodes, checks blacklist """

    async def __call__(self, request: Request) -> dict:
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)

        if not credentials or credentials.scheme.lower() != "bearer":
            raise HTTPException(status_code=403, detail="No bearer token provided")

        token = credentials.credentials
        payload = decode_token(token)

        # blacklist check
        jti = payload.get("jti")
        if jti and await token_in_blacklist(jti):
            raise HTTPException(status_code=403, detail="Token revoked")

        self.verify_token_data(payload)

        return payload

    def verify_token_data(self, payload: dict) -> None:
        raise NotImplementedError


class AccessTokenBearer(TokenBearer):
    def verify_token_data(self, payload: dict) -> None:
        if payload.get("refresh"):
            raise HTTPException(status_code=403, detail="Refresh token not allowed")


class RefreshTokenBearer(TokenBearer):
    def verify_token_data(self, payload: dict) -> None:
        if not payload.get("refresh"):
            raise HTTPException(status_code=403, detail="Access token not allowed")


async def get_current_user(
    payload: dict = Depends(AccessTokenBearer()),
    db: AsyncSession = Depends(get_session),
) -> User:
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(401, "Invalid token payload")

    service = UserService(db)
    user = await service.get_by_id(user_id)

    if not user:
        raise HTTPException(404, "User not found")

    return user


class RoleChecker:
    def __init__(self, allowed_roles: List[str]) -> None:
        self.allowed_roles = allowed_roles

    async def __call__(self, current_user: User = Depends(get_current_user)):
        if current_user.role.value not in self.allowed_roles:
            raise HTTPException(403, "Not enough permissions")
        return True


class RoleChecker:
    def __init__(self, allowed_roles: List[str]) -> None:
        self.allowed_roles = allowed_roles
    
    async def __call__(self, current_user: User = Depends(get_current_user)) -> Any:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have enough permissions to access this resource.",
            )
        return True
