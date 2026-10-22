"""FastAPI dependencies for authentication, token extraction, and service injection."""
from typing import Optional

from fastapi import Header, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    x_api_key: Optional[str] = Security(api_key_header),
    authorization: Optional[str] = Header(None),
) -> None:
    """Optionally verify server API key if API_KEY setting is configured."""
    settings = get_settings()
    if not settings.API_KEY:
        return

    # Check X-API-Key header or Bearer authorization
    provided_key = x_api_key
    if not provided_key and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            # If it's not a GitHub token (ghp_ etc.), treat as API key
            if not parts[1].startswith(("ghp_", "github_pat_", "gho_")):
                provided_key = parts[1]

    if not provided_key or provided_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


async def get_custom_github_token(
    x_github_token: Optional[str] = Header(None, alias="X-GitHub-Token"),
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    """Extract GitHub token from X-GitHub-Token header or Authorization Bearer."""
    if x_github_token:
        return x_github_token.strip()

    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token_candidate = parts[1].strip()
            # If it looks like a GitHub token or no server-level API_KEY is set, use it
            return token_candidate

    return None
