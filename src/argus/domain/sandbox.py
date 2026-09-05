from typing import Any

from pydantic import BaseModel, Field, model_validator

from argus.domain.index import ValidationResult  # Re-export for domain convenience


class SandboxConfig(BaseModel):
    """
    Configuration for the ephemeral Docker environment.
    """

    postgres_image: str = Field("postgres:16-alpine", description="Docker image to use")
    container_memory_limit: str = Field("512m", description="Memory limit (e.g., 512m)")
    shared_buffers: str = Field("128MB", description="Postgres shared_buffers setting")
    max_prepared_transactions: int = Field(0, description="Disable two-phase commit")
    cleanup: bool = Field(True, description="Remove container after use")

    # Timeouts
    statement_timeout_ms: int = Field(
        5000, description="Max execution time per test query (ms)"
    )
    container_timeout_sec: int = Field(
        30, description="Max lifespan of the sandbox container"
    )

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "image" in data and "postgres_image" not in data:
                data["postgres_image"] = data.pop("image")
            if "timeout_seconds" in data and "container_timeout_sec" not in data:
                data["container_timeout_sec"] = data.pop("timeout_seconds")
            if "memory_mb" in data and "container_memory_limit" not in data:
                data["container_memory_limit"] = f"{data.pop('memory_mb')}m"
        return data

    @property
    def image(self) -> str:
        return self.postgres_image

    @property
    def timeout_seconds(self) -> int:
        return self.container_timeout_sec


__all__ = ["SandboxConfig", "ValidationResult"]
