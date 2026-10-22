"""Thread-Safe Audit Logging Service.

This module provides an in-memory, bounded audit log service that records operations
dispatched by both the FastAPI REST API and the Model Context Protocol (MCP) server.

Key features:
1. Thread-safe mutations using `threading.Lock`.
2. Memory bounded by a double-ended queue (`collections.deque`) with `maxlen`.
3. Automatic redaction of sensitive credentials (tokens, passwords, secret keys).
4. Payload size limiting to avoid unbounded log growth from file contents.
"""
import threading
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from app.models.schemas import OperationLog

# Set of substring tokens that trigger automatic value redaction
SENSITIVE_KEYS = {
    "token",
    "password",
    "secret",
    "authorization",
    "api_key",
    "key",
    "github_token",
    "credential",
}


def sanitize_params(data: Any) -> Any:
    """Recursively sanitize sensitive values from dictionary or list payloads.

    Any dictionary key matching known sensitive keywords will have its value replaced
    with '***REDACTED***'. Large string values (>500 chars, e.g. base64 or whole files)
    are truncated to keep the audit logs lightweight.

    Args:
        data: Arbitrary Python data structure (dict, list, str, etc.)

    Returns:
        A deep copy of the structure with sensitive values masked.
    """
    if isinstance(data, dict):
        sanitized: Dict[str, Any] = {}
        for k, v in data.items():
            # Check if any sensitive word appears in the key name (case-insensitive)
            if any(sensitive in k.lower() for sensitive in SENSITIVE_KEYS):
                sanitized[k] = "***REDACTED***"
            else:
                sanitized[k] = sanitize_params(v)
        return sanitized
    elif isinstance(data, (list, tuple)):
        return [sanitize_params(x) for x in data]
    elif isinstance(data, str) and len(data) > 500:
        # Avoid storing megabytes of file content in the audit log
        return data[:500] + "... [truncated]"
    return data


class AuditService:
    """Thread-safe in-memory audit log manager.

    Maintains a FIFO / ring buffer of the most recent operation logs, ensuring
    memory usage remains capped even after millions of requests.
    """

    def __init__(self, max_entries: int = 500):
        """Initialize the audit service.

        Args:
            max_entries: Maximum number of historical records to keep before dropping oldest.
        """
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
        """Create and store a new audit log entry.

        Args:
            operation: Name of the action (e.g. 'create_branch', 'merge_pull_request').
            channel: 'rest' if called via HTTP REST API, or 'mcp' if called via MCP tool.
            status: 'success' or 'error'.
            duration_ms: Time in milliseconds the operation took to execute.
            parameters: Dictionary of arguments passed to the action.
            result_summary: Optional one-line summary of successful outcome.
            error: Optional error message if the action failed.

        Returns:
            OperationLog: The newly created and recorded log entry.
        """
        # Deep scrub of parameters before storing in memory
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
            # appendleft puts the most recent record at the beginning of the list
            self._logs.appendleft(entry)

        return entry

    def list_logs(
        self,
        limit: int = 100,
        channel: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[OperationLog]:
        """Retrieve recent audit logs with optional filtering.

        Args:
            limit: Maximum number of entries to return (defaults to 100).
            channel: Filter by channel ('rest' or 'mcp').
            status: Filter by status ('success', 'error', 'pending').

        Returns:
            List[OperationLog]: Filtered list of operation logs ordered newest first.
        """
        with self._lock:
            # Create a shallow snapshot of current deque items to iterate safely
            entries = list(self._logs)

        filtered = entries
        if channel:
            filtered = [e for e in filtered if e.channel == channel]
        if status:
            filtered = [e for e in filtered if e.status == status]

        return filtered[:limit]

    def clear(self) -> None:
        """Clear all stored audit logs. Typically used for test setups or admin reset."""
        with self._lock:
            self._logs.clear()


# Singleton instance shared across FastAPI routers and MCP tool functions
_audit_service_instance: Optional[AuditService] = None


def get_audit_service(max_entries: int = 500) -> AuditService:
    """Get or initialize the singleton AuditService instance.

    Args:
        max_entries: Upper bound of log entries retained in memory.

    Returns:
        AuditService: The shared audit logging service.
    """
    global _audit_service_instance
    if _audit_service_instance is None:
        _audit_service_instance = AuditService(max_entries=max_entries)
    return _audit_service_instance
