"""GitHub Actions workflow management REST endpoints."""
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_custom_github_token, verify_api_key
from app.services.audit import get_audit_service
from app.services.github_service import get_github_service

router = APIRouter(prefix="/api/repos/{owner}/{repo}/actions", tags=["Workflows"], dependencies=[Depends(verify_api_key)])


@router.get("/workflows")
async def list_workflows(
    owner: str,
    repo: str,
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Dict[str, Any]:
    """List GitHub Actions workflows for a repository."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = {"owner": owner, "repo": repo}
    try:
        res = await gh.list_workflows(owner, repo, custom_token=custom_token)
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("list_workflows", "rest", "success", duration_ms, params, f"Loaded workflows for {owner}/{repo}")
        return res
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("list_workflows", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))


@router.get("/runs")
async def get_workflow_runs(
    owner: str,
    repo: str,
    workflow_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    per_page: int = Query(30, ge=1, le=100),
    page: int = Query(1, ge=1),
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Dict[str, Any]:
    """Get workflow execution runs."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = {"owner": owner, "repo": repo, "workflow_id": workflow_id, "status": status, "per_page": per_page, "page": page}
    try:
        res = await gh.get_workflow_runs(
            owner=owner,
            repo=repo,
            workflow_id=workflow_id,
            status=status,
            per_page=per_page,
            page=page,
            custom_token=custom_token,
        )
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("get_workflow_runs", "rest", "success", duration_ms, params, f"Loaded {res.get('total_count', 0)} runs")
        return res
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("get_workflow_runs", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))


@router.get("/runs/{run_id}/logs")
async def get_workflow_run_logs(
    owner: str,
    repo: str,
    run_id: int,
    custom_token: Optional[str] = Depends(get_custom_github_token),
) -> Dict[str, Any]:
    """Get workflow run logs and job steps."""
    t0 = time.perf_counter()
    gh = get_github_service()
    audit = get_audit_service()
    params = {"owner": owner, "repo": repo, "run_id": run_id}
    try:
        res = await gh.get_workflow_run_logs(owner, repo, run_id, custom_token=custom_token)
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("get_workflow_run_logs", "rest", "success", duration_ms, params, f"Fetched logs for run {run_id}")
        return res
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        audit.record("get_workflow_run_logs", "rest", "error", duration_ms, params, error=str(exc))
        raise HTTPException(status_code=getattr(exc, "status_code", 500), detail=str(exc))
