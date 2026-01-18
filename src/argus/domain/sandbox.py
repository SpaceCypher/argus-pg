from pydantic import BaseModel, Field


class SandboxConfig(BaseModel):
    """
    Configuration for the ephemeral Docker environment.
    """

    postgres_image: str = Field("postgres:15-alpine", description="Docker image to use")
    container_memory_limit: str = Field("512m", description="Memory limit (e.g., 512m)")
    shared_buffers: str = Field("128MB", description="Postgres shared_buffers setting")
    max_prepared_transactions: int = Field(0, description="Disable two-phase commit")

    # Timeouts
    statement_timeout_ms: int = Field(
        5000, description="Max execution time per test query (ms)"
    )
    container_timeout_sec: int = Field(
        30, description="Max lifespan of the sandbox container"
    )


class ValidationResult(BaseModel):
    """
    Result of a completed index validation experiment.
    """

    run_id: str = Field(..., description="Unique run identifier")

    # Outcomes
    baseline_cost: float = Field(..., description="Cost without index")
    optimized_cost: float = Field(..., description="Cost with index")
    baseline_time_ms: float = Field(..., description="Execution time without index")
    optimized_time_ms: float = Field(..., description="Execution time with index")

    # Analysis
    cost_improvement_factor: float = Field(
        ..., description="baseline / optimized (e.g. 2.5x)"
    )
    time_improvement_factor: float = Field(
        ..., description="baseline / optimized (e.g. 2.5x)"
    )

    is_regression: bool = Field(False, description="Did performance get worse?")
    error_message: str | None = Field(None, description="If validation failed")
