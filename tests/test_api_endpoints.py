"""Integration tests for FastAPI REST API endpoints."""
import httpx
import pytest

from app.main import app
from app.services.audit import get_audit_service
from app.services.github_service import GitHubService


@pytest.fixture
def test_client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.asyncio
async def test_health_check(test_client):
    async with test_client as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


@pytest.mark.asyncio
async def test_mcp_info_endpoint(test_client):
    async with test_client as client:
        response = await client.get("/api/mcp/info")
        assert response.status_code == 200
        data = response.json()
        assert data["total_tools"] == 22
        assert "transports" in data
        assert data["transports"]["streamable_http"] == "/mcp"


@pytest.mark.asyncio
async def test_operations_audit_endpoints(test_client):
    audit = get_audit_service()
    audit.clear()
    audit.record("test_op", "rest", "success", 10.0, {"param1": "val1"})

    async with test_client as client:
        response = await client.get("/api/operations")
        assert response.status_code == 200
        logs = response.json()
        assert len(logs) == 1
        assert logs[0]["operation"] == "test_op"

        # Delete / clear operations
        del_resp = await client.delete("/api/operations")
        assert del_resp.status_code == 200

        check_resp = await client.get("/api/operations")
        assert len(check_resp.json()) == 0


@pytest.mark.asyncio
async def test_repos_delete_requires_exact_confirmation(test_client, monkeypatch):
    async def mock_delete(self, owner, repo, **kwargs):
        return {"deleted": True}

    monkeypatch.setattr(GitHubService, "delete_repository", mock_delete)

    async with test_client as client:
        # 1. Mismatched confirmation should fail 400
        resp_bad = await client.delete("/api/repos/octocat/my-repo?confirm=wrong-name")
        assert resp_bad.status_code == 400

        # 2. Correct confirmation succeeds 200
        resp_good = await client.delete("/api/repos/octocat/my-repo?confirm=my-repo")
        assert resp_good.status_code == 200
        assert resp_good.json()["status"] == "deleted"
