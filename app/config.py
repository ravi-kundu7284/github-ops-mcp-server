"""Application Configuration Module.

This module defines central application configuration settings using Pydantic Settings.
It reads configuration variables from environment variables or a local `.env` file,
with sensible development defaults and strict type validation.
"""
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration class backed by environment variables.

    Attributes:
        GITHUB_TOKEN: Optional default Personal Access Token (PAT) used by the server.
                      If omitted, requests can still provide their own token via the
                      `X-GitHub-Token` HTTP header.
        GITHUB_API_URL: Base URL for GitHub REST API (defaults to public GitHub api.github.com,
                        can be pointed to GitHub Enterprise Server instances).
        APP_HOST: Network interface host to bind the FastAPI server.
        APP_PORT: Network port number to listen on.
        ENVIRONMENT: Current deployment environment ('development', 'production', 'testing').
        LOG_LEVEL: Logging verbosity ('DEBUG', 'INFO', 'WARNING', 'ERROR').
        CORS_ORIGINS: Comma-separated list of approved frontend origins for CORS headers.
        API_KEY: Optional secret key required to access REST endpoints via X-API-Key header.
        MCP_SERVER_NAME: Identifier reported by the Model Context Protocol server.
        MCP_SERVER_VERSION: Version reported in MCP initialization handshakes.
        MAX_AUDIT_LOGS: Maximum number of recent operation records preserved in memory.
    """

    # --- GitHub API Settings ---
    GITHUB_TOKEN: Optional[str] = Field(
        default=None,
        description="Default GitHub Personal Access Token (classic or fine-grained)",
    )
    GITHUB_API_URL: str = Field(
        default="https://api.github.com",
        description="GitHub REST API Base URL (override for GitHub Enterprise)",
    )

    # --- Server Settings ---
    APP_HOST: str = Field(
        default="0.0.0.0",
        description="FastAPI host binding (0.0.0.0 for containerized deployment)",
    )
    APP_PORT: int = Field(
        default=8000,
        description="FastAPI port binding",
    )
    ENVIRONMENT: str = Field(
        default="development",
        description="Runtime environment mode (development, staging, production)",
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Log verbosity level (DEBUG, INFO, WARNING, ERROR)",
    )

    # --- Security & Access Control ---
    CORS_ORIGINS: str = Field(
        default="http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
        description="Comma-separated allowed web origins for cross-origin resource sharing",
    )
    API_KEY: Optional[str] = Field(
        default=None,
        description="Optional shared secret key to protect backend REST API routes",
    )

    # --- Model Context Protocol (MCP) Metadata ---
    MCP_SERVER_NAME: str = Field(
        default="github-ops-mcp-server",
        description="Unique identifier exposed to MCP clients (e.g. Claude Desktop)",
    )
    MCP_SERVER_VERSION: str = Field(
        default="1.0.0",
        description="Semantic version string of the MCP server",
    )

    # --- Audit & Diagnostics ---
    MAX_AUDIT_LOGS: int = Field(
        default=500,
        description="Maximum number of historical operations preserved in the ring buffer",
    )

    # Pydantic configuration to automatically parse .env file
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS_ORIGINS string into a clean list of origins.

        Returns:
            List[str]: A list of whitespace-trimmed origin URL strings. If '*' is set,
                       returns ['*'] to allow wildcard origins in development.
        """
        if not self.CORS_ORIGINS:
            return ["*"]
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


# Cached singleton instance to avoid re-reading disk/environment on every access
_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """Retrieve the singleton Settings instance.

    Returns:
        Settings: The validated application configuration instance.
    """
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
