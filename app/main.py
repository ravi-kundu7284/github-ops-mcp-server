"""FastAPI application entrypoint integrating REST API and MCP server."""
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

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("github_ops")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting GitHub Operations Server v%s...", __version__)
    logger.info("CORS Origins: %s", settings.cors_origins_list)
    yield
    logger.info("Shutting down GitHub Operations Server...")


app = FastAPI(
    title="GitHub Operations Management API & MCP Server",
    description="High-performance backend providing GitHub operations management via REST API and Model Context Protocol (MCP).",
    version=__version__,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS Middleware
origins = settings.cors_origins_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True if origins != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers for structured GitHub errors
@app.exception_handler(GitHubAuthError)
async def auth_error_handler(request: Request, exc: GitHubAuthError):
    return JSONResponse(
        status_code=401,
        content={"error": "AuthenticationError", "message": exc.message, "details": exc.details},
    )


@app.exception_handler(GitHubNotFoundError)
async def not_found_handler(request: Request, exc: GitHubNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"error": "NotFoundError", "message": exc.message, "details": exc.details},
    )


@app.exception_handler(GitHubRateLimitError)
async def rate_limit_handler(request: Request, exc: GitHubRateLimitError):
    return JSONResponse(
        status_code=429,
        content={"error": "RateLimitError", "message": exc.message, "reset_at": exc.reset_at, "details": exc.details},
    )


@app.exception_handler(GitHubValidationError)
async def validation_handler(request: Request, exc: GitHubValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": "ValidationError", "message": exc.message, "details": exc.details},
    )


@app.exception_handler(GitHubAPIError)
async def github_api_error_handler(request: Request, exc: GitHubAPIError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "GitHubAPIError", "message": exc.message, "details": exc.details},
    )


# Health check endpoints
@app.get("/health", response_model=HealthResponse, tags=["Health"])
@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    gh = get_github_service()
    user_login = None
    connected = False
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


# MCP Info Endpoint
@app.get("/api/mcp/info", tags=["MCP"])
async def mcp_info() -> Dict[str, Any]:
    """Inspect registered MCP tools, instructions, and transports."""
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


# Include REST API routes
app.include_router(api_router)

# Mount MCP Transports
# 1. Streamable HTTP at /mcp
try:
    app.mount("/mcp", mcp_server.streamable_http_app())
except Exception as e:
    logger.warning("Could not mount streamable_http_app: %s", e)

# 2. SSE at /sse
try:
    app.mount("/sse", mcp_server.sse_app())
except Exception as e:
    logger.warning("Could not mount sse_app: %s", e)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
    )
