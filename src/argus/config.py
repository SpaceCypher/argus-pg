import os
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

# --- Configuration Models ---


class DatabaseConfig(BaseModel):
    dsn: str = Field(..., description="PostgreSQL connection string")


class SandboxConfig(BaseModel):
    image: str = Field("postgres:16", description="Docker image for sandbox")
    cleanup: bool = Field(True, description="Remove container after use")
    timeout_seconds: int = Field(300, description="Max execution time per validation")
    memory_mb: int = Field(1024, description="Container memory limit in MB")


class GeminiConfig(BaseModel):
    enabled: bool = Field(False)
    api_key: str | None = Field(None)
    model: str = Field("gemini-1.5-flash")


class BrainConfig(BaseModel):
    provider: Literal["heuristic", "gemini"] = Field("heuristic")
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)


class ArgusConfig(BaseModel):
    """
    Root configuration object.
    """

    database: DatabaseConfig
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    brain: BrainConfig = Field(default_factory=BrainConfig)


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""

    pass


# --- Loader Logic ---


def load_config(path: str | Path | None = None) -> ArgusConfig:
    """
    Load configuration from TOML file and environment variables.
    Precedence: Env Vars > File > Defaults.

    Default path: 'argus.toml' in current directory.
    """
    # 1. Determine Path
    path = Path("argus.toml") if path is None else Path(path)

    config_data: dict[str, Any] = {}

    # 2. Load File (if exists)
    if path.exists():
        try:
            with open(path, "rb") as f:
                config_data = tomllib.load(f)
        except Exception as e:
            raise ConfigurationError(
                f"Failed to parse config file '{path}': {e}"
            ) from e
    elif str(path) != "argus.toml":
        # If user specified a non-default path that doesn't exist, warn or error?
        # Standard unix practice: validation fails if required fields missing.
        # We proceed with empty dict.
        pass

    # 3. Apply Environment Overrides (Manual flattening for key fields)

    # Database
    if env_dsn := os.environ.get("ARGUS_DATABASE_DSN"):
        if "database" not in config_data:
            config_data["database"] = {}
        config_data["database"]["dsn"] = env_dsn

    # Sandbox
    if env_sb_image := os.environ.get("ARGUS_SANDBOX_IMAGE"):
        if "sandbox" not in config_data:
            config_data["sandbox"] = {}
        config_data["sandbox"]["image"] = env_sb_image

    # Brain
    if env_brain_provider := os.environ.get("ARGUS_BRAIN_PROVIDER"):
        if "brain" not in config_data:
            config_data["brain"] = {}
        config_data["brain"]["provider"] = env_brain_provider

    # Gemini
    if env_gemini_key := os.environ.get("ARGUS_BRAIN_GEMINI_API_KEY"):
        if "brain" not in config_data:
            config_data["brain"] = {}
        if "gemini" not in config_data["brain"]:
            config_data["brain"]["gemini"] = {}
        config_data["brain"]["gemini"]["api_key"] = env_gemini_key

    # 4. Validate and Build
    try:
        return ArgusConfig(**config_data)
    except ValidationError as e:
        raise ConfigurationError(f"Invalid configuration: {e}") from e
