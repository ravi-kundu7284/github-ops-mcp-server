"""Application configuration and environment settings."""
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration class backed by environment variables."""

    # GitHub
    GITHUB_TOKEN: Optional[str] = Field(default=None, description="Default GitHub PAT token")
    GITHUB_API_URL: str = Field(default="https://api.github.com", description="GitHub REST API Base URL")

    # Server
    APP_HOST: str = Field(default="0.0.0.0", description="FastAPI bind host")
    APP_PORT: int = Field(default=8000, description="FastAPI bind port")
    ENVIRONMENT: str = Field(default="development", description="development / production / testing")
    LOG_LEVEL: str = Field(default="INFO", description="Log level")

    # Security
    CORS_ORIGINS: str = Field(
        default="http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
        description="Comma-separated allowed CORS origins",
    )
    API_KEY: Optional[str] = Field(
        default=None, description="Optional backend API key to protect REST endpoints"
    )

    # MCP
    MCP_SERVER_NAME: str = Field(default="github-ops-mcp-server", description="MCP Server Name")
    MCP_SERVER_VERSION: str = Field(default="1.0.0", description="MCP Server Version")

    # Audit
    MAX_AUDIT_LOGS: int = Field(default=500, description="Max audit log entries in memory")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Return CORS origins as a trimmed list."""
        if not self.CORS_ORIGINS:
            return ["*"]
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """Retrieve singleton settings instance."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
