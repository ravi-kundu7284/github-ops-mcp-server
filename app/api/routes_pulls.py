"""Pull Request management REST endpoints."""
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_custom_github_token, verify_api_key
from app.models.schemas import PullRequestCreate, PullRequestMerge, PullRequestReview
from app.services.audit import get_audit_service
from app.services.github_service import get_github_service

router = APIRouter(prefix="/api/repos/{owner}/{repo}/pulls", tags=["Pull Requests"], dependencies=[Depends(verify_api_key)])


@router.get("")
async def list_pull_requests(
    owner: str,
    repo: str,
    state: str = Query("open", pattern="^(open|closed|all)$"),
    sort: str = Query("created", pattern="^(created|updated|popularity|long-running)$"),
    direction: str = Query("desc", pattern="^(asc|desc)$"),
    per_page: int = Query(30, ge=1, le=100),
    page: int = Query(1, ge=1),
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> List[Dict[str, Any]]:
    """List pull requests for a repository."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = {"owner": owner, "repo": repo, "state": state, "sort": sort, "direction": direction, "per_page": per_page, "page": page}
    try:
        prs = await gh.list_pull_requests(
            owner=owner,
            repo=repo,
            state=state,
            sort=sort,
            direction=direction,
            per_page=per_page,
            page=page,
            custom_token=custom_token,
        )
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("list_pull_requests", "rest", "success", duration_ms, params, f"Loaded {len(prs)} PRs")
        return prs
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("list_pull_requests", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_pull_request(
    owner: str,
    repo: str,
    body: PullRequestCreate,
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Dict[str, Any]:
    """Create a new pull request."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = {"owner": owner, "repo": repo, **body.model_dump()}
    try:
        res = await gh.create_pull_request(
            owner=owner,
            repo=repo,
            title=body.title,
            head=body.head,
            base=body.base,
            body=body.body,
            draft=body.draft,
            custom_token=custom_token,
        )
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("create_pull_request", "rest", "success", duration_ms, params, f"Created PR #{res.get('number')}")
        return res
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("create_pull_request", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))


@router.get("/{pull_number}")
async def get_pull_request(
    owner: str,
    repo: str,
    pull_number: int,
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Dict[str, Any]:
    """Get pull request details."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = {"owner": owner, "repo": repo, "pull_number": pull_number}
    try:
        res = await gh.get_pull_request(owner, repo, pull_number, custom_token=custom_token)
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("get_pull_request", "rest", "success", duration_ms, params, f"Loaded PR #{pull_number}")
        return res
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("get_pull_request", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))


@router.post("/{pull_number}/reviews")
async def review_pull_request(
    owner: str,
    repo: str,
    pull_number: int,
    body: PullRequestReview,
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Dict[str, Any]:
    """Submit a review on a pull request."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = {"owner": owner, "repo": repo, "pull_number": pull_number, "event": body.event}
    try:
        res = await gh.review_pull_request(
            owner=owner,
            repo=repo,
            pull_number=pull_number,
            event=body.event,
            body=body.body,
            custom_token=custom_token,
        )
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("review_pull_request", "rest", "success", duration_ms, params, f"Reviewed PR #{pull_number}")
        return res
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("review_pull_request", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))


@router.put("/{pull_number}/merge")
async def merge_pull_request(
    owner: str,
    repo: str,
    pull_number: int,
    body: PullRequestMerge,
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Dict[str, Any]:
    """Merge a pull request."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = {"owner": owner, "repo": repo, "pull_number": pull_number, "merge_method": body.merge_method}
    try:
        res = await gh.merge_pull_request(
            owner=owner,
            repo=repo,
            pull_number=pull_number,
            commit_title=body.commit_title,
            commit_message=body.commit_message,
            merge_method=body.merge_method,
            custom_token=custom_token,
        )
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("merge_pull_request", "rest", "success", duration_ms, params, f"Merged PR #{pull_number}")
        return res
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("merge_pull_request", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))
