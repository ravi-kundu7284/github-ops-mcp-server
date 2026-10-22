"""Auth and rate limit routes."""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends

from app.api.dependencies import get_custom_github_token, verify_api_key
from app.config import get_settings
from app.services.github_service import get_github_service

router = APIRouter(prefix="/api/auth", tags=["Auth & Status"], dependencies=[Depends(verify_api_key)])


@router.get("/status")
async def get_auth_status(
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Dict[str, Any]:
    """Check GitHub authentication and return user profile information."""
    settings = get_settings()
    gh = get_github_service()
    token_used = bool(custom_token or settings.GITHUB_TOKEN)
    if not token_used:
        return {
            "authenticated": False,
            "message": "No GitHub token configured. Provide GITHUB_TOKEN in env or X-GitHub-Token header.",
            "user": None,
        }

    try:
        user = await gh.get_authenticated_user(custom_token=custom_token)
        return {
            "authenticated": True,
            "user": {
                "login": user.get("login"),
                "id": user.get("id"),
                "avatar_url": user.get("avatar_url"),
                "name": user.get("name"),
                "bio": user.get("bio"),
                "public_repos": user.get("public_repos"),
                "total_private_repos": user.get("total_private_repos", 0),
                "followers": user.get("followers"),
                "following": user.get("following"),
                "html_url": user.get("html_url"),
            },
        }
    except Exception as exc:
        return {
            "authenticated": False,
            "error": str(exc),
            "user": None,
        }


@router.get("/ratelimit")
async def get_ratelimit(
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Dict[str, Any]:
    """Get current GitHub rate limits."""
    gh = get_github_service()
    try:
        data = await gh.get_rate_limit(custom_token=custom_token)
        return data
    except Exception as exc:
        return {"error": str(exc), "cached": gh.last_rate_limit}
