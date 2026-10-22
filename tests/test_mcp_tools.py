"""Integration tests for MCP Server and tools."""
import pytest

from app.mcp.server import mcp_server
from app.services.audit import get_audit_service
from app.services.github_service import GitHubService

REQUIRED_TOOLS = [
    "list_repositories",
    "get_repository",
    "create_repository",
    "update_repository",
    "delete_repository",
    "list_branches",
    "create_branch",
    "list_pull_requests",
    "create_pull_request",
    "review_pull_request",
    "merge_pull_request",
    "list_issues",
    "create_issue",
    "update_issue",
    "close_issue",
    "list_commits",
    "get_file_contents",
    "create_or_update_file",
    "list_workflows",
    "get_workflow_runs",
    "get_workflow_run_logs",
    "search_github",
]


@pytest.mark.asyncio
async def test_all_22_tools_registered():
    tools = await mcp_server.list_tools()
    tool_names = {t.name for t in tools}
    for req in REQUIRED_TOOLS:
        assert req in tool_names, f"Missing MCP tool: {req}"
    assert len(REQUIRED_TOOLS) == 22


@pytest.mark.asyncio
async def test_mcp_call_list_repositories(monkeypatch):
    audit = get_audit_service()
    audit.clear()

    async def mock_list_repos(self, **kwargs):
        return [
            {
                "name": "sample-repo",
                "full_name": "octocat/sample-repo",
                "owner": {"login": "octocat"},
                "private": False,
                "html_url": "https://github.com/octocat/sample-repo",
                "description": "Sample description",
                "fork": False,
                "default_branch": "main",
                "stargazers_count": 5,
                "forks_count": 1,
                "open_issues_count": 0,
                "updated_at": "2026-10-22T00:00:00Z",
            }
        ]

    monkeypatch.setattr(GitHubService, "list_repositories", mock_list_repos)

    result = await mcp_server.call_tool("list_repositories", {"visibility": "all"})
    assert not result.is_error
    assert len(result.content) > 0
    assert "sample-repo" in result.content[0].text

    # Verify audit log was created with channel='mcp'
    logs = audit.list_logs(channel="mcp")
    assert len(logs) >= 1
    assert logs[0].operation == "list_repositories"
    assert logs[0].status == "success"


@pytest.mark.asyncio
async def test_mcp_call_delete_repository_destructive_check(monkeypatch):
    # Without confirm=True, should refuse to delete
    res = await mcp_server.call_tool("delete_repository", {"owner": "octocat", "repo": "test-repo", "confirm": False})
    assert not res.is_error
    assert "cancelled" in res.content[0].text or "prevented" in res.content[0].text

    # With confirm=True
    async def mock_delete_repo(self, owner, repo):
        return {"deleted": True}

    monkeypatch.setattr(GitHubService, "delete_repository", mock_delete_repo)
    res_confirmed = await mcp_server.call_tool("delete_repository", {"owner": "octocat", "repo": "test-repo", "confirm": True})
    assert not res_confirmed.is_error
    assert "deleted" in res_confirmed.content[0].text
