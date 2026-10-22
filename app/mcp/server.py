"""Model Context Protocol (MCP) Server for GitHub Operations.

This module initializes the official Model Context Protocol server using the Python MCP SDK
(`mcp.server.mcpserver.MCPServer`). It exposes 22 comprehensive tools allowing AI agents
(such as Claude Desktop, Cursor, or custom autonomous agents) to inspect, manage, and
automate GitHub workflows, repositories, branches, issues, pull requests, files, and searches.

Key features:
1. Native MCP tool registration using the `@mcp_server.tool()` decorator.
2. Full async execution delegating to the unified `GitHubService` business logic.
3. Automated audit logging of every tool call with latency measurement, parameter
   sanitization, and error tracking.
4. Destructive operation protections (e.g., repository deletion requires explicit confirmation).
"""
import time
from typing import Any, Dict, List, Literal, Optional

from mcp.server.mcpserver import MCPServer

from app.config import get_settings
from app.services.audit import get_audit_service
from app.services.github_service import get_github_service

# Load global application configuration
settings = get_settings()

# Initialize the central MCP server instance
mcp_server = MCPServer(
    name=settings.MCP_SERVER_NAME,
    version=settings.MCP_SERVER_VERSION,
    instructions=(
        "Comprehensive GitHub Operations MCP Server allowing management of repositories, "
        "branches, pull requests, issues, commits, files, workflows, and search."
    ),
)


def _record_audit(
    op_name: str,
    params: Dict[str, Any],
    start_time: float,
    status: Literal["success", "error"],
    summary: Optional[str] = None,
    err_msg: Optional[str] = None,
):
    """Helper utility to measure duration and log MCP tool execution to the audit service.

    Args:
        op_name: Name of the executed MCP tool.
        params: Arguments supplied by the calling MCP client.
        start_time: High-precision timestamp when execution began (from time.perf_counter()).
        status: Either 'success' or 'error'.
        summary: Optional summary of the result for quick human inspection.
        err_msg: Optional error description if an exception was caught.
    """
    audit = get_audit_service()
    duration_ms = (time.perf_counter() - start_time) * 1000
    audit.record(
        operation=op_name,
        channel="mcp",
        status=status,
        duration_ms=duration_ms,
        parameters=params,
        result_summary=summary,
        error=err_msg,
    )


# ---------------------------------------------------------------------------
# Tool 1: list_repositories
# ---------------------------------------------------------------------------
@mcp_server.tool()
async def list_repositories(
    visibility: str = "all",
    sort: str = "updated",
    direction: str = "desc",
    per_page: int = 30,
    page: int = 1,
) -> Dict[str, Any]:
    """List GitHub repositories accessible to the authenticated user.

    Args:
        visibility: Can be 'all', 'public', or 'private'.
        sort: Property to sort by ('created', 'updated', 'pushed', 'full_name').
        direction: Sort direction ('asc' or 'desc').
        per_page: Number of items per page (max 100).
        page: Page number of results.
    """
    t0 = time.perf_counter()
    gh = get_github_service()
    params = locals()
    try:
        repos = await gh.list_repositories(
            visibility=visibility,
            sort=sort,
            direction=direction,
            per_page=per_page,
            page=page,
        )
        res = {
            "total_fetched": len(repos),
            "page": page,
            "per_page": per_page,
            "repositories": [
                {
                    "name": r.get("name"),
                    "full_name": r.get("full_name"),
                    "owner": r.get("owner", {}).get("login"),
                    "private": r.get("private"),
                    "html_url": r.get("html_url"),
                    "description": r.get("description"),
                    "fork": r.get("fork"),
                    "default_branch": r.get("default_branch"),
                    "stargazers_count": r.get("stargazers_count"),
                    "forks_count": r.get("forks_count"),
                    "open_issues_count": r.get("open_issues_count"),
                    "updated_at": r.get("updated_at"),
                }
                for r in repos
            ],
        }
        _record_audit("list_repositories", params, t0, "success", f"Found {len(repos)} repositories")
        return res
    except Exception as exc:
        _record_audit("list_repositories", params, t0, "error", err_msg=str(exc))
        raise


# ---------------------------------------------------------------------------
# Tool 2: get_repository
# ---------------------------------------------------------------------------
@mcp_server.tool()
async def get_repository(owner: str, repo: str) -> Dict[str, Any]:
    """Get detailed information about a GitHub repository.

    Args:
        owner: The account owner of the repository.
        repo: The name of the repository.
    """
    t0 = time.perf_counter()
    gh = get_github_service()
    params = {"owner": owner, "repo": repo}
    try:
        data = await gh.get_repository(owner, repo)
        _record_audit("get_repository", params, t0, "success", f"Loaded repo {owner}/{repo}")
        return data
    except Exception as exc:
        _record_audit("get_repository", params, t0, "error", err_msg=str(exc))
        raise


# ---------------------------------------------------------------------------
# Tool 3: create_repository
# ---------------------------------------------------------------------------
@mcp_server.tool()
async def create_repository(
    name: str,
    description: Optional[str] = None,
    private: bool = False,
    auto_init: bool = True,
) -> Dict[str, Any]:
    """Create a new GitHub repository for the authenticated user.

    Args:
        name: The name of the new repository.
        description: A short description of the repository.
        private: Whether the repository should be private.
        auto_init: Whether to initialize the repository with an initial commit and README.
    """
    t0 = time.perf_counter()
    gh = get_github_service()
    params = {"name": name, "description": description, "private": private, "auto_init": auto_init}
    try:
        res = await gh.create_repository(
            name=name,
            description=description,
            private=private,
            auto_init=auto_init,
        )
        _record_audit("create_repository", params, t0, "success", f"Created repo {res.get('full_name')}")
        return res
    except Exception as exc:
        _record_audit("create_repository", params, t0, "error", err_msg=str(exc))
        raise


# ---------------------------------------------------------------------------
# Tool 4: update_repository
# ---------------------------------------------------------------------------
@mcp_server.tool()
async def update_repository(
    owner: str,
    repo: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    private: Optional[bool] = None,
) -> Dict[str, Any]:
    """Update settings and metadata for a repository.

    Args:
        owner: The account owner of the repository.
        repo: The name of the repository.
        name: New name for the repository (renames repo if changed).
        description: New description.
        private: Change repository visibility.
    """
    t0 = time.perf_counter()
    gh = get_github_service()
    params = {"owner": owner, "repo": repo, "name": name, "description": description, "private": private}
    try:
        res = await gh.update_repository(
            owner=owner,
            repo=repo,
            name=name,
            description=description,
            private=private,
        )
        _record_audit("update_repository", params, t0, "success", f"Updated repo {owner}/{repo}")
        return res
    except Exception as exc:
        _record_audit("update_repository", params, t0, "error", err_msg=str(exc))
        raise


# ---------------------------------------------------------------------------
# Tool 5: delete_repository
# ---------------------------------------------------------------------------
@mcp_server.tool()
async def delete_repository(owner: str, repo: str, confirm: bool = False) -> Dict[str, Any]:
    """Delete a repository. Requires explicit confirm=True as this is a destructive operation.

    Args:
        owner: The account owner of the repository.
        repo: The name of the repository to delete.
        confirm: Confirmation flag. Must be explicitly set to True to execute deletion.
    """
    t0 = time.perf_counter()
    params = {"owner": owner, "repo": repo, "confirm": confirm}
    if not confirm:
        err = "Destructive operation prevented: 'confirm' parameter must be True to delete a repository."
        _record_audit("delete_repository", params, t0, "error", err_msg=err)
        return {"status": "cancelled", "message": err, "deleted": False}

    gh = get_github_service()
    try:
        await gh.delete_repository(owner, repo)
        _record_audit("delete_repository", params, t0, "success", f"Deleted repository {owner}/{repo}")
        return {"status": "deleted", "repository": f"{owner}/{repo}", "deleted": True}
    except Exception as exc:
        _record_audit("delete_repository", params, t0, "error", err_msg=str(exc))
        raise


# ---------------------------------------------------------------------------
# Tool 6: list_branches
# ---------------------------------------------------------------------------
@mcp_server.tool()
async def list_branches(
    owner: str,
    repo: str,
    per_page: int = 30,
    page: int = 1,
) -> Dict[str, Any]:
    """List branches in a repository.

    Args:
        owner: The account owner of the repository.
        repo: The name of the repository.
        per_page: Results per page (max 100).
        page: Page number.
    """
    t0 = time.perf_counter()
    gh = get_github_service()
    params = {"owner": owner, "repo": repo, "per_page": per_page, "page": page}
    try:
        branches = await gh.list_branches(owner, repo, per_page=per_page, page=page)
        _record_audit("list_branches", params, t0, "success", f"Found {len(branches)} branches for {owner}/{repo}")
        return {"owner": owner, "repo": repo, "page": page, "branches": branches}
    except Exception as exc:
        _record_audit("list_branches", params, t0, "error", err_msg=str(exc))
        raise


# ---------------------------------------------------------------------------
# Tool 7: create_branch
# ---------------------------------------------------------------------------
@mcp_server.tool()
async def create_branch(
    owner: str,
    repo: str,
    branch: str,
    from_branch: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new branch from an existing branch or commit SHA.

    Args:
        owner: The account owner of the repository.
        repo: The name of the repository.
        branch: Name of the new branch to create.
        from_branch: Source branch or 40-character commit SHA (defaults to default branch).
    """
    t0 = time.perf_counter()
    gh = get_github_service()
    params = {"owner": owner, "repo": repo, "branch": branch, "from_branch": from_branch}
    try:
        res = await gh.create_branch(owner, repo, branch, from_branch=from_branch)
        _record_audit("create_branch", params, t0, "success", f"Created branch {branch} in {owner}/{repo}")
        return res
    except Exception as exc:
        _record_audit("create_branch", params, t0, "error", err_msg=str(exc))
        raise


# ---------------------------------------------------------------------------
# Tool 8: list_pull_requests
# ---------------------------------------------------------------------------
@mcp_server.tool()
async def list_pull_requests(
    owner: str,
    repo: str,
    state: str = "open",
    sort: str = "created",
    direction: str = "desc",
    per_page: int = 30,
    page: int = 1,
) -> Dict[str, Any]:
    """List pull requests in a repository.

    Args:
        owner: Repository owner.
        repo: Repository name.
        state: 'open', 'closed', or 'all'.
        sort: 'created', 'updated', 'popularity', 'long-running'.
        direction: 'asc' or 'desc'.
        per_page: Items per page.
        page: Page number.
    """
    t0 = time.perf_counter()
    gh = get_github_service()
    params = locals()
    try:
        prs = await gh.list_pull_requests(
            owner=owner,
            repo=repo,
            state=state,
            sort=sort,
            direction=direction,
            per_page=per_page,
            page=page,
        )
        _record_audit("list_pull_requests", params, t0, "success", f"Found {len(prs)} pull requests")
        return {"owner": owner, "repo": repo, "page": page, "pull_requests": prs}
    except Exception as exc:
        _record_audit("list_pull_requests", params, t0, "error", err_msg=str(exc))
        raise


# ---------------------------------------------------------------------------
# Tool 9: create_pull_request
# ---------------------------------------------------------------------------
@mcp_server.tool()
async def create_pull_request(
    owner: str,
    repo: str,
    title: str,
    head: str,
    base: str,
    body: Optional[str] = None,
    draft: bool = False,
) -> Dict[str, Any]:
    """Create a new pull request.

    Args:
        owner: Repository owner.
        repo: Repository name.
        title: Title of the pull request.
        head: Branch containing the changes.
        base: Target branch into which changes should be merged.
        body: Description or body text of the pull request.
        draft: Whether to open as draft PR.
    """
    t0 = time.perf_counter()
    gh = get_github_service()
    params = {"owner": owner, "repo": repo, "title": title, "head": head, "base": base, "draft": draft}
    try:
        res = await gh.create_pull_request(
            owner=owner,
            repo=repo,
            title=title,
            head=head,
            base=base,
            body=body,
            draft=draft,
        )
        _record_audit("create_pull_request", params, t0, "success", f"Created PR #{res.get('number')}")
        return res
    except Exception as exc:
        _record_audit("create_pull_request", params, t0, "error", err_msg=str(exc))
        raise


# ---------------------------------------------------------------------------
# Tool 10: review_pull_request
# ---------------------------------------------------------------------------
@mcp_server.tool()
async def review_pull_request(
    owner: str,
    repo: str,
    pull_number: int,
    event: str,
    body: str,
) -> Dict[str, Any]:
    """Submit a review on a pull request.

    Args:
        owner: Repository owner.
        repo: Repository name.
        pull_number: The pull request number.
        event: Review action ('APPROVE', 'REQUEST_CHANGES', or 'COMMENT').
        body: Text feedback/comment for the review.
    """
    t0 = time.perf_counter()
    gh = get_github_service()
    params = {"owner": owner, "repo": repo, "pull_number": pull_number, "event": event}
    try:
        res = await gh.review_pull_request(
            owner=owner,
            repo=repo,
            pull_number=pull_number,
            event=event,
            body=body,
        )
        _record_audit("review_pull_request", params, t0, "success", f"Submitted {event} review on PR #{pull_number}")
        return res
    except Exception as exc:
        _record_audit("review_pull_request", params, t0, "error", err_msg=str(exc))
        raise


# ---------------------------------------------------------------------------
# Tool 11: merge_pull_request
# ---------------------------------------------------------------------------
@mcp_server.tool()
async def merge_pull_request(
    owner: str,
    repo: str,
    pull_number: int,
    commit_title: Optional[str] = None,
    commit_message: Optional[str] = None,
    merge_method: str = "merge",
) -> Dict[str, Any]:
    """Merge a pull request.

    Args:
        owner: Repository owner.
        repo: Repository name.
        pull_number: The pull request number.
        commit_title: Title for the merge commit.
        commit_message: Detailed message for the merge commit.
        merge_method: Merge method: 'merge', 'squash', or 'rebase'.
    """
    t0 = time.perf_counter()
    gh = get_github_service()
    params = {"owner": owner, "repo": repo, "pull_number": pull_number, "merge_method": merge_method}
    try:
        res = await gh.merge_pull_request(
            owner=owner,
            repo=repo,
            pull_number=pull_number,
            commit_title=commit_title,
            commit_message=commit_message,
            merge_method=merge_method,
        )
        _record_audit("merge_pull_request", params, t0, "success", f"Merged PR #{pull_number}")
        return res
    except Exception as exc:
        _record_audit("merge_pull_request", params, t0, "error", err_msg=str(exc))
        raise


# ---------------------------------------------------------------------------
# Tool 12: list_issues
# ---------------------------------------------------------------------------
@mcp_server.tool()
async def list_issues(
    owner: str,
    repo: str,
    state: str = "open",
    labels: Optional[str] = None,
    sort: str = "created",
    direction: str = "desc",
    per_page: int = 30,
    page: int = 1,
) -> Dict[str, Any]:
    """List issues in a repository (excluding pull requests).

    Args:
        owner: Repository owner.
        repo: Repository name.
        state: 'open', 'closed', or 'all'.
        labels: Comma-separated list of label names.
        sort: 'created', 'updated', or 'comments'.
        direction: 'asc' or 'desc'.
        per_page: Issues per page.
        page: Page number.
    """
    t0 = time.perf_counter()
    gh = get_github_service()
    params = locals()
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
        )
        _record_audit("list_issues", params, t0, "success", f"Found {len(issues)} issues")
        return {"owner": owner, "repo": repo, "page": page, "issues": issues}
    except Exception as exc:
        _record_audit("list_issues", params, t0, "error", err_msg=str(exc))
        raise


# ---------------------------------------------------------------------------
# Tool 13: create_issue
# ---------------------------------------------------------------------------
@mcp_server.tool()
async def create_issue(
    owner: str,
    repo: str,
    title: str,
    body: Optional[str] = None,
    assignees: Optional[List[str]] = None,
    labels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create a new issue in a repository.

    Args:
        owner: Repository owner.
        repo: Repository name.
        title: Issue title.
        body: Issue description markdown.
        assignees: List of GitHub usernames to assign.
        labels: List of label names to attach.
    """
    t0 = time.perf_counter()
    gh = get_github_service()
    params = {"owner": owner, "repo": repo, "title": title}
    try:
        res = await gh.create_issue(
            owner=owner,
            repo=repo,
            title=title,
            body=body,
            assignees=assignees,
            labels=labels,
        )
        _record_audit("create_issue", params, t0, "success", f"Created issue #{res.get('number')}")
        return res
    except Exception as exc:
        _record_audit("create_issue", params, t0, "error", err_msg=str(exc))
        raise


# ---------------------------------------------------------------------------
# Tool 14: update_issue
# ---------------------------------------------------------------------------
@mcp_server.tool()
async def update_issue(
    owner: str,
    repo: str,
    issue_number: int,
    title: Optional[str] = None,
    body: Optional[str] = None,
    state: Optional[str] = None,
    assignees: Optional[List[str]] = None,
    labels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Update an issue's details, assignees, labels, or state.

    Args:
        owner: Repository owner.
        repo: Repository name.
        issue_number: Issue number.
        title: New title.
        body: New body markdown.
        state: 'open' or 'closed'.
        assignees: New list of assignees.
        labels: New list of labels.
    """
    t0 = time.perf_counter()
    gh = get_github_service()
    params = {"owner": owner, "repo": repo, "issue_number": issue_number, "state": state}
    try:
        res = await gh.update_issue(
            owner=owner,
            repo=repo,
            issue_number=issue_number,
            title=title,
            body=body,
            state=state,
            assignees=assignees,
            labels=labels,
        )
        _record_audit("update_issue", params, t0, "success", f"Updated issue #{issue_number}")
        return res
    except Exception as exc:
        _record_audit("update_issue", params, t0, "error", err_msg=str(exc))
        raise


# ---------------------------------------------------------------------------
# Tool 15: close_issue
# ---------------------------------------------------------------------------
@mcp_server.tool()
async def close_issue(
    owner: str,
    repo: str,
    issue_number: int,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    """Close an issue and optionally leave a closing comment.

    Args:
        owner: Repository owner.
        repo: Repository name.
        issue_number: Issue number.
        comment: Optional comment explaining the closure.
    """
    t0 = time.perf_counter()
    gh = get_github_service()
    params = {"owner": owner, "repo": repo, "issue_number": issue_number}
    try:
        res = await gh.close_issue(
            owner=owner,
            repo=repo,
            issue_number=issue_number,
            comment=comment,
        )
        _record_audit("close_issue", params, t0, "success", f"Closed issue #{issue_number}")
        return res
    except Exception as exc:
        _record_audit("close_issue", params, t0, "error", err_msg=str(exc))
        raise


# ---------------------------------------------------------------------------
# Tool 16: list_commits
# ---------------------------------------------------------------------------
@mcp_server.tool()
async def list_commits(
    owner: str,
    repo: str,
    sha: Optional[str] = None,
    path: Optional[str] = None,
    author: Optional[str] = None,
    per_page: int = 30,
    page: int = 1,
) -> Dict[str, Any]:
    """View commit history for a repository.

    Args:
        owner: Repository owner.
        repo: Repository name.
        sha: SHA or branch to start listing commits from.
        path: Only commits containing this file path.
        author: GitHub login or email address of author.
        per_page: Number of commits per page.
        page: Page number.
    """
    t0 = time.perf_counter()
    gh = get_github_service()
    params = locals()
    try:
        commits = await gh.list_commits(
            owner=owner,
            repo=repo,
            sha=sha,
            path=path,
            author=author,
            per_page=per_page,
            page=page,
        )
        _record_audit("list_commits", params, t0, "success", f"Found {len(commits)} commits")
        return {"owner": owner, "repo": repo, "page": page, "commits": commits}
    except Exception as exc:
        _record_audit("list_commits", params, t0, "error", err_msg=str(exc))
        raise


# ---------------------------------------------------------------------------
# Tool 17: get_file_contents
# ---------------------------------------------------------------------------
@mcp_server.tool()
async def get_file_contents(
    owner: str,
    repo: str,
    path: str = "",
    ref: Optional[str] = None,
) -> Any:
    """Retrieve the contents of a file or directory listing in a repository.

    Args:
        owner: Repository owner.
        repo: Repository name.
        path: File or directory path in the repository (empty for root).
        ref: Commit SHA or branch name (defaults to default branch).
    """
    t0 = time.perf_counter()
    gh = get_github_service()
    params = {"owner": owner, "repo": repo, "path": path, "ref": ref}
    try:
        res = await gh.get_file_contents(owner, repo, path=path, ref=ref)
        summary = f"Retrieved path '{path}'" if path else "Retrieved root directory"
        _record_audit("get_file_contents", params, t0, "success", summary)
        return res
    except Exception as exc:
        _record_audit("get_file_contents", params, t0, "error", err_msg=str(exc))
        raise


# ---------------------------------------------------------------------------
# Tool 18: create_or_update_file
# ---------------------------------------------------------------------------
@mcp_server.tool()
async def create_or_update_file(
    owner: str,
    repo: str,
    path: str,
    message: str,
    content: str,
    sha: Optional[str] = None,
    branch: Optional[str] = None,
) -> Dict[str, Any]:
    """Create or update a file in a repository.

    Args:
        owner: Repository owner.
        repo: Repository name.
        path: Target file path.
        message: Commit message.
        content: The text content to write to the file.
        sha: The blob SHA of the file being replaced (required when updating existing file).
        branch: The branch name (defaults to repository default branch).
    """
    t0 = time.perf_counter()
    gh = get_github_service()
    params = {"owner": owner, "repo": repo, "path": path, "message": message, "branch": branch}
    try:
        res = await gh.create_or_update_file(
            owner=owner,
            repo=repo,
            path=path,
            message=message,
            content=content,
            sha=sha,
            branch=branch,
        )
        action = "Updated" if sha else "Created"
        _record_audit("create_or_update_file", params, t0, "success", f"{action} file '{path}'")
        return res
    except Exception as exc:
        _record_audit("create_or_update_file", params, t0, "error", err_msg=str(exc))
        raise


# ---------------------------------------------------------------------------
# Tool 19: list_workflows
# ---------------------------------------------------------------------------
@mcp_server.tool()
async def list_workflows(owner: str, repo: str) -> Dict[str, Any]:
    """List GitHub Actions workflows for a repository.

    Args:
        owner: Repository owner.
        repo: Repository name.
    """
    t0 = time.perf_counter()
    gh = get_github_service()
    params = {"owner": owner, "repo": repo}
    try:
        res = await gh.list_workflows(owner, repo)
        total = res.get("total_count", 0)
        _record_audit("list_workflows", params, t0, "success", f"Found {total} workflows")
        return res
    except Exception as exc:
        _record_audit("list_workflows", params, t0, "error", err_msg=str(exc))
        raise


# ---------------------------------------------------------------------------
# Tool 20: get_workflow_runs
# ---------------------------------------------------------------------------
@mcp_server.tool()
async def get_workflow_runs(
    owner: str,
    repo: str,
    workflow_id: Optional[str] = None,
    status: Optional[str] = None,
    per_page: int = 30,
    page: int = 1,
) -> Dict[str, Any]:
    """Get workflow execution runs for a repository.

    Args:
        owner: Repository owner.
        repo: Repository name.
        workflow_id: ID or file name of workflow (e.g. 'main.yml'). If omitted, runs for all workflows.
        status: Run status filter ('completed', 'in_progress', 'queued', 'failure', 'success').
        per_page: Results per page.
        page: Page number.
    """
    t0 = time.perf_counter()
    gh = get_github_service()
    params = locals()
    try:
        res = await gh.get_workflow_runs(
            owner=owner,
            repo=repo,
            workflow_id=workflow_id,
            status=status,
            per_page=per_page,
            page=page,
        )
        total = res.get("total_count", 0)
        _record_audit("get_workflow_runs", params, t0, "success", f"Found {total} runs")
        return res
    except Exception as exc:
        _record_audit("get_workflow_runs", params, t0, "error", err_msg=str(exc))
        raise


# ---------------------------------------------------------------------------
# Tool 21: get_workflow_run_logs
# ---------------------------------------------------------------------------
@mcp_server.tool()
async def get_workflow_run_logs(owner: str, repo: str, run_id: int) -> Dict[str, Any]:
    """Get workflow run jobs, steps, and log locations for a specific run.

    Args:
        owner: Repository owner.
        repo: Repository name.
        run_id: Workflow run ID.
    """
    t0 = time.perf_counter()
    gh = get_github_service()
    params = {"owner": owner, "repo": repo, "run_id": run_id}
    try:
        res = await gh.get_workflow_run_logs(owner, repo, run_id)
        _record_audit("get_workflow_run_logs", params, t0, "success", f"Fetched logs/jobs for run {run_id}")
        return res
    except Exception as exc:
        _record_audit("get_workflow_run_logs", params, t0, "error", err_msg=str(exc))
        raise


# ---------------------------------------------------------------------------
# Tool 22: search_github
# ---------------------------------------------------------------------------
@mcp_server.tool()
async def search_github(
    query: str,
    search_type: str = "repositories",
    per_page: int = 30,
    page: int = 1,
) -> Dict[str, Any]:
    """Search GitHub for repositories, issues, pull requests, commits, code, or users.

    Args:
        query: Search keywords or GitHub search syntax (e.g. 'react stars:>1000').
        search_type: 'repositories', 'issues', 'pullrequests', 'commits', 'code', or 'users'.
        per_page: Results per page.
        page: Page number.
    """
    t0 = time.perf_counter()
    gh = get_github_service()
    params = locals()
    try:
        res = await gh.search_github(
            query=query,
            search_type=search_type,
            per_page=per_page,
            page=page,
        )
        total = res.get("total_count", 0)
        _record_audit("search_github", params, t0, "success", f"Found {total} items for '{query}'")
        return res
    except Exception as exc:
        _record_audit("search_github", params, t0, "error", err_msg=str(exc))
        raise
