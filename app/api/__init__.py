"""API router aggregator."""
from fastapi import APIRouter

from app.api.routes_audit import router as audit_router
from app.api.routes_auth import router as auth_router
from app.api.routes_branches import router as branches_router
from app.api.routes_commits import router as commits_router
from app.api.routes_files import router as files_router
from app.api.routes_issues import router as issues_router
from app.api.routes_pulls import router as pulls_router
from app.api.routes_repos import router as repos_router
from app.api.routes_search import router as search_router
from app.api.routes_workflows import router as workflows_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(repos_router)
api_router.include_router(branches_router)
api_router.include_router(pulls_router)
api_router.include_router(issues_router)
api_router.include_router(commits_router)
api_router.include_router(files_router)
api_router.include_router(workflows_router)
api_router.include_router(search_router)
api_router.include_router(audit_router)

__all__ = ["api_router"]
