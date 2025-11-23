import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import create_tables
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.communities import router as communities_router
from app.api.community_management import router as community_management_router
from app.api.posts import router as posts_router
from app.api.comments import router as comments_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="RantVent API",
        version="1.1.1",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # -------------------------------------
    # CORS
    # -------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -------------------------------------
    # Routing
    # -------------------------------------
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(communities_router)
    app.include_router(community_management_router)
    app.include_router(posts_router)
    app.include_router(comments_router)

    # -------------------------------------
    # Startup event
    # -------------------------------------
    @app.on_event("startup")
    async def startup_event():
        logging.info("Server starting...")
        if settings.DEBUG:
            logging.info("DEBUG MODE — Creating DB tables (dev mode)")
            await create_tables()

    @app.on_event("shutdown")
    async def shutdown_event():
        logging.info("Server shutting down...")

    return app


app = create_app()
