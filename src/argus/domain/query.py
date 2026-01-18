import hashlib
from typing import NewType

from pydantic import BaseModel, Field, field_validator

QueryId = NewType("QueryId", str)


class SqlStatement(BaseModel):
    """
    Represents a raw SQL statement.
    Strictly forbids empty strings.
    """

    raw_query: str = Field(..., description="The original SQL statement text")

    @field_validator("raw_query")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("SQL statement cannot be empty")
        return v

    @property
    def query_id(self) -> QueryId:
        """Deterministic hash of the normalized query text."""
        # Simple normalization: strip whitespace.
        # In Core layer we might want more robust normalization.
        normalized = self.raw_query.strip()
        hash_digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return QueryId(hash_digest)


class PgStatStats(BaseModel):
    """
    Statistics from pg_stat_statements for a specific query.
    Used for prioritization.
    """

    calls: int = Field(..., ge=0, description="Number of times executed")
    total_exec_time: float = Field(..., ge=0.0, description="Total time spent (ms)")
    rows: int = Field(..., ge=0, description="Total rows retrieved")

    @property
    def mean_exec_time(self) -> float:
        if self.calls == 0:
            return 0.0
        return self.total_exec_time / self.calls
