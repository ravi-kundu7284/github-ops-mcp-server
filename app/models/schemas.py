"""Pydantic schemas and request/response models."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Audit & Operations
# ---------------------------------------------------------------------------

class OperationLog(BaseModel):
    """Log entry representing an executed operation."""
    id: str = Field(description="Unique operation identifier")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="UTC timestamp")
    operation: str = Field(description="Name of the operation/tool")
    channel: Literal["rest", "mcp"] = Field(description="Channel: REST API or MCP tool")
    status: Literal["success", "error", "pending"] = Field(description="Execution status")
    duration_ms: float = Field(default=0.0, description="Duration in milliseconds")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Sanitized parameters")
    result_summary: Optional[str] = Field(default=None, description="Short summary of the result")
    error: Optional[str] = Field(default=None, description="Error message if failed")


# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------

class RepositoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Repository name")
    description: Optional[str] = Field(default=None, description="Short description")
    private: bool = Field(default=False, description="Whether the repository is private")
    auto_init: bool = Field(default=True, description="Create an initial commit with empty README")


class RepositoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, description="New repository name")
    description: Optional[str] = Field(default=None, description="New description")
    private: Optional[bool] = Field(default=None, description="Toggle private/public status")


class RepositoryDelete(BaseModel):
    confirm_name: str = Field(..., description="Confirmation: must match the repository name exactly")


# ---------------------------------------------------------------------------
# Branches
# ---------------------------------------------------------------------------

class BranchCreate(BaseModel):
    branch: str = Field(..., min_length=1, description="Name of the new branch")
    from_branch: Optional[str] = Field(
        default=None,
        description="Source branch or SHA to branch from (defaults to default branch)",
    )


# ---------------------------------------------------------------------------
# Pull Requests
# ---------------------------------------------------------------------------

class PullRequestCreate(BaseModel):
    title: str = Field(..., min_length=1, description="Pull request title")
    head: str = Field(..., description="Branch containing your changes")
    base: str = Field(..., description="Branch you want to merge into")
    body: Optional[str] = Field(default=None, description="Pull request body/description")
    draft: bool = Field(default=False, description="Create as draft pull request")


class PullRequestReview(BaseModel):
    event: Literal["APPROVE", "REQUEST_CHANGES", "COMMENT"] = Field(
        ..., description="The review action to perform"
    )
    body: str = Field(..., min_length=1, description="The body text of the pull request review")


class PullRequestMerge(BaseModel):
    commit_title: Optional[str] = Field(default=None, description="Title for the merge commit")
    commit_message: Optional[str] = Field(default=None, description="Extra detail for the merge commit")
    merge_method: Literal["merge", "squash", "rebase"] = Field(
        default="merge", description="Merge method to use"
    )


# ---------------------------------------------------------------------------
# Issues
# ---------------------------------------------------------------------------

class IssueCreate(BaseModel):
    title: str = Field(..., min_length=1, description="The title of the issue")
    body: Optional[str] = Field(default=None, description="The contents of the issue")
    assignees: Optional[List[str]] = Field(default=None, description="Usernames to assign")
    labels: Optional[List[str]] = Field(default=None, description="Labels to associate")


class IssueUpdate(BaseModel):
    title: Optional[str] = Field(default=None, description="New title")
    body: Optional[str] = Field(default=None, description="New body")
    state: Optional[Literal["open", "closed"]] = Field(default=None, description="Issue state")
    assignees: Optional[List[str]] = Field(default=None, description="Assigned usernames")
    labels: Optional[List[str]] = Field(default=None, description="Labels")


class IssueClose(BaseModel):
    comment: Optional[str] = Field(default=None, description="Optional closing comment")


# ---------------------------------------------------------------------------
# Files & Contents
# ---------------------------------------------------------------------------

class FileCreateOrUpdate(BaseModel):
    message: str = Field(..., min_length=1, description="Commit message")
    content: str = Field(..., description="File content (plain text utf-8 or base64)")
    is_base64: bool = Field(default=False, description="Whether content is already base64 encoded")
    sha: Optional[str] = Field(
        default=None,
        description="The blob SHA of the file being replaced. Required when updating an existing file.",
    )
    branch: Optional[str] = Field(default=None, description="Branch to commit to (defaults to default branch)")


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query string")
    search_type: Literal["repositories", "issues", "pullrequests", "commits", "users", "code"] = Field(
        default="repositories", description="Type of resource to search"
    )
    per_page: int = Field(default=30, ge=1, le=100)
    page: int = Field(default=1, ge=1)


# ---------------------------------------------------------------------------
# System & Rate Limit
# ---------------------------------------------------------------------------

class RateLimitInfo(BaseModel):
    limit: int
    remaining: int
    reset_timestamp: int
    used: int


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    environment: str
    github_connected: bool
    authenticated_user: Optional[str] = None
