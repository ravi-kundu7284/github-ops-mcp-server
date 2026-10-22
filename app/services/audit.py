"""Audit logging service for tracking REST and MCP operations."""
import threading
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from app.models.schemas import OperationLog

SENSITIVE_KEYS = {"token", "password", "secret", "authorization", "api_key", "key", "github_token"}


def sanitize_params(data: Any) -> Any:
    """Recursively sanitize sensitive values from dictionary or list."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if any(sensitive in k.lower() for sensitive in SENSITIVE_KEYS):
                sanitized[k] = "***REDACTED***"
            else:
                sanitized[k] = sanitize_params(v)
        return sanitized
    elif isinstance(data, (list, tuple)):
        return [sanitize_params(x) for x in data]
    elif isinstance(data, str) and len(data) > 500:
        return data[:500] + "... [truncated]"
    return data


class AuditService:
    """In-memory thread-safe audit log service."""

    def __init__(self, max_entries: int = 500):
        self._max_entries = max_entries
        self._logs: deque[OperationLog] = deque(maxlen=max_entries)
        self._lock = threading.Lock()

    def record(
        self,
        operation: str,
        channel: Literal["rest", "mcp"],
        status: Literal["success", "error", "pending"],
        duration_ms: float = 0.0,
        parameters: Optional[Dict[str, Any]] = None,
        result_summary: Optional[str] = None,
        error: Optional[str] = None,
    ) -> OperationLog:
        """Create and store an audit log entry."""
        sanitized_params = sanitize_params(parameters or {})
        entry = OperationLog(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            operation=operation,
            channel=channel,
            status=status,
            duration_ms=round(duration_ms, 2),
            parameters=sanitized_params,
            result_summary=result_summary,
            error=error,
        )
        with self._lock:
            self._logs.appendleft(entry)
        return entry

    def list_logs(
        self,
        limit: int = 100,
        channel: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[OperationLog]:
        """Retrieve recent audit logs with optional filtering."""
        with self._lock:
            entries = list(self._logs)

        filtered = entries
        if channel:
            filtered = [e for e in filtered if e.channel == channel]
        if status:
            filtered = [e for e in filtered if e.status == status]

        return filtered[:limit]

    def clear(self) -> None:
        """Clear all audit logs."""
        with self._lock:
            self._logs.clear()


_audit_service_instance: Optional[AuditService] = None


def get_audit_service(max_entries: int = 500) -> AuditService:
    global _audit_service_instance
    if _audit_service_instance is None:
        _audit_service_instance = AuditService(max_entries=max_entries)
    return _audit_service_instance
