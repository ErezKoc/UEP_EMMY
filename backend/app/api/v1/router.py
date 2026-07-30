from fastapi import APIRouter

from app.api.v1 import analysis, animals, auth, posts, users, verification, vets

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(animals.router, prefix="/animals", tags=["animals"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts"])
api_router.include_router(vets.router, prefix="/vets", tags=["vets"])
api_router.include_router(verification.router, prefix="/verification", tags=["verification"])
