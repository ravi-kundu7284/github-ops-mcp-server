"""GitHub Service layer handling all GitHub REST API interactions."""
import base64
from typing import Any, Dict, List, Optional

import httpx

from app.config import get_settings


class GitHubAPIError(Exception):
    """Base exception for GitHub API errors."""

    def __init__(self, message: str, status_code: int = 500, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


class GitHubAuthError(GitHubAPIError):
    """Authentication or token permission error."""

    def __init__(self, message: str = "GitHub authentication failed or token is missing/invalid", details: Optional[Any] = None):
        super().__init__(message, status_code=401, details=details)


class GitHubNotFoundError(GitHubAPIError):
    """Resource not found."""

    def __init__(self, message: str = "GitHub resource not found", details: Optional[Any] = None):
        super().__init__(message, status_code=404, details=details)


class GitHubRateLimitError(GitHubAPIError):
    """API rate limit exceeded."""

    def __init__(self, message: str = "GitHub API rate limit exceeded", reset_at: Optional[int] = None, details: Optional[Any] = None):
        super().__init__(message, status_code=429, details=details)
        self.reset_at = reset_at


class GitHubValidationError(GitHubAPIError):
    """Validation or unprocessable entity."""

    def __init__(self, message: str = "GitHub validation error", details: Optional[Any] = None):
        super().__init__(message, status_code=422, details=details)


class GitHubService:
    """Async client for GitHub REST API v3."""

    def __init__(self, token: Optional[str] = None, base_url: Optional[str] = None):
        settings = get_settings()
        self.token = token or settings.GITHUB_TOKEN
        self.base_url = (base_url or settings.GITHUB_API_URL).rstrip("/")
        self.last_rate_limit: Dict[str, Any] = {
            "limit": 5000,
            "remaining": 5000,
            "reset": 0,
            "used": 0,
        }

    def _headers(self, custom_token: Optional[str] = None) -> Dict[str, str]:
        token_to_use = custom_token or self.token
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "GitHub-Ops-App/1.0.0",
        }
        if token_to_use:
            headers["Authorization"] = f"Bearer {token_to_use}"
        return headers

    def _update_rate_limits(self, response: httpx.Response) -> None:
        """Extract rate limit headers from response."""
        limit = response.headers.get("x-ratelimit-limit")
        remaining = response.headers.get("x-ratelimit-remaining")
        reset = response.headers.get("x-ratelimit-reset")
        used = response.headers.get("x-ratelimit-used")
        if limit is not None:
            self.last_rate_limit["limit"] = int(limit)
        if remaining is not None:
            self.last_rate_limit["remaining"] = int(remaining)
        if reset is not None:
            self.last_rate_limit["reset"] = int(reset)
        if used is not None:
            self.last_rate_limit["used"] = int(used)

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Any] = None,
        custom_token: Optional[str] = None,
        follow_redirects: bool = True,
    ) -> Any:
        """Execute async HTTP request against GitHub API."""
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
        headers = self._headers(custom_token=custom_token)

        # Filter None params
        if params:
            params = {k: v for k, v in params.items() if v is not None}

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=follow_redirects) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_data,
                )
            except httpx.TimeoutException as exc:
                raise GitHubAPIError("GitHub API request timed out after 30s", status_code=504) from exc
            except httpx.RequestError as exc:
                raise GitHubAPIError(f"GitHub network connection error: {str(exc)}", status_code=502) from exc

        self._update_rate_limits(response)

        # Handle specific error status codes
        if response.status_code == 401 or response.status_code == 403:
            msg = "Authentication failed or token lacks required permissions."
            try:
                err_data = response.json()
                msg = err_data.get("message", msg)
            except Exception:
                err_data = response.text
            if "rate limit" in str(msg).lower():
                raise GitHubRateLimitError(msg, details=err_data)
            raise GitHubAuthError(msg, details=err_data)

        if response.status_code == 404:
            try:
                err_data = response.json()
                msg = err_data.get("message", "Requested GitHub resource not found.")
            except Exception:
                err_data = response.text
                msg = "Requested GitHub resource not found."
            raise GitHubNotFoundError(msg, details=err_data)

        if response.status_code == 422:
            try:
                err_data = response.json()
                msg = err_data.get("message", "Validation failed.")
            except Exception:
                err_data = response.text
                msg = "Validation failed."
            raise GitHubValidationError(msg, details=err_data)

        if response.status_code == 429:
            raise GitHubRateLimitError("GitHub API rate limit reached.", details=response.text)

        if response.status_code >= 400:
            try:
                err_data = response.json()
                msg = err_data.get("message", f"GitHub API error ({response.status_code})")
            except Exception:
                err_data = response.text
                msg = f"GitHub API error ({response.status_code})"
            raise GitHubAPIError(msg, status_code=response.status_code, details=err_data)

        if response.status_code == 204:
            return {"success": True}

        try:
            return response.json()
        except Exception:
            return response.text

    # -----------------------------------------------------------------------
    # Authentication & Rate Limit
    # -----------------------------------------------------------------------

    async def get_authenticated_user(self, custom_token: Optional[str] = None) -> Dict[str, Any]:
        """Fetch the authenticated user profile."""
        return await self._request("GET", "/user", custom_token=custom_token)

    async def get_rate_limit(self, custom_token: Optional[str] = None) -> Dict[str, Any]:
        """Fetch current rate limit status."""
        return await self._request("GET", "/rate_limit", custom_token=custom_token)

    # -----------------------------------------------------------------------
    # Repositories
    # -----------------------------------------------------------------------

    async def list_repositories(
        self,
        visibility: str = "all",
        sort: str = "updated",
        direction: str = "desc",
        per_page: int = 30,
        page: int = 1,
        custom_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List repositories for authenticated user or accessible repos."""
        params = {
            "visibility": visibility,
            "sort": sort,
            "direction": direction,
            "per_page": per_page,
            "page": page,
        }
        res = await self._request("GET", "/user/repos", params=params, custom_token=custom_token)
        return res if isinstance(res, list) else []

    async def get_repository(
        self,
        owner: str,
        repo: str,
        custom_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get repository metadata and settings."""
        return await self._request("GET", f"/repos/{owner}/{repo}", custom_token=custom_token)

    async def create_repository(
        self,
        name: str,
        description: Optional[str] = None,
        private: bool = False,
        auto_init: bool = True,
        custom_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new repository for authenticated user."""
        payload = {
            "name": name,
            "description": description,
            "private": private,
            "auto_init": auto_init,
        }
        return await self._request("POST", "/user/repos", json_data=payload, custom_token=custom_token)

    async def update_repository(
        self,
        owner: str,
        repo: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        private: Optional[bool] = None,
        custom_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update repository metadata/settings."""
        payload: Dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if private is not None:
            payload["private"] = private
        return await self._request("PATCH", f"/repos/{owner}/{repo}", json_data=payload, custom_token=custom_token)

    async def delete_repository(
        self,
        owner: str,
        repo: str,
        custom_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Delete repository (destructive)."""
        return await self._request("DELETE", f"/repos/{owner}/{repo}", custom_token=custom_token)

    # -----------------------------------------------------------------------
    # Branches
    # -----------------------------------------------------------------------

    async def list_branches(
        self,
        owner: str,
        repo: str,
        per_page: int = 30,
        page: int = 1,
        custom_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List branches for a repository."""
        params = {"per_page": per_page, "page": page}
        res = await self._request("GET", f"/repos/{owner}/{repo}/branches", params=params, custom_token=custom_token)
        return res if isinstance(res, list) else []

    async def get_branch(
        self,
        owner: str,
        repo: str,
        branch: str,
        custom_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get details for a specific branch."""
        return await self._request("GET", f"/repos/{owner}/{repo}/branches/{branch}", custom_token=custom_token)

    async def create_branch(
        self,
        owner: str,
        repo: str,
        branch: str,
        from_branch: Optional[str] = None,
        custom_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new branch from an existing branch or default branch SHA."""
        # 1. Resolve source commit SHA
        if not from_branch:
            repo_info = await self.get_repository(owner, repo, custom_token=custom_token)
            from_branch = repo_info.get("default_branch", "main")

        # Check if from_branch is a SHA or branch name
        if len(from_branch) == 40 and all(c in "0123456789abcdefABCDEF" for c in from_branch):
            sha = from_branch
        else:
            branch_data = await self.get_branch(owner, repo, from_branch, custom_token=custom_token)
            sha = branch_data["commit"]["sha"]

        payload = {
            "ref": f"refs/heads/{branch}",
            "sha": sha,
        }
        return await self._request("POST", f"/repos/{owner}/{repo}/git/refs", json_data=payload, custom_token=custom_token)

    # -----------------------------------------------------------------------
    # Pull Requests
    # -----------------------------------------------------------------------

    async def list_pull_requests(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        sort: str = "created",
        direction: str = "desc",
        per_page: int = 30,
        page: int = 1,
        custom_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List pull requests for a repository."""
        params = {
            "state": state,
            "sort": sort,
            "direction": direction,
            "per_page": per_page,
            "page": page,
        }
        res = await self._request("GET", f"/repos/{owner}/{repo}/pulls", params=params, custom_token=custom_token)
        return res if isinstance(res, list) else []

    async def get_pull_request(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        custom_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get pull request details."""
        return await self._request("GET", f"/repos/{owner}/{repo}/pulls/{pull_number}", custom_token=custom_token)

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: Optional[str] = None,
        draft: bool = False,
        custom_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a pull request."""
        payload = {
            "title": title,
            "head": head,
            "base": base,
            "body": body or "",
            "draft": draft,
        }
        return await self._request("POST", f"/repos/{owner}/{repo}/pulls", json_data=payload, custom_token=custom_token)

    async def review_pull_request(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        event: str,
        body: str,
        custom_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit a review on a pull request."""
        payload = {
            "event": event,
            "body": body,
        }
        return await self._request("POST", f"/repos/{owner}/{repo}/pulls/{pull_number}/reviews", json_data=payload, custom_token=custom_token)

    async def merge_pull_request(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        commit_title: Optional[str] = None,
        commit_message: Optional[str] = None,
        merge_method: str = "merge",
        custom_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Merge a pull request."""
        payload: Dict[str, Any] = {"merge_method": merge_method}
        if commit_title:
            payload["commit_title"] = commit_title
        if commit_message:
            payload["commit_message"] = commit_message
        return await self._request("PUT", f"/repos/{owner}/{repo}/pulls/{pull_number}/merge", json_data=payload, custom_token=custom_token)

    # -----------------------------------------------------------------------
    # Issues
    # -----------------------------------------------------------------------

    async def list_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        labels: Optional[str] = None,
        sort: str = "created",
        direction: str = "desc",
        per_page: int = 30,
        page: int = 1,
        custom_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List issues for a repository."""
        params: Dict[str, Any] = {
            "state": state,
            "sort": sort,
            "direction": direction,
            "per_page": per_page,
            "page": page,
        }
        if labels:
            params["labels"] = labels
        res = await self._request("GET", f"/repos/{owner}/{repo}/issues", params=params, custom_token=custom_token)
        if isinstance(res, list):
            # GitHub issues endpoint returns pull requests as well unless filtered
            return [item for item in res if "pull_request" not in item]
        return []

    async def get_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        custom_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get an issue by number."""
        return await self._request("GET", f"/repos/{owner}/{repo}/issues/{issue_number}", custom_token=custom_token)

    async def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: Optional[str] = None,
        assignees: Optional[List[str]] = None,
        labels: Optional[List[str]] = None,
        custom_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new issue."""
        payload: Dict[str, Any] = {"title": title}
        if body:
            payload["body"] = body
        if assignees:
            payload["assignees"] = assignees
        if labels:
            payload["labels"] = labels
        return await self._request("POST", f"/repos/{owner}/{repo}/issues", json_data=payload, custom_token=custom_token)

    async def update_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        state: Optional[str] = None,
        assignees: Optional[List[str]] = None,
        labels: Optional[List[str]] = None,
        custom_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update an issue."""
        payload: Dict[str, Any] = {}
        if title is not None:
            payload["title"] = title
        if body is not None:
            payload["body"] = body
        if state is not None:
            payload["state"] = state
        if assignees is not None:
            payload["assignees"] = assignees
        if labels is not None:
            payload["labels"] = labels
        return await self._request("PATCH", f"/repos/{owner}/{repo}/issues/{issue_number}", json_data=payload, custom_token=custom_token)

    async def close_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        comment: Optional[str] = None,
        custom_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Close an issue and optionally add a closing comment."""
        if comment:
            await self._request(
                "POST",
                f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
                json_data={"body": comment},
                custom_token=custom_token,
            )
        return await self.update_issue(
            owner=owner,
            repo=repo,
            issue_number=issue_number,
            state="closed",
            custom_token=custom_token,
        )

    # -----------------------------------------------------------------------
    # Commits
    # -----------------------------------------------------------------------

    async def list_commits(
        self,
        owner: str,
        repo: str,
        sha: Optional[str] = None,
        path: Optional[str] = None,
        author: Optional[str] = None,
        per_page: int = 30,
        page: int = 1,
        custom_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List repository commits."""
        params: Dict[str, Any] = {
            "sha": sha,
            "path": path,
            "author": author,
            "per_page": per_page,
            "page": page,
        }
        res = await self._request("GET", f"/repos/{owner}/{repo}/commits", params=params, custom_token=custom_token)
        return res if isinstance(res, list) else []

    async def get_commit(
        self,
        owner: str,
        repo: str,
        sha: str,
        custom_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get commit details including diff and files changed."""
        return await self._request("GET", f"/repos/{owner}/{repo}/commits/{sha}", custom_token=custom_token)

    # -----------------------------------------------------------------------
    # Files / Contents
    # -----------------------------------------------------------------------

    async def get_file_contents(
        self,
        owner: str,
        repo: str,
        path: str = "",
        ref: Optional[str] = None,
        custom_token: Optional[str] = None,
    ) -> Any:
        """Get file contents or directory listing."""
        params = {"ref": ref} if ref else {}
        clean_path = path.lstrip("/")
        endpoint = f"/repos/{owner}/{repo}/contents/{clean_path}" if clean_path else f"/repos/{owner}/{repo}/contents"
        data = await self._request("GET", endpoint, params=params, custom_token=custom_token)

        # If it's a file with base64 content, decode text utf-8 if possible
        if isinstance(data, dict) and data.get("type") == "file" and data.get("encoding") == "base64":
            content_b64 = data.get("content", "").replace("\n", "")
            try:
                decoded_bytes = base64.b64decode(content_b64)
                data["decoded_content"] = decoded_bytes.decode("utf-8")
            except Exception:
                data["decoded_content"] = None
        return data

    async def create_or_update_file(
        self,
        owner: str,
        repo: str,
        path: str,
        message: str,
        content: str,
        sha: Optional[str] = None,
        branch: Optional[str] = None,
        is_base64: bool = False,
        custom_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create or update a file in the repository."""
        clean_path = path.lstrip("/")
        if not is_base64:
            encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        else:
            encoded_content = content

        payload: Dict[str, Any] = {
            "message": message,
            "content": encoded_content,
        }
        if sha:
            payload["sha"] = sha
        if branch:
            payload["branch"] = branch

        return await self._request("PUT", f"/repos/{owner}/{repo}/contents/{clean_path}", json_data=payload, custom_token=custom_token)

    # -----------------------------------------------------------------------
    # Workflows / Actions
    # -----------------------------------------------------------------------

    async def list_workflows(
        self,
        owner: str,
        repo: str,
        custom_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List GitHub Actions workflows for a repository."""
        return await self._request("GET", f"/repos/{owner}/{repo}/actions/workflows", custom_token=custom_token)

    async def get_workflow_runs(
        self,
        owner: str,
        repo: str,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        per_page: int = 30,
        page: int = 1,
        custom_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List workflow runs."""
        params: Dict[str, Any] = {"per_page": per_page, "page": page}
        if status:
            params["status"] = status
        if workflow_id:
            endpoint = f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
        else:
            endpoint = f"/repos/{owner}/{repo}/actions/runs"
        return await self._request("GET", endpoint, params=params, custom_token=custom_token)

    async def get_workflow_run_logs(
        self,
        owner: str,
        repo: str,
        run_id: int,
        custom_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch workflow run jobs, steps, and download URLs for logs."""
        # 1. Fetch the jobs and step logs summary for the run
        jobs_data = await self._request("GET", f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs", custom_token=custom_token)

        # 2. Check download URL for archive
        archive_url = f"{self.base_url}/repos/{owner}/{repo}/actions/runs/{run_id}/logs"

        return {
            "run_id": run_id,
            "jobs": jobs_data.get("jobs", []) if isinstance(jobs_data, dict) else [],
            "archive_url": archive_url,
            "total_count": jobs_data.get("total_count", 0) if isinstance(jobs_data, dict) else 0,
        }

    # -----------------------------------------------------------------------
    # Search
    # -----------------------------------------------------------------------

    async def search_github(
        self,
        query: str,
        search_type: str = "repositories",
        per_page: int = 30,
        page: int = 1,
        custom_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search across GitHub entities."""
        params = {"q": query, "per_page": per_page, "page": page}
        type_clean = search_type.lower()
        if type_clean in ("repositories", "repos"):
            endpoint = "/search/repositories"
        elif type_clean in ("issues", "issue"):
            endpoint = "/search/issues"
        elif type_clean in ("pullrequests", "pulls", "prs"):
            params["q"] = f"{query} is:pr"
            endpoint = "/search/issues"
        elif type_clean in ("commits", "commit"):
            endpoint = "/search/commits"
        elif type_clean in ("users", "user"):
            endpoint = "/search/users"
        elif type_clean in ("code",):
            endpoint = "/search/code"
        else:
            endpoint = "/search/repositories"

        return await self._request("GET", endpoint, params=params, custom_token=custom_token)


_github_service_instance: Optional[GitHubService] = None


def get_github_service() -> GitHubService:
    global _github_service_instance
    if _github_service_instance is None:
        _github_service_instance = GitHubService()
    return _github_service_instance
