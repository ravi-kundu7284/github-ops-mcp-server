"""File and repository content management REST endpoints."""
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_custom_github_token, verify_api_key
from app.models.schemas import FileCreateOrUpdate
from app.services.audit import get_audit_service
from app.services.github_service import get_github_service

router = APIRouter(prefix="/api/repos/{owner}/{repo}/contents", tags=["Files & Contents"], dependencies=[Depends(verify_api_key)])


@router.get("")
async def get_root_contents(
    owner: str,
    repo: str,
    ref: Optional[str] = Query(None),
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Any:
    """Get root directory contents."""
    return await get_file_contents(owner=owner, repo=repo, path="", ref=ref, custom_token=custom_token)


@router.get("/{path:path}")
async def get_file_contents(
    owner: str,
    repo: str,
    path: str = "",
    ref: Optional[str] = Query(None),
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Any:
    """Get contents of file or directory at specified path."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = {"owner": owner, "repo": repo, "path": path, "ref": ref}
    try:
        contents = await gh.get_file_contents(owner, repo, path=path, ref=ref, custom_token=custom_token)
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("get_file_contents", "rest", "success", duration_ms, params, f"Read '{path or 'root'}'")
        return contents
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("get_file_contents", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))


@router.put("/{path:path}")
async def create_or_update_file(
    owner: str,
    repo: str,
    path: str,
    body: FileCreateOrUpdate,
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Dict[str, Any]:
    """Create or update a file in the repository."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = {"owner": owner, "repo": repo, "path": path, "message": body.message, "branch": body.branch}
    try:
        res = await gh.create_or_update_file(
            owner=owner,
            repo=repo,
            path=path,
            message=body.message,
            content=body.content,
            sha=body.sha,
            branch=body.branch,
            is_base64=body.is_base64,
            custom_token=custom_token,
        )
        duration_ms = (time.perf_counter() - t0) * 1000
        action = "Updated" if body.sha else "Created"
        audit.record("create_or_update_file", "rest", "success", duration_ms, params, f"{action} '{path}'")
        return res
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("create_or_update_file", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))
