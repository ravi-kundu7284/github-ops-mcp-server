"""Branch management REST endpoints."""
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_custom_github_token, verify_api_key
from app.models.schemas import BranchCreate
from app.services.audit import get_audit_service
from app.services.github_service import get_github_service

router = APIRouter(prefix="/api/repos/{owner}/{repo}/branches", tags=["Branches"], dependencies=[Depends(verify_api_key)])


@router.get("")
async def list_branches(
    owner: str,
    repo: str,
    per_page: int = Query(30, ge=1, le=100),
    page: int = Query(1, ge=1),
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> List[Dict[str, Any]]:
    """List branches for a repository."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = {"owner": owner, "repo": repo, "per_page": per_page, "page": page}
    try:
        branches = await gh.list_branches(owner, repo, per_page=per_page, page=page, custom_token=custom_token)
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("list_branches", "rest", "success", duration_ms, params, f"Loaded {len(branches)} branches")
        return branches
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("list_branches", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_branch(
    owner: str,
    repo: str,
    body: BranchCreate,
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Dict[str, Any]:
    """Create a new branch."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = {"owner": owner, "repo": repo, **body.model_dump()}
    try:
        res = await gh.create_branch(
            owner=owner,
            repo=repo,
            branch=body.branch,
            from_branch=body.from_branch,
            custom_token=custom_token,
        )
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("create_branch", "rest", "success", duration_ms, params, f"Created branch {body.branch}")
        return res
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("create_branch", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))
