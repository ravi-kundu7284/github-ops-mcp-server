"""Unit tests for the audit logging service."""
from app.services.audit import AuditService, sanitize_params


def test_sanitize_params_redacts_tokens():
    raw = {
        "repo": "test-repo",
        "github_token": "ghp_secret12345",
        "nested": {"api_key": "supersecret", "normal": "hello"},
    }
    sanitized = sanitize_params(raw)
    assert sanitized["repo"] == "test-repo"
    assert sanitized["github_token"] == "***REDACTED***"
    assert sanitized["nested"]["api_key"] == "***REDACTED***"
    assert sanitized["nested"]["normal"] == "hello"


def test_audit_service_recording_and_filtering():
    audit = AuditService(max_entries=10)
    audit.clear()

    audit.record("list_repositories", "rest", "success", 12.5, {"page": 1})
    audit.record("delete_repository", "mcp", "error", 45.0, {"owner": "test"}, error="Not confirmed")
    e3 = audit.record("create_issue", "rest", "success", 20.0, {"title": "Bug"})

    all_logs = audit.list_logs()
    assert len(all_logs) == 3
    assert all_logs[0].id == e3.id  # Newest first

    mcp_logs = audit.list_logs(channel="mcp")
    assert len(mcp_logs) == 1
    assert mcp_logs[0].operation == "delete_repository"

    error_logs = audit.list_logs(status="error")
    assert len(error_logs) == 1
    assert error_logs[0].operation == "delete_repository"

    audit.clear()
    assert len(audit.list_logs()) == 0


def test_audit_service_max_entries_limit():
    audit = AuditService(max_entries=5)
    for i in range(10):
        audit.record(f"op_{i}", "rest", "success")

    logs = audit.list_logs()
    assert len(logs) == 5
    assert logs[0].operation == "op_9"
