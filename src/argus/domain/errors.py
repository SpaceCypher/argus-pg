from typing import Any


class ArgusError(Exception):
    """Base exception for all Argus-PG errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


class DependencyError(ArgusError):
    """
    Raised when an external system (Docker, Postgres, Gemini) fails.
    This logic suggests a retry might be possible or the environment is broken.
    """

    pass


class ValidationError(ArgusError):
    """
    Raised when logical validation fails definitively.
    e.g. Models are malformed, or Sandbox constraints violated.
    """

    pass


class ConfigurationError(ArgusError):
    """
    Raised when the system is misconfigured.
    """

    pass


class SandboxError(DependencyError):
    """
    Specific failure during a sandbox experiment execution.
    """

    pass
