"""Unit tests for GitHubService with mocked HTTP responses."""
import base64

import pytest

from app.services.github_service import (
    GitHubService,
)


@pytest.fixture
def gh_service():
    return GitHubService(token="test_mock_token")


@pytest.mark.asyncio
async def test_get_authenticated_user(gh_service, monkeypatch):
    async def mock_request(self, method, endpoint, **kwargs):
        assert method == "GET"
        assert endpoint == "/user"
        return {"login": "octocat", "id": 1, "name": "The Octocat"}

    monkeypatch.setattr(GitHubService, "_request", mock_request)
    user = await gh_service.get_authenticated_user()
    assert user["login"] == "octocat"
    assert user["id"] == 1


@pytest.mark.asyncio
async def test_list_repositories(gh_service, monkeypatch):
    async def mock_request(self, method, endpoint, params=None, **kwargs):
        assert method == "GET"
        assert endpoint == "/user/repos"
        assert params["visibility"] == "all"
        return [{"id": 101, "name": "repo-one", "full_name": "octocat/repo-one"}]

    monkeypatch.setattr(GitHubService, "_request", mock_request)
    repos = await gh_service.list_repositories()
    assert len(repos) == 1
    assert repos[0]["name"] == "repo-one"


@pytest.mark.asyncio
async def test_create_and_delete_repository(gh_service, monkeypatch):
    async def mock_request(self, method, endpoint, json_data=None, **kwargs):
        if method == "POST":
            assert endpoint == "/user/repos"
            assert json_data["name"] == "new-repo"
            return {"name": "new-repo", "full_name": "octocat/new-repo"}
        elif method == "DELETE":
            assert endpoint == "/repos/octocat/new-repo"
            return {"success": True}

    monkeypatch.setattr(GitHubService, "_request", mock_request)
    created = await gh_service.create_repository(name="new-repo", description="Testing")
    assert created["name"] == "new-repo"

    deleted = await gh_service.delete_repository("octocat", "new-repo")
    assert deleted["success"] is True


@pytest.mark.asyncio
async def test_create_branch_resolves_sha(gh_service, monkeypatch):
    async def mock_request(self, method, endpoint, json_data=None, **kwargs):
        if method == "GET" and "/branches/main" in endpoint:
            return {"name": "main", "commit": {"sha": "c0ffee1234567890123456789012345678901234"}}
        if method == "POST" and "/git/refs" in endpoint:
            assert json_data["ref"] == "refs/heads/feature-x"
            assert json_data["sha"] == "c0ffee1234567890123456789012345678901234"
            return {"ref": "refs/heads/feature-x", "object": {"sha": json_data["sha"]}}

    monkeypatch.setattr(GitHubService, "_request", mock_request)
    res = await gh_service.create_branch("octocat", "hello-world", "feature-x", from_branch="main")
    assert res["ref"] == "refs/heads/feature-x"


@pytest.mark.asyncio
async def test_pull_request_operations(gh_service, monkeypatch):
    async def mock_request(self, method, endpoint, json_data=None, **kwargs):
        if method == "POST" and endpoint.endswith("/pulls"):
            return {"number": 42, "title": "New feature"}
        if method == "POST" and "/reviews" in endpoint:
            return {"id": 1, "state": "APPROVED"}
        if method == "PUT" and "/merge" in endpoint:
            return {"sha": "mergedsha123", "merged": True, "message": "Pull Request successfully merged"}

    monkeypatch.setattr(GitHubService, "_request", mock_request)
    pr = await gh_service.create_pull_request("octocat", "repo", "New feature", "feat", "main")
    assert pr["number"] == 42

    review = await gh_service.review_pull_request("octocat", "repo", 42, "APPROVE", "Looks great!")
    assert review["state"] == "APPROVED"

    merged = await gh_service.merge_pull_request("octocat", "repo", 42)
    assert merged["merged"] is True


@pytest.mark.asyncio
async def test_issue_operations(gh_service, monkeypatch):
    async def mock_request(self, method, endpoint, json_data=None, **kwargs):
        if method == "POST" and endpoint.endswith("/issues"):
            return {"number": 10, "title": "Bug in login", "state": "open"}
        if method == "PATCH" and "/issues/10" in endpoint:
            return {"number": 10, "state": json_data.get("state", "open")}
        if method == "POST" and "/comments" in endpoint:
            return {"id": 999, "body": json_data.get("body")}

    monkeypatch.setattr(GitHubService, "_request", mock_request)
    issue = await gh_service.create_issue("octocat", "repo", "Bug in login")
    assert issue["number"] == 10

    closed = await gh_service.close_issue("octocat", "repo", 10, comment="Fixed in #42")
    assert closed["state"] == "closed"


@pytest.mark.asyncio
async def test_file_contents_decoded(gh_service, monkeypatch):
    async def mock_request(self, method, endpoint, **kwargs):
        return {
            "type": "file",
            "encoding": "base64",
            "content": base64.b64encode(b"# Hello World\n").decode("utf-8"),
            "sha": "blobsha123",
        }

    monkeypatch.setattr(GitHubService, "_request", mock_request)
    res = await gh_service.get_file_contents("octocat", "repo", "README.md")
    assert res["decoded_content"] == "# Hello World\n"
