"""Repository management REST endpoints."""
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_custom_github_token, verify_api_key
from app.models.schemas import RepositoryCreate, RepositoryDelete, RepositoryUpdate
from app.services.audit import get_audit_service
from app.services.github_service import get_github_service

router = APIRouter(prefix="/api/repos", tags=["Repositories"], dependencies=[Depends(verify_api_key)])


@router.get("")
async def list_repositories(
    visibility: str = Query("all", pattern="^(all|public|private)$"),
    sort: str = Query("updated", pattern="^(created|updated|pushed|full_name)$"),
    direction: str = Query("desc", pattern="^(asc|desc)$"),
    per_page: int = Query(30, ge=1, le=100),
    page: int = Query(1, ge=1),
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> List[Dict[str, Any]]:
    """List repositories for authenticated user."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = {"visibility": visibility, "sort": sort, "direction": direction, "per_page": per_page, "page": page}
    try:
        repos = await gh.list_repositories(
            visibility=visibility,
            sort=sort,
            direction=direction,
            per_page=per_page,
            page=page,
            custom_token=custom_token,
        )
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("list_repositories", "rest", "success", duration_ms, params, f"Loaded {len(repos)} repos")
        return repos
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("list_repositories", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_repository(
    body: RepositoryCreate,
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Dict[str, Any]:
    """Create a new repository."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = body.model_dump()
    try:
        res = await gh.create_repository(
            name=body.name,
            description=body.description,
            private=body.private,
            auto_init=body.auto_init,
            custom_token=custom_token,
        )
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("create_repository", "rest", "success", duration_ms, params, f"Created {res.get('full_name')}")
        return res
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("create_repository", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))


@router.get("/{owner}/{repo}")
async def get_repository(
    owner: str,
    repo: str,
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Dict[str, Any]:
    """Get detailed information about a repository."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = {"owner": owner, "repo": repo}
    try:
        data = await gh.get_repository(owner, repo, custom_token=custom_token)
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("get_repository", "rest", "success", duration_ms, params, f"Retrieved {owner}/{repo}")
        return data
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("get_repository", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))


@router.patch("/{owner}/{repo}")
async def update_repository(
    owner: str,
    repo: str,
    body: RepositoryUpdate,
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Dict[str, Any]:
    """Update repository settings."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = {"owner": owner, "repo": repo, **body.model_dump(exclude_unset=True)}
    try:
        res = await gh.update_repository(
            owner=owner,
            repo=repo,
            name=body.name,
            description=body.description,
            private=body.private,
            custom_token=custom_token,
        )
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("update_repository", "rest", "success", duration_ms, params, f"Updated {owner}/{repo}")
        return res
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("update_repository", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))


@router.delete("/{owner}/{repo}")
async def delete_repository(
    owner: str,
    repo: str,
    confirm: Optional[str] = Query(None, description="Repository name for confirmation"),
    body: Optional[RepositoryDelete] = None,
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Dict[str, Any]:
    """Delete a repository with required confirmation."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    provided_confirm = confirm or (body.confirm_name if body else None)
    params = {"owner": owner, "repo": repo, "confirm": provided_confirm}

    if provided_confirm != repo:
        err_msg = f"Confirmation failed: confirm value '{provided_confirm}' must match repository name '{repo}'"
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("delete_repository", "rest", "error", duration_ms, params, error=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    try:
        await gh.delete_repository(owner, repo, custom_token=custom_token)
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("delete_repository", "rest", "success", duration_ms, params, f"Deleted {owner}/{repo}")
        return {"status": "deleted", "repository": f"{owner}/{repo}", "success": True}
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("delete_repository", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))
