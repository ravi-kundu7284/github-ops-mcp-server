"""FastAPI Main Application Entrypoint.

This module initializes the FastAPI server, registers CORS middleware, configures
global structured exception handlers, exposes diagnostic health endpoints, mounts
all REST API routes under `/api`, and mounts the Model Context Protocol (MCP) server
transports (`/mcp` for Streamable HTTP and `/sse` for Server-Sent Events).
"""
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api import api_router
from app.config import get_settings
from app.mcp.server import mcp_server
from app.models.schemas import HealthResponse
from app.services.github_service import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubValidationError,
    get_github_service,
)

# Initialize application settings from environment
settings = get_settings()

# Configure standardized logging format
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("github_ops")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager handling server startup and shutdown hooks.

    Initializes shared resources on startup and gracefully closes connections on shutdown.
    """
    logger.info("Starting GitHub Operations Server v%s...", __version__)
    logger.info("CORS Allowed Origins: %s", settings.cors_origins_list)
    yield
    logger.info("Shutting down GitHub Operations Server...")


# Create central FastAPI instance
app = FastAPI(
    title="GitHub Operations Management API & MCP Server",
    description=(
        "High-performance backend providing full GitHub operations management "
        "via typed REST endpoints and the Model Context Protocol (MCP)."
    ),
    version=__version__,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ---------------------------------------------------------------------------
# Cross-Origin Resource Sharing (CORS) Configuration
# ---------------------------------------------------------------------------
origins = settings.cors_origins_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True if origins != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global Exception Handlers for Structured GitHub Error Responses
# ---------------------------------------------------------------------------

@app.exception_handler(GitHubAuthError)
async def auth_error_handler(request: Request, exc: GitHubAuthError) -> JSONResponse:
    """Handle 401 Unauthorized errors (missing, invalid, or expired GitHub tokens)."""
    return JSONResponse(
        status_code=401,
        content={"error": "AuthenticationError", "message": exc.message, "details": exc.details},
    )


@app.exception_handler(GitHubNotFoundError)
async def not_found_handler(request: Request, exc: GitHubNotFoundError) -> JSONResponse:
    """Handle 404 Not Found errors (non-existent repos, branches, issues, or PRs)."""
    return JSONResponse(
        status_code=404,
        content={"error": "NotFoundError", "message": exc.message, "details": exc.details},
    )


@app.exception_handler(GitHubRateLimitError)
async def rate_limit_handler(request: Request, exc: GitHubRateLimitError) -> JSONResponse:
    """Handle 429 Too Many Requests errors when GitHub API quota is reached."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "RateLimitError",
            "message": exc.message,
            "reset_at": exc.reset_at,
            "details": exc.details,
        },
    )


@app.exception_handler(GitHubValidationError)
async def validation_handler(request: Request, exc: GitHubValidationError) -> JSONResponse:
    """Handle 422 Unprocessable Entity errors (invalid branch names, merge conflicts)."""
    return JSONResponse(
        status_code=422,
        content={"error": "ValidationError", "message": exc.message, "details": exc.details},
    )


@app.exception_handler(GitHubAPIError)
async def github_api_error_handler(request: Request, exc: GitHubAPIError) -> JSONResponse:
    """Catch-all handler for general GitHub REST API failures."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "GitHubAPIError", "message": exc.message, "details": exc.details},
    )


# ---------------------------------------------------------------------------
# Health & Status Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["Health"])
@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Perform a service health check and test connectivity to the GitHub API.

    Returns:
        HealthResponse: Status string, application version, environment, and whether
                        the active token successfully connects to GitHub.
    """
    gh = get_github_service()
    user_login = None
    connected = False

    # If a server token is configured, test connectivity to GitHub
    if settings.GITHUB_TOKEN:
        try:
            user = await gh.get_authenticated_user()
            user_login = user.get("login")
            connected = True
        except Exception:
            connected = False

    return HealthResponse(
        status="ok",
        version=__version__,
        environment=settings.ENVIRONMENT,
        github_connected=connected,
        authenticated_user=user_login,
    )


# ---------------------------------------------------------------------------
# Model Context Protocol (MCP) Diagnostics Endpoint
# ---------------------------------------------------------------------------

@app.get("/api/mcp/info", tags=["MCP"])
async def mcp_info() -> Dict[str, Any]:
    """Inspect all registered MCP tools, parameter schemas, and available transports.

    Allows MCP clients and debugging dashboards to verify what capabilities
    are currently exposed by the MCP server.
    """
    tools = await mcp_server.list_tools()
    return {
        "server_name": settings.MCP_SERVER_NAME,
        "version": settings.MCP_SERVER_VERSION,
        "transports": {
            "streamable_http": "/mcp",
            "sse": "/sse",
        },
        "total_tools": len(tools),
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters if hasattr(t, "parameters") else {},
            }
            for t in tools
        ],
    }


# ---------------------------------------------------------------------------
# Route Registration & MCP Sub-App Mounting
# ---------------------------------------------------------------------------

# Include the aggregated REST API router (repos, branches, PRs, issues, commits, etc.)
app.include_router(api_router)

# Mount MCP Transport 1: Streamable HTTP at /mcp
# This enables direct HTTP streaming MCP tool invocations without WebSockets
try:
    app.mount("/mcp", mcp_server.streamable_http_app())
except Exception as e:
    logger.warning("Could not mount streamable_http_app: %s", e)

# Mount MCP Transport 2: Server-Sent Events at /sse
# Legacy / standard SSE transport for MCP clients that prefer SSE over Streamable HTTP
try:
    app.mount("/sse", mcp_server.sse_app())
except Exception as e:
    logger.warning("Could not mount sse_app: %s", e)


# Local development entrypoint
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
    )
