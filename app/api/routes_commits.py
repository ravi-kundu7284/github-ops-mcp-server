"""Commit management REST endpoints."""
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_custom_github_token, verify_api_key
from app.services.audit import get_audit_service
from app.services.github_service import get_github_service

router = APIRouter(prefix="/api/repos/{owner}/{repo}/commits", tags=["Commits"], dependencies=[Depends(verify_api_key)])


@router.get("")
async def list_commits(
    owner: str,
    repo: str,
    sha: Optional[str] = Query(None),
    path: Optional[str] = Query(None),
    author: Optional[str] = Query(None),
    per_page: int = Query(30, ge=1, le=100),
    page: int = Query(1, ge=1),
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> List[Dict[str, Any]]:
    """List repository commits."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = {"owner": owner, "repo": repo, "sha": sha, "path": path, "author": author, "per_page": per_page, "page": page}
    try:
        commits = await gh.list_commits(
            owner=owner,
            repo=repo,
            sha=sha,
            path=path,
            author=author,
            per_page=per_page,
            page=page,
            custom_token=custom_token,
        )
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("list_commits", "rest", "success", duration_ms, params, f"Loaded {len(commits)} commits")
        return commits
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("list_commits", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))


@router.get("/{sha}")
async def get_commit(
    owner: str,
    repo: str,
    sha: str,
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Dict[str, Any]:
    """Get commit details including diff stats and files."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = {"owner": owner, "repo": repo, "sha": sha}
    try:
        commit = await gh.get_commit(owner, repo, sha, custom_token=custom_token)
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("get_commit", "rest", "success", duration_ms, params, f"Loaded commit {sha[:7]}")
        return commit
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("get_commit", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))
