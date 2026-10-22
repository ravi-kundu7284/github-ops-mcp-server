"""Search REST endpoints."""
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_custom_github_token, verify_api_key
from app.services.audit import get_audit_service
from app.services.github_service import get_github_service

router = APIRouter(prefix="/api/search", tags=["Search"], dependencies=[Depends(verify_api_key)])


@router.get("")
async def search_github(
    q: str = Query(..., min_length=1, description="Search query string"),
    type: str = Query("repositories", pattern="^(repositories|repos|issues|issue|pullrequests|pulls|prs|commits|commit|code|users|user)$"),
    per_page: int = Query(30, ge=1, le=100),
    page: int = Query(1, ge=1),
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Dict[str, Any]:
    """Search GitHub for repositories, issues, PRs, commits, code, or users."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = {"query": q, "search_type": type, "per_page": per_page, "page": page}
    try:
        res = await gh.search_github(query=q, search_type=type, per_page=per_page, page=page, custom_token=custom_token)
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("search_github", "rest", "success", duration_ms, params, f"Found {res.get('total_count', 0)} items")
        return res
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("search_github", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))
