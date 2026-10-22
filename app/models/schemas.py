"""Pydantic Data Models and Validation Schemas.

This module defines all request bodies, query models, responses, and audit
data structures used across the FastAPI REST endpoints and MCP tool implementations.
Strong typing and runtime validation via Pydantic v2 ensures strict contract compliance.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Audit & Operation Telemetry Models
# ---------------------------------------------------------------------------

class OperationLog(BaseModel):
    """Represents a single recorded action dispatched by either REST or MCP.

    Used to provide an audit trail of every GitHub operation, its latency,
    the parameters supplied (scrubbed of tokens), and execution outcome.
    """
    id: str = Field(
        description="Unique UUID identifying this specific operation execution",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the operation was recorded",
    )
    operation: str = Field(
        description="Name of the API endpoint or MCP tool executed (e.g. 'list_repositories')",
    )
    channel: Literal["rest", "mcp"] = Field(
        description="The interface channel through which the action was invoked",
    )
    status: Literal["success", "error", "pending"] = Field(
        description="Outcome of the operation ('success', 'error', or 'pending')",
    )
    duration_ms: float = Field(
        default=0.0,
        description="Round-trip execution duration in milliseconds",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Sanitized input arguments (sensitive fields like tokens are masked)",
    )
    result_summary: Optional[str] = Field(
        default=None,
        description="Short human-readable summary of the successful result",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message and diagnostic explanation if the action failed",
    )


# ---------------------------------------------------------------------------
# Repository Request Models
# ---------------------------------------------------------------------------

class RepositoryCreate(BaseModel):
    """Payload for creating a new repository under the authenticated user account."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="The desired name of the new repository (e.g. 'my-awesome-project')",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional brief description of the project purpose",
    )
    private: bool = Field(
        default=False,
        description="Whether the repository should be private (true) or public (false)",
    )
    auto_init: bool = Field(
        default=True,
        description="Initialize repository with an initial commit containing a README.md",
    )


class RepositoryUpdate(BaseModel):
    """Payload for updating an existing repository's metadata or visibility."""
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="New name for the repository (renames repository if changed)",
    )
    description: Optional[str] = Field(
        default=None,
        description="Updated description text",
    )
    private: Optional[bool] = Field(
        default=None,
        description="Change repository visibility between public and private",
    )


class RepositoryDelete(BaseModel):
    """Payload for confirming the destructive deletion of a repository."""
    confirm_name: str = Field(
        ...,
        description="Safety verification challenge: must match the repository name verbatim",
    )


# ---------------------------------------------------------------------------
# Branch Management Models
# ---------------------------------------------------------------------------

class BranchCreate(BaseModel):
    """Payload for branching a repository."""
    branch: str = Field(
        ...,
        min_length=1,
        description="The name of the new branch to create (e.g. 'feature/login-page')",
    )
    from_branch: Optional[str] = Field(
        default=None,
        description="Source branch name or 40-character commit SHA (defaults to repository default branch)",
    )


# ---------------------------------------------------------------------------
# Pull Request Request Models
# ---------------------------------------------------------------------------

class PullRequestCreate(BaseModel):
    """Payload for opening a new pull request between two branches."""
    title: str = Field(
        ...,
        min_length=1,
        description="Pull request headline title summarizing the changes",
    )
    head: str = Field(
        ...,
        description="Branch containing the modifications you want to merge (e.g. 'feature-branch')",
    )
    base: str = Field(
        ...,
        description="Target branch into which the changes should be incorporated (e.g. 'main')",
    )
    body: Optional[str] = Field(
        default=None,
        description="Extended markdown description explaining context, issues fixed, or testing notes",
    )
    draft: bool = Field(
        default=False,
        description="Whether to open the PR as a draft (cannot be merged until marked ready)",
    )


class PullRequestReview(BaseModel):
    """Payload for submitting a review on an existing pull request."""
    event: Literal["APPROVE", "REQUEST_CHANGES", "COMMENT"] = Field(
        ...,
        description="The review action: 'APPROVE' to approve, 'REQUEST_CHANGES' to block, 'COMMENT' for general feedback",
    )
    body: str = Field(
        ...,
        min_length=1,
        description="Review commentary text provided to the PR author",
    )


class PullRequestMerge(BaseModel):
    """Payload for merging an approved pull request into the target branch."""
    commit_title: Optional[str] = Field(
        default=None,
        description="Title for the merge commit message (defaults to GitHub automatic title)",
    )
    commit_message: Optional[str] = Field(
        default=None,
        description="Extended commit message details",
    )
    merge_method: Literal["merge", "squash", "rebase"] = Field(
        default="merge",
        description="The merge strategy: 'merge' (creates merge commit), 'squash' (combines commits), or 'rebase'",
    )


# ---------------------------------------------------------------------------
# Issue Request Models
# ---------------------------------------------------------------------------

class IssueCreate(BaseModel):
    """Payload for creating a new issue in a repository."""
    title: str = Field(
        ...,
        min_length=1,
        description="The title of the issue",
    )
    body: Optional[str] = Field(
        default=None,
        description="The issue description in GitHub Flavored Markdown",
    )
    assignees: Optional[List[str]] = Field(
        default=None,
        description="List of GitHub usernames to assign to this issue",
    )
    labels: Optional[List[str]] = Field(
        default=None,
        description="List of label names to attach to the issue (e.g. ['bug', 'help wanted'])",
    )


class IssueUpdate(BaseModel):
    """Payload for updating an existing issue."""
    title: Optional[str] = Field(
        default=None,
        description="Updated issue title",
    )
    body: Optional[str] = Field(
        default=None,
        description="Updated issue markdown description",
    )
    state: Optional[Literal["open", "closed"]] = Field(
        default=None,
        description="Transition issue state between 'open' and 'closed'",
    )
    assignees: Optional[List[str]] = Field(
        default=None,
        description="Updated list of assigned GitHub usernames",
    )
    labels: Optional[List[str]] = Field(
        default=None,
        description="Updated list of label strings",
    )


class IssueClose(BaseModel):
    """Payload for closing an issue with an optional closing remark."""
    comment: Optional[str] = Field(
        default=None,
        description="Optional comment explaining resolution before closing",
    )


# ---------------------------------------------------------------------------
# File & Repository Contents Models
# ---------------------------------------------------------------------------

class FileCreateOrUpdate(BaseModel):
    """Payload for creating or updating a file in the repository tree."""
    message: str = Field(
        ...,
        min_length=1,
        description="Commit message recording the change (e.g. 'feat: add auth middleware')",
    )
    content: str = Field(
        ...,
        description="The contents of the file (UTF-8 plain text or base64 encoded string)",
    )
    is_base64: bool = Field(
        default=False,
        description="Set to true if content is already base64 encoded (useful for binaries)",
    )
    sha: Optional[str] = Field(
        default=None,
        description="The blob SHA of the file being overwritten. Required by GitHub when updating an existing file.",
    )
    branch: Optional[str] = Field(
        default=None,
        description="Branch name to commit to (defaults to repository default branch)",
    )


# ---------------------------------------------------------------------------
# Global Search Models
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    """Query parameters for global GitHub entity search."""
    query: str = Field(
        ...,
        min_length=1,
        description="Search query string (supports GitHub search syntax like 'language:python')",
    )
    search_type: Literal["repositories", "issues", "pullrequests", "commits", "users", "code"] = Field(
        default="repositories",
        description="The entity category to query",
    )
    per_page: int = Field(default=30, ge=1, le=100, description="Items returned per page")
    page: int = Field(default=1, ge=1, description="Page index number")


# ---------------------------------------------------------------------------
# Health & Rate Limit System Models
# ---------------------------------------------------------------------------

class RateLimitInfo(BaseModel):
    """Rate limit quota details extracted from GitHub response headers."""
    limit: int = Field(description="Total requests allowed per hour window")
    remaining: int = Field(description="Requests remaining in the current hourly window")
    reset_timestamp: int = Field(description="Unix epoch timestamp when quota resets")
    used: int = Field(description="Total requests consumed so far")


class HealthResponse(BaseModel):
    """Application health and connection diagnostic report."""
    status: str = Field(default="ok", description="Server health status indicator")
    version: str = Field(description="Application version number")
    environment: str = Field(description="Active runtime environment")
    github_connected: bool = Field(description="Whether a valid connection to GitHub API is verified")
    authenticated_user: Optional[str] = Field(
        default=None,
        description="GitHub username associated with the active token",
    )
