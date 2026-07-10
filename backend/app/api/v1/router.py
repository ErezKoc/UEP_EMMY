from fastapi import APIRouter

from app.api.v1 import analysis, posts

api_router = APIRouter()
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts"])
