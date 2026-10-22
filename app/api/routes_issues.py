"""Issue management REST endpoints."""
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_custom_github_token, verify_api_key
from app.models.schemas import IssueClose, IssueCreate, IssueUpdate
from app.services.audit import get_audit_service
from app.services.github_service import get_github_service

router = APIRouter(prefix="/api/repos/{owner}/{repo}/issues", tags=["Issues"], dependencies=[Depends(verify_api_key)])


@router.get("")
async def list_issues(
    owner: str,
    repo: str,
    state: str = Query("open", pattern="^(open|closed|all)$"),
    labels: Optional[str] = Query(None),
    sort: str = Query("created", pattern="^(created|updated|comments)$"),
    direction: str = Query("desc", pattern="^(asc|desc)$"),
    per_page: int = Query(30, ge=1, le=100),
    page: int = Query(1, ge=1),
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> List[Dict[str, Any]]:
    """List repository issues."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = {"owner": owner, "repo": repo, "state": state, "labels": labels, "sort": sort, "direction": direction, "per_page": per_page, "page": page}
    try:
        issues = await gh.list_issues(
            owner=owner,
            repo=repo,
            state=state,
            labels=labels,
            sort=sort,
            direction=direction,
            per_page=per_page,
            page=page,
            custom_token=custom_token,
        )
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("list_issues", "rest", "success", duration_ms, params, f"Loaded {len(issues)} issues")
        return issues
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("list_issues", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_issue(
    owner: str,
    repo: str,
    body: IssueCreate,
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Dict[str, Any]:
    """Create a new issue."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = {"owner": owner, "repo": repo, **body.model_dump()}
    try:
        res = await gh.create_issue(
            owner=owner,
            repo=repo,
            title=body.title,
            body=body.body,
            assignees=body.assignees,
            labels=body.labels,
            custom_token=custom_token,
        )
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("create_issue", "rest", "success", duration_ms, params, f"Created issue #{res.get('number')}")
        return res
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("create_issue", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))


@router.get("/{issue_number}")
async def get_issue(
    owner: str,
    repo: str,
    issue_number: int,
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Dict[str, Any]:
    """Get issue details."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = {"owner": owner, "repo": repo, "issue_number": issue_number}
    try:
        res = await gh.get_issue(owner, repo, issue_number, custom_token=custom_token)
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("get_issue", "rest", "success", duration_ms, params, f"Loaded issue #{issue_number}")
        return res
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("get_issue", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))


@router.patch("/{issue_number}")
async def update_issue(
    owner: str,
    repo: str,
    issue_number: int,
    body: IssueUpdate,
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Dict[str, Any]:
    """Update issue properties or status."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = {"owner": owner, "repo": repo, "issue_number": issue_number, **body.model_dump(exclude_unset=True)}
    try:
        res = await gh.update_issue(
            owner=owner,
            repo=repo,
            issue_number=issue_number,
            title=body.title,
            body=body.body,
            state=body.state,
            assignees=body.assignees,
            labels=body.labels,
            custom_token=custom_token,
        )
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("update_issue", "rest", "success", duration_ms, params, f"Updated issue #{issue_number}")
        return res
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("update_issue", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))


@router.post("/{issue_number}/close")
async def close_issue(
    owner: str,
    repo: str,
    issue_number: int,
    body: Optional[IssueClose] = None,
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Dict[str, Any]:
    """Close an issue (destructive state transition) with optional comment."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    comment = body.comment if body else None
    params = {"owner": owner, "repo": repo, "issue_number": issue_number, "comment": comment}
    try:
        res = await gh.close_issue(
            owner=owner,
            repo=repo,
            issue_number=issue_number,
            comment=comment,
            custom_token=custom_token,
        )
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("close_issue", "rest", "success", duration_ms, params, f"Closed issue #{issue_number}")
        return res
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("close_issue", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))
