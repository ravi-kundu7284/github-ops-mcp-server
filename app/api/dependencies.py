"""FastAPI Dependency Injection Module.

This module provides reusable FastAPI dependencies for:
1. Validating backend server access via an optional API key (`X-API-Key` or `Authorization: Bearer <key>`).
2. Extracting per-request GitHub Personal Access Tokens (PAT) from client headers (`X-GitHub-Token`),
   allowing users to authenticate their own GitHub accounts without storing tokens in the backend server.
"""
from typing import Optional

from fastapi import Header, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

# Security scheme allowing Swagger UI to pass an API key in the X-API-Key header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    x_api_key: Optional[str] = Security(api_key_header),
    authorization: Optional[str] = Header(None),
) -> None:
    """Validate server-level API key if configured.

    If `API_KEY` is not set in application configuration, this dependency allows
    requests through without restriction. If `API_KEY` is set, requests must pass
    either the `X-API-Key` header or `Authorization: Bearer <API_KEY>`.

    Raises:
        HTTPException (401): If an API key is required but missing or invalid.
    """
    settings = get_settings()

    # If no API key is enforced by the server configuration, allow access
    if not settings.API_KEY:
        return

    # Extract key candidate from X-API-Key header or standard Bearer authorization
    provided_key = x_api_key
    if not provided_key and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            # Avoid mistaking a GitHub Personal Access Token (e.g. ghp_...) for a backend API key
            if not parts[1].startswith(("ghp_", "github_pat_", "gho_")):
                provided_key = parts[1]

    # Validate against configured API key
    if not provided_key or provided_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key for backend access.",
        )


async def get_custom_github_token(
    x_github_token: Optional[str] = Header(None, alias="X-GitHub-Token"),
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    """Extract a user's GitHub Personal Access Token from request headers.

    This allows the frontend application to pass the active user's GitHub token
    on every request rather than relying strictly on the server's environment variable.

    Priority:
    1. `X-GitHub-Token` header (highest priority, unambiguous).
    2. `Authorization: Bearer <token>` if formatted like a GitHub token (starts with ghp_, github_pat_, etc.).
    3. `None` (falls back to server-level default `settings.GITHUB_TOKEN`).

    Returns:
        Optional[str]: The extracted GitHub token string or None.
    """
    # 1. Check explicit custom header
    if x_github_token:
        return x_github_token.strip()

    # 2. Check standard Authorization header
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token_candidate = parts[1].strip()
            return token_candidate

    # 3. None returned; service layer will default to settings.GITHUB_TOKEN if present
    return None
